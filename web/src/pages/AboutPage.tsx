/**
 * 指標・対局条件についての説明。
 *
 * ランキング表・モデル詳細・対局詳細に表示される数値が何を意味し、
 * どういう条件で作られたデータかを説明する(サイトの企画経緯には触れない)。
 * 内容はdocs/shared/metrics.md・docs/engine/rules.mdの記述と対応するが、
 * このページ自身が随時最新化する前提で独立して書く。
 */

export function AboutPage() {
  return (
    <>
      <p className="eyebrow">About</p>
      <h1>指標 · 対局条件について</h1>
      <p className="lede">
        ランキング表 · モデル詳細 · 対局詳細に出てくる数値の意味と、対局がどういう条件で行われているかをまとめる。
      </p>

      <section className="section">
        <div className="section__head">
          <h2>対局条件</h2>
        </div>
        <div className="rows card" style={{ padding: "4px 16px" }}>
          <div className="rows__row">
            <span className="rows__key">着手の決定</span>
            <span className="rows__value">
              合法手の列挙 · 石の反転 · 勝敗判定はプログラムが行う。盤面と合法手一覧を提示し、どこに置くかだけを各LLMに決めさせる。全モデルに同一のプロンプトを与える。
            </span>
          </div>
          <div className="rows__row">
            <span className="rows__key">対戦形式</span>
            <span className="rows__value">
              全モデルの総当たり。同一カードは先手 · 後手を入れ替えて2局(先手 · 後手1回ずつ)対戦する。
            </span>
          </div>
          <div className="rows__row">
            <span className="rows__key">リトライ</span>
            <span className="rows__value">
              パース失敗 · APIエラーは原因を問わず1手あたり通算1回だけ再試行する。パース失敗時は直前の失敗理由をプロンプトにフィードバックし、APIエラー時は同一内容で再送する。
            </span>
          </div>
          <div className="rows__row">
            <span className="rows__key">反則負け</span>
            <span className="rows__value">
              合法手一覧にない着手はその場で反則負け(リトライしない)。1手30秒のタイムアウトを超えた場合も反則負けとする。反則負けは通常の対局と同じく記録 · 集計に含めるが、石数は記録しない(反則そのもので決着しており、石数で決着したわけではないため)。
            </span>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section__head">
          <h2>ランキング指標</h2>
        </div>
        <div className="rows card" style={{ padding: "4px 16px" }}>
          <div className="rows__row">
            <span className="rows__key">勝点方式</span>
            <span className="rows__value">
              勝ち1点 · 引き分け0.5点 · 負け0点の単純合計。
            </span>
          </div>
          <div className="rows__row">
            <span className="rows__key">Bradley-Terry強さ推定</span>
            <span className="rows__value">
              全対局結果から相手の強さを考慮して推定した相対的な強さ。ELOのような逐次更新と異なり全対局を一括で最尤推定するため、対局を処理する順序に結果が依存しない。全モデルの値の合計が1になるよう正規化してあり、値そのものが「相対的な強さの割合」を表す。
            </span>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section__head">
          <h2>モデル単位の指標</h2>
        </div>
        <div className="rows card" style={{ padding: "4px 16px" }}>
          <div className="rows__row">
            <span className="rows__key">勝率</span>
            <span className="rows__value">全体 · 先手時 · 後手時をそれぞれ別集計する。</span>
          </div>
          <div className="rows__row">
            <span className="rows__key">反則負け率</span>
            <span className="rows__value">
              非合法手 · タイムアウト · パース失敗 · APIエラーの内訳込みで表示する。安定性(ルールを守って対局を成立させ続けられるか)の指標として採用しているのはこの反則負け率のみで、応答時間のばらつきやリトライ発生率は指標化していない(応答時間はモデルのAPI応答特性に左右される要素が大きいため)。
            </span>
          </div>
          <div className="rows__row">
            <span className="rows__key">平均応答時間</span>
            <span className="rows__value">1手あたりの応答時間の平均(パスは除く)。参考情報であり安定性の指標としては扱わない。</span>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section__head">
          <h2>対局詳細で確認できること</h2>
        </div>
        <p className="lede">
          棋譜リプレイに加えて、手ごとにLLMの生応答 · 反則理由 · トークン数 · 応答時間を確認できる。指標はこれらの生ログを集計したものなので、数値の根拠を個々の対局まで遡って確認できる。
        </p>
      </section>
    </>
  );
}
