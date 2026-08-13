"""盤面表現・合法手判定・着手・終局判定。

盤面は64文字の文字列(`.`=空/`b`=黒/`w`=白)でそのまま表現する
(docs/shared/log-schema.md の `board_after` と同一形式)。
index = 行 * 8 + 列 で、index 0 が a1、index 63 が h8。
"""

from __future__ import annotations

from typing import Literal

Player = Literal["black", "white"]
BoardState = str

EMPTY = "."
BLACK = "b"
WHITE = "w"

BOARD_SIZE = 8
CELL_COUNT = BOARD_SIZE * BOARD_SIZE
COLUMNS = "abcdefgh"
ROWS = "12345678"

_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)

_STONES: dict[str, str] = {"black": BLACK, "white": WHITE}


def stone_of(player: Player) -> str:
    """手番の石の文字を返す。"""
    try:
        return _STONES[player]
    except KeyError:
        raise ValueError(f"不正な手番: {player!r}") from None


def opponent(player: Player) -> Player:
    """相手の手番を返す。"""
    if player == "black":
        return "white"
    if player == "white":
        return "black"
    raise ValueError(f"不正な手番: {player!r}")


def index_of(position: str) -> int:
    """`d3` のような代数記法を盤面文字列のindexに変換する。"""
    if not isinstance(position, str) or len(position) != 2:
        raise ValueError(f"不正な着手位置: {position!r}")
    column, row = position[0].lower(), position[1]
    if column not in COLUMNS or row not in ROWS:
        raise ValueError(f"不正な着手位置: {position!r}")
    return ROWS.index(row) * BOARD_SIZE + COLUMNS.index(column)


def position_of(index: int) -> str:
    """盤面文字列のindexを `d3` のような代数記法に変換する。"""
    if not 0 <= index < CELL_COUNT:
        raise ValueError(f"不正なindex: {index!r}")
    row, column = divmod(index, BOARD_SIZE)
    return f"{COLUMNS[column]}{ROWS[row]}"


def initial_board() -> BoardState:
    """標準の初期配置(中央4マスに斜め配置)を返す。"""
    cells = [EMPTY] * CELL_COUNT
    cells[index_of("d4")] = WHITE
    cells[index_of("e4")] = BLACK
    cells[index_of("d5")] = BLACK
    cells[index_of("e5")] = WHITE
    return "".join(cells)


def validate_board(board: BoardState) -> None:
    """盤面文字列の形式を検証する。"""
    if not isinstance(board, str) or len(board) != CELL_COUNT:
        raise ValueError(f"盤面は{CELL_COUNT}文字の文字列である必要がある: {board!r}")
    invalid = set(board) - {EMPTY, BLACK, WHITE}
    if invalid:
        raise ValueError(f"盤面に不正な文字が含まれている: {sorted(invalid)}")


def _flips(board: BoardState, index: int, stone: str) -> list[int]:
    """indexに着手したときに反転する石のindex一覧を返す。空なら非合法手。"""
    if board[index] != EMPTY:
        return []
    other = WHITE if stone == BLACK else BLACK
    row, column = divmod(index, BOARD_SIZE)
    flipped: list[int] = []
    for d_row, d_column in _DIRECTIONS:
        line: list[int] = []
        r, c = row + d_row, column + d_column
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
            i = r * BOARD_SIZE + c
            if board[i] == other:
                line.append(i)
            elif board[i] == stone:
                flipped.extend(line)
                break
            else:
                break
            r += d_row
            c += d_column
    return flipped


def legal_moves(board: BoardState, player: Player) -> list[str]:
    """合法手を代数記法で返す(a1→h8の順、つまり盤面index昇順)。"""
    validate_board(board)
    stone = stone_of(player)
    return [
        position_of(index)
        for index in range(CELL_COUNT)
        if board[index] == EMPTY and _flips(board, index, stone)
    ]


def is_legal_move(board: BoardState, player: Player, position: str) -> bool:
    """指定の着手が合法かどうかを返す。"""
    try:
        index = index_of(position)
    except ValueError:
        return False
    return bool(_flips(board, index, stone_of(player)))


def apply_move(board: BoardState, player: Player, position: str) -> BoardState:
    """着手を適用した新しい盤面を返す。非合法手なら ValueError。"""
    validate_board(board)
    stone = stone_of(player)
    index = index_of(position)
    flipped = _flips(board, index, stone)
    if not flipped:
        raise ValueError(f"非合法手: {position} ({player})")
    cells = list(board)
    cells[index] = stone
    for i in flipped:
        cells[i] = stone
    return "".join(cells)


def count_stones(board: BoardState) -> dict[str, int]:
    """石数を `{"black": n, "white": n}` で返す。"""
    validate_board(board)
    return {"black": board.count(BLACK), "white": board.count(WHITE)}


def is_full(board: BoardState) -> bool:
    """盤面が埋まっているかどうかを返す。"""
    return EMPTY not in board


def format_grid(board: BoardState) -> str:
    """LLMのプロンプト用に、列(a-h)・行(1-8)ラベル付きのグリッド表記へ変換する。"""
    validate_board(board)
    lines = ["    " + " ".join(COLUMNS)]
    for row in range(BOARD_SIZE):
        cells = " ".join(board[row * BOARD_SIZE : (row + 1) * BOARD_SIZE])
        lines.append(f"  {ROWS[row]} {cells}")
    return "\n".join(lines)
