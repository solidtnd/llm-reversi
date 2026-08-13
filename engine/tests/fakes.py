"""`LLMAdapter` Protocolを実装したテストダブル。

実プロバイダのSDKを呼ばずに反則負け判定・タイムアウト処理・リトライ制御を検証するため
(docs/engine/engine-architecture.md「テスト方針」)。ダミーデータ生成
(`tests/generate_dummy_data.py`)でも同じクラスをランダムモードで使う。
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from reversi_engine.adapters.base import MoveResponse
from reversi_engine.board import BoardState, Player


class _RandomChoice:
    """「合法手からランダムに1つ選ぶ」ことを表すセンチネル。"""

    def __repr__(self) -> str:  # pragma: no cover - デバッグ表示用
        return "RANDOM"


#: `responses` の要素として使うと、その手は合法手からランダムに選ばれる。
RANDOM = _RandomChoice()


@dataclass(frozen=True)
class FakeStep:
    """1回の呼び出しの振る舞い(遅延を伴う応答/例外)。"""

    result: Any = RANDOM
    delay: float = 0.0


@dataclass
class FakeCall:
    """`request_move` の呼び出し引数の記録。"""

    board: BoardState
    legal_moves: list[str]
    player: Player
    retry_reason: str | None


class FakeAdapter:
    """呼び出しごとに異なる応答/例外を返せるAdapter。

    `responses` の各要素は次のいずれか。

    - `RANDOM`: 合法手からランダムに1つ選ぶ(ランダムモード)
    - `str`: その位置を返す(非合法手を渡せば`illegal_move`の検証に使える)
    - `MoveResponse`: そのまま返す
    - 例外インスタンス: 送出する(`AdapterParseError`/`AdapterAPIError`等)
    - `FakeStep`: 上記に遅延(`delay`秒)を付けたもの(タイムアウト検証用)

    `responses` を使い切った後は、`random_seed` が指定されていればランダムモードで
    続行し、そうでなければ AssertionError にする(想定外の呼び出しを検出するため)。
    """

    provider = "fake"

    def __init__(
        self,
        model: str = "fake-model",
        *,
        responses: Sequence[Any] | None = None,
        random_seed: int | None = None,
        usage: dict[str, int] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model
        self.responses = list(responses or [])
        self.random = random.Random(random_seed) if random_seed is not None else None
        self.usage = usage
        self._sleep = sleep
        self.calls: list[FakeCall] = []

    # ------------------------------------------------------------------
    def request_move(
        self,
        board: BoardState,
        legal_moves: list[str],
        player: Player,
        retry_reason: str | None = None,
    ) -> MoveResponse:
        index = len(self.calls)
        self.calls.append(
            FakeCall(
                board=board,
                legal_moves=list(legal_moves),
                player=player,
                retry_reason=retry_reason,
            )
        )
        step = self._step(index)
        if step.delay:
            self._sleep(step.delay)
        result = step.result
        if isinstance(result, BaseException):
            raise result
        if isinstance(result, MoveResponse):
            return result
        if isinstance(result, _RandomChoice):
            if self.random is None:  # pragma: no cover - 使い方の誤り
                raise AssertionError("ランダムモードには random_seed が必要")
            position = self.random.choice(list(legal_moves))
        elif isinstance(result, str):
            position = result
        else:  # pragma: no cover - 使い方の誤り
            raise AssertionError(f"FakeAdapter: 未対応の応答 {result!r}")
        return MoveResponse(
            position=position,
            llm_raw_response=f'{{"position": "{position}"}}',
            usage=dict(self.usage) if self.usage is not None else None,
        )

    # ------------------------------------------------------------------
    @property
    def call_count(self) -> int:
        return len(self.calls)

    def _step(self, index: int) -> FakeStep:
        if index < len(self.responses):
            step = self.responses[index]
            return step if isinstance(step, FakeStep) else FakeStep(result=step)
        if self.random is not None:
            return FakeStep(result=RANDOM)
        raise AssertionError(
            f"FakeAdapter: {index + 1}回目の呼び出しに対する応答が定義されていない"
        )


def participant(
    player_id: str,
    adapter: Any,
    *,
    provider: str | None = None,
    model: str | None = None,
    display_name: str | None = None,
    config: dict[str, Any] | None = None,
):
    """テスト用に`Participant`を組み立てる。"""
    from reversi_engine.game import Participant

    return Participant(
        id=player_id,
        provider=provider or getattr(adapter, "provider", "fake"),
        model=model or getattr(adapter, "model", "fake-model"),
        display_name=display_name or player_id,
        config=dict(config or {}),
        adapter=adapter,
    )


def random_participant(player_id: str, seed: int, **kwargs: Any):
    """ランダムモードのFakeAdapterを持つ`Participant`を作る。"""
    return participant(player_id, FakeAdapter(random_seed=seed), **kwargs)


@dataclass
class RecordedClient:
    """SDKクライアントの代わりに呼び出し引数を記録するテストダブル。"""

    responses: list[Any] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        result = self.responses[index]
        if isinstance(result, BaseException):
            raise result
        return result

    @property
    def last_call(self) -> dict[str, Any]:
        return self.calls[-1]
