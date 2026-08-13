"""設定ファイル読み込みの単体テスト。"""

from __future__ import annotations

import textwrap

import pytest

from reversi_engine.config import (
    DEFAULT_LEAGUE_PATH,
    DEFAULT_MODELS_PATH,
    Points,
    load_league,
    load_models,
)


def _write(tmp_path, name: str, text: str):
    path = tmp_path / name
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def test_repository_models_yaml_is_valid():
    specs = load_models(DEFAULT_MODELS_PATH)
    assert specs
    assert len({spec.id for spec in specs}) == len(specs)


def test_repository_league_yaml_matches_rules_defaults():
    config = load_league(DEFAULT_LEAGUE_PATH)
    assert config.timeout_seconds == 30
    assert config.concurrent_games == 4
    assert config.points == Points(win=1.0, draw=0.5, loss=0.0)


def test_load_models_reads_entries(tmp_path):
    path = _write(
        tmp_path,
        "models.yaml",
        """
        models:
          - id: gpt-4o
            provider: openai
            model: gpt-4o
            display_name: "GPT-4o"
            config: {}
          - id: claude-thinking
            provider: anthropic
            model: claude-opus-5
            display_name: "Claude Opus 5 (Thinkあり)"
            config:
              thinking: true
        """,
    )

    specs = load_models(path)

    assert [spec.id for spec in specs] == ["gpt-4o", "claude-thinking"]
    assert specs[1].config == {"thinking": True}
    assert specs[1].model == "claude-opus-5"


def test_load_models_rejects_duplicate_id(tmp_path):
    path = _write(
        tmp_path,
        "models.yaml",
        """
        models:
          - {id: same, provider: openai, model: gpt-4o, display_name: A}
          - {id: same, provider: openai, model: gpt-4o-mini, display_name: B}
        """,
    )
    with pytest.raises(ValueError, match="重複"):
        load_models(path)


def test_load_models_rejects_unknown_provider(tmp_path):
    path = _write(
        tmp_path,
        "models.yaml",
        """
        models:
          - {id: x, provider: cohere, model: command, display_name: X}
        """,
    )
    with pytest.raises(ValueError, match="provider"):
        load_models(path)


def test_load_models_rejects_missing_field(tmp_path):
    path = _write(
        tmp_path,
        "models.yaml",
        """
        models:
          - {id: x, provider: openai, model: gpt-4o}
        """,
    )
    with pytest.raises(ValueError, match="display_name"):
        load_models(path)


def test_load_models_rejects_empty_list(tmp_path):
    path = _write(tmp_path, "models.yaml", "models: []\n")
    with pytest.raises(ValueError, match="models"):
        load_models(path)


def test_load_models_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_models(tmp_path / "missing.yaml")


def test_load_league_uses_defaults_for_missing_keys(tmp_path):
    path = _write(tmp_path, "league.yaml", "timeout_seconds: 10\n")
    config = load_league(path)

    assert config.timeout_seconds == 10
    assert config.concurrent_games == 4
    assert config.points == Points()


def test_load_league_reads_points(tmp_path):
    path = _write(
        tmp_path,
        "league.yaml",
        """
        timeout_seconds: 5
        concurrent_games: 2
        points:
          win: 3
          draw: 1
          loss: 0
        """,
    )
    config = load_league(path)

    assert config.concurrent_games == 2
    assert config.points == Points(win=3.0, draw=1.0, loss=0.0)


@pytest.mark.parametrize("body", ["timeout_seconds: 0\n", "concurrent_games: 0\n"])
def test_load_league_rejects_invalid_values(tmp_path, body):
    path = _write(tmp_path, "league.yaml", body)
    with pytest.raises(ValueError):
        load_league(path)
