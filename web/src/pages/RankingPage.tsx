/** トップ: モデルランキング表 + 総当たり対戦表。 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { HeadToHeadMatrix } from "../components/HeadToHeadMatrix";
import {
  RankingTable,
  SORT_COLUMNS,
  sortModels,
  sortName,
  type Sort,
  type SortKey,
} from "../components/RankingTable";
import { ProviderBadge, providerLabel } from "../components/ProviderBadge";
import { useRanking } from "../lib/api";
import { dateTime, percent, points as formatPoints } from "../lib/format";
import type { ModelStats } from "../lib/types";

export function RankingPage() {
  const { data, error, loading } = useRanking();
  const [sort, setSort] = useState<Sort>({ key: "points", dir: "desc" });
  const [provider, setProvider] = useState<string | null>(null);

  const models = data?.models ?? [];

  /** provider → モデル数。絞り込みの選択肢はデータから作る(providerを決め打ちしない)。 */
  const providers = useMemo(() => {
    const counts = new Map<string, number>();
    for (const model of models) {
      counts.set(model.provider, (counts.get(model.provider) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [models]);

  const visible = useMemo(() => {
    const matched = provider ? models.filter((model) => model.provider === provider) : models;
    return sortModels(matched, sort);
  }, [models, provider, sort]);

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
  const leaders = visible.slice(0, 3);

  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">LLM × リバーシ</p>
          <h1>モデルランキング</h1>
          <p className="lede">
            同一のプロンプトを全モデルに与え、先手後手を入れ替えて総当たりで対局させた記録です。
            合法手の判定 · 石の反転 · 勝敗判定はプログラムが行い、着手そのものは各LLMが決定します。
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
          <p className="muted" style={{ marginTop: 16, fontSize: 12 }}>
            対局条件 · 指標の定義は<Link to="/about">指標 · 対局条件について</Link>を参照。
          </p>
        </div>

        <div className="leaders">
          <p className="leaders__caption">
            上位3モデル · {sortName(sort.key)}
            {sort.dir === "asc" ? "(小さい順)" : ""}
            {provider ? ` · ${providerLabel(provider)}のみ` : ""}
          </p>
          {leaders.map((model, index) => (
            <LeaderRow key={model.id} model={model} rank={index + 1} sortKey={sort.key} />
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section__head">
          <h2>ランキング</h2>
          <span className="section__note">
            列見出しを選ぶとその項目で並べ替え(同じ見出しをもう一度選ぶと昇降が反転)
          </span>
        </div>

        <div className="filters">
          <span className="field__label">プロバイダ</span>
          <div className="chips">
            <button
              type="button"
              className="chip"
              aria-pressed={!provider}
              onClick={() => setProvider(null)}
            >
              すべて<span className="chip__count">{models.length}</span>
            </button>
            {providers.map(([id, modelCount]) => (
              <button
                key={id}
                type="button"
                className="chip"
                aria-pressed={provider === id}
                onClick={() => setProvider(id)}
              >
                {providerLabel(id)}
                <span className="chip__count">{modelCount}</span>
              </button>
            ))}
          </div>
        </div>

        <RankingTable models={visible} sort={sort} onSortChange={setSort} />
      </section>

      <section className="section">
        <div className="section__head">
          <h2>対戦表</h2>
          <span className="section__note">セルを選ぶとそのカードの対局一覧へ</span>
        </div>
        {/* 絞り込みは行(見る側のモデル)だけに効かせる。列を絞ると同じproviderの
            組み合わせしか残らず、「他社モデルにどう勝ったか」が見えなくなるため。 */}
        <HeadToHeadMatrix rows={visible} columns={models} headToHead={data.head_to_head} />
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
 * 勝点以外の並べ替え軸では石を並べる意味がないため、値だけを見せる。
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
      <span className="leader__points">{SORT_COLUMNS[sortKey].format(model)}</span>
      {sortKey === "points" && (
        <span className="discs" aria-hidden="true">
          {Array.from({ length: whole }, (_, index) => (
            <span key={index} className="discs__disc" />
          ))}
          {hasHalf && <span className="discs__disc discs__disc--half" />}
        </span>
      )}
      <span className="leader__rank" style={{ gridColumn: "2 / -1", fontSize: 12 }}>
        <ProviderBadge provider={model.provider} /> 勝率 {percent(model.win_rate, 1)} ·{" "}
        {model.games}局
        {sortKey === "points" ? "" : ` · 勝点 ${formatPoints(model.points)}`}
      </span>
    </div>
  );
}
