/** モデル詳細: 指標 + 対局履歴(相手モデル・勝敗で絞り込み)。 */

import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  GameHistoryTable,
  gameOutcome,
  outcomeLabel,
  type ResultFilter,
} from "../components/GameHistoryTable";
import { ProviderBadge } from "../components/ProviderBadge";
import { useRanking } from "../lib/api";
import { duration, percent, points as formatPoints } from "../lib/format";
import {
  FORFEIT_REASONS,
  FORFEIT_REASON_LABELS,
  type GameSummary,
  type ModelStats,
} from "../lib/types";

const OUTCOMES: ResultFilter[] = ["all", "win", "loss", "draw"];

export function ModelDetailPage() {
  const { modelId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [outcome, setOutcome] = useState<ResultFilter>("all");
  const { data, error, loading } = useRanking();

  const opponentId = searchParams.get("opponent");

  const modelsById = useMemo(
    () => new Map((data?.models ?? []).map((model) => [model.id, model])),
    [data],
  );
  const model = modelsById.get(modelId);

  const allGames = useMemo(() => {
    const games = (data?.games ?? []).filter(
      (game) => game.black === modelId || game.white === modelId,
    );
    return games.sort((a, b) => b.ended_at.localeCompare(a.ended_at));
  }, [data, modelId]);

  const opponents = useMemo(() => countOpponents(allGames, modelId), [allGames, modelId]);

  const visibleGames = allGames.filter((game) => {
    const other = game.black === modelId ? game.white : game.black;
    if (opponentId && other !== opponentId) return false;
    if (outcome !== "all" && gameOutcome(game, modelId) !== outcome) return false;
    return true;
  });

  if (loading) return <p className="state">読み込み中…</p>;
  if (error || !data) {
    return <p className="state">データを読み込めませんでした。{error?.message}</p>;
  }
  if (!model) {
    return (
      <p className="state">
        <span className="mono">{modelId}</span> は集計結果に含まれていません。
        <br />
        <Link to="/">ランキングへ戻る</Link>
      </p>
    );
  }

  const setOpponent = (next: string | null) => {
    const params = new URLSearchParams(searchParams);
    if (next) params.set("opponent", next);
    else params.delete("opponent");
    setSearchParams(params, { replace: true });
  };

  return (
    <>
      <p className="breadcrumb">
        <Link to="/">ランキング</Link> / {model.display_name}
      </p>

      <header>
        <p className="eyebrow">モデル詳細</p>
        <h1>{model.display_name}</h1>
        <div className="filters" style={{ marginTop: 4 }}>
          <ProviderBadge provider={model.provider} />
          <span className="muted mono">{model.id}</span>
        </div>
      </header>

      <section className="section">
        <div className="section__head">
          <h2>指標</h2>
          <span className="section__note">{model.games}局の集計</span>
        </div>
        <div className="metrics">
          <div className="metric">
            <div className="metric__label">勝点</div>
            <div className="metric__value">{formatPoints(model.points)}</div>
            <div className="metric__sub">
              {model.wins}勝 {model.losses}敗 {model.draws}分
            </div>
          </div>
          <div className="metric">
            <div className="metric__label">BT強さ(相対)</div>
            <div className="metric__value">{model.bt_strength.toFixed(3)}</div>
            <div className="metric__sub">全モデル合計が1になる正規化値</div>
          </div>
          <div className="metric">
            <div className="metric__label">平均応答時間</div>
            <div className="metric__value">{duration(model.avg_response_time_ms)}</div>
            <div className="metric__sub">1手あたり(パスを除く)</div>
          </div>
          <div className="metric">
            <div className="metric__label">勝率</div>
            <div className="rates">
              <RateBar label="全体" value={model.win_rate} />
              <RateBar label="先手" value={model.win_rate_as_black} />
              <RateBar label="後手" value={model.win_rate_as_white} />
            </div>
          </div>
          <div className="metric">
            <div className="metric__label">反則負け率</div>
            <div className="metric__value">{percent(model.forfeit_loss_rate, 1)}</div>
            <ForfeitBreakdown model={model} />
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section__head">
          <h2>対局履歴</h2>
          <span className="section__note">
            {visibleGames.length} / {allGames.length}局を表示
          </span>
        </div>

        <div className="filters">
          <span className="field__label">相手</span>
          <div className="chips">
            <button
              type="button"
              className="chip"
              aria-pressed={!opponentId}
              onClick={() => setOpponent(null)}
            >
              すべて<span className="chip__count">{allGames.length}</span>
            </button>
            {opponents.map(([id, count]) => (
              <button
                key={id}
                type="button"
                className="chip"
                aria-pressed={opponentId === id}
                onClick={() => setOpponent(id)}
              >
                {modelsById.get(id)?.display_name ?? id}
                <span className="chip__count">{count}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="filters">
          <span className="field__label">結果</span>
          <div className="chips">
            {OUTCOMES.map((value) => (
              <button
                key={value}
                type="button"
                className="chip"
                aria-pressed={outcome === value}
                onClick={() => setOutcome(value)}
              >
                {outcomeLabel(value)}
              </button>
            ))}
          </div>
        </div>

        <GameHistoryTable games={visibleGames} modelId={modelId} modelsById={modelsById} />
      </section>
    </>
  );
}

function RateBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="rate">
      <span className="rate__label">{label}</span>
      <span className="meter__track">
        <span className="meter__fill" style={{ width: `${Math.min(1, value) * 100}%` }} />
      </span>
      <span className="rate__value">{percent(value, 1)}</span>
    </div>
  );
}

/**
 * 反則理由の内訳。1〜2件しか出ない量なので、棒グラフではなく数値のチップで示す
 * (少数のカウントを面積で見せると精度を装ってしまうため)。
 */
function ForfeitBreakdown({ model }: { model: ModelStats }) {
  return (
    <div className="chips" style={{ marginTop: 8 }}>
      {FORFEIT_REASONS.map((reason) => {
        const count = model.forfeit_reasons[reason];
        return (
          <span key={reason} className="chip" style={{ opacity: count > 0 ? 1 : 0.5 }}>
            {FORFEIT_REASON_LABELS[reason]}
            <span className="chip__count">{count}</span>
          </span>
        );
      })}
    </div>
  );
}

function countOpponents(games: GameSummary[], modelId: string): [string, number][] {
  const counts = new Map<string, number>();
  for (const game of games) {
    const other = game.black === modelId ? game.white : game.black;
    counts.set(other, (counts.get(other) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}
