"""盤面ロジックの単体テスト。"""

from __future__ import annotations

import pytest

from reversi_engine import board as b


def test_initial_board_is_standard_layout():
    state = b.initial_board()
    assert len(state) == 64
    assert state[b.index_of("d4")] == b.WHITE
    assert state[b.index_of("e5")] == b.WHITE
    assert state[b.index_of("d5")] == b.BLACK
    assert state[b.index_of("e4")] == b.BLACK
    assert b.count_stones(state) == {"black": 2, "white": 2}
    assert not b.is_full(state)


def test_index_and_position_round_trip():
    assert b.index_of("a1") == 0
    assert b.index_of("h8") == 63
    assert b.index_of("d3") == 19
    assert b.position_of(19) == "d3"
    for index in range(64):
        assert b.index_of(b.position_of(index)) == index


@pytest.mark.parametrize("position", ["", "a", "i1", "a9", "aa", "1a", "a10"])
def test_index_of_rejects_invalid_position(position):
    with pytest.raises(ValueError):
        b.index_of(position)


def test_legal_moves_at_initial_position():
    state = b.initial_board()
    # docs/engine/adapter-interface.md のプロンプト例と同じ順序(盤面index昇順)
    assert b.legal_moves(state, "black") == ["d3", "c4", "f5", "e6"]
    assert b.legal_moves(state, "white") == ["e3", "f4", "c5", "d6"]


def test_apply_move_flips_stones():
    state = b.apply_move(b.initial_board(), "black", "d3")
    assert state[b.index_of("d3")] == b.BLACK
    assert state[b.index_of("d4")] == b.BLACK  # 反転した
    assert state[b.index_of("e5")] == b.WHITE  # 無関係な石はそのまま
    assert b.count_stones(state) == {"black": 4, "white": 1}


def test_apply_move_flips_multiple_directions():
    # 中央に黒を集めて、複数方向を同時に反転する局面を作る
    cells = [b.EMPTY] * 64
    for position in ("c3", "d3", "e3", "c4", "e4", "c5", "d5", "e5"):
        cells[b.index_of(position)] = b.WHITE
    for position in ("b2", "d2", "f2", "b4", "f4", "b6", "d6", "f6"):
        cells[b.index_of(position)] = b.BLACK
    state = "".join(cells)
    flipped = b.apply_move(state, "black", "d4")
    assert b.count_stones(flipped)["white"] == 0
    assert b.count_stones(flipped)["black"] == 8 + 8 + 1


def test_apply_move_rejects_illegal_move():
    state = b.initial_board()
    with pytest.raises(ValueError):
        b.apply_move(state, "black", "a1")
    with pytest.raises(ValueError):
        b.apply_move(state, "black", "d4")  # 既に石がある


def test_is_legal_move():
    state = b.initial_board()
    assert b.is_legal_move(state, "black", "d3")
    assert not b.is_legal_move(state, "black", "a1")
    assert not b.is_legal_move(state, "black", "zz")  # 不正な表記でも例外にしない


def test_no_legal_moves_when_opponent_has_no_stones():
    cells = [b.EMPTY] * 64
    cells[b.index_of("d4")] = b.BLACK
    state = "".join(cells)
    assert b.legal_moves(state, "black") == []
    assert b.legal_moves(state, "white") == []


def test_is_full_and_count_stones():
    state = b.BLACK * 40 + b.WHITE * 24
    assert b.is_full(state)
    assert b.count_stones(state) == {"black": 40, "white": 24}


def test_format_grid_matches_documented_layout():
    grid = b.format_grid(b.initial_board())
    assert grid.splitlines()[0] == "    a b c d e f g h"
    assert grid.splitlines()[4] == "  4 . . . w b . . ."
    assert grid.splitlines()[5] == "  5 . . . b w . . ."


def test_validate_board_rejects_broken_state():
    with pytest.raises(ValueError):
        b.validate_board("." * 63)
    with pytest.raises(ValueError):
        b.validate_board("x" + "." * 63)


def test_opponent_and_stone_of():
    assert b.opponent("black") == "white"
    assert b.opponent("white") == "black"
    assert b.stone_of("black") == b.BLACK
    assert b.stone_of("white") == b.WHITE
    with pytest.raises(ValueError):
        b.opponent("green")
    with pytest.raises(ValueError):
        b.stone_of("green")
