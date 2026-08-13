/** モデルランキング表。勝点方式とBradley-Terry強さ推定を併記し、ソート軸を切り替える。 */

import { Link } from "react-router-dom";
import { duration, percent, points as formatPoints } from "../lib/format";
import { FORFEIT_REASON_LABELS, FORFEIT_REASONS, type ModelStats } from "../lib/types";
import { ProviderBadge } from "./ProviderBadge";

export type SortKey = "points" | "bt_strength";

interface Props {
  models: ModelStats[];
  sortKey: SortKey;
  onSortKeyChange: (key: SortKey) => void;
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

export function RankingTable({ models, sortKey, onSortKeyChange }: Props) {
  const maxPoints = Math.max(...models.map((model) => model.points), 0);
  const maxStrength = Math.max(...models.map((model) => model.bt_strength), 0);

  if (models.length === 0) {
    return <div className="table-wrap empty">条件に合うモデルがありません。</div>;
  }

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th className="table__rank">順位</th>
            <th>モデル</th>
            <th className="num">対局</th>
            <th className="num">勝 / 負 / 分</th>
            <th className="num">勝率</th>
            <th className="num">先手</th>
            <th className="num">後手</th>
            <th className="num">反則負け</th>
            <th className="num">平均応答</th>
            <th>
              <button
                type="button"
                className="table__sort"
                aria-pressed={sortKey === "points"}
                onClick={() => onSortKeyChange("points")}
              >
                勝点
              </button>
            </th>
            <th>
              <button
                type="button"
                className="table__sort"
                aria-pressed={sortKey === "bt_strength"}
                onClick={() => onSortKeyChange("bt_strength")}
              >
                BT強さ
              </button>
            </th>
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
