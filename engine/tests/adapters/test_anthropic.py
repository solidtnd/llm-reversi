"""Anthropic Adapterの単体テスト(実APIは呼ばない)。"""

from __future__ import annotations

from types import SimpleNamespace

import anthropic
import httpx
import pytest

from fakes import RecordedClient
from reversi_engine.adapters.anthropic import DEFAULT_MAX_TOKENS, AnthropicAdapter
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
from reversi_engine.board import initial_board, legal_moves

BOARD = initial_board()
LEGAL = legal_moves(BOARD, "black")


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _thinking_block(text: str):
    return SimpleNamespace(type="thinking", thinking=text)


def _response(
    content=None,
    *,
    stop_reason: str = "end_turn",
    usage: SimpleNamespace | None = SimpleNamespace(input_tokens=150, output_tokens=12),
):
    if content is None:
        content = [_text_block('{"position": "d3"}')]
    return SimpleNamespace(
        id="msg_1",
        stop_reason=stop_reason,
        content=content,
        usage=usage,
    )


def _adapter(responses, config=None) -> tuple[AnthropicAdapter, RecordedClient]:
    create = RecordedClient(responses=list(responses))
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return AnthropicAdapter("claude-opus-5", config, client=client), create


def _status_error(status: int, message: str = "boom") -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request)
    error_class = anthropic.RateLimitError if status == 429 else anthropic.APIStatusError
    return error_class(message, response=response, body=None)


# ---------------------------------------------------------------------------
# リクエスト整形
# ---------------------------------------------------------------------------


def test_request_uses_output_config_format():
    adapter, create = _adapter([_response()])

    adapter.request_move(BOARD, LEGAL, "black")

    call = create.last_call
    assert call["model"] == "claude-opus-5"
    assert call["output_config"] == {
        "format": {"type": "json_schema", "schema": MOVE_JSON_SCHEMA}
    }
    assert call["max_tokens"] == DEFAULT_MAX_TOKENS
    prompt = call["messages"][0]["content"]
    assert "あなたは黒です" in prompt
    assert "d3, c4, f5, e6" in prompt


def test_max_tokens_can_be_overridden_by_config():
    adapter, create = _adapter([_response()], {"max_tokens": 512})
    adapter.request_move(BOARD, LEGAL, "black")
    assert create.last_call["max_tokens"] == 512


def test_thinking_true_is_converted_to_adaptive():
    adapter, create = _adapter([_response()], {"thinking": True})
    adapter.request_move(BOARD, LEGAL, "black")
    assert create.last_call["thinking"] == {"type": "adaptive"}


def test_thinking_false_is_converted_to_disabled():
    adapter, create = _adapter([_response()], {"thinking": False})
    adapter.request_move(BOARD, LEGAL, "black")
    assert create.last_call["thinking"] == {"type": "disabled"}


def test_thinking_mapping_is_passed_through():
    adapter, create = _adapter([_response()], {"thinking": {"type": "adaptive", "display": "summarized"}})
    adapter.request_move(BOARD, LEGAL, "black")
    assert create.last_call["thinking"] == {"type": "adaptive", "display": "summarized"}


def test_other_config_keys_are_passed_through():
    adapter, create = _adapter([_response()], {"some_future_param": "high"})
    adapter.request_move(BOARD, LEGAL, "black")
    assert create.last_call["some_future_param"] == "high"


def test_output_config_extra_keys_are_merged_with_format():
    adapter, create = _adapter([_response()], {"output_config": {"effort": "low"}})
    adapter.request_move(BOARD, LEGAL, "black")
    assert create.last_call["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": MOVE_JSON_SCHEMA},
    }


def test_output_config_cannot_override_format():
    adapter, create = _adapter(
        [_response()], {"output_config": {"format": {"type": "text"}}}
    )
    adapter.request_move(BOARD, LEGAL, "black")
    assert create.last_call["output_config"] == {
        "format": {"type": "json_schema", "schema": MOVE_JSON_SCHEMA}
    }


def test_config_is_not_mutated_between_calls():
    adapter, create = _adapter([_response(), _response()], {"max_tokens": 256})

    adapter.request_move(BOARD, LEGAL, "black")
    adapter.request_move(BOARD, LEGAL, "black")

    assert adapter.config == {"max_tokens": 256}
    assert create.calls[1]["max_tokens"] == 256


def test_retry_reason_is_appended_to_prompt():
    adapter, create = _adapter([_response()])
    adapter.request_move(BOARD, LEGAL, "black", retry_reason="形式が違います")
    assert "形式が違います" in create.last_call["messages"][0]["content"]


# ---------------------------------------------------------------------------
# レスポンスのパース
# ---------------------------------------------------------------------------


def test_successful_parse_returns_move_response():
    adapter, _ = _adapter([_response()])

    result = adapter.request_move(BOARD, LEGAL, "black")

    assert result.position == "d3"
    assert result.usage == {"prompt_tokens": 150, "completion_tokens": 12}
    assert "msg_1" in result.llm_raw_response


def test_thinking_block_is_skipped_but_kept_in_raw_response():
    adapter, _ = _adapter(
        [_response([_thinking_block("考え中..."), _text_block('{"position": "c4"}')])]
    )

    result = adapter.request_move(BOARD, LEGAL, "black")

    assert result.position == "c4"
    assert "考え中" in result.llm_raw_response  # 思考過程も生ログには残る


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (_response(stop_reason="refusal"), MSG_REFUSAL),
        (_response(stop_reason="max_tokens"), MSG_TRUNCATED),
        (_response([]), MSG_NO_STRUCTURED_OUTPUT),
        (_response([_thinking_block("考えただけ")]), MSG_NO_STRUCTURED_OUTPUT),
        (_response([_text_block("JSONではない")]), MSG_FORMAT_MISMATCH),
        (_response([_text_block('{"pos": "d3"}')]), MSG_FORMAT_MISMATCH),
    ],
)
def test_parse_failures(response, message):
    adapter, _ = _adapter([response])

    with pytest.raises(AdapterParseError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")

    assert excinfo.value.message == message
    assert excinfo.value.llm_raw_response


def test_usage_is_none_when_absent():
    adapter, _ = _adapter([_response(usage=None)])
    assert adapter.request_move(BOARD, LEGAL, "black").usage is None


# ---------------------------------------------------------------------------
# 例外変換
# ---------------------------------------------------------------------------


def test_rate_limit_error():
    adapter, _ = _adapter([_status_error(429)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == MSG_RATE_LIMIT


def test_server_error_includes_status():
    adapter, _ = _adapter([_status_error(500)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == "APIサーバーエラーが発生しました(HTTP 500)"


def test_client_error_is_reported_with_class_name():
    adapter, _ = _adapter([_status_error(400)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert "APIStatusError" in excinfo.value.message


def test_connection_error_is_network_error():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    adapter, _ = _adapter([anthropic.APIConnectionError(request=request)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == MSG_NETWORK_ERROR


def test_unexpected_exception_is_wrapped():
    adapter, _ = _adapter([ValueError("想定外")])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == "ValueError: 想定外"


def test_provider_and_model_are_exposed():
    adapter, _ = _adapter([_response()])
    assert adapter.provider == "anthropic"
    assert adapter.model == "claude-opus-5"
