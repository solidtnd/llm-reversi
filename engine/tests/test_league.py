"""総当たり組み合わせ・差分実行・並列実行の単体テスト。"""

from __future__ import annotations

import pytest

from fakes import FakeAdapter, participant, random_participant
from reversi_engine.league import Card, League, build_cards, pending_cards, played_card_keys
from reversi_engine.storage import Storage


def _participants(count: int):
    return [random_participant(f"model-{index}", seed=index) for index in range(count)]


# ---------------------------------------------------------------------------
# カード生成
# ---------------------------------------------------------------------------


def test_build_cards_covers_both_orientations():
    cards = build_cards(_participants(3))
    keys = [card.key for card in cards]

    assert len(cards) == 6  # 3C2 * 2局
    assert keys == [
        ("model-0", "model-1"),
        ("model-1", "model-0"),
        ("model-0", "model-2"),
        ("model-2", "model-0"),
        ("model-1", "model-2"),
        ("model-2", "model-1"),
    ]


def test_build_cards_with_single_participant_is_empty():
    assert build_cards(_participants(1)) == []


def test_played_card_keys_reads_black_and_white_ids():
    rows = [
        {"black": {"id": "a"}, "white": {"id": "b"}},
        {"black": {"id": "b"}, "white": {"id": "a"}},
        {"broken": True},
    ]
    assert played_card_keys(rows) == {("a", "b"), ("b", "a")}


def test_pending_cards_skips_played_orientations():
    participants = _participants(2)
    results = [{"black": {"id": "model-0"}, "white": {"id": "model-1"}}]

    pending, skipped = pending_cards(participants, results)

    assert [card.key for card in skipped] == [("model-0", "model-1")]
    assert [card.key for card in pending] == [("model-1", "model-0")]


def test_pending_cards_only_runs_new_model_cards():
    """A/B/Cが総当たり済みの状態でDを追加したら、Dが絡むカードだけ実行する。"""
    participants = [random_participant(name, seed=index) for index, name in enumerate("ABCD")]
    played = [
        {"black": {"id": black}, "white": {"id": white}}
        for black, white in [
            ("A", "B"),
            ("B", "A"),
            ("A", "C"),
            ("C", "A"),
            ("B", "C"),
            ("C", "B"),
        ]
    ]

    pending, skipped = pending_cards(participants, played)

    assert len(skipped) == 6
    assert {card.key for card in pending} == {
        ("A", "D"),
        ("D", "A"),
        ("B", "D"),
        ("D", "B"),
        ("C", "D"),
        ("D", "C"),
    }


# ---------------------------------------------------------------------------
# 実行
# ---------------------------------------------------------------------------


def test_league_run_writes_games_and_results(tmp_path):
    storage = Storage(tmp_path)
    league = League(
        _participants(3),
        storage=storage,
        timeout_seconds=5,
        concurrent_games=2,
    )

    result = league.run()

    assert len(result.records) == 6
    assert result.failures == []
    assert len({record.game_id for record in result.records}) == 6
    assert len(list(storage.games_dir.glob("*.json"))) == 6
    rows = storage.read_results()
    assert len(rows) == 6
    assert {(row["black"]["id"], row["white"]["id"]) for row in rows} == {
        card.key for card in build_cards(_participants(3))
    }
    # 棋譜JSONは1対局1ファイルで、そのまま読み込める
    saved = storage.read_game(result.records[0].game_id)
    assert saved["game_id"] == result.records[0].game_id


def test_league_run_is_incremental(tmp_path):
    storage = Storage(tmp_path)
    participants = _participants(2)

    first = League(participants, storage=storage, timeout_seconds=5).run()
    assert len(first.records) == 2

    second = League(participants, storage=storage, timeout_seconds=5).run()
    assert second.records == []
    assert len(second.skipped) == 2
    assert len(storage.read_results()) == 2


def test_league_records_failures_without_stopping(tmp_path):
    storage = Storage(tmp_path)
    # 1回目の呼び出しだけ想定外の例外を投げ、以降はランダムに着手する
    broken = participant("broken", FakeAdapter(responses=[RuntimeError("バグ")], random_seed=1))
    healthy = random_participant("healthy", seed=2)

    result = League(
        [broken, healthy], storage=storage, timeout_seconds=5, concurrent_games=1
    ).run()

    assert len(result.failures) == 1
    assert isinstance(result.failures[0][1], RuntimeError)
    assert len(result.records) == 1  # もう片方の向きは完走する
    assert len(storage.read_results()) == 1


def test_league_rejects_invalid_concurrency(tmp_path):
    with pytest.raises(ValueError):
        League(_participants(2), storage=Storage(tmp_path), concurrent_games=0)


def test_card_str_shows_both_sides():
    black, white = _participants(2)
    assert str(Card(black=black, white=white)) == "model-0(黒) vs model-1(白)"
