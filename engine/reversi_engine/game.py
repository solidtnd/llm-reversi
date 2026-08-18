"""1対局の進行(1手ごとの処理、パス/反則負け判定、タイムアウト、リトライ)。

docs/engine/rules.md「1手ごとの処理」と docs/shared/log-schema.md に対応する。
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from .adapters.base import AdapterAPIError, AdapterParseError, LLMAdapter
from .board import (
    BoardState,
    Player,
    apply_move,
    count_stones,
    initial_board,
    is_full,
    legal_moves,
    opponent,
)

DEFAULT_TIMEOUT_SECONDS = 30.0

#: 1手あたりのリトライ予算。原因(パース失敗/APIエラー)を問わず通算1回まで
#: (docs/engine/rules.md「1手ごとの処理」)。ルールとして固定なので設定値にはしない。
RETRY_BUDGET_PER_MOVE = 1

MoveType = Literal["move", "pass", "forfeit"]
ForfeitReason = Literal["illegal_move", "timeout", "parse_failure", "api_error"]
Retried = Literal["none", "parse_failure", "api_error"]


# ---------------------------------------------------------------------------
# 対局者・棋譜のデータ構造
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Participant:
    """1対局に参加するプレイヤー(`models.yaml`の1エントリ + Adapter)。"""

    id: str
    provider: str
    model: str
    display_name: str
    config: dict[str, Any]
    adapter: LLMAdapter

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "model": self.model,
            "provider": self.provider,
            "display_name": self.display_name,
            "config": dict(self.config),
        }


@dataclass
class MoveRecord:
    """1手の記録(docs/shared/log-schema.md の Move)。"""

    turn: int
    player: Player
    type: MoveType
    position: str | None
    board_after: BoardState
    legal_moves: list[str]
    llm_raw_response: str | None = None
    retried: Retried = "none"
    response_time_ms: int = 0
    forfeit_reason: ForfeitReason | None = None
    error_detail: str | None = None
    usage: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "player": self.player,
            "type": self.type,
            "position": self.position,
            "board_after": self.board_after,
            "legal_moves": list(self.legal_moves),
            "llm_raw_response": self.llm_raw_response,
            "retried": self.retried,
            "response_time_ms": self.response_time_ms,
            "forfeit_reason": self.forfeit_reason,
            "error_detail": self.error_detail,
            "usage": dict(self.usage) if self.usage is not None else None,
        }


@dataclass
class GameResult:
    """対局結果。"""

    winner: Literal["black", "white", "draw"]
    reason: Literal["score", "forfeit"]
    score: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "winner": self.winner,
            "reason": self.reason,
            "score": dict(self.score) if self.score is not None else None,
        }


@dataclass
class GameRecord:
    """1対局分の棋譜(docs/shared/log-schema.md のトップレベル構造)。"""

    game_id: str
    black: Participant
    white: Participant
    result: GameResult
    moves: list[MoveRecord] = field(default_factory=list)
    started_at: str = ""
    ended_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "players": {
                "black": self.black.to_dict(),
                "white": self.white.to_dict(),
            },
            "result": self.result.to_dict(),
            "moves": [move.to_dict() for move in self.moves],
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }

    def summary(self) -> dict[str, Any]:
        """`data/results.jsonl` の1行(集計・差分実行判定の入力)を返す。

        `provider`・`display_name`は指標計算には使わないが、集計を`models.yaml`から
        独立させるためここに含める(docs/shared/log-schema.md「対局結果ログ」)。
        """
        return {
            "game_id": self.game_id,
            "black": self._player_summary("black"),
            "white": self._player_summary("white"),
            "winner": self.result.winner,
            "reason": self.result.reason,
            "forfeit_reason": self._forfeit_reason(),
            "ended_at": self.ended_at,
        }

    def _player_summary(self, player: Player) -> dict[str, Any]:
        participant = self.black if player == "black" else self.white
        return {
            "id": participant.id,
            "provider": participant.provider,
            "display_name": participant.display_name,
            "avg_response_time_ms": self.average_response_time_ms(player),
        }

    def average_response_time_ms(self, player: Player) -> int:
        """LLMに問い合わせた手の応答時間の単純平均(ミリ秒)。

        パス(LLMを呼ばない手)は応答時間を持たないため平均から除外する。
        """
        times = [
            move.response_time_ms
            for move in self.moves
            if move.player == player and move.type != "pass"
        ]
        if not times:
            return 0
        return round(sum(times) / len(times))

    def _forfeit_reason(self) -> ForfeitReason | None:
        if self.result.reason != "forfeit" or not self.moves:
            return None
        return self.moves[-1].forfeit_reason


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_game_id(now: Callable[[], datetime] | None = None) -> str:
    """`{UTC時刻}-{6桁hex}` 形式の対局IDを生成する。

    並列実行時に同一マイクロ秒で開始しても衝突しないようランダムサフィックスを付ける。
    コロンはWindowsのファイル名に使えないため使用しない。
    """
    moment = now() if now is not None else datetime.now(timezone.utc)
    return f"{moment.strftime('%Y%m%dT%H%M%S%f')}-{secrets.token_hex(3)}"


class _TimeoutExceeded(Exception):
    """1手あたりの時間予算を超過した(engine内部の制御用)。"""


def _run_with_timeout(func: Callable[[], Any], timeout: float | None) -> Any:
    """`func`を別スレッドで実行し、`timeout`秒を超えたら呼び出しを打ち切る。

    Pythonではスレッドを強制終了できないため、超過時は結果を捨てて呼び出し元へ制御を返す
    (デーモンスレッドなのでプロセス終了を妨げない)。
    """
    if timeout is not None and timeout <= 0:
        raise _TimeoutExceeded
    box: dict[str, Any] = {}
    finished = threading.Event()

    def worker() -> None:
        try:
            box["value"] = func()
        except BaseException as exc:  # noqa: BLE001 - 呼び出し元スレッドへ引き継ぐ
            box["error"] = exc
        finally:
            finished.set()

    threading.Thread(target=worker, daemon=True).start()
    if not finished.wait(timeout):
        raise _TimeoutExceeded
    if "error" in box:
        raise box["error"]
    return box["value"]


def _api_error_detail(exc: AdapterAPIError) -> str:
    """`AdapterAPIError`から`error_detail`用の文字列を作る(元例外も残す)。"""
    if exc.original_exception is None:
        return exc.message
    return f"{exc.message}: {exc.original_exception!r}"


# ---------------------------------------------------------------------------
# 対局
# ---------------------------------------------------------------------------


class Game:
    """1対局を最後まで進める。

    Adapterの呼び出し以外(タイムアウト・リトライ・合法手検証)はすべてこのクラスが行う。
    """

    def __init__(
        self,
        black: Participant,
        white: Participant,
        *,
        timeout_seconds: float | None = DEFAULT_TIMEOUT_SECONDS,
        game_id: str | None = None,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], str] = utc_now_iso,
    ) -> None:
        self.black = black
        self.white = white
        self.timeout_seconds = timeout_seconds
        self.game_id = game_id or new_game_id()
        self._clock = clock
        self._now = now

    # ------------------------------------------------------------------
    def play(self) -> GameRecord:
        started_at = self._now()
        board = initial_board()
        moves: list[MoveRecord] = []
        current: Player = "black"
        consecutive_passes = 0
        turn = 1
        result: GameResult | None = None

        while True:
            available = legal_moves(board, current)
            if not available:
                moves.append(
                    MoveRecord(
                        turn=turn,
                        player=current,
                        type="pass",
                        position=None,
                        board_after=board,
                        legal_moves=[],
                    )
                )
                turn += 1
                consecutive_passes += 1
                if consecutive_passes >= 2:
                    break
                current = opponent(current)
                continue

            consecutive_passes = 0
            record = self._play_move(turn, current, board, available)
            moves.append(record)
            turn += 1
            if record.type == "forfeit":
                result = GameResult(winner=opponent(current), reason="forfeit", score=None)
                break
            board = record.board_after
            if is_full(board):
                break
            current = opponent(current)

        if result is None:
            score = count_stones(board)
            if score["black"] > score["white"]:
                winner: Literal["black", "white", "draw"] = "black"
            elif score["white"] > score["black"]:
                winner = "white"
            else:
                winner = "draw"
            result = GameResult(winner=winner, reason="score", score=score)

        return GameRecord(
            game_id=self.game_id,
            black=self.black,
            white=self.white,
            result=result,
            moves=moves,
            started_at=started_at,
            ended_at=self._now(),
        )

    # ------------------------------------------------------------------
    def _participant(self, player: Player) -> Participant:
        return self.black if player == "black" else self.white

    def _play_move(
        self,
        turn: int,
        player: Player,
        board: BoardState,
        available: list[str],
    ) -> MoveRecord:
        """1手をLLMに問い合わせて記録を作る(リトライ・タイムアウト・合法手検証込み)。"""
        adapter = self._participant(player).adapter
        start = self._clock()
        retried: Retried = "none"
        pending_retry_cause: Retried = "none"
        retry_reason: str | None = None
        attempt = 0
        last_error_detail: str | None = None

        def elapsed_ms() -> int:
            return round((self._clock() - start) * 1000)

        def forfeit(
            reason: ForfeitReason,
            *,
            position: str | None = None,
            llm_raw_response: str | None = None,
            error_detail: str | None = None,
            usage: dict[str, int] | None = None,
        ) -> MoveRecord:
            return MoveRecord(
                turn=turn,
                player=player,
                type="forfeit",
                position=position,
                board_after=board,
                legal_moves=list(available),
                llm_raw_response=llm_raw_response,
                retried=retried,
                response_time_ms=elapsed_ms(),
                forfeit_reason=reason,
                error_detail=error_detail,
                usage=usage,
            )

        while True:
            remaining: float | None = None
            if self.timeout_seconds is not None:
                remaining = self.timeout_seconds - (self._clock() - start)
                if remaining <= 0:
                    # 予算超過は原因を問わず timeout として扱う(rules.md「タイムアウトの扱い」)
                    return forfeit("timeout", error_detail=last_error_detail)
            if attempt > 0:
                # 実際にリトライを開始した時点で記録する
                retried = pending_retry_cause

            try:
                response = _run_with_timeout(
                    lambda: adapter.request_move(board, list(available), player, retry_reason),
                    remaining,
                )
            except _TimeoutExceeded:
                return forfeit("timeout", error_detail=last_error_detail)
            except AdapterParseError as exc:
                attempt += 1
                last_error_detail = exc.message
                if attempt <= RETRY_BUDGET_PER_MOVE:
                    pending_retry_cause = "parse_failure"
                    retry_reason = exc.message
                    continue
                return forfeit(
                    "parse_failure",
                    llm_raw_response=exc.llm_raw_response or None,
                    error_detail=exc.message,
                )
            except AdapterAPIError as exc:
                attempt += 1
                last_error_detail = _api_error_detail(exc)
                if attempt <= RETRY_BUDGET_PER_MOVE:
                    pending_retry_cause = "api_error"
                    retry_reason = None  # APIエラーは同一内容で再送する
                    continue
                return forfeit("api_error", error_detail=last_error_detail)

            attempt += 1
            if response.position not in available:
                # 非合法手はリトライせずそのまま反則負け(原因はposition/legal_movesで分かる)
                return forfeit(
                    "illegal_move",
                    position=response.position,
                    llm_raw_response=response.llm_raw_response,
                    usage=response.usage,
                )

            return MoveRecord(
                turn=turn,
                player=player,
                type="move",
                position=response.position,
                board_after=apply_move(board, player, response.position),
                legal_moves=list(available),
                llm_raw_response=response.llm_raw_response,
                retried=retried,
                response_time_ms=elapsed_ms(),
                usage=response.usage,
            )
