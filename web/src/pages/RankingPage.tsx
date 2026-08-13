/** トップ: モデルランキング表 + 総当たり対戦表。 */

import { useMemo, useState } from "react";
import { HeadToHeadMatrix } from "../components/HeadToHeadMatrix";
import { ModelSearchBox } from "../components/ModelSearchBox";
import { RankingTable, type SortKey } from "../components/RankingTable";
import { providerLabel } from "../components/ProviderBadge";
import { useRanking } from "../lib/api";
import { dateTime, percent, points as formatPoints } from "../lib/format";
import type { ModelStats } from "../lib/types";

const SORT_LABELS: Record<SortKey, string> = {
  points: "勝点方式",
  bt_strength: "Bradley-Terry強さ推定",
};

export function RankingPage() {
  const { data, error, loading } = useRanking();
  const [sortKey, setSortKey] = useState<SortKey>("points");
  const [query, setQuery] = useState("");

  const models = data?.models ?? [];
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matched = needle
      ? models.filter((model) =>
          [model.display_name, model.id, model.provider, providerLabel(model.provider)]
            .join(" ")
            .toLowerCase()
            .includes(needle),
        )
      : models;
    return [...matched].sort((a, b) => b[sortKey] - a[sortKey]);
  }, [models, query, sortKey]);

  if (loading) return <p className="state">読み込み中…</p>;
  if (error || !data) {
    return (
      <p className="state">
        データを読み込めませんでした。{error?.message}
        <br />
        <span className="muted">
          engineで対局を実行するか、ダミーデータを生成してから `npm run copy-data` を実行してください。
        </span>
      </p>
    );
  }

  const forfeitGames = data.games.filter((game) => game.reason === "forfeit").length;
  const leaders = [...models].sort((a, b) => b[sortKey] - a[sortKey]).slice(0, 3);

  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">LLM × リバーシ</p>
          <h1>
            石を数えて、
            <br />
            モデルの強さを比べる。
          </h1>
          <p className="lede">
            合法手の列挙・反転・勝敗判定だけをアルゴリズムが行い、どこに石を置くかは各LLMが決めます。
            全モデルに同じプロンプトを与え、先手後手を入れ替えて総当たりで戦わせた記録です。
          </p>
          <div className="stats">
            <div className="stat">
              <div className="stat__value">{data.games.length}</div>
              <div className="stat__label">対局</div>
            </div>
            <div className="stat">
              <div className="stat__value">{models.length}</div>
              <div className="stat__label">モデル</div>
            </div>
            <div className="stat">
              <div className="stat__value">{forfeitGames}</div>
              <div className="stat__label">反則負けで決着</div>
            </div>
          </div>
        </div>

        <div className="leaders">
          <p className="leaders__caption">上位3モデル · {SORT_LABELS[sortKey]}</p>
          {leaders.map((model, index) => (
            <LeaderRow key={model.id} model={model} rank={index + 1} sortKey={sortKey} />
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section__head">
          <h2>ランキング</h2>
          <span className="section__note">
            勝点方式とBradley-Terry強さ推定を併記(列見出しで切り替え)
          </span>
        </div>
        <ModelSearchBox
          value={query}
          onChange={setQuery}
          resultCount={filtered.length}
          totalCount={models.length}
        />
        <RankingTable models={filtered} sortKey={sortKey} onSortKeyChange={setSortKey} />
      </section>

      <section className="section">
        <div className="section__head">
          <h2>対戦表</h2>
          <span className="section__note">セルを選ぶとそのカードの対局一覧へ</span>
        </div>
        <HeadToHeadMatrix models={filtered} headToHead={data.head_to_head} />
      </section>

      <p className="muted" style={{ marginTop: 32, fontSize: 12 }}>
        集計日時: <span className="mono">{dateTime(data.generated_at)}</span>
      </p>
    </>
  );
}

/**
 * 上位モデルの勝点を石の数で表す。リバーシの「終局後に石を数える」動作をそのまま
 * 指標の読み方に持ち込む、この画面の signature 要素。数値も併記する。
 */
function LeaderRow({
  model,
  rank,
  sortKey,
}: {
  model: ModelStats;
  rank: number;
  sortKey: SortKey;
}) {
  const whole = Math.floor(model.points);
  const hasHalf = model.points - whole >= 0.5;
  return (
    <div className="leader">
      <span className="leader__rank">{rank}</span>
      <a className="leader__name" href={`#/models/${encodeURIComponent(model.id)}`}>
        {model.display_name}
      </a>
      <span className="leader__points">
        {sortKey === "points" ? `${formatPoints(model.points)}点` : model.bt_strength.toFixed(3)}
      </span>
      <span className="discs" aria-hidden="true">
        {Array.from({ length: whole }, (_, index) => (
          <span key={index} className="discs__disc" />
        ))}
        {hasHalf && <span className="discs__disc discs__disc--half" />}
      </span>
      <span className="leader__rank" style={{ gridColumn: "2 / -1", fontSize: 12 }}>
        勝率 {percent(model.win_rate, 1)} · {model.games}局
      </span>
    </div>
  );
}
