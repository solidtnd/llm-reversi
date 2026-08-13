"""Gemini Adapterの単体テスト(実APIは呼ばない)。"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors

from fakes import RecordedClient
from reversi_engine.adapters.base import (
    MSG_FORMAT_MISMATCH,
    MSG_NETWORK_ERROR,
    MSG_NO_STRUCTURED_OUTPUT,
    MSG_RATE_LIMIT,
    MSG_REFUSAL,
    MSG_TRUNCATED,
    AdapterAPIError,
    AdapterParseError,
)
from reversi_engine.adapters.gemini import GEMINI_MOVE_SCHEMA, GeminiAdapter
from reversi_engine.board import initial_board, legal_moves

BOARD = initial_board()
LEGAL = legal_moves(BOARD, "black")


def _part(text: str, *, thought: bool = False):
    return SimpleNamespace(text=text, thought=thought)


def _response(
    parts=None,
    *,
    finish_reason: str = "STOP",
    usage: SimpleNamespace | None = SimpleNamespace(
        prompt_token_count=200, candidates_token_count=15
    ),
    candidates_missing: bool = False,
    block_reason: str | None = None,
):
    if parts is None:
        parts = [_part('{"position": "d3"}')]
    candidates = (
        []
        if candidates_missing
        else [
            SimpleNamespace(
                finish_reason=finish_reason,
                content=SimpleNamespace(parts=parts, role="model"),
            )
        ]
    )
    return SimpleNamespace(
        candidates=candidates,
        usage_metadata=usage,
        prompt_feedback=SimpleNamespace(block_reason=block_reason) if block_reason else None,
    )


def _adapter(responses, config=None) -> tuple[GeminiAdapter, RecordedClient]:
    generate = RecordedClient(responses=list(responses))
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    return GeminiAdapter("gemini-2.5-flash", config, client=client), generate


def _api_error(code: int) -> genai_errors.APIError:
    return genai_errors.APIError(code, {"error": {"message": "boom", "code": code}})


# ---------------------------------------------------------------------------
# リクエスト整形
# ---------------------------------------------------------------------------


def test_request_uses_json_schema_without_additional_properties():
    adapter, generate = _adapter([_response()])

    adapter.request_move(BOARD, LEGAL, "black")

    call = generate.last_call
    assert call["model"] == "gemini-2.5-flash"
    assert call["config"]["response_mime_type"] == "application/json"
    assert call["config"]["response_json_schema"] == GEMINI_MOVE_SCHEMA
    assert "additionalProperties" not in GEMINI_MOVE_SCHEMA
    assert GEMINI_MOVE_SCHEMA["required"] == ["position"]
    assert "あなたは黒です" in call["contents"]


def test_config_is_merged_into_request_config():
    adapter, generate = _adapter([_response()], {"temperature": 0.4})
    adapter.request_move(BOARD, LEGAL, "black")
    assert generate.last_call["config"]["temperature"] == 0.4


def test_retry_reason_is_appended_to_prompt():
    adapter, generate = _adapter([_response()])
    adapter.request_move(BOARD, LEGAL, "white", retry_reason="拒否されました")
    assert "拒否されました" in generate.last_call["contents"]


# ---------------------------------------------------------------------------
# レスポンスのパース
# ---------------------------------------------------------------------------


def test_successful_parse_returns_move_response():
    adapter, _ = _adapter([_response()])

    result = adapter.request_move(BOARD, LEGAL, "black")

    assert result.position == "d3"
    assert result.usage == {"prompt_tokens": 200, "completion_tokens": 15}
    assert "d3" in result.llm_raw_response


def test_thought_parts_are_excluded_from_parsing():
    adapter, _ = _adapter(
        [_response([_part("考え中...", thought=True), _part('{"position": "c4"}')])]
    )

    result = adapter.request_move(BOARD, LEGAL, "black")

    assert result.position == "c4"
    assert "考え中" in result.llm_raw_response  # 生ログには思考過程も残る


def test_split_text_parts_are_concatenated():
    adapter, _ = _adapter([_response([_part('{"position":'), _part(' "f5"}')])])
    assert adapter.request_move(BOARD, LEGAL, "black").position == "f5"


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (_response(finish_reason="MAX_TOKENS"), MSG_TRUNCATED),
        (_response(finish_reason="SAFETY"), MSG_REFUSAL),
        (_response(finish_reason="PROHIBITED_CONTENT"), MSG_REFUSAL),
        (_response([]), MSG_NO_STRUCTURED_OUTPUT),
        (_response([_part("考えただけ", thought=True)]), MSG_NO_STRUCTURED_OUTPUT),
        (_response(candidates_missing=True), MSG_NO_STRUCTURED_OUTPUT),
        (_response(candidates_missing=True, block_reason="SAFETY"), MSG_REFUSAL),
        (_response([_part("JSONではない")]), MSG_FORMAT_MISMATCH),
        (_response([_part('{"square": "d3"}')]), MSG_FORMAT_MISMATCH),
    ],
)
def test_parse_failures(response, message):
    adapter, _ = _adapter([response])

    with pytest.raises(AdapterParseError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")

    assert excinfo.value.message == message
    assert excinfo.value.llm_raw_response


def test_enum_like_finish_reason_is_handled():
    adapter, _ = _adapter([_response(finish_reason=SimpleNamespace(name="MAX_TOKENS"))])
    with pytest.raises(AdapterParseError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == MSG_TRUNCATED


def test_usage_is_none_when_absent():
    adapter, _ = _adapter([_response(usage=None)])
    assert adapter.request_move(BOARD, LEGAL, "black").usage is None


# ---------------------------------------------------------------------------
# 例外変換
# ---------------------------------------------------------------------------


def test_rate_limit_error():
    adapter, _ = _adapter([_api_error(429)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == MSG_RATE_LIMIT


def test_server_error_includes_status():
    adapter, _ = _adapter([_api_error(503)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert excinfo.value.message == "APIサーバーエラーが発生しました(HTTP 503)"


def test_client_error_is_reported_with_class_name():
    adapter, _ = _adapter([_api_error(400)])
    with pytest.raises(AdapterAPIError) as excinfo:
        adapter.request_move(BOARD, LEGAL, "black")
    assert "Error" in excinfo.value.message


def test_transport_error_is_network_error():
    adapter, _ = _adapter([httpx.ConnectError("接続できない")])
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
    assert adapter.provider == "gemini"
    assert adapter.model == "gemini-2.5-flash"
