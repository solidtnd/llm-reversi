"""集計(ranking.json生成)の単体テスト。docs/shared/metrics.md に対応。"""

from __future__ import annotations

from reversi_engine.aggregate import aggregate
from reversi_engine.config import Points

#: id → (provider, display_name)。結果ログの各行が持つ表示用メタデータ
META = {
    "strong": ("openai", "強いモデル"),
    "weak": ("anthropic", "弱いモデル"),
}


def player(model_id: str, ms: int) -> dict:
    provider, display_name = META.get(model_id, ("openai", model_id))
    return {
        "id": model_id,
        "provider": provider,
        "display_name": display_name,
        "avg_response_time_ms": ms,
    }


def row(
    game_id: str,
    black: str,
    white: str,
    winner: str,
    *,
    reason: str = "score",
    forfeit_reason: str | None = None,
    black_ms: int = 1000,
    white_ms: int = 2000,
):
    return {
        "game_id": game_id,
        "black": player(black, black_ms),
        "white": player(white, white_ms),
        "winner": winner,
        "reason": reason,
        "forfeit_reason": forfeit_reason,
        "ended_at": f"2026-01-01T00:00:0{game_id[-1]}+00:00",
    }


def _model(ranking: dict, model_id: str) -> dict:
    return next(entry for entry in ranking["models"] if entry["id"] == model_id)


def test_aggregate_shape():
    ranking = aggregate([row("g1", "strong", "weak", "black")])
    assert set(ranking) == {"generated_at", "models", "head_to_head", "games"}
    assert set(ranking["models"][0]) == {
        "id",
        "display_name",
        "provider",
        "games",
        "wins",
        "losses",
        "draws",
        "win_rate",
        "win_rate_as_black",
        "win_rate_as_white",
        "forfeit_loss_rate",
        "forfeit_reasons",
        "avg_response_time_ms",
        "points",
        "bt_strength",
    }
    assert set(ranking["head_to_head"][0]) == {"a", "b", "a_wins", "b_wins", "draws", "game_ids"}
    assert set(ranking["games"][0]) == {
        "game_id",
        "black",
        "white",
        "winner",
        "reason",
        "forfeit_reason",
        "ended_at",
    }


def test_model_metrics():
    rows = [
        row("g1", "strong", "weak", "black"),
        row("g2", "weak", "strong", "white"),
        row("g3", "strong", "weak", "draw"),
        row("g4", "weak", "strong", "black", reason="forfeit", forfeit_reason="illegal_move"),
    ]
    ranking = aggregate(rows)

    strong = _model(ranking, "strong")
    assert strong["games"] == 4
    assert (strong["wins"], strong["losses"], strong["draws"]) == (2, 1, 1)
    assert strong["win_rate"] == 0.5
    assert strong["win_rate_as_black"] == 0.5  # g1勝ち / g3引き分け
    assert strong["win_rate_as_white"] == 0.5  # g2勝ち / g4負け
    assert strong["forfeit_loss_rate"] == 0.25
    assert strong["forfeit_reasons"] == {
        "illegal_move": 1,
        "timeout": 0,
        "parse_failure": 0,
        "api_error": 0,
    }
    assert strong["points"] == 2.5  # 2勝 + 引き分け0.5
    assert strong["display_name"] == "強いモデル"
    assert strong["provider"] == "openai"

    weak = _model(ranking, "weak")
    assert (weak["wins"], weak["losses"], weak["draws"]) == (1, 2, 1)
    assert weak["forfeit_reasons"]["illegal_move"] == 0  # 反則したのはstrong側


def test_avg_response_time_is_mean_of_game_averages():
    rows = [
        row("g1", "strong", "weak", "black", black_ms=1000, white_ms=500),
        row("g2", "weak", "strong", "black", black_ms=3000, white_ms=2000),
    ]
    ranking = aggregate(rows)

    assert _model(ranking, "strong")["avg_response_time_ms"] == 1500  # (1000 + 2000) / 2
    assert _model(ranking, "weak")["avg_response_time_ms"] == 1750  # (500 + 3000) / 2


