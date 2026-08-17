"""Anthropic用Adapter(`output_config.format`の構造化出力を使用)。"""

from __future__ import annotations

from typing import Any

import anthropic

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

DEFAULT_MAX_TOKENS = 4096


class AnthropicAdapter:
    """Anthropic Messages APIで1手を問い合わせるAdapter。"""

    provider = "anthropic"

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
        self._client = client if client is not None else anthropic.Anthropic(api_key=api_key)

    # ------------------------------------------------------------------
    def request_move(
        self,
        board: BoardState,
        legal_moves: list[str],
        player: Player,
        retry_reason: str | None = None,
    ) -> MoveResponse:
        prompt = build_prompt(board, legal_moves, player, retry_reason)
        extra = _normalize_config(self.config)
        # configの output_config (例: {"effort": "low"}) はマージする。params.update(extra)で
        # 丸ごと上書きすると構造化出力用のformatが消えてしまうため、ここで先に取り出しておく。
        output_config = extra.pop("output_config", {})
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": extra.pop("max_tokens", DEFAULT_MAX_TOKENS),
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {
                **output_config,
                "format": {"type": "json_schema", "schema": MOVE_JSON_SCHEMA},
            },
        }
        params.update(extra)
        try:
            response = self._client.messages.create(**params)
        except Exception as exc:  # noqa: BLE001 - SDK例外をAdapter例外へ変換する
            raise _translate_error(exc) from exc
        return _to_move_response(response)


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    """`models.yaml`のconfigをAnthropic APIのパラメータへ整える。

    `thinking: true/false` という素直な書き方だけAPIの形式(`{"type": ...}`)へ変換し、
    それ以外のキーはそのまま素通しする。
    """
    normalized = dict(config)
    thinking = normalized.get("thinking")
    if isinstance(thinking, bool):
        normalized["thinking"] = {"type": "adaptive"} if thinking else {"type": "disabled"}
    return normalized


def _translate_error(exc: BaseException) -> AdapterAPIError:
    if isinstance(exc, anthropic.APIConnectionError):  # APITimeoutErrorも含む
        return AdapterAPIError(MSG_NETWORK_ERROR, exc)
    if isinstance(exc, anthropic.APIStatusError):
        return api_error_from_status(exc, getattr(exc, "status_code", None))
    return api_error_from_status(exc, None)


def _to_move_response(response: Any) -> MoveResponse:
    raw = serialize_response(response)
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "refusal":
        raise AdapterParseError(MSG_REFUSAL, raw)
    if stop_reason == "max_tokens":
        raise AdapterParseError(MSG_TRUNCATED, raw)
    text = _first_text(response)
    if text is None:
        raise AdapterParseError(MSG_NO_STRUCTURED_OUTPUT, raw)
    position = parse_position(text, raw)
    return MoveResponse(position=position, llm_raw_response=raw, usage=_to_usage(response))


def _first_text(response: Any) -> str | None:
    """thinkingブロック等を飛ばして、最初のtextブロックの本文を返す。"""
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", None)
            if text:
                return text
    return None


def _to_usage(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    if input_tokens is None and output_tokens is None:
        return None
    return {
        "prompt_tokens": int(input_tokens or 0),
        "completion_tokens": int(output_tokens or 0),
    }
