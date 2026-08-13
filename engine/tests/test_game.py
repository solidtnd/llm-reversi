"""1対局の進行(反則負け・タイムアウト・リトライ)の単体テスト。"""

from __future__ import annotations

import re

import pytest

from fakes import RANDOM, FakeAdapter, FakeStep, participant, random_participant
from reversi_engine.adapters.base import (
    MSG_FORMAT_MISMATCH,
    MSG_RATE_LIMIT,
    AdapterAPIError,
    AdapterParseError,
    MoveResponse,
)
from reversi_engine.board import apply_move, initial_board, legal_moves
from reversi_engine.game import Game, MoveRecord, new_game_id

USAGE = {"prompt_tokens": 10, "completion_tokens": 3}


def _game(black_adapter, white_adapter, **kwargs) -> Game:
    return Game(
        participant("black-model", black_adapter),
        participant("white-model", white_adapter),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 通常進行
# ---------------------------------------------------------------------------


def test_random_game_finishes_with_score():
    record = _game(
        FakeAdapter(random_seed=1, usage=USAGE),
        FakeAdapter(random_seed=2, usage=USAGE),
        timeout_seconds=5,
    ).play()

    assert record.result.reason == "score"
    assert record.result.score is not None
    assert sum(record.result.score.values()) <= 64
    assert record.result.winner in ("black", "white", "draw")
    assert [move.turn for move in record.moves] == list(range(1, len(record.moves) + 1))
    assert record.moves[0].player == "black"


def test_board_after_chain_is_consistent():
    record = _game(FakeAdapter(random_seed=3), FakeAdapter(random_seed=4), timeout_seconds=5).play()
    board = initial_board()
    for move in record.moves:
        if move.type == "move":
            assert move.position in move.legal_moves
            board = apply_move(board, move.player, move.position)
        assert move.board_after == board


def test_first_move_prompt_inputs_are_passed_to_adapter():
    black = FakeAdapter(random_seed=5)
    _game(black, FakeAdapter(random_seed=6), timeout_seconds=5).play()
    first = black.calls[0]
    assert first.board == initial_board()
    assert first.legal_moves == legal_moves(initial_board(), "black")
    assert first.player == "black"
    assert first.retry_reason is None


def test_pass_move_is_recorded_without_calling_adapter():
    """合法手が無い手番は自動パスし、LLMを呼ばない。"""
    for seed in range(20):
        black = FakeAdapter(random_seed=seed)
        white = FakeAdapter(random_seed=seed + 100)
        record = _game(black, white, timeout_seconds=5).play()
        passes = [move for move in record.moves if move.type == "pass"]
        if not passes:
            continue
        for move in passes:
            assert move.position is None
            assert move.legal_moves == []
            assert move.llm_raw_response is None
            assert move.usage is None
            assert move.retried == "none"
            assert move.response_time_ms == 0
        played = [move for move in record.moves if move.type != "pass"]
        assert black.call_count + white.call_count == len(played)
        return
    pytest.fail("パスを含む対局が見つからなかった(テストの前提が崩れている)")


def test_game_id_format():
    assert re.fullmatch(r"\d{8}T\d{12}-[0-9a-f]{6}", new_game_id())


def test_game_id_is_unique_per_call():
    assert len({new_game_id() for _ in range(50)}) == 50


# ---------------------------------------------------------------------------
# 反則負け: 非合法手
# ---------------------------------------------------------------------------


def test_illegal_move_forfeits_immediately():
    black = FakeAdapter(responses=["a1"])  # 初期局面でa1は非合法
    record = _game(black, FakeAdapter(random_seed=7), timeout_seconds=5).play()

    assert black.call_count == 1  # リトライしない
    assert record.result.winner == "white"
    assert record.result.reason == "forfeit"
    assert record.result.score is None
    last = record.moves[-1]
    assert last.type == "forfeit"
    assert last.forfeit_reason == "illegal_move"
    assert last.position == "a1"  # モデルが返した非合法手を残す
    assert last.error_detail is None
    assert last.retried == "none"
    assert last.board_after == initial_board()
    assert record.summary()["forfeit_reason"] == "illegal_move"


# ---------------------------------------------------------------------------
# 反則負け・リトライ: パース失敗
# ---------------------------------------------------------------------------


def test_parse_failure_retries_once_with_feedback():
    black = FakeAdapter(
        responses=[
            AdapterParseError(MSG_FORMAT_MISMATCH, "壊れた応答"),
            MoveResponse(position="d3", llm_raw_response="成功した応答", usage=USAGE),
        ],
        random_seed=100,  # 1手目の検証後は最後まで対局を続ける
    )
    record = _game(black, FakeAdapter(random_seed=8), timeout_seconds=5).play()

    assert black.calls[0].retry_reason is None
    assert black.calls[1].retry_reason == MSG_FORMAT_MISMATCH  # 失敗理由をフィードバック
    assert black.calls[1].board == black.calls[0].board  # 盤面・合法手は初回と同一
    first_move = record.moves[0]
    assert first_move.type == "move"
    assert first_move.retried == "parse_failure"
    assert first_move.llm_raw_response == "成功した応答"  # 最終レスポンスのみ記録
    assert first_move.usage == USAGE


def test_parse_failure_twice_forfeits():
    black = FakeAdapter(
        responses=[
            AdapterParseError(MSG_FORMAT_MISMATCH, "1回目の応答"),
            AdapterParseError("2回目の失敗", "2回目の応答"),
        ]
    )
    record = _game(black, FakeAdapter(random_seed=9), timeout_seconds=5).play()

    assert black.call_count == 2  # 1手あたりのリトライは通算1回まで
    last = record.moves[-1]
    assert last.forfeit_reason == "parse_failure"
    assert last.retried == "parse_failure"
    assert last.error_detail == "2回目の失敗"
    assert last.llm_raw_response == "2回目の応答"
    assert last.position is None
    assert record.result.winner == "white"


# ---------------------------------------------------------------------------
# 反則負け・リトライ: APIエラー
# ---------------------------------------------------------------------------


def test_api_error_retries_without_feedback():
    black = FakeAdapter(
        responses=[
            AdapterAPIError(MSG_RATE_LIMIT, RuntimeError("429")),
            "d3",
        ],
        random_seed=101,  # 1手目の検証後は最後まで対局を続ける
    )
    record = _game(black, FakeAdapter(random_seed=10), timeout_seconds=5).play()

    assert black.calls[1].retry_reason is None  # APIエラーは同一内容で再送
    assert record.moves[0].retried == "api_error"
    assert record.moves[0].type == "move"


def test_api_error_twice_forfeits_with_original_exception():
    original = RuntimeError("503")
    black = FakeAdapter(
        responses=[
            AdapterAPIError(MSG_RATE_LIMIT, RuntimeError("429")),
            AdapterAPIError("APIサーバーエラー", original),
        ]
    )
    record = _game(black, FakeAdapter(random_seed=11), timeout_seconds=5).play()

    last = record.moves[-1]
    assert last.forfeit_reason == "api_error"
    assert last.retried == "api_error"
    assert last.error_detail is not None
    assert "APIサーバーエラー" in last.error_detail
    assert repr(original) in last.error_detail
    assert last.llm_raw_response is None  # レスポンスを受け取れていない


def test_retry_budget_is_shared_between_causes():
    """パース失敗で1回使い切った後にAPIエラーが起きたら、そのまま反則負け。"""
    black = FakeAdapter(
        responses=[
            AdapterParseError(MSG_FORMAT_MISMATCH, "壊れた応答"),
            AdapterAPIError(MSG_RATE_LIMIT, RuntimeError("429")),
        ]
    )
    record = _game(black, FakeAdapter(random_seed=12), timeout_seconds=5).play()

    assert black.call_count == 2
    last = record.moves[-1]
    assert last.forfeit_reason == "api_error"
    # retriedは「何が引き金でリトライしたか」なのでforfeit_reasonとは独立
    assert last.retried == "parse_failure"


# ---------------------------------------------------------------------------
# タイムアウト
# ---------------------------------------------------------------------------


def test_timeout_forfeits_without_error_detail():
    black = FakeAdapter(responses=[FakeStep(result="d3", delay=0.30)])
    record = _game(black, FakeAdapter(random_seed=13), timeout_seconds=0.05).play()

    last = record.moves[-1]
    assert last.forfeit_reason == "timeout"
    assert last.error_detail is None  # 例外なしの単なる遅延
    assert last.retried == "none"
    assert last.response_time_ms >= 0
    assert record.result.winner == "white"
    assert record.result.score is None


def test_timeout_after_exception_records_last_error_detail():
    """リトライ中に予算を超過した場合、直近の例外メッセージを残す。"""
    black = FakeAdapter(
        responses=[
            AdapterParseError("最初の失敗理由", "壊れた応答"),
            FakeStep(result="d3", delay=0.30),
        ]
    )
    record = _game(black, FakeAdapter(random_seed=14), timeout_seconds=0.05).play()

    last = record.moves[-1]
    assert last.forfeit_reason == "timeout"
    assert last.error_detail == "最初の失敗理由"
    assert last.retried == "parse_failure"


def test_retry_is_not_marked_when_budget_is_already_exhausted():
    """リトライを開始する前に予算超過が確定した場合、retriedはnoneのまま。"""
    ticks = iter([0.00, 0.04, 0.08, 0.12])  # start → 1回目のremaining判定 → 2回目 → elapsed
    black = FakeAdapter(responses=[AdapterParseError("最初の失敗理由", "壊れた応答"), "d3"])
    record = Game(
        participant("black-model", black),
        participant("white-model", FakeAdapter(random_seed=15)),
        timeout_seconds=0.05,
        clock=lambda: next(ticks),
    ).play()

    last = record.moves[-1]
    assert last.forfeit_reason == "timeout"
    assert last.error_detail == "最初の失敗理由"  # 直近の例外は残す
    assert last.retried == "none"  # 実際にはリトライを開始していない
    assert black.call_count == 1


def test_timeout_can_be_disabled():
    black = FakeAdapter(responses=[FakeStep(result="d3", delay=0.02)], random_seed=16)
    record = _game(black, FakeAdapter(random_seed=17), timeout_seconds=None).play()
    assert record.moves[0].type == "move"


# ---------------------------------------------------------------------------
# 棋譜・要約
# ---------------------------------------------------------------------------


def test_record_to_dict_matches_schema_keys():
    record = _game(FakeAdapter(random_seed=18), FakeAdapter(random_seed=19), timeout_seconds=5).play()
    payload = record.to_dict()

    assert set(payload) == {"game_id", "players", "result", "moves", "started_at", "ended_at"}
    assert set(payload["players"]) == {"black", "white"}
    assert set(payload["players"]["black"]) == {
        "id",
        "model",
        "provider",
        "display_name",
        "config",
    }
    assert set(payload["result"]) == {"winner", "reason", "score"}
    assert set(payload["moves"][0]) == {
        "turn",
        "player",
        "type",
        "position",
        "board_after",
        "legal_moves",
        "llm_raw_response",
        "retried",
        "response_time_ms",
        "forfeit_reason",
        "error_detail",
        "usage",
    }


def test_summary_matches_results_jsonl_schema():
    record = _game(FakeAdapter(random_seed=20), FakeAdapter(random_seed=21), timeout_seconds=5).play()
    summary = record.summary()

    assert set(summary) == {
        "game_id",
        "black",
        "white",
        "winner",
        "reason",
        "forfeit_reason",
        "ended_at",
    }
    assert set(summary["black"]) == {"id", "avg_response_time_ms"}
    assert summary["black"]["id"] == "black-model"
    assert summary["forfeit_reason"] is None


def test_average_response_time_excludes_pass_moves():
    record = _game(FakeAdapter(random_seed=22), FakeAdapter(random_seed=23), timeout_seconds=5).play()
    record.moves = [
        MoveRecord(1, "black", "move", "d3", initial_board(), ["d3"], response_time_ms=100),
        MoveRecord(2, "white", "pass", None, initial_board(), [], response_time_ms=0),
        MoveRecord(3, "black", "move", "c4", initial_board(), ["c4"], response_time_ms=300),
    ]
    assert record.average_response_time_ms("black") == 200
    assert record.average_response_time_ms("white") == 0
