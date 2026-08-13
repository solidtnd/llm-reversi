"""`data/results.jsonl` → `data/ranking.json` の集計。

指標の定義は docs/shared/metrics.md、入力の行スキーマは
docs/shared/log-schema.md「対局結果ログ」に対応する。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .config import ModelSpec, Points
from .game import utc_now_iso

FORFEIT_REASONS = ("illegal_move", "timeout", "parse_failure", "api_error")

#: Bradley-Terry推定の正則化項。全勝/全敗のモデルがいても発散させないための小さな値。
BT_ALPHA = 0.01


@dataclass
class _ModelStats:
    id: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    games_as_black: int = 0
    wins_as_black: int = 0
    games_as_white: int = 0
    wins_as_white: int = 0
    forfeit_losses: int = 0
    forfeit_reasons: dict[str, int] = field(
        default_factory=lambda: {reason: 0 for reason in FORFEIT_REASONS}
    )
    response_times: list[float] = field(default_factory=list)


def aggregate(
    results: Iterable[dict[str, Any]],
    *,
    models: Sequence[ModelSpec] = (),
    points: Points | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """結果ログから `ranking.json` の内容を組み立てる(全量再生成)。

    `display_name` / `provider` は結果ログに含まれないため `models.yaml`
    (= `models` 引数)から補う。ログにしか存在しないモデル(設定から削除された等)は
    `display_name` に id を、`provider` に `"unknown"` を入れる。
    """
    weights = points or Points()
    rows = [row for row in results if _is_valid_row(row)]

    stats: dict[str, _ModelStats] = {}
    head_to_head: dict[tuple[str, str], dict[str, Any]] = {}
    games: list[dict[str, Any]] = []

    for row in rows:
        black_id = row["black"]["id"]
        white_id = row["white"]["id"]
        winner = row["winner"]
        reason = row.get("reason")
        forfeit_reason = row.get("forfeit_reason")

        black = stats.setdefault(black_id, _ModelStats(id=black_id))
        white = stats.setdefault(white_id, _ModelStats(id=white_id))

        black.games += 1
        white.games += 1
        black.games_as_black += 1
        white.games_as_white += 1
        _add_response_time(black, row["black"].get("avg_response_time_ms"))
        _add_response_time(white, row["white"].get("avg_response_time_ms"))

        if winner == "black":
            black.wins += 1
            black.wins_as_black += 1
            white.losses += 1
            loser = white
        elif winner == "white":
            white.wins += 1
            white.wins_as_white += 1
            black.losses += 1
            loser = black
        else:
            black.draws += 1
            white.draws += 1
            loser = None

        if reason == "forfeit" and loser is not None:
            loser.forfeit_losses += 1
            if forfeit_reason in loser.forfeit_reasons:
                loser.forfeit_reasons[forfeit_reason] += 1

        _accumulate_head_to_head(head_to_head, row)
        games.append(
            {
                "game_id": row["game_id"],
                "black": black_id,
                "white": white_id,
                "winner": winner,
                "reason": reason,
                "forfeit_reason": forfeit_reason,
                "ended_at": row.get("ended_at"),
            }
        )

    metadata = {spec.id: spec for spec in models}
    model_ids = sorted(stats)
    strengths = _bradley_terry_strengths(model_ids, rows)

    model_entries = []
    for model_id in model_ids:
        entry = stats[model_id]
        spec = metadata.get(model_id)
        model_entries.append(
            {
                "id": model_id,
                "display_name": spec.display_name if spec else model_id,
                "provider": spec.provider if spec else "unknown",
                "games": entry.games,
                "wins": entry.wins,
                "losses": entry.losses,
                "draws": entry.draws,
                "win_rate": _ratio(entry.wins, entry.games),
                "win_rate_as_black": _ratio(entry.wins_as_black, entry.games_as_black),
                "win_rate_as_white": _ratio(entry.wins_as_white, entry.games_as_white),
                "forfeit_loss_rate": _ratio(entry.forfeit_losses, entry.games),
                "forfeit_reasons": dict(entry.forfeit_reasons),
                "avg_response_time_ms": _average(entry.response_times),
                "points": round(
                    entry.wins * weights.win
                    + entry.draws * weights.draw
                    + entry.losses * weights.loss,
                    3,
                ),
                "bt_strength": strengths[model_id],
            }
        )

    return {
        "generated_at": generated_at or utc_now_iso(),
        "models": model_entries,
        "head_to_head": [
            head_to_head[key] for key in sorted(head_to_head, key=lambda pair: pair)
        ],
        "games": sorted(games, key=lambda game: game["game_id"]),
    }


# ---------------------------------------------------------------------------
# 内部処理
# ---------------------------------------------------------------------------


def _is_valid_row(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    black = row.get("black")
    white = row.get("white")
    return (
        isinstance(row.get("game_id"), str)
        and isinstance(black, dict)
        and isinstance(white, dict)
        and isinstance(black.get("id"), str)
        and isinstance(white.get("id"), str)
        and row.get("winner") in ("black", "white", "draw")
    )


def _add_response_time(stats: _ModelStats, value: Any) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        stats.response_times.append(float(value))


def _accumulate_head_to_head(
    table: dict[tuple[str, str], dict[str, Any]],
    row: dict[str, Any],
) -> None:
    black_id = row["black"]["id"]
    white_id = row["white"]["id"]
    if black_id == white_id:
        return
    a, b = sorted((black_id, white_id))
    entry = table.setdefault(
        (a, b),
        {"a": a, "b": b, "a_wins": 0, "b_wins": 0, "draws": 0, "game_ids": []},
    )
    winner = row["winner"]
    if winner == "draw":
        entry["draws"] += 1
    else:
        winner_id = black_id if winner == "black" else white_id
        entry["a_wins" if winner_id == a else "b_wins"] += 1
    entry["game_ids"].append(row["game_id"])


def _bradley_terry_strengths(
    model_ids: Sequence[str],
    rows: Sequence[dict[str, Any]],
) -> dict[str, float]:
    """Bradley-Terryモデルで強さを推定し、合計1になるよう正規化して返す。

    引き分けは両者に半勝ちを1回ずつ与える(`(a, b)`と`(b, a)`を1件ずつ追加する)。
    反則負けも通常の負けと同じ1勝1敗として扱う。
    """
    count = len(model_ids)
    if count == 0:
        return {}
    uniform = {model_id: 1.0 / count for model_id in model_ids}
    if count < 2:
        return uniform

    index_of = {model_id: index for index, model_id in enumerate(model_ids)}
    data: list[tuple[int, int]] = []
    for row in rows:
        black_id = row["black"]["id"]
        white_id = row["white"]["id"]
        if black_id == white_id:
            continue
        black_index = index_of[black_id]
        white_index = index_of[white_id]
        winner = row["winner"]
        if winner == "black":
            data.append((black_index, white_index))
        elif winner == "white":
            data.append((white_index, black_index))
        else:
            data.append((black_index, white_index))
            data.append((white_index, black_index))
    if not data:
        return uniform

    import choix

    try:
        params = choix.ilsr_pairwise(count, data, alpha=BT_ALPHA)
    except Exception:  # noqa: BLE001 - 推定が収束しない場合は一律の値にフォールバックする
        return uniform

    weights = [math.exp(float(value)) for value in params]
    total = sum(weights)
    if total <= 0 or not math.isfinite(total):
        return uniform
    return {
        model_id: round(weights[index_of[model_id]] / total, 6) for model_id in model_ids
    }


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _average(values: Sequence[float]) -> int:
    if not values:
        return 0
    return round(sum(values) / len(values))
