"""実プロバイダAPIに接続して動作確認するテスト。

通常の単体テスト実行に含めない方針(docs/engine/engine-architecture.md「テスト方針」)だが、
`uv run pytest` で収集されても**APIキーが未設定なら自動的にスキップ**されるようにしてある。
実行する場合は `engine/.env` にキーを設定した上で
`uv run pytest tests/live -v` のように明示的に呼ぶ。1テスト = 1手の問い合わせなので、
費用は最小限に留まる。
"""

from __future__ import annotations

import os

import pytest

from reversi_engine.config import (
    DEFAULT_ENV_PATH,
    DEFAULT_MODELS_PATH,
    build_adapter,
    load_env,
    load_models,
)
from reversi_engine.board import initial_board, legal_moves

API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}

BOARD = initial_board()
LEGAL = legal_moves(BOARD, "black")


@pytest.fixture(scope="session", autouse=True)
def _load_env() -> None:
    load_env(DEFAULT_ENV_PATH)


def _adapter_for(provider: str):
    key = API_KEY_ENV[provider]
    if not os.environ.get(key):
        pytest.skip(f"{key} が未設定のためスキップ(実APIを呼ぶテスト)")
    specs = [spec for spec in load_models(DEFAULT_MODELS_PATH) if spec.provider == provider]
    if not specs:
        pytest.skip(f"models.yaml に provider={provider} のモデルが無い")
    return build_adapter(specs[0]), specs[0]


@pytest.mark.parametrize("provider", sorted(API_KEY_ENV))
def test_request_move_returns_legal_position(provider: str) -> None:
    adapter, spec = _adapter_for(provider)

    response = adapter.request_move(BOARD, LEGAL, "black")

    assert response.position in LEGAL, f"{spec.id}: 合法手以外を返した ({response.position})"
    assert response.llm_raw_response
    if response.usage is not None:
        assert response.usage["prompt_tokens"] > 0


@pytest.mark.parametrize("provider", sorted(API_KEY_ENV))
def test_request_move_with_retry_reason(provider: str) -> None:
    """リトライ時のプロンプト(前回の失敗理由付き)でも合法手が返ることを確認する。"""
    adapter, spec = _adapter_for(provider)

    response = adapter.request_move(
        BOARD,
        LEGAL,
        "black",
        retry_reason="応答が期待する形式(`position`を含むJSON)と一致しませんでした",
    )

    assert response.position in LEGAL, f"{spec.id}: 合法手以外を返した ({response.position})"
