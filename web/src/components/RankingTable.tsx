/**
 * モデルランキング表。
 *
 * 勝点方式・Bradley-Terry強さ推定・平均石数差を併記し、どの列見出しからでも並べ替えられる。
 * 「良い方向」が列によって違う(勝率は高い方が良い、反則負け率・応答時間は低い方が良い)ため、
 * 列ごとに既定の並び順を持たせ、同じ見出しを押すと昇降を切り替える。
 */

import { Link } from "react-router-dom";
import { duration, percent, points as formatPoints, stoneDiff } from "../lib/format";
import { FORFEIT_REASON_LABELS, FORFEIT_REASONS, type ModelStats } from "../lib/types";
import { ProviderBadge } from "./ProviderBadge";

export type SortKey =
  | "games"
  | "wins"
  | "win_rate"
  | "win_rate_as_black"
  | "win_rate_as_white"
  | "forfeit_loss_rate"
  | "avg_response_time_ms"
  | "avg_stone_diff"
  | "points"
  | "bt_strength";

export type SortDir = "asc" | "desc";

export interface Sort {
  key: SortKey;
  dir: SortDir;
}

interface SortColumn {
  /** 列見出しの文字列。12列を横スクロールなしで収めるため短く省略する */
  label: string;
  /** 省略しない名前(見出しのツールチップ・ランキング上位パネルの見出しに使う) */
  name?: string;
  /** その列を押したときの既定の並び順(値が大きい方が良い列はdesc) */
  dir: SortDir;
  /** ランキング上位パネルで値を1つだけ見せるときの表記 */
  format: (model: ModelStats) => string;
}

export const SORT_COLUMNS: Record<SortKey, SortColumn> = {
  games: { label: "対局", dir: "desc", format: (m) => `${m.games}局` },
  wins: {
    label: "勝/負/分",
    dir: "desc",
    format: (m) => `${m.wins}勝 ${m.losses}敗 ${m.draws}分`,
  },
  win_rate: { label: "勝率", dir: "desc", format: (m) => percent(m.win_rate, 1) },
  win_rate_as_black: {
    label: "先手",
    name: "先手時の勝率",
    dir: "desc",
    format: (m) => percent(m.win_rate_as_black, 1),
  },
  win_rate_as_white: {
    label: "後手",
    name: "後手時の勝率",
    dir: "desc",
    format: (m) => percent(m.win_rate_as_white, 1),
  },
  forfeit_loss_rate: {
    label: "反則",
    name: "反則負け率",
    dir: "asc",
    format: (m) => percent(m.forfeit_loss_rate, 1),
  },
  avg_response_time_ms: {
    label: "応答",
    name: "平均応答時間",
    dir: "asc",
    format: (m) => duration(m.avg_response_time_ms),
  },
  avg_stone_diff: {
    label: "石差",
    name: "平均石数差",
    dir: "desc",
    format: (m) => stoneDiff(m.avg_stone_diff),
  },
  points: { label: "勝点", dir: "desc", format: (m) => `${formatPoints(m.points)}点` },
  bt_strength: {
    label: "BT強さ",
    name: "Bradley-Terry強さ推定",
    dir: "desc",
    format: (m) => m.bt_strength.toFixed(3),
  },
};

/** 省略しない項目名(ランキング上位パネルの見出し等、表の外で使う)。 */
export function sortName(key: SortKey): string {
  return SORT_COLUMNS[key].name ?? SORT_COLUMNS[key].label;
}

/** 並べ替えに使う数値。すべて`ModelStats`の数値フィールドをそのまま読む。 */
export function sortValue(model: ModelStats, key: SortKey): number {
  return model[key];
}

/** 列の既定の並び順で並べ替える(同じ列を再度押した場合は昇降を反転する)。 */
export function nextSort(current: Sort, key: SortKey): Sort {
  if (current.key !== key) return { key, dir: SORT_COLUMNS[key].dir };
  return { key, dir: current.dir === "desc" ? "asc" : "desc" };
}

