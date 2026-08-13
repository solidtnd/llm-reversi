"""`models.yaml` / `league.yaml` の読み込みとAdapterの組み立て。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from .adapters.base import LLMAdapter
from .game import DEFAULT_TIMEOUT_SECONDS, Participant

ENGINE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODELS_PATH = ENGINE_DIR / "models.yaml"
DEFAULT_LEAGUE_PATH = ENGINE_DIR / "league.yaml"
DEFAULT_ENV_PATH = ENGINE_DIR / ".env"

SUPPORTED_PROVIDERS = ("openai", "anthropic", "gemini")


@dataclass(frozen=True)
class ModelSpec:
    """`models.yaml` の1エントリ。"""

    id: str
    provider: str
    model: str
    display_name: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Points:
    """勝点方式の重み。"""

    win: float = 1.0
    draw: float = 0.5
    loss: float = 0.0


@dataclass(frozen=True)
class LeagueConfig:
    """`league.yaml` の内容。"""

    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    concurrent_games: int = 4
    points: Points = field(default_factory=Points)


# ---------------------------------------------------------------------------
# 読み込み
# ---------------------------------------------------------------------------


def load_models(path: Path | str = DEFAULT_MODELS_PATH) -> list[ModelSpec]:
    """`models.yaml` を読み込んでモデル一覧を返す。"""
    payload = _load_yaml(path)
    entries = payload.get("models")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{path}: `models` に1件以上のモデルを記述する必要がある")

    specs: list[ModelSpec] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: models[{index}] がマッピングではない")
        spec = ModelSpec(
            id=_require_str(entry, "id", path, index),
            provider=_require_str(entry, "provider", path, index),
            model=_require_str(entry, "model", path, index),
            display_name=_require_str(entry, "display_name", path, index),
            config=dict(entry.get("config") or {}),
        )
        if spec.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"{path}: models[{index}] の provider が未対応: {spec.provider!r} "
                f"(対応: {', '.join(SUPPORTED_PROVIDERS)})"
            )
        if spec.id in seen:
            raise ValueError(f"{path}: id が重複している: {spec.id!r}")
        seen.add(spec.id)
        specs.append(spec)
    return specs


def load_league(path: Path | str = DEFAULT_LEAGUE_PATH) -> LeagueConfig:
    """`league.yaml` を読み込んでリーグ運営パラメータを返す。"""
    payload = _load_yaml(path)
    points_payload = payload.get("points") or {}
    if not isinstance(points_payload, dict):
        raise ValueError(f"{path}: `points` がマッピングではない")
    defaults = Points()
    points = Points(
        win=float(points_payload.get("win", defaults.win)),
        draw=float(points_payload.get("draw", defaults.draw)),
        loss=float(points_payload.get("loss", defaults.loss)),
    )
    config = LeagueConfig(
        timeout_seconds=float(payload.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
        concurrent_games=int(payload.get("concurrent_games", 4)),
        points=points,
    )
    if config.timeout_seconds <= 0:
        raise ValueError(f"{path}: timeout_seconds は正の数である必要がある")
    if config.concurrent_games < 1:
        raise ValueError(f"{path}: concurrent_games は1以上である必要がある")
    return config


def load_env(path: Path | str = DEFAULT_ENV_PATH) -> None:
    """`engine/.env` からAPIキーを読み込む(存在しなければ何もしない)。"""
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(path), override=False)


# ---------------------------------------------------------------------------
# Adapterの組み立て
# ---------------------------------------------------------------------------


def _build_openai(spec: ModelSpec) -> LLMAdapter:
    from .adapters.openai import OpenAIAdapter

    return OpenAIAdapter(spec.model, spec.config)


def _build_anthropic(spec: ModelSpec) -> LLMAdapter:
    from .adapters.anthropic import AnthropicAdapter

    return AnthropicAdapter(spec.model, spec.config)


def _build_gemini(spec: ModelSpec) -> LLMAdapter:
    from .adapters.gemini import GeminiAdapter

    return GeminiAdapter(spec.model, spec.config)


#: provider名 → Adapter生成関数。SDKの読み込みを遅延させるため関数越しに解決する。
ADAPTER_FACTORIES: dict[str, Callable[[ModelSpec], LLMAdapter]] = {
    "openai": _build_openai,
    "anthropic": _build_anthropic,
    "gemini": _build_gemini,
}


def build_adapter(spec: ModelSpec) -> LLMAdapter:
    """`models.yaml` の1エントリからAdapterを組み立てる。"""
    try:
        factory = ADAPTER_FACTORIES[spec.provider]
    except KeyError:
        raise ValueError(f"未対応のprovider: {spec.provider!r}") from None
    return factory(spec)


def build_participant(spec: ModelSpec) -> Participant:
    """`models.yaml` の1エントリを対局参加者に変換する。"""
    return Participant(
        id=spec.id,
        provider=spec.provider,
        model=spec.model,
        display_name=spec.display_name,
        config=dict(spec.config),
        adapter=build_adapter(spec),
    )


def build_participants(specs: list[ModelSpec]) -> list[Participant]:
    return [build_participant(spec) for spec in specs]


# ---------------------------------------------------------------------------
# 内部ヘルパ
# ---------------------------------------------------------------------------


def _load_yaml(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"設定ファイルが見つからない: {target}")
    with target.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"{target}: トップレベルがマッピングではない")
    return payload


def _require_str(entry: dict[str, Any], key: str, path: Path | str, index: int) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: models[{index}] の {key} が未設定または文字列ではない")
    return value