def test_points_use_configured_weights():
    rows = [row("g1", "strong", "weak", "black"), row("g2", "weak", "strong", "draw")]
    ranking = aggregate(rows, points=Points(win=3, draw=1, loss=0))

    assert _model(ranking, "strong")["points"] == 4.0  # 1勝(3) + 引き分け(1)
    assert _model(ranking, "weak")["points"] == 1.0


def test_head_to_head_is_id_ordered_and_color_agnostic():
    rows = [
        row("g1", "strong", "weak", "black"),
        row("g2", "weak", "strong", "black"),
        row("g3", "strong", "weak", "draw"),
    ]
    ranking = aggregate(rows)

    assert len(ranking["head_to_head"]) == 1
    card = ranking["head_to_head"][0]
    assert (card["a"], card["b"]) == ("strong", "weak")  # id昇順
    assert card["a_wins"] == 1  # g1
    assert card["b_wins"] == 1  # g2(weakが黒で勝ち)
    assert card["draws"] == 1
    assert card["game_ids"] == ["g1", "g2", "g3"]


def test_games_are_sorted_by_game_id():
    rows = [row("g2", "strong", "weak", "black"), row("g1", "weak", "strong", "white")]
    ranking = aggregate(rows)
    assert [game["game_id"] for game in ranking["games"]] == ["g1", "g2"]


def test_bt_strength_ranks_stronger_model_higher():
    rows = [
        row(f"g{index}", "strong", "weak", "black")
        for index in range(1, 5)
    ] + [row("g5", "weak", "strong", "white")]
    ranking = aggregate(rows)

    strengths = {entry["id"]: entry["bt_strength"] for entry in ranking["models"]}
    assert strengths["strong"] > strengths["weak"]
    assert abs(sum(strengths.values()) - 1.0) < 1e-6


def test_bt_strength_is_uniform_for_single_model():
    rows = [row("g1", "solo", "solo", "draw")]
    ranking = aggregate(rows)
    assert _model(ranking, "solo")["bt_strength"] == 1.0


def test_bt_strength_handles_undefeated_model():
    """全勝モデルがいても正則化により有限の値に収まる。"""
    rows = [row(f"g{index}", "strong", "weak", "black") for index in range(1, 4)]
    ranking = aggregate(rows)
    for entry in ranking["models"]:
        assert 0.0 < entry["bt_strength"] < 1.0


def test_metadata_comes_from_the_result_rows():
    """models.yamlを渡さなくても、表示名・providerは結果ログの行から埋まる。"""
    ranking = aggregate([row("g1", "strong", "weak", "black")])

    assert _model(ranking, "strong")["display_name"] == "強いモデル"
    assert _model(ranking, "strong")["provider"] == "openai"
    assert _model(ranking, "weak")["display_name"] == "弱いモデル"
    assert _model(ranking, "weak")["provider"] == "anthropic"


def test_renamed_display_name_uses_the_latest_row():
    """同一idでdisplay_nameが変わった場合は後勝ち(最後に対戦した時点の値)。"""
    old = row("g1", "strong", "weak", "black")
    new = row("g2", "strong", "weak", "black")
    new["black"] = {**new["black"], "display_name": "強いモデル(改名後)"}

    ranking = aggregate([old, new])

    assert _model(ranking, "strong")["display_name"] == "強いモデル(改名後)"


def test_rows_without_metadata_fall_back_to_id_and_unknown():
    """provider/display_nameを持たない古い形式の行でも集計対象から落とさない。"""
    legacy = row("g1", "retired", "weak", "black")
    legacy["black"] = {"id": "retired", "avg_response_time_ms": 1000}

    ranking = aggregate([legacy])

    retired = _model(ranking, "retired")
    assert retired["display_name"] == "retired"
    assert retired["provider"] == "unknown"


def test_invalid_rows_are_ignored():
    rows = [
        row("g1", "strong", "weak", "black"),
        {"game_id": "broken"},
        {"black": {"id": "strong"}, "white": {"id": "weak"}, "winner": "black"},  # game_idなし
        "文字列",
    ]
    ranking = aggregate(rows)
    assert [game["game_id"] for game in ranking["games"]] == ["g1"]


def test_empty_results():
    ranking = aggregate([])
    assert ranking["models"] == []
    assert ranking["head_to_head"] == []
    assert ranking["games"] == []
