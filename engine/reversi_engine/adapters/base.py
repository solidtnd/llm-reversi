"""Adapter共通のインターフェース・例外・プロンプト整形。

docs/engine/adapter-interface.md に対応する。プロンプトテンプレートと例外メッセージは
全プロバイダで共通(実験の再現性・公平性のため)なので、ここに1箇所だけ持つ。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from ..board import BoardState, Player, format_grid

# ---------------------------------------------------------------------------
# 出力(MoveResponse)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MoveResponse:
    """Adapterの戻り値。docs/engine/adapter-interface.md「入出力」に対応。"""

    position: str
    llm_raw_response: str
    usage: dict[str, int] | None = None


@runtime_checkable
class LLMAdapter(Protocol):
    """1手の着手をLLMに問い合わせるインターフェース。

    タイムアウト・リトライ・合法手検証は呼び出し元(engine側)が制御する。
    """

    provider: str
    model: str

    def request_move(
        self,
        board: BoardState,
        legal_moves: list[str],
        player: Player,
        retry_reason: str | None = None,
    ) -> MoveResponse: ...


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class AdapterError(Exception):
    """Adapterが送出する例外の基底。"""


class AdapterParseError(AdapterError):
    """レスポンスは受信できたが、構造化出力としてパースできなかった。

    `message` はリトライ時に `request_move(retry_reason=...)` へそのまま渡され、
    モデルへのフィードバックに使われる。
    """

    def __init__(self, message: str, llm_raw_response: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.llm_raw_response = llm_raw_response


class AdapterAPIError(AdapterError):
    """APIへのリクエスト自体が失敗した(レート制限・5xx・ネットワーク等)。"""

    def __init__(self, message: str, original_exception: BaseException | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception


# ---------------------------------------------------------------------------
# 例外メッセージ(docs/engine/adapter-interface.md「message文言」に対応)
# ---------------------------------------------------------------------------

MSG_REFUSAL = "モデルが応答を拒否しました"
MSG_NO_STRUCTURED_OUTPUT = "応答に有効な構造化出力が含まれていませんでした"
MSG_TRUNCATED = "応答が途中で切断され、有効なJSONになりませんでした"
MSG_FORMAT_MISMATCH = "応答が期待する形式(`position`を含むJSON)と一致しませんでした"

MSG_RATE_LIMIT = "レート制限に達しました"
MSG_SERVER_ERROR = "APIサーバーエラーが発生しました(HTTP {status})"
MSG_NETWORK_ERROR = "ネットワークエラーが発生しました"


def unexpected_api_error_message(exc: BaseException) -> str:
    """想定外のSDK例外に対する `AdapterAPIError.message`。"""
    return f"{type(exc).__name__}: {exc}"


def api_error_from_status(exc: BaseException, status: int | None) -> AdapterAPIError:
    """HTTPステータスから `AdapterAPIError` を組み立てる。

    レート制限(429)・サーバーエラー(5xx)は専用の文言を使い、それ以外の
    ステータス(4xx等)は想定外扱いでSDK例外のクラス名とメッセージを残す。
    """
    if status == 429:
        return AdapterAPIError(MSG_RATE_LIMIT, exc)
    if status is not None and status >= 500:
        return AdapterAPIError(MSG_SERVER_ERROR.format(status=status), exc)
    return AdapterAPIError(unexpected_api_error_message(exc), exc)


# ---------------------------------------------------------------------------
# 構造化出力スキーマ
# ---------------------------------------------------------------------------

MOVE_SCHEMA_NAME = "reversi_move"

MOVE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"position": {"type": "string"}},
    "required": ["position"],
    "additionalProperties": False,
}


def parse_position(text: str | None, llm_raw_response: str) -> str:
    """構造化出力のJSON文字列から `position` を取り出す。

    JSONとして読めない/`position` が文字列で入っていない場合は
    `AdapterParseError` を送出する。
    """
    if text is None or not text.strip():
        raise AdapterParseError(MSG_NO_STRUCTURED_OUTPUT, llm_raw_response)
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        raise AdapterParseError(MSG_FORMAT_MISMATCH, llm_raw_response) from None
    if not isinstance(payload, dict):
        raise AdapterParseError(MSG_FORMAT_MISMATCH, llm_raw_response)
    position = payload.get("position")
    if not isinstance(position, str) or not position.strip():
        raise AdapterParseError(MSG_FORMAT_MISMATCH, llm_raw_response)
    return position.strip()


def serialize_response(response: Any) -> str:
    """APIレスポンス全体をログ用のJSON文字列にする。

    thinkingの思考過程を含むレスポンス全体を残す方針
    (docs/engine/adapter-interface.md「入出力」)のため、SDKのレスポンスオブジェクトを
    まるごとシリアライズする。dumpに対応しないオブジェクト(テスト用のダミー等)は
    `str()` にフォールバックする。
    """
    dump = getattr(response, "model_dump_json", None)
    if callable(dump):
        try:
            return dump()
        except Exception:  # noqa: BLE001 - ログ用途なので失敗しても続行する
            pass
    return str(response)


# ---------------------------------------------------------------------------
# プロンプト
# ---------------------------------------------------------------------------

_COLOR_LABELS: dict[str, str] = {"black": "黒", "white": "白"}

_PROMPT_TEMPLATE = """あなたはリバーシ(オセロ)の対局者です。あなたは{color}です。

## 盤面
現在の盤面は以下の通りです(列はa-h、行は1-8)。
"."は空きマス、"b"は黒石、"w"は白石を表します。

{grid}

## 合法手
あなたが打てる合法手は以下の通りです: {legal_moves}
{retry_section}
## 指示
上記の合法手の中から1つを選び、着手位置を指定してください。
"""

_RETRY_TEMPLATE = """
## 前回の応答について
前回の応答は次の理由により受け付けられませんでした: {retry_reason}
上記の合法手の中から、有効な形式で選び直してください。
"""


def build_prompt(
    board: BoardState,
    legal_moves: list[str],
    player: Player,
    retry_reason: str | None = None,
) -> str:
    """全プロバイダ共通のプロンプトを組み立てる。"""
    retry_section = (
        _RETRY_TEMPLATE.format(retry_reason=retry_reason) if retry_reason else ""
    )
    return _PROMPT_TEMPLATE.format(
        color=_COLOR_LABELS.get(player, player),
        grid=format_grid(board),
        legal_moves=", ".join(legal_moves),
        retry_section=retry_section,
    )


Provider = Literal["openai", "anthropic", "gemini"]
