"""OpenAI用Adapter(Structured Outputsを使用)。"""

from __future__ import annotations

from typing import Any

import openai

from ..board import BoardState, Player
from .base import (
    MOVE_JSON_SCHEMA,
    MOVE_SCHEMA_NAME,
    MSG_NO_STRUCTURED_OUTPUT,
    MSG_NETWORK_ERROR,
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


class OpenAIAdapter:
    """OpenAI Chat Completions APIで1手を問い合わせるAdapter。"""

    provider = "openai"

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
        self._client = client if client is not None else openai.OpenAI(api_key=api_key)

    # ------------------------------------------------------------------
    def request_move(
        self,
        board: BoardState,
        legal_moves: list[str],
        player: Player,
        retry_reason: str | None = None,
    ) -> MoveResponse:
        prompt = build_prompt(board, legal_moves, player, retry_reason)
        params: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": MOVE_SCHEMA_NAME,
                    "strict": True,
                    "schema": MOVE_JSON_SCHEMA,
                },
            },
        }
        params.update(self.config)
        try:
            response = self._client.chat.completions.create(**params)
        except Exception as exc:  # noqa: BLE001 - SDK例外をAdapter例外へ変換する
            raise _translate_error(exc) from exc
        return _to_move_response(response)


def _translate_error(exc: BaseException) -> AdapterAPIError:
    if isinstance(exc, openai.APIConnectionError):  # APITimeoutErrorも含む
        return AdapterAPIError(MSG_NETWORK_ERROR, exc)
    if isinstance(exc, openai.APIStatusError):
        return api_error_from_status(exc, getattr(exc, "status_code", None))
    return api_error_from_status(exc, None)


def _to_move_response(response: Any) -> MoveResponse:
    raw = serialize_response(response)
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise AdapterParseError(MSG_NO_STRUCTURED_OUTPUT, raw)
    choice = choices[0]
    message = getattr(choice, "message", None)
    if message is not None and getattr(message, "refusal", None):
        raise AdapterParseError(MSG_REFUSAL, raw)
    if getattr(choice, "finish_reason", None) == "length":
        raise AdapterParseError(MSG_TRUNCATED, raw)
    content = getattr(message, "content", None) if message is not None else None
    position = parse_position(content, raw)
    return MoveResponse(position=position, llm_raw_response=raw, usage=_to_usage(response))


def _to_usage(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    if prompt_tokens is None and completion_tokens is None:
        return None
    return {
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
    }
