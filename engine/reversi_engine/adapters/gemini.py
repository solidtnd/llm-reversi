"""Google Gemini用Adapter(`responseJsonSchema`の構造化出力を使用)。"""

from __future__ import annotations

from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors

from ..board import BoardState, Player
from .base import (
    MOVE_JSON_SCHEMA,
    MSG_NETWORK_ERROR,
    MSG_NO_STRUCTURED_OUTPUT,
    MSG_REFUSAL,
    MSG_TRUNCATED,
    AdapterAPIError,
    AdapterParseError,
    MoveResponse,
    api_error_from_status,
    build_prompt,
    parse_position,
    serialize_response,
)

# Geminiの`responseJsonSchema`が受け付けるキーワードの範囲はOpenAI/Anthropicより狭いため、
# `additionalProperties`は外して渡す。`position`が必須の文字列であるという制約は同じで、
# 余分なキーの有無は`parse_position`が無視するので、モデル間の有利不利は生じない。
GEMINI_MOVE_SCHEMA: dict[str, Any] = {
    key: value for key, value in MOVE_JSON_SCHEMA.items() if key != "additionalProperties"
}

# 応答が拒否・打ち切りされたときのfinish_reason(SDKのenumでも文字列でも比較できるよう文字列で保持)
_TRUNCATED_FINISH_REASONS = {"MAX_TOKENS"}
_REFUSAL_FINISH_REASONS = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "RECITATION"}


class GeminiAdapter:
    """Gemini APIで1手を問い合わせるAdapter。"""

    provider = "gemini"

    def __init__(
        self,
        model: str,
        config: dict[str, Any] | None = None,
        *,
        client: Any | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.config = dict(config or {})
        self._client = client if client is not None else genai.Client(api_key=api_key)

    # ------------------------------------------------------------------
    def request_move(
        self,
        board: BoardState,
        legal_moves: list[str],
        player: Player,
        retry_reason: str | None = None,
    ) -> MoveResponse:
        prompt = build_prompt(board, legal_moves, player, retry_reason)
        request_config: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_json_schema": GEMINI_MOVE_SCHEMA,
        }
        request_config.update(self.config)
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=request_config,
            )
        except Exception as exc:  # noqa: BLE001 - SDK例外をAdapter例外へ変換する
            raise _translate_error(exc) from exc
        return _to_move_response(response)


def _translate_error(exc: BaseException) -> AdapterAPIError:
    if isinstance(exc, httpx.TransportError):
        return AdapterAPIError(MSG_NETWORK_ERROR, exc)
    if isinstance(exc, genai_errors.APIError):
        return api_error_from_status(exc, getattr(exc, "code", None))
    return api_error_from_status(exc, None)


def _to_move_response(response: Any) -> MoveResponse:
    raw = serialize_response(response)
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        # プロンプト自体がブロックされた場合はcandidatesが空になる
        raise AdapterParseError(MSG_REFUSAL if _is_blocked(response) else MSG_NO_STRUCTURED_OUTPUT, raw)
    candidate = candidates[0]
    finish_reason = _as_name(getattr(candidate, "finish_reason", None))
    if finish_reason in _TRUNCATED_FINISH_REASONS:
        raise AdapterParseError(MSG_TRUNCATED, raw)
    if finish_reason in _REFUSAL_FINISH_REASONS:
        raise AdapterParseError(MSG_REFUSAL, raw)
    text = _response_text(candidate)
    if text is None:
        raise AdapterParseError(MSG_NO_STRUCTURED_OUTPUT, raw)
    position = parse_position(text, raw)
    return MoveResponse(position=position, llm_raw_response=raw, usage=_to_usage(response))


def _is_blocked(response: Any) -> bool:
    feedback = getattr(response, "prompt_feedback", None)
    return bool(feedback is not None and getattr(feedback, "block_reason", None))


def _as_name(value: Any) -> str | None:
    """SDKのenum・文字列のどちらでも名前文字列に揃える。"""
    if value is None:
        return None
    return str(getattr(value, "name", value))


def _response_text(candidate: Any) -> str | None:
    """thinkingのパート(`thought=True`)を除いたテキストを連結して返す。"""
    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None) or []
    texts = [
        part.text
        for part in parts
        if getattr(part, "text", None) and not getattr(part, "thought", False)
    ]
    if not texts:
        return None
    return "".join(texts)


def _to_usage(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None
    prompt_tokens = getattr(usage, "prompt_token_count", None)
    completion_tokens = getattr(usage, "candidates_token_count", None)
    if prompt_tokens is None and completion_tokens is None:
        return None
    return {
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
    }
