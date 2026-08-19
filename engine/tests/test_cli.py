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


def _write_result_row(data_dir, game_id, *, forfeit_reason):
    data_dir.mkdir(exist_ok=True)
    games_dir = data_dir / "games"
    games_dir.mkdir(exist_ok=True)
    row = {
        "game_id": game_id,
        "black": {"id": "alpha", "provider": "openai", "display_name": "Alpha", "avg_response_time_ms": 1000},
        "white": {"id": "beta", "provider": "anthropic", "display_name": "Beta", "avg_response_time_ms": 2000},
        "winner": "white" if forfeit_reason else "black",
        "reason": "forfeit" if forfeit_reason else "score",
        "forfeit_reason": forfeit_reason,
        "ended_at": "2026-01-01T00:00:00+00:00",
    }
    with (data_dir / "results.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")
    (games_dir / f"{game_id}.json").write_text("{}", encoding="utf-8")


def test_clear_forfeits_removes_only_matching_reason(workspace, capsys):
    data_dir = workspace / "data"
    _write_result_row(data_dir, "g-api-error", forfeit_reason="api_error")
    _write_result_row(data_dir, "g-illegal", forfeit_reason="illegal_move")
    _write_result_row(data_dir, "g-ok", forfeit_reason=None)

    exit_code = main(["clear-forfeits", *_common_args(workspace)])

    assert exit_code == 0
    remaining = {json.loads(line)["game_id"] for line in (data_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()}
    assert remaining == {"g-illegal", "g-ok"}
    assert not (data_dir / "games" / "g-api-error.json").exists()
    assert (data_dir / "games" / "g-illegal.json").exists()
    assert "1局を削除しました" in capsys.readouterr().out


def test_clear_forfeits_dry_run_does_not_delete(workspace, capsys):
    data_dir = workspace / "data"
    _write_result_row(data_dir, "g-api-error", forfeit_reason="api_error")

    exit_code = main(["clear-forfeits", *_common_args(workspace), "--dry-run"])

    assert exit_code == 0
    assert (data_dir / "games" / "g-api-error.json").exists()
    output = capsys.readouterr().out
    assert "dry-run" in output
    assert "未削除" in output


def test_clear_forfeits_accepts_custom_reason(workspace, capsys):
    data_dir = workspace / "data"
    _write_result_row(data_dir, "g-timeout", forfeit_reason="timeout")
    _write_result_row(data_dir, "g-api-error", forfeit_reason="api_error")

    exit_code = main(["clear-forfeits", *_common_args(workspace), "--reason", "timeout"])

    assert exit_code == 0
    remaining = {json.loads(line)["game_id"] for line in (data_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()}
    assert remaining == {"g-api-error"}


def test_clear_forfeits_without_matches_reports_none(workspace, capsys):
    data_dir = workspace / "data"
    _write_result_row(data_dir, "g-ok", forfeit_reason=None)

    exit_code = main(["clear-forfeits", *_common_args(workspace)])

    assert exit_code == 0
    assert "ありません" in capsys.readouterr().out
