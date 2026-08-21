/** モデル詳細内の対局履歴。相手モデル・勝敗で絞り込める。 */

import { Link } from "react-router-dom";
import { dateTime, shortGameId, stoneDiff } from "../lib/format";
import {
  FORFEIT_REASON_LABELS,
  type GameSummary,
  type ModelStats,
} from "../lib/types";

export type ResultFilter = "all" | "win" | "loss" | "draw";

interface Props {
  games: GameSummary[];
  modelId: string;
  modelsById: Map<string, ModelStats>;
}

function outcomeOf(game: GameSummary, modelId: string): ResultFilter {
  if (game.winner === "draw") return "draw";
  const winnerId = game.winner === "black" ? game.black : game.white;
  return winnerId === modelId ? "win" : "loss";
}

const OUTCOME_LABELS: Record<ResultFilter, string> = {
  all: "すべて",
  win: "勝ち",
  loss: "負け",
  draw: "引き分け",
};

export function gameOutcome(game: GameSummary, modelId: string): ResultFilter {
  return outcomeOf(game, modelId);
}

export function outcomeLabel(outcome: ResultFilter): string {
  return OUTCOME_LABELS[outcome];
}

export function GameHistoryTable({ games, modelId, modelsById }: Props) {
  if (games.length === 0) {
    return <div className="table-wrap empty">条件に合う対局がありません。</div>;
  }

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>終局</th>
            <th>手番</th>
            <th>相手</th>
            <th>結果</th>
            <th>決着</th>
            <th>棋譜</th>
          </tr>
        </thead>
        <tbody>
          {games.map((game) => {
            const isBlack = game.black === modelId;
            const opponentId = isBlack ? game.white : game.black;
            const opponent = modelsById.get(opponentId);
            const outcome = outcomeOf(game, modelId);
            // 石数決着は「僅差か圧倒的か」が分かるよう、そのモデルから見た石数と差を出す
            const mine = game.score ? (isBlack ? game.score.black : game.score.white) : null;
            const theirs = game.score ? (isBlack ? game.score.white : game.score.black) : null;
            return (
              <tr key={game.game_id}>
                <td className="mono">{dateTime(game.ended_at)}</td>
                <td>{isBlack ? "先手(黒)" : "後手(白)"}</td>
                <td>
                  <Link to={`/models/${encodeURIComponent(opponentId)}`}>
                    {opponent?.display_name ?? opponentId}
                  </Link>
                </td>
                <td>{OUTCOME_LABELS[outcome]}</td>
                <td>
                  {game.reason === "forfeit" ? (
                    `反則負け(${game.forfeit_reason ? FORFEIT_REASON_LABELS[game.forfeit_reason] : "不明"})`
                  ) : mine !== null && theirs !== null ? (
                    <span className="mono">
                      石数 {mine} - {theirs}{" "}
                      <span className="muted">({stoneDiff(mine - theirs)})</span>
                    </span>
                  ) : (
                    "石数"
                  )}
                </td>
                <td>
                  <Link to={`/games/${encodeURIComponent(game.game_id)}`} className="mono">
                    {shortGameId(game.game_id)}
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