export function sortModels(models: ModelStats[], sort: Sort): ModelStats[] {
  const sign = sort.dir === "asc" ? 1 : -1;
  return [...models].sort((a, b) => {
    const diff = (sortValue(a, sort.key) - sortValue(b, sort.key)) * sign;
    // 同値のときは表示名で安定させる(データの並び順に依存させない)
    return diff !== 0 ? diff : a.display_name.localeCompare(b.display_name);
  });
}

interface Props {
  models: ModelStats[];
  sort: Sort;
  onSortChange: (sort: Sort) => void;
}

/** セル内バー。順位ではなく値の大きさを表す(magnitude)ので無彩色にする。 */
function Meter({ value, max, label }: { value: number; max: number; label: string }) {
  const ratio = max > 0 ? Math.min(1, value / max) : 0;
  return (
    <div className="meter">
      <span className="num">{label}</span>
      <span className="meter__track">
        <span className="meter__fill" style={{ width: `${ratio * 100}%` }} />
      </span>
    </div>
  );
}

function forfeitTitle(model: ModelStats): string {
  const detail = FORFEIT_REASONS.filter((reason) => model.forfeit_reasons[reason] > 0)
    .map((reason) => `${FORFEIT_REASON_LABELS[reason]} ${model.forfeit_reasons[reason]}`)
    .join(" / ");
  return detail ? `内訳: ${detail}` : "反則負けなし";
}

export function RankingTable({ models, sort, onSortChange }: Props) {
  const maxPoints = Math.max(...models.map((model) => model.points), 0);
  const maxStrength = Math.max(...models.map((model) => model.bt_strength), 0);

  if (models.length === 0) {
    return <div className="table-wrap empty">条件に合うモデルがありません。</div>;
  }

  const SortTh = ({ k, className }: { k: SortKey; className?: string }) => {
    const active = sort.key === k;
    return (
      <th
        className={className}
        title={sortName(k)}
        aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
      >
        <button
          type="button"
          className="table__sort"
          aria-pressed={active}
          onClick={() => onSortChange(nextSort(sort, k))}
        >
          {SORT_COLUMNS[k].label}
          <span aria-hidden="true">{active ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}</span>
        </button>
      </th>
    );
  };

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th className="table__rank">順位</th>
            <th>モデル</th>
            <SortTh k="games" className="num" />
            <SortTh k="wins" className="num" />
            <SortTh k="win_rate" className="num" />
            <SortTh k="win_rate_as_black" className="num" />
            <SortTh k="win_rate_as_white" className="num" />
            <SortTh k="forfeit_loss_rate" className="num" />
            <SortTh k="avg_response_time_ms" className="num" />
            <SortTh k="avg_stone_diff" className="num" />
            <SortTh k="points" />
            <SortTh k="bt_strength" />
          </tr>
        </thead>
        <tbody>
          {models.map((model, index) => (
            <tr key={model.id}>
              <td className="table__rank num">{index + 1}</td>
              <td>
                <Link to={`/models/${encodeURIComponent(model.id)}`}>{model.display_name}</Link>
                <div>
                  <ProviderBadge provider={model.provider} />
                </div>
              </td>
              <td className="num">{model.games}</td>
              <td className="num">
                {model.wins} / {model.losses} / {model.draws}
              </td>
              <td className="num">{percent(model.win_rate, 1)}</td>
              <td className="num">{percent(model.win_rate_as_black, 1)}</td>
              <td className="num">{percent(model.win_rate_as_white, 1)}</td>
              <td className="num" title={forfeitTitle(model)}>
                {percent(model.forfeit_loss_rate, 1)}
              </td>
              <td className="num">{duration(model.avg_response_time_ms)}</td>
              <td className="num" title="石数決着局における(自分の石 - 相手の石)の平均">
                {stoneDiff(model.avg_stone_diff)}
              </td>
              <td>
                <Meter value={model.points} max={maxPoints} label={formatPoints(model.points)} />
              </td>
              <td>
                <Meter
                  value={model.bt_strength}
                  max={maxStrength}
                  label={model.bt_strength.toFixed(3)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
