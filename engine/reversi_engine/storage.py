"""`data/`への棋譜JSON書き出し・JSONL追記(スレッドセーフ)。"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .game import GameRecord

#: リポジトリ直下の`data/`(engine/reversi_engine/storage.py から2階層上)
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class Storage:
    """`data/`配下の読み書きをまとめる。

    `results.jsonl`への追記は複数スレッドから発生するためロックで直列化する
    (docs/engine/engine-architecture.md「並列実行」)。
    """

    def __init__(self, data_dir: Path | str = DEFAULT_DATA_DIR) -> None:
        self.data_dir = Path(data_dir)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    @property
    def games_dir(self) -> Path:
        return self.data_dir / "games"

    @property
    def results_path(self) -> Path:
        return self.data_dir / "results.jsonl"

    @property
    def ranking_path(self) -> Path:
        return self.data_dir / "ranking.json"

    # ------------------------------------------------------------------
    def write_game(self, record: GameRecord) -> Path:
        """棋譜JSONを `data/games/<game_id>.json` に書き出す。"""
        self.games_dir.mkdir(parents=True, exist_ok=True)
        path = self.games_dir / f"{record.game_id}.json"
        _write_json(path, record.to_dict())
        return path

    def append_result(self, summary: dict[str, Any]) -> None:
        """対局結果の要約を `data/results.jsonl` へ1行追記する。"""
        line = json.dumps(summary, ensure_ascii=False)
        with self._lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with self.results_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(line + "\n")
                stream.flush()

    def record_game(self, record: GameRecord) -> Path:
        """棋譜本体と結果ログの書き出しをまとめて行う。"""
        path = self.write_game(record)
        self.append_result(record.summary())
        return path

    def read_results(self) -> list[dict[str, Any]]:
        """`data/results.jsonl` を読み込む(未作成なら空リスト)。"""
        if not self.results_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.results_path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    rows.append(json.loads(text))
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"{self.results_path} の {number} 行目がJSONとして読めない: {exc}"
                    ) from exc
        return rows

    def read_game(self, game_id: str) -> dict[str, Any]:
        """棋譜JSONを読み込む。"""
        path = self.games_dir / f"{game_id}.json"
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)

    def write_ranking(self, ranking: dict[str, Any]) -> Path:
        """集計結果を `data/ranking.json` に書き出す(全量再生成)。"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        _write_json(self.ranking_path, ranking)
        return self.ranking_path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
