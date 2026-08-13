/**
 * 64文字の盤面文字列を盤面グリッドとして描く。
 *
 * 棋譜の`board_after`をそのまま描くだけで、反転ロジックは持たない
 * (docs/shared/log-schema.md「board_beforeは持たない」)。選ばれなかった合法手は
 * 薄い点で示す。
 */

import { COLUMNS, ROWS, indexOf, stoneColor } from "../lib/board";
import { COLOR_LABELS } from "../lib/types";

interface Props {
  board: string;
  /** その手番で選べた合法手。選ばれた手を除いて薄く表示する。 */
  legalMoves?: string[];
  /** その手で実際に打たれた位置(丸で囲む)。 */
  playedPosition?: string | null;
  /** 非合法手として反則負けになった位置(×印を付ける)。 */
  illegalPosition?: string | null;
}

export function Board({ board, legalMoves = [], playedPosition, illegalPosition }: Props) {
  const hints = new Set(
    legalMoves.filter((position) => position !== playedPosition).map(indexOf),
  );
  const playedIndex = playedPosition ? indexOf(playedPosition) : -1;
  const illegalIndex = illegalPosition ? indexOf(illegalPosition) : -1;

  return (
    <div className="board-frame">
      <div className="board" role="img" aria-label={boardDescription(board)}>
        <span className="board__label" aria-hidden="true" />
        {COLUMNS.map((column) => (
          <span key={column} className="board__label" aria-hidden="true">
            {column}
          </span>
        ))}
        {ROWS.map((row, rowIndex) => (
          <BoardRow
            key={row}
            row={row}
            rowIndex={rowIndex}
            board={board}
            hints={hints}
            playedIndex={playedIndex}
            illegalIndex={illegalIndex}
          />
        ))}
      </div>
    </div>
  );
}

function BoardRow({
  row,
  rowIndex,
  board,
  hints,
  playedIndex,
  illegalIndex,
}: {
  row: string;
  rowIndex: number;
  board: string;
  hints: Set<number>;
  playedIndex: number;
  illegalIndex: number;
}) {
  return (
    <>
      <span className="board__label" aria-hidden="true">
        {row}
      </span>
      {COLUMNS.map((_, columnIndex) => {
        const index = rowIndex * 8 + columnIndex;
        const stone = stoneColor(board[index] ?? ".");
        const classes = ["board__cell"];
        if (rowIndex === 0) classes.push("board__cell--top");
        if (columnIndex === 0) classes.push("board__cell--left");
        if (index === playedIndex) classes.push("board__cell--played");
        if (index === illegalIndex) classes.push("board__cell--illegal");
        return (
          <span key={index} className={classes.join(" ")}>
            {stone ? (
              <span className={`board__stone board__stone--${stone}`} />
            ) : hints.has(index) ? (
              <span className="board__hint" />
            ) : null}
          </span>
        );
      })}
    </>
  );
}

function boardDescription(board: string): string {
  let black = 0;
  let white = 0;
  for (const cell of board) {
    if (cell === "b") black += 1;
    if (cell === "w") white += 1;
  }
  return `盤面: ${COLOR_LABELS.black} ${black}石、${COLOR_LABELS.white} ${white}石`;
}
