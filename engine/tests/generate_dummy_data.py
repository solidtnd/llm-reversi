"""`data/`へダミー対局データを生成する手動実行スクリプト。

web実装(表示確認)には実APIなしでスキーマ準拠のデータが必要になる。手書きのJSONは
64文字の`board_after`や着手履歴の整合性を壊しやすいため、`FakeAdapter`のランダムモードで
実際に`Game`を走らせて出力する(docs/engine/engine-architecture.md「ダミーデータ生成」)。

- `models.yaml`のprovider解決(`config.py`)は経由せず、ここでFakeAdapterを直接組み立てる。
- 反則負け4種(illegal_move/timeout/parse_failure/api_error)・リトライ発生・複数provider混在・
  `usage`がnullのプロバイダを、いずれも最低1件含む。生成後に充足を検証して落とす。
- 時刻・game_id・着手はすべて固定シードで決めるため、**再実行すると同じ内容が生成される**
  (data/はコミット対象なので、無意味な差分が出ないようにするため)。

使い方:

    uv run python tests/generate_dummy_data.py --reset
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fakes import RANDOM, FakeAdapter  # noqa: E402
from reversi_engine.adapters.base import (  # noqa: E402
    MSG_FORMAT_MISMATCH,
    MSG_NO_STRUCTURED_OUTPUT,
    MSG_RATE_LIMIT,
    MSG_SERVER_ERROR,
    AdapterAPIError,
    AdapterParseError,
    MoveResponse,
)
from reversi_engine.aggregate import aggregate  # noqa: E402
from reversi_engine.config import ModelSpec, Points  # noqa: E402
from reversi_engine.game import Game, GameRecord, Participant  # noqa: E402
from reversi_engine.league import build_cards  # noqa: E402
from reversi_engine.storage import DEFAULT_DATA_DIR, Storage  # noqa: E402

TIMEOUT_SECONDS = 30.0

#: 対局開始時刻の起点(固定値。実行日時に依存させると毎回差分が出るため)
BASE_TIME = datetime(2026, 1, 10, 3, 0, 0, tzinfo=timezone.utc)

#: ダミーの出場モデル(provider混在。geminiはusageを返さないプロバイダの代表として扱う)
DUMMY_MODELS: list[ModelSpec] = [
    ModelSpec(id="gpt-4o", provider="openai", model="gpt-4o", display_name="GPT-4o"),
    ModelSpec(
        id="gpt-4o-mini",
        provider="openai",
        model="gpt-4o-mini",
        display_name="GPT-4o mini",
    ),
    ModelSpec(
        id="claude-opus-5-thinking",
        provider="anthropic",
        model="claude-opus-5",
        display_name="Claude Opus 5 (Thinkあり)",
        config={"thinking": True, "max_tokens": 4096},
    ),
    ModelSpec(
        id="claude-haiku-4-5",
        provider="anthropic",
        model="claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        config={"max_tokens": 2048},
    ),
    ModelSpec(
        id="gemini-2.5-flash",
        provider="gemini",
        model="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
    ),
]

#: usageを返さないプロバイダ(Move.usageがnullになる経路をweb側で確認するため)
PROVIDERS_WITHOUT_USAGE = {"gemini"}


# ---------------------------------------------------------------------------
# 生ログ(llm_raw_response)の見た目をプロバイダらしくする
# ---------------------------------------------------------------------------


def _openai_raw(position: str | None, *, broken: bool = False) -> str:
    content = "位置は" + str(position) if broken else json.dumps({"position": position})
    return json.dumps(
        {
            "id": "chatcmpl-dummy",
            "object": "chat.completion",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content, "refusal": None},
                }
            ],
            "usage": {"prompt_tokens": 412, "completion_tokens": 9, "total_tokens": 421},
        },
        ensure_ascii=False,
    )


def _anthropic_raw(position: str | None, *, broken: bool = False) -> str:
    content: list[dict[str, Any]] = [
        {"type": "thinking", "thinking": "角に近いマスを優先し、相手の返し手を確認した。"}
    ]
    if not broken:
        content.append({"type": "text", "text": json.dumps({"position": position})})
    return json.dumps(
        {
            "id": "msg_dummy",
            "type": "message",
            "model": "claude-opus-5",
            "stop_reason": "end_turn",
            "content": content,
            "usage": {"input_tokens": 508, "output_tokens": 14},
        },
        ensure_ascii=False,
    )


def _gemini_raw(position: str | None, *, broken: bool = False) -> str:
    text = "```\n" + str(position) + "\n```" if broken else json.dumps({"position": position})
    return json.dumps(
        {
            "candidates": [
                {
                    "finish_reason": "STOP",
                    "content": {
                        "role": "model",
                        "parts": [
                            {"text": "盤面全体を確認した。", "thought": True},
                            {"text": text},
                        ],
                    },
                }
            ]
        },
        ensure_ascii=False,
    )


RAW_BUILDERS: dict[str, Callable[..., str]] = {
    "openai": _openai_raw,
    "anthropic": _anthropic_raw,
    "gemini": _gemini_raw,
}


class DummyAdapter(FakeAdapter):
    """`FakeAdapter`の生ログを、そのプロバイダのレスポンスらしいJSONに差し替える。

    web側の生ログパネルの表示確認に耐えるダミーにするための拡張で、着手の決め方
    (ランダムモード・スクリプト)は`FakeAdapter`のままにしてある。
    """

    def __init__(self, spec: ModelSpec, **kwargs: Any) -> None:
        usage = None if spec.provider in PROVIDERS_WITHOUT_USAGE else {
            "prompt_tokens": 412,
            "completion_tokens": 9,
        }
        super().__init__(spec.model, usage=usage, **kwargs)
        self.provider = spec.provider

    def request_move(self, board, legal_moves, player, retry_reason=None) -> MoveResponse:
        response = super().request_move(board, legal_moves, player, retry_reason)
        builder = RAW_BUILDERS[self.provider]
        return replace(response, llm_raw_response=builder(response.position))


def broken_raw(provider: str) -> str:
    return RAW_BUILDERS[provider]("d3", broken=True)


# ---------------------------------------------------------------------------
# シナリオ定義
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """1対局に仕込む事象。"""

    name: str
    #: 事象を起こす側("black" / "white")
    side: str = "black"
    #: 何手目(その対局でLLMに問い合わせた手のうち何番目)に起こすか
    at_move: int = 0
    #: 仕込む応答/例外(FakeAdapterのresponsesへ後ろに足す)
    faults: tuple[Any, ...] = ()
    #: 擬似時計の特定呼び出しだけ大きく進める(タイムアウト再現用)
    clock_overrides: dict[int, float] = field(default_factory=dict)


def _parse_error(provider: str, message: str = MSG_FORMAT_MISMATCH) -> AdapterParseError:
    return AdapterParseError(message, broken_raw(provider))


def scenarios_for(provider_of_side: Callable[[str], str]) -> dict[int, Scenario]:
    """カードindex → シナリオ。指定の無いカードは通常進行(全手ランダム)。"""
    return {
        1: Scenario(
            name="retry_parse_then_success",
            side="black",
            at_move=3,
            faults=(_parse_error(provider_of_side("black")),),
        ),
        3: Scenario(
            name="retry_api_then_success",
            side="white",
            at_move=2,
            faults=(AdapterAPIError(MSG_RATE_LIMIT, RuntimeError("429 Too Many Requests")),),
        ),
        4: Scenario(name="forfeit_illegal_move", side="black", at_move=7, faults=("d4",)),
        6: Scenario(
            name="forfeit_parse_failure",
            side="white",
            at_move=5,
            faults=(
                _parse_error(provider_of_side("white")),
                _parse_error(provider_of_side("white"), MSG_NO_STRUCTURED_OUTPUT),
            ),
        ),
        8: Scenario(
            name="forfeit_api_error",
            side="black",
            at_move=4,
            faults=(
                AdapterAPIError(MSG_RATE_LIMIT, RuntimeError("429 Too Many Requests")),
                AdapterAPIError(
                    MSG_SERVER_ERROR.format(status=503), RuntimeError("503 Service Unavailable")
                ),
            ),
        ),
        10: Scenario(
            name="forfeit_timeout",
            side="white",
            # 12手目(LLM問い合わせ通算)の予算判定で31秒経過している状態を作る
            clock_overrides={3 * 11 + 1: 31.0},
        ),
        13: Scenario(
            name="retry_parse_then_success",
            side="white",
            at_move=6,
            faults=(_parse_error(provider_of_side("white")),),
        ),
        17: Scenario(
            name="forfeit_illegal_move",
            side="white",
            at_move=9,
            faults=("z9",),  # 表記そのものが不正なケース
        ),
    }


class StepClock:
    """呼び出しごとに一定時間進む擬似時計。

    実時間で待たずに現実的な`response_time_ms`を作るために使う。`overrides`で特定の
    呼び出しだけ大きく進めると、1手あたりの予算超過(タイムアウト)を再現できる。
    """

    def __init__(self, step: float = 0.45, overrides: dict[int, float] | None = None) -> None:
        self.step = step
        self.overrides = dict(overrides or {})
        self.calls = 0
        self.value = 0.0

    def __call__(self) -> float:
        increment = self.overrides.get(self.calls, self.step)
        self.calls += 1
        self.value += increment
        return self.value


# ---------------------------------------------------------------------------
# 生成
# ---------------------------------------------------------------------------


def build_participant(spec: ModelSpec, adapter: FakeAdapter) -> Participant:
    return Participant(
        id=spec.id,
        provider=spec.provider,
        model=spec.model,
        display_name=spec.display_name,
        config=dict(spec.config),
        adapter=adapter,
    )


def _responses_for(scenario: Scenario | None, side: str) -> list[Any]:
    if scenario is None or scenario.side != side or not scenario.faults:
        return []
    return [RANDOM] * scenario.at_move + list(scenario.faults)


def _timestamps(index: int, move_count: int) -> Callable[[], str]:
    """started_at → ended_at を返すcallable(対局ごとに現実的な時刻を割り当てる)。"""
    start = BASE_TIME + timedelta(minutes=17 * index)
    end = start + timedelta(seconds=1.4 * max(move_count, 1))
    moments = iter([start.isoformat(), end.isoformat()])
    return lambda: next(moments)


def generate(data_dir: Path) -> list[GameRecord]:
    """ダミー対局を生成して`data/`へ書き出し、棋譜のリストを返す。"""
    storage = Storage(data_dir)
    specs = {spec.id: spec for spec in DUMMY_MODELS}
    # build_cardsに渡すためだけの仮のParticipant(adapterはカードごとに作り直す)
    placeholders = [build_participant(spec, FakeAdapter(random_seed=0)) for spec in DUMMY_MODELS]
    cards = build_cards(placeholders)

    records: list[GameRecord] = []
    for index, card in enumerate(cards):
        black_spec = specs[card.black.id]
        white_spec = specs[card.white.id]
        scenario = scenarios_for(
            lambda side: black_spec.provider if side == "black" else white_spec.provider
        ).get(index)

        black = build_participant(
            black_spec,
            DummyAdapter(
                black_spec,
                responses=_responses_for(scenario, "black"),
                random_seed=1000 + index * 2,
            ),
        )
        white = build_participant(
            white_spec,
            DummyAdapter(
                white_spec,
                responses=_responses_for(scenario, "white"),
                random_seed=2000 + index * 2,
            ),
        )

        game_id_random = random.Random(index)
        clock = StepClock(overrides=scenario.clock_overrides if scenario else None)
        start = BASE_TIME + timedelta(minutes=17 * index)
        game_id = f"{start.strftime('%Y%m%dT%H%M%S%f')}-{game_id_random.randbytes(3).hex()}"

        # 手数が確定してから ended_at を決めたいので、まず時刻を仮置きして対局を進める
        game = Game(
            black,
            white,
            timeout_seconds=TIMEOUT_SECONDS,
            game_id=game_id,
            clock=clock,
            now=lambda: start.isoformat(),
        )
        record = game.play()
        stamps = _timestamps(index, len(record.moves))
        record.started_at = stamps()
        record.ended_at = stamps()

        storage.record_game(record)
        records.append(record)

    ranking = aggregate(
        storage.read_results(),
        models=DUMMY_MODELS,
        points=Points(),
        generated_at=(BASE_TIME + timedelta(minutes=17 * len(cards))).isoformat(),
    )
    storage.write_ranking(ranking)
    return records


# ---------------------------------------------------------------------------
# 検証・表示
# ---------------------------------------------------------------------------


def summarize(records: Sequence[GameRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}

    def bump(key: str) -> None:
        counts[key] = counts.get(key, 0) + 1

    for record in records:
        if record.result.reason == "forfeit":
            bump(f"forfeit:{record.moves[-1].forfeit_reason}")
        else:
            bump(f"score:{record.result.winner}")
        for move in record.moves:
            if move.retried != "none":
                bump(f"retried:{move.retried}")
            if move.type == "pass":
                bump("pass")
            if move.usage is None and move.type == "move":
                bump("usage:null")
    return counts


REQUIRED_KEYS = (
    "forfeit:illegal_move",
    "forfeit:timeout",
    "forfeit:parse_failure",
    "forfeit:api_error",
    "retried:parse_failure",
    "retried:api_error",
    "usage:null",
)


def verify(counts: dict[str, int], records: Sequence[GameRecord]) -> list[str]:
    problems = [f"{key} が0件" for key in REQUIRED_KEYS if not counts.get(key)]
    providers = {
        participant.provider
        for record in records
        for participant in (record.black, record.white)
    }
    if len(providers) < 2:
        problems.append(f"provider が混在していない: {sorted(providers)}")
    return problems


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="data/へダミー対局データを生成する")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="出力先(既定: リポジトリ直下のdata/)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="既存のgames/・results.jsonl・ranking.jsonを削除してから生成する",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    data_dir = Path(args.data_dir)
    storage = Storage(data_dir)
    if args.reset:
        shutil.rmtree(storage.games_dir, ignore_errors=True)
        storage.results_path.unlink(missing_ok=True)
        storage.ranking_path.unlink(missing_ok=True)
    elif storage.results_path.exists():
        print(
            f"{storage.results_path} が既に存在します。既存データと混ざるため中断しました。"
            "\n上書きしてよい場合は --reset を付けて実行してください。",
            file=sys.stderr,
        )
        return 1

    records = generate(data_dir)
    counts = summarize(records)
    print(f"{len(records)}局を生成しました -> {data_dir}")
    for key in sorted(counts):
        print(f"  {key}: {counts[key]}")

    problems = verify(counts, records)
    if problems:
        print("\n必要なケースが不足しています:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
