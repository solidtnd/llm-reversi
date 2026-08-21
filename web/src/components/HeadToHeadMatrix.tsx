/**
 * 総当たり対戦表(マトリクス)。
 *
 * セルの値は「行のモデルから見た勝ち越し度」= (行の勝ち - 列の勝ち) / 対局数 で、
 * -1〜+1の**極性**を持つ。極性なので配色は発散(diverging)配色を使い、
 * 中央(勝ち負け同数)は無彩色にする。セルには常に「勝-分-負」の数値も入れるため、
 * 色だけで読ませることはしない。
 */

import { Link } from "react-router-dom";
import type { HeadToHead, ModelStats } from "../lib/types";

interface Props {
  /** 行(その視点から勝ち越し/負け越しを読むモデル)。絞り込みはここだけに効かせる */
  rows: ModelStats[];
  /** 列(対戦相手)。絞り込んでも他社モデルとの成績が見えるよう常に全モデルを渡す */
  columns: ModelStats[];
  headToHead: HeadToHead[];
}

interface CellData {
  wins: number;
  draws: number;
  losses: number;
  games: number;
}

/** 濃くしすぎるとセル内の文字が読めなくなるため、混色は60%で打ち切る。 */
const MAX_MIX = 60;

function cellBackground(cell: CellData): string {
  if (cell.games === 0) return "transparent";
  const balance = (cell.wins - cell.losses) / cell.games; // -1 〜 +1
  const strength = Math.abs(balance) * MAX_MIX;
  if (strength < 1) return "var(--div-mid)";
  const pole = balance > 0 ? "var(--div-pos)" : "var(--div-neg)";
  return `color-mix(in oklab, ${pole} ${strength.toFixed(0)}%, var(--div-mid))`;
}

function buildLookup(headToHead: HeadToHead[]): Map<string, CellData> {
  const lookup = new Map<string, CellData>();
  for (const card of headToHead) {
    const games = card.a_wins + card.b_wins + card.draws;
    lookup.set(`${card.a}|${card.b}`, {
      wins: card.a_wins,
      draws: card.draws,
      losses: card.b_wins,
      games,
    });
    lookup.set(`${card.b}|${card.a}`, {
      wins: card.b_wins,
      draws: card.draws,
      losses: card.a_wins,
      games,
    });
  }
  return lookup;
}

export function HeadToHeadMatrix({ rows, columns, headToHead }: Props) {
  const lookup = buildLookup(headToHead);

  if (rows.length < 1 || columns.length < 2) {
    return <div className="table-wrap empty">対戦表を出すには2モデル以上必要です。</div>;
  }

  return (
    <>
      <div className="table-wrap">
        <table className="table matrix">
          <caption className="visually-hidden">
            行のモデルから見た対戦成績(勝-分-負)。セルを選ぶとそのカードで絞り込んだモデル詳細へ移動します。
          </caption>
          <thead>
            <tr>
              <th scope="col">行 \ 列</th>
              {columns.map((model) => (
                <th key={model.id} scope="col">
                  {model.display_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <th scope="row">{row.display_name}</th>
                {columns.map((column) => {
                  if (row.id === column.id) {
                    return (
                      <td key={column.id} className="matrix__cell matrix__self" aria-label="自分自身" />
                    );
                  }
                  const cell = lookup.get(`${row.id}|${column.id}`);
                  if (!cell || cell.games === 0) {
                    return (
                      <td key={column.id} className="matrix__cell">
                        <span className="matrix__empty" title="未対戦">
                          —
                        </span>
                      </td>
                    );
                  }
                  return (
                    <td
                      key={column.id}
                      className="matrix__cell"
                      style={{ background: cellBackground(cell) }}
                    >
                      <Link
                        className="matrix__link"
                        to={`/models/${encodeURIComponent(row.id)}?opponent=${encodeURIComponent(column.id)}`}
                        title={`${row.display_name} 対 ${column.display_name}: ${cell.wins}勝 ${cell.draws}分 ${cell.losses}敗 (${cell.games}局)`}
                      >
                        {cell.wins}-{cell.draws}-{cell.losses}
                      </Link>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="legend">
        <span>行が負け越し</span>
        <span className="legend__ramp" aria-hidden="true">
          <span style={{ background: "color-mix(in oklab, var(--div-neg) 60%, var(--div-mid))" }} />
          <span style={{ background: "color-mix(in oklab, var(--div-neg) 30%, var(--div-mid))" }} />
          <span style={{ background: "var(--div-mid)" }} />
          <span style={{ background: "color-mix(in oklab, var(--div-pos) 30%, var(--div-mid))" }} />
          <span style={{ background: "color-mix(in oklab, var(--div-pos) 60%, var(--div-mid))" }} />
        </span>
        <span>行が勝ち越し</span>
        <span className="muted">セルの数値は行のモデルから見た 勝-分-負</span>
      </div>
    </>
  );
}
