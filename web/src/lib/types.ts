/**
 * `data/`のJSONの型定義。
 *
 * 棋譜JSONは docs/shared/log-schema.md、`ranking.json` は docs/shared/metrics.md に対応する。
 * engineが書き出したものをそのまま読むだけなので、web側で正規化はしない。
 */

export type Color = "black" | "white";
export type Winner = Color | "draw";
export type ResultReason = "score" | "forfeit";
export type ForfeitReason = "illegal_move" | "timeout" | "parse_failure" | "api_error";
export type MoveType = "move" | "pass" | "forfeit";
export type Retried = "none" | "parse_failure" | "api_error";

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
}

/** 棋譜JSONの`players.black` / `players.white`。 */
export interface PlayerInfo {
  id: string;
  model: string;
  provider: string;
  display_name: string;
  config: Record<string, unknown>;
}

export interface GameResult {
  winner: Winner;
  reason: ResultReason;
  score: Record<Color, number> | null;
}

/** 棋譜JSONの`moves[]`。 */
export interface Move {
  turn: number;
  player: Color;
  type: MoveType;
  position: string | null;
  board_after: string;
  legal_moves: string[];
  llm_raw_response: string | null;
  retried: Retried;
  response_time_ms: number;
  forfeit_reason: ForfeitReason | null;
  error_detail: string | null;
  usage: Usage | null;
}

/** 棋譜JSON(`data/games/<game_id>.json`)。 */
export interface GameRecord {
  game_id: string;
  players: Record<Color, PlayerInfo>;
  result: GameResult;
  moves: Move[];
  started_at: string;
  ended_at: string;
}

/** `ranking.json`の`models[]`。 */
export interface ModelStats {
  id: string;
  display_name: string;
  provider: string;
  games: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  win_rate_as_black: number;
  win_rate_as_white: number;
  forfeit_loss_rate: number;
  forfeit_reasons: Record<ForfeitReason, number>;
  avg_response_time_ms: number;
  /** 全対局の入力トークン合計(概算。リトライ分は含まない) */
  prompt_tokens: number;
  /** 全対局の出力トークン合計(概算。リトライ分は含まない) */
  completion_tokens: number;
  /** 石数決着局における石数差(自分 - 相手)の平均。石数決着局が0局なら0 */
  avg_stone_diff: number;
  points: number;
  bt_strength: number;
}

/** `ranking.json`の`head_to_head[]`(a < b のid順)。 */
export interface HeadToHead {
  a: string;
  b: string;
  a_wins: number;
  b_wins: number;
  draws: number;
  game_ids: string[];
}

/** `ranking.json`の`games[]`(対局一覧用の軽量インデックス)。 */
export interface GameSummary {
  game_id: string;
  black: string;
  white: string;
  winner: Winner;
  reason: ResultReason;
  forfeit_reason: ForfeitReason | null;
  /** 石数決着局のみ石数が入る(反則決着局はnull) */
  score: Record<Color, number> | null;
  ended_at: string;
}

/** `data/ranking.json`。 */
export interface Ranking {
  generated_at: string;
  models: ModelStats[];
  head_to_head: HeadToHead[];
  games: GameSummary[];
}

export const FORFEIT_REASONS: ForfeitReason[] = [
  "illegal_move",
  "timeout",
  "parse_failure",
  "api_error",
];

export const FORFEIT_REASON_LABELS: Record<ForfeitReason, string> = {
  illegal_move: "非合法手",
  timeout: "タイムアウト",
  parse_failure: "パース失敗",
  api_error: "APIエラー",
};

export const RETRIED_LABELS: Record<Retried, string> = {
  none: "なし",
  parse_failure: "パース失敗で1回",
  api_error: "APIエラーで1回",
};

export const COLOR_LABELS: Record<Color, string> = {
  black: "黒",
  white: "白",
};
