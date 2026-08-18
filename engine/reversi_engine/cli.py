"""CLIエントリポイント(`run-league` / `aggregate` の2コマンド)。

試合実行と集計実行は別コマンドとする(docs/engine/engine-architecture.md「並列実行」)。
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Sequence

from .aggregate import aggregate
from .config import (
    DEFAULT_ENV_PATH,
    DEFAULT_LEAGUE_PATH,
    DEFAULT_MODELS_PATH,
    ModelSpec,
    build_participants,
    load_env,
    load_league,
    load_models,
)
from .game import GameRecord, Participant
from .league import Card, League
from .storage import DEFAULT_DATA_DIR, Storage


class _PlaceholderAdapter:
    """`--dry-run` 用のダミーAdapter(APIキーなしで実行計画だけ出せるようにする)。"""

    def __init__(self, spec: ModelSpec) -> None:
        self.provider = spec.provider
        self.model = spec.model

    def request_move(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        raise RuntimeError("--dry-run では対局を実行しない")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run-league":
        return _run_league(args)
    if args.command == "aggregate":
        return _run_aggregate(args)
    parser.error(f"未知のコマンド: {args.command}")  # pragma: no cover
    return 2


# ---------------------------------------------------------------------------
# run-league
# ---------------------------------------------------------------------------


def _run_league(args: argparse.Namespace) -> int:
    load_env(args.env)
    specs = load_models(args.models)
    league_config = load_league(args.league)
    storage = Storage(args.data_dir)

    if args.dry_run:
        participants = [
            Participant(
                id=spec.id,
                provider=spec.provider,
                model=spec.model,
                display_name=spec.display_name,
                config=dict(spec.config),
                adapter=_PlaceholderAdapter(spec),  # type: ignore[arg-type]
            )
            for spec in specs
        ]
    else:
        try:
            participants = build_participants(specs)
        except Exception as exc:  # noqa: BLE001 - APIキー未設定等を分かりやすく伝える
            print(
                f"Adapterの初期化に失敗しました({exc})。"
                f"engine/.env にAPIキーを設定してください。",
                file=sys.stderr,
            )
            return 1

    league = League(
        participants,
        storage=storage,
        timeout_seconds=league_config.timeout_seconds,
        concurrent_games=league_config.concurrent_games,
        on_start=_print_start,
        on_complete=_print_complete,
        on_error=_print_error,
    )

    pending, skipped = league.plan()
    print(f"出場モデル: {len(participants)}")
    print(f"実施済みカード: {len(skipped)} / 未実施カード: {len(pending)}")
    if args.dry_run:
        for card in pending:
            print(f"  [未実施] {card}")
        return 0
    if not pending:
        print("未実施カードはありません。")
        return 0

    print(f"同時実行数: {league_config.concurrent_games} / 1手のタイムアウト: {league_config.timeout_seconds}秒")
    result = league.run()
    print(f"完了: {len(result.records)}局 / 失敗: {len(result.failures)}局")
    print(f"棋譜: {storage.games_dir} / 結果ログ: {storage.results_path}")
    if result.failures:
        return 1
    return 0


def _print_start(card: Card) -> None:
    print(f"  開始: {card}")


def _print_complete(card: Card, record: GameRecord) -> None:
    result = record.result
    detail = f"{result.winner}の勝ち({result.reason})"
    if result.reason == "forfeit" and record.moves:
        detail += f" 理由={record.moves[-1].forfeit_reason}"
    print(f"  完了: {card} -> {detail} [{record.game_id}]")


def _print_error(card: Card, exc: BaseException) -> None:
    print(f"  失敗: {card} -> {type(exc).__name__}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------


def _run_aggregate(args: argparse.Namespace) -> int:
    storage = Storage(args.data_dir)
    results = storage.read_results()
    if not results:
        print(f"{storage.results_path} に対局結果がありません。", file=sys.stderr)
        return 1

    # models.yamlは参照しない(表示名も結果ログ側が持つ。docs/shared/metrics.md参照)
    league_config = load_league(args.league)
    ranking = aggregate(results, points=league_config.points)
    path = storage.write_ranking(ranking)
    print(f"{len(results)}局を集計し {len(ranking['models'])}モデル分を書き出しました: {path}")
    return 0


# ---------------------------------------------------------------------------
# パーサ
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reversi-engine",
        description="複数のLLMにリバーシを対戦させる対戦エンジン",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_league = subparsers.add_parser("run-league", help="未実施カードの対局を実行する")
    _add_common_arguments(run_league)
    run_league.add_argument(
        "--models",
        default=str(DEFAULT_MODELS_PATH),
        help="モデル一覧YAMLのパス(既定: engine/models.yaml)",
    )
    run_league.add_argument(
        "--env",
        default=str(DEFAULT_ENV_PATH),
        help="APIキーを読み込む.envのパス(既定: engine/.env)",
    )
    run_league.add_argument(
        "--dry-run",
        action="store_true",
        help="対局は行わず、実行予定のカードだけを表示する",
    )

    aggregate_parser = subparsers.add_parser("aggregate", help="results.jsonlからranking.jsonを生成する")
    _add_common_arguments(aggregate_parser)

    return parser


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--league",
        default=str(DEFAULT_LEAGUE_PATH),
        help="リーグ設定YAMLのパス(既定: engine/league.yaml)",
    )
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="データ受け渡しディレクトリ(既定: リポジトリ直下のdata/)",
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
