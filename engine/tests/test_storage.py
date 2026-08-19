"""`data/`の読み書きの単体テスト。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from fakes import FakeAdapter, participant
from reversi_engine.game import Game
from reversi_engine.storage import Storage


def _record(game_id: str):
    return Game(
        participant("black-model", FakeAdapter(random_seed=1)),
        participant("white-model", FakeAdapter(random_seed=2)),
        timeout_seconds=5,
        game_id=game_id,
    ).play()


def test_read_results_on_missing_file(tmp_path):
    assert Storage(tmp_path).read_results() == []


def test_record_game_writes_json_and_jsonl(tmp_path):
    storage = Storage(tmp_path)
    record = _record("20260101T000000000000-aaaaaa")

    path = storage.record_game(record)

    assert path == tmp_path / "games" / "20260101T000000000000-aaaaaa.json"
    assert json.loads(path.read_text(encoding="utf-8")) == record.to_dict()
    assert storage.read_results() == [record.summary()]


def test_append_result_is_thread_safe(tmp_path):
    storage = Storage(tmp_path)
    rows = [{"game_id": f"g{index}", "value": index} for index in range(50)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(storage.append_result, rows))

    saved = storage.read_results()
    assert len(saved) == 50
    assert {row["game_id"] for row in saved} == {row["game_id"] for row in rows}


def test_read_results_reports_broken_line(tmp_path):
    storage = Storage(tmp_path)
    storage.append_result({"game_id": "g1"})
    with storage.results_path.open("a", encoding="utf-8") as stream:
        stream.write("これはJSONではない\n")

    with pytest.raises(ValueError, match="2 行目"):
        storage.read_results()


def test_read_results_skips_blank_lines(tmp_path):
    storage = Storage(tmp_path)
    storage.results_path.parent.mkdir(parents=True, exist_ok=True)
    storage.results_path.write_text('\n{"game_id": "g1"}\n\n', encoding="utf-8")
    assert storage.read_results() == [{"game_id": "g1"}]


def test_remove_games_deletes_from_results_and_games_dir(tmp_path):
    storage = Storage(tmp_path)
    kept = _record("20260101T000000000000-aaaaaa")
    removed = _record("20260101T000000000001-bbbbbb")
    storage.record_game(kept)
    storage.record_game(removed)

    storage.remove_games([removed.game_id])

    assert not (tmp_path / "games" / f"{removed.game_id}.json").exists()
    assert (tmp_path / "games" / f"{kept.game_id}.json").exists()
    assert [row["game_id"] for row in storage.read_results()] == [kept.game_id]


def test_remove_games_with_missing_game_file_does_not_raise(tmp_path):
    storage = Storage(tmp_path)
    storage.append_result({"game_id": "g1"})

    storage.remove_games(["g1"])  # data/games/g1.json は存在しない

    assert storage.read_results() == []


def test_remove_games_with_empty_iterable_is_noop(tmp_path):
    storage = Storage(tmp_path)
    storage.append_result({"game_id": "g1"})

    storage.remove_games([])

    assert [row["game_id"] for row in storage.read_results()] == ["g1"]


def test_write_ranking(tmp_path):
    storage = Storage(tmp_path)
    ranking = {"generated_at": "2026-01-01T00:00:00+00:00", "models": [], "games": []}

    path = storage.write_ranking(ranking)

    assert path == tmp_path / "ranking.json"
    assert json.loads(path.read_text(encoding="utf-8")) == ranking
