"""CLI(run-league / aggregate)の単体テスト。実APIは呼ばない。"""

from __future__ import annotations

import json
import textwrap

import pytest

from reversi_engine.cli import main

MODELS_YAML = textwrap.dedent(
    """
    models:
      - {id: alpha, provider: openai, model: gpt-4o, display_name: Alpha}
      - {id: beta, provider: anthropic, model: claude-opus-5, display_name: Beta}
    """
)

LEAGUE_YAML = "timeout_seconds: 5\nconcurrent_games: 2\n"


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "models.yaml").write_text(MODELS_YAML, encoding="utf-8")
    (tmp_path / "league.yaml").write_text(LEAGUE_YAML, encoding="utf-8")
    return tmp_path


def _common_args(workspace):
    return [
        "--league",
        str(workspace / "league.yaml"),
        "--data-dir",
        str(workspace / "data"),
    ]


def test_run_league_dry_run_lists_cards(workspace, capsys):
    exit_code = main(
        [
            "run-league",
            *_common_args(workspace),
            "--models",
            str(workspace / "models.yaml"),
            "--env",
            str(workspace / ".env"),
            "--dry-run",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "出場モデル: 2" in output
    assert output.count("[未実施]") == 2  # 先手後手を入れ替えた2局
    assert not (workspace / "data").exists()  # 対局は行わない


def _write_results(data_dir):
    data_dir.mkdir(exist_ok=True)
    row = {
        "game_id": "g1",
        "black": {
            "id": "alpha",
            "provider": "openai",
            "display_name": "Alpha",
            "avg_response_time_ms": 1000,
        },
        "white": {
            "id": "beta",
            "provider": "anthropic",
            "display_name": "Beta",
            "avg_response_time_ms": 2000,
        },
        "winner": "black",
        "reason": "score",
        "forfeit_reason": None,
        "ended_at": "2026-01-01T00:00:00+00:00",
    }
    (data_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_aggregate_writes_ranking(workspace, capsys):
    data_dir = workspace / "data"
    _write_results(data_dir)

    exit_code = main(["aggregate", *_common_args(workspace)])

    assert exit_code == 0
    ranking = json.loads((data_dir / "ranking.json").read_text(encoding="utf-8"))
    assert {entry["id"] for entry in ranking["models"]} == {"alpha", "beta"}
    assert {entry["display_name"] for entry in ranking["models"]} == {"Alpha", "Beta"}
    assert "1局を集計" in capsys.readouterr().out


def test_aggregate_does_not_need_models_yaml(workspace):
    """集計はmodels.yamlを参照しない(削除したモデルの過去対局も表示名を保つ)。"""
    data_dir = workspace / "data"
    _write_results(data_dir)
    (workspace / "models.yaml").unlink()

    exit_code = main(["aggregate", *_common_args(workspace)])

    assert exit_code == 0
    ranking = json.loads((data_dir / "ranking.json").read_text(encoding="utf-8"))
    assert {entry["display_name"] for entry in ranking["models"]} == {"Alpha", "Beta"}
    assert {entry["provider"] for entry in ranking["models"]} == {"openai", "anthropic"}


def test_aggregate_without_results_fails(workspace, capsys):
    exit_code = main(["aggregate", *_common_args(workspace)])
    assert exit_code == 1
    assert "対局結果がありません" in capsys.readouterr().err


def test_unknown_command_is_rejected(workspace):
    with pytest.raises(SystemExit):
        main(["no-such-command"])
