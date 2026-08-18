"""総当たり組み合わせ生成・差分実行判定・並列実行制御。

docs/engine/rules.md「リーグ運営」と docs/engine/engine-architecture.md「並列実行」に対応する。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from .game import DEFAULT_TIMEOUT_SECONDS, Game, GameRecord, Participant, new_game_id
from .storage import Storage


@dataclass(frozen=True)
class Card:
    """1対局分の組み合わせ(先手・後手が決まった状態)。"""

    black: Participant
    white: Participant

    @property
    def key(self) -> tuple[str, str]:
        return (self.black.id, self.white.id)

    def __str__(self) -> str:  # ログ表示用
        return f"{self.black.id}(黒) vs {self.white.id}(白)"


@dataclass
class LeagueRunResult:
    """リーグ実行の結果。"""

    records: list[GameRecord] = field(default_factory=list)
    skipped: list[Card] = field(default_factory=list)
    failures: list[tuple[Card, BaseException]] = field(default_factory=list)


def build_cards(participants: Sequence[Participant]) -> list[Card]:
    """全組み合わせの総当たりカードを作る。

    同一カードは先手後手を入れ替えて2局(先手・後手1回ずつ)。
    """
    cards: list[Card] = []
    for index, first in enumerate(participants):
        for second in participants[index + 1 :]:
            cards.append(Card(black=first, white=second))
            cards.append(Card(black=second, white=first))
    return cards


def played_card_keys(results: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    """`data/results.jsonl` の各行から、実施済みカード(黒id, 白id)の集合を作る。"""
    keys: set[tuple[str, str]] = set()
    for row in results:
        black = (row.get("black") or {}).get("id")
        white = (row.get("white") or {}).get("id")
        if isinstance(black, str) and isinstance(white, str):
            keys.add((black, white))
    return keys


def pending_cards(
    participants: Sequence[Participant],
    results: Iterable[dict[str, Any]],
) -> tuple[list[Card], list[Card]]:
    """未実施カードと実施済みカードに振り分ける(差分実行)。

    先手後手の組み合わせ単位で判定するため、片側の向きだけ実施済みの場合は
    残りの向きだけが実行対象になる。
    """
    played = played_card_keys(results)
    pending: list[Card] = []
    skipped: list[Card] = []
    for card in build_cards(participants):
        (skipped if card.key in played else pending).append(card)
    return pending, skipped


class League:
    """未実施カードを並列に消化していくリーグ運営。"""

    def __init__(
        self,
        participants: Sequence[Participant],
        *,
        storage: Storage,
        timeout_seconds: float | None = DEFAULT_TIMEOUT_SECONDS,
        concurrent_games: int = 4,
        game_id_factory: Callable[[], str] = new_game_id,
        on_start: Callable[[Card], None] | None = None,
        on_complete: Callable[[Card, GameRecord], None] | None = None,
        on_error: Callable[[Card, BaseException], None] | None = None,
    ) -> None:
        if concurrent_games < 1:
            raise ValueError("concurrent_games は1以上である必要がある")
        self.participants = list(participants)
        self.storage = storage
        self.timeout_seconds = timeout_seconds
        self.concurrent_games = concurrent_games
        self._game_id_factory = game_id_factory
        self._on_start = on_start
        self._on_complete = on_complete
        self._on_error = on_error

    # ------------------------------------------------------------------
    def plan(self) -> tuple[list[Card], list[Card]]:
        """未実施カードと実施済みカードを返す。"""
        return pending_cards(self.participants, self.storage.read_results())

    def run(self) -> LeagueRunResult:
        """未実施カードを実行し、棋譜と結果ログを`data/`へ書き出す。"""
        pending, skipped = self.plan()
        result = LeagueRunResult(skipped=skipped)
        if not pending:
            return result

        with ThreadPoolExecutor(max_workers=self.concurrent_games) as executor:
            futures = {executor.submit(self._play_card, card): card for card in pending}
            for future in as_completed(futures):
                card = futures[future]
                try:
                    record = future.result()
                except BaseException as exc:  # noqa: BLE001 - 1局の失敗で全体を止めない
                    result.failures.append((card, exc))
                    if self._on_error is not None:
                        self._on_error(card, exc)
                else:
                    result.records.append(record)
                    if self._on_complete is not None:
                        self._on_complete(card, record)

        result.records.sort(key=lambda record: record.game_id)
        return result

    # ------------------------------------------------------------------
    def _play_card(self, card: Card) -> GameRecord:
        if self._on_start is not None:
            self._on_start(card)
        game = Game(
            card.black,
            card.white,
            timeout_seconds=self.timeout_seconds,
            game_id=self._game_id_factory(),
        )
        record = game.play()
        self.storage.record_game(record)
        return record
