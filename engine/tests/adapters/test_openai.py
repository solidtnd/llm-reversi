"""OpenAI Adapterの単体テスト(実APIは呼ばない)。"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import openai
import pytest

from fakes import RecordedClient
from reversi_engine.adapters.base import (
    MOVE_JSON_SCHEMA,
    MSG_FORMAT_MISMATCH,
    MSG_NETWORK_ERROR,
    MSG_NO_STRUCTURED_OUTPUT,
    MSG_RATE_LIMIT,
    MSG_REFUSAL,
    MSG_TRUNCATED,
    AdapterAPIError,
    AdapterParseError,
)
from reversi_engine.adapters.openai import OpenAIAdapter
from reversi_engine.board import initial_board, legal_moves

BOARD = initial_board()
LEGAL = legal_moves(BOARD, "black")


def _response(
    content: str | None = '{"position": "d3"}',
    *,
    refusal: str | None = None,
    finish_reason: str = "stop",
    usage: SimpleNamespace | None = SimpleNamespace(prompt_tokens=120, completion_tokens=8),
):
    return SimpleNamespace(
        id="chatcmpl-1",
        choices=[
            SimpleNamespace(
                index=0,
                finish_reason=finish_reason,
                message=SimpleNamespace(role="assistant", content=content, refusal=refusal),
            )
        ],
        usage=usage,
    )


def _adapter(responses, config=None) -> tuple[OpenAIAdapter, RecordedClient]:
    create = RecordedClient(responses=list(responses))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return OpenAIAdapter("gpt-4o", config, client=client), create


def _status_error(status: int, message: str = "boom") -> openai.APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status, request=request)
    error_class = openai.RateLimitError if status == 429 else openai.APIStatusError
    return error_class(message, response=response, body=None)


# ---------------------------------------------------------------------------
# リクエスト整形
# ---------------------------------------------------------------------------


def test_request_uses_common_prompt_and_schema():
    adapter, create = _adapter([_response()])

    adapter.request_move(BOARD, LEGAL, "black")

    call = create.last_call
    assert call["model"] == "gpt-4o"
    assert call["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "reversi_move", "strict": True, "schema": MOVE_JSON_SCHEMA},
    }
    prompt = call["messages"][0]["content"]
    assert call["messages"][0]["role"] == "user"
    assert "あなたは黒です" in prompt
    assert "    a b c d e f g h" in prompt
    assert "d3, c4, f5, e6" in prompt
    assert "前回の応答について" not in prompt


def test_retry_reason_is_appended_to_prompt():
    adapter, create = _adapter([_response()])

    adapter.request_move(BOARD, LEGAL, "white", retry_reason="壊れていました")

    prompt = create.last_call["messages"][0]["content"]
    assert "あなたは白です" in prompt
    assert "前回の応答について" in prompt
    assert "壊れていました" in prompt
    assert prompt.index("前回の応答について") < prompt.index("## 指示")


def test_config_is_passed_through_as_request_parameters():
    adapter, create = _adapter([_response()], {"temperature": 0.2, "seed": 7})

    adapter.request_move(BOARD, LEGAL, "black")

    assert create.last_call["temperature"] == 0.2
    assert create.last_call["seed"] == 7


# ---------------------------------------------------------------------------
# レスポンスのパース
# ---------------------------------------------------------------------------


def test_successful_parse_returns_move_response():
    adapter, _ = _adapter([_response()])

    result = adapter.request_move(BOARD, LEGAL, "black")

    assert result.position == "d3"
    assert result.usage == {"prompt_tokens": 120, "completion_tokens": 8}
    assert "chatcmpl-1" in result.llm_raw_response  # レスポンス全体を残す


def test_position_is_stripped():
    adapter, _ = _adapter([_response('{"position": " d3 "}')])
    assert adapter.request_move(BOARD, LEGAL, "black").position == "d3"


def test_usage_is_none_when_absent():
    adapter, _ = _adapter([_response(usage=None)])
    assert adapter.request_move(BOARD, LEGAL, "black").usage is None


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (_response(refusal="お断りします"), MSG_REFUSAL),
        (_response(finish_reason="length"), MSG_TRUNCATED),
        (_response(None), MSG_NO_STRUCTURED_OUTPUT),
        (_response(""), MSG_NO_STRUCTURED_OUTPUT),
        (_response("これはJSONではない"), MSG_FORMAT_MISMATCH),
        (_response('{"move": "d3"}'), MSG_FORMAT_MISMATCH),
        (_response('{"position": 3}'), MSG_FORMAT_MISMATCH),
        (_response("[1, 2, 3]"), MSG_FORMAT_MISMATCH),
    ],
)
def test_parse_failures(response, message):
    adapter, _ = _adapter([response])

    with pytest.raises(AdapterParseError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")

    assert excinfo.value.message == message
    assert excinfo.value.llm_raw_response  # 生レスポンスを保持する


def test_missing_choices_is_parse_error():
    adapter, _ = _adapter([SimpleNamespace(choices=[], usage=None)])
    with pytest.raises(AdapterParseError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == MSG_NO_STRUCTURED_OUTPUT


# ---------------------------------------------------------------------------
# 例外変換
# ---------------------------------------------------------------------------


def test_rate_limit_error():
    adapter, _ = _adapter([_status_error(429)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == MSG_RATE_LIMIT
    assert isinstance(excinfo.value.original_exception, openai.RateLimitError)


def test_server_error_includes_status():
    adapter, _ = _adapter([_status_error(503)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == "APIサーバーエラーが発生しました(HTTP 503)"


def test_client_error_is_reported_with_class_name():
    adapter, _ = _adapter([_status_error(400, "bad request")])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert "APIStatusError" in excinfo.value.message


def test_connection_error_is_network_error():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    adapter, _ = _adapter([openai.APIConnectionError(request=request)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == MSG_NETWORK_ERROR


def test_timeout_error_is_network_error():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    adapter, _ = _adapter([openai.APITimeoutError(request=request)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == MSG_NETWORK_ERROR


def test_unexpected_exception_is_wrapped():
    adapter, _ = _adapter([RuntimeError("想定外")])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == "RuntimeError: 想定外"


def test_provider_and_model_are_exposed():
    adapter, _ = _adapter([_response()])
    assert adapter.provider == "openai"
    assert adapter.model == "gpt-4o"
