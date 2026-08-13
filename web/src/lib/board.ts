/**
 * 盤面文字列(64文字)を表示用に扱うための最小限のヘルパ。
 *
 * リバーシのルール(合法手判定・反転)はengine側の責務で、webは棋譜の`board_after`を
 * 並べるだけ(docs/shared/log-schema.md)。ここにあるのは初期配置の定数と石数の数え上げだけで、
 * 反転ロジックは持たない。
 */

import type { Color } from "./types";

export const COLUMNS = ["a", "b", "c", "d", "e", "f", "g", "h"] as const;
export const ROWS = ["1", "2", "3", "4", "5", "6", "7", "8"] as const;

export const EMPTY = ".";
export const BLACK = "b";
export const WHITE = "w";

/** 標準の初期配置(d4/e5に白、d5/e4に黒)。リプレイの開始局面に使う。 */
export const INITIAL_BOARD = [
  "........",
  "........",
  "........",
  "...wb...",
  "...bw...",
  "........",
  "........",
  "........",
].join("");

/** `d3`のような代数記法から盤面文字列のindexへ。不正な表記は-1。 */
export function indexOf(position: string): number {
  if (position.length !== 2) return -1;
  const column = COLUMNS.indexOf(position[0].toLowerCase() as (typeof COLUMNS)[number]);
  const row = ROWS.indexOf(position[1] as (typeof ROWS)[number]);
  if (column < 0 || row < 0) return -1;
  return row * 8 + column;
}

/** 盤面文字列のindexから`d3`のような代数記法へ。 */
export function positionOf(index: number): string {
  return `${COLUMNS[index % 8]}${ROWS[Math.floor(index / 8)]}`;
}

/** 石数を数える。 */
export function countStones(board: string): Record<Color, number> {
  let black = 0;
  let white = 0;
  for (const cell of board) {
    if (cell === BLACK) black += 1;
    else if (cell === WHITE) white += 1;
  }
  return { black, white };
}

export function stoneColor(cell: string): Color | null {
  if (cell === BLACK) return "black";
  if (cell === WHITE) return "white";
  return null;
}
