# webアーキテクチャ

web(フロントエンド)の構成方針。全体構成・engine/web/dataの分離方針は[../shared/architecture.md](../shared/architecture.md)を参照。

## 責務

- モデルランキング表示(勝点方式・Bradley-Terry方式を併記)・対戦表(総当たりマトリクス)表示
- モデル詳細(個別指標・対局履歴)表示
- 棋譜リプレイ(手順再生)・生ログ閲覧(反則理由・LLMの生応答・トークン数など、`data/`が持つ診断情報を必要に応じて見られる機能)

## 技術方針

- **React + Vite**を採用する。素のTypeScriptだと棋譜リプレイのような状態を伴うUIでコード量が増えがちなため避け、Vue/Svelteよりも情報量・実績が多くAI駆動開発(コード生成)と相性が良いReactを選ぶ。
- ルーティングは`react-router`の**`HashRouter`**を使う(例: `#/models/<id>`)。GitHub Pagesは素の静的ホスティングのため、パス型ルーティング(`BrowserRouter`)は直接アクセス・リロード時に404になる問題があり、回避には`404.html`にリダイレクトを仕込む工夫が必要になる。この工夫を丸ごと不要にするため`HashRouter`を選ぶ。
- 状態管理ライブラリ(Redux/Zustand等)は導入しない。表示専用アプリで、扱う状態は「fetchしてきたJSONをそのまま表示する」程度のため、Reactの標準的な`useState`/`useEffect`で十分。
- `data/`のJSONを表示専用で読み込む。engine側のロジックには依存しない。
- **GitHub Pagesでデプロイできる静的ファイル構成**を維持する(ビルド成果物のみで完結し、サーバーサイド処理を持たない)。キュレーションや絞り込みは行わず、`data/`の全量をそのままビルド成果物に取り込む。
- レスポンシブはCSS(flexbox/grid + メディアクエリ)のみで対応し、PC/スマホ専用の別コンポーネント・別ルートには分岐しない。対戦表のような横に長い表は、スマホでは横スクロールさせる。

## 画面構成

1. **トップ**: モデルランキング表(勝点方式/Bradley-Terry方式でソート切替、モデル名・provider名で検索/絞り込み可) + 対戦表(総当たりマトリクス)
2. **モデル詳細**(`#/models/<id>`): そのモデルの指標(勝率・先手後手別勝率・反則負け率とその内訳・平均応答時間・リトライ発生率) + 対局履歴(相手モデル・勝敗等で絞り込み可、対局詳細へのリンク付き)
3. **対局詳細**(`#/games/<game_id>`): 棋譜リプレイ(盤面 + 手送り操作、その時点の`legal_moves`のうち選ばれなかった手も盤面上に薄く表示) + 手ごとの生ログパネル(`llm_raw_response`・反則理由・トークン数・応答時間)
4. **About**(`#/about`): 指標(勝点方式/Bradley-Terry強さ推定・反則負け率など)の定義と対局条件(タイムアウト・リトライ・反則負けの扱い等)の説明。ヘッダー・フッター・トップページから導線を張る。サイトの企画経緯には触れない(「表示されている情報の意味・作られ方」だけを説明する)。内容はdocs(本ファイル・[../shared/metrics.md](../shared/metrics.md)・[../engine/rules.md](../engine/rules.md))の記述と対応するが、このページ自身が随時最新化する前提でdocsへの参照は行わず独立して書く。

モデル名を表示する箇所(ランキング表・モデル詳細・対局詳細の対局者表示など)では、provider(OpenAI/Anthropic/Gemini)ごとのバッジを共通して表示する。

対局への導線は「モデル詳細ページの対局履歴」に統一する。対戦表のセルは、相手モデルで絞り込み済みの状態でモデル詳細ページ(例: `#/models/<id>?opponent=<other_id>`)へ遷移する形にし、「全対局を時系列で並べた一覧」のような独立ページは持たない。対局は常に「どのモデルの対局か」という文脈と共に閲覧する想定のため。

## モジュール構成

```
web/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── scripts/
│   ├── copy-data.mjs        # data/をweb/public/data/へコピーするビルド前処理
│   └── screenshot.mjs       # デザイン確認用のスクリーンショット撮影(下記「テスト方針」参照)
├── public/
│   └── data/                 # copy-data.mjsの出力先(gitignore対象、ビルド時に生成)
└── src/
    ├── main.tsx               # エントリポイント(HashRouterのセットアップ)
    ├── App.tsx                # ルーティング定義(4ルート)+ 共通レイアウト(ヘッダーのGitHubリンク・テーマ切り替えを含む)
    ├── styles.css             # デザイントークンと全画面共通スタイル(1ファイルに集約)
    ├── pages/
    │   ├── RankingPage.tsx        # トップ: ランキング表 + 対戦表
    │   ├── ModelDetailPage.tsx    # モデル指標 + 対局履歴
    │   ├── GameDetailPage.tsx     # 棋譜リプレイ + 生ログパネル
    │   └── AboutPage.tsx          # 指標・対局条件の説明
    ├── components/
    │   ├── RankingTable.tsx
    │   ├── ModelSearchBox.tsx     # モデル名・provider名での検索/絞り込み(RankingTableで使用)
    │   ├── ProviderBadge.tsx      # provider(OpenAI/Anthropic/Gemini)ごとのバッジ表示
    │   ├── HeadToHeadMatrix.tsx
    │   ├── GameHistoryTable.tsx   # モデル詳細内の対局履歴(相手モデルで絞り込み可能)
    │   ├── Board.tsx              # 64文字盤面文字列→盤面グリッド描画。選ばれなかったlegal_movesの薄い表示も担当
    │   ├── ReplayControls.tsx     # 手送り・自動再生の操作
    │   ├── MoveLogPanel.tsx       # 生ログ・反則理由・トークン数・応答時間の表示
    │   ├── Icons.tsx               # ヘッダー用アイコン(GitHub・ライト/ダーク)。外部アイコンライブラリは使わずインラインSVGで持つ
    │   └── ThemeToggle.tsx         # ライト/ダークモードの手動切り替えボタン
    └── lib/
        ├── types.ts               # ranking.json・対局JSONの型定義([../shared/log-schema.md](../shared/log-schema.md)・[../shared/metrics.md](../shared/metrics.md)に対応)
        ├── api.ts                 # ranking.jsonの取得・対局JSON個別取得のラッパ(取得結果のキャッシュとhookを含む)
        ├── board.ts               # 盤面文字列の表示用ヘルパ(初期配置の定数・座標変換・石数カウントのみ)
        └── format.ts              # 数値・時刻の表示整形
```

`lib/board.ts`に**リバーシのルール(合法手判定・反転)は置かない**。webは`board_after`を並べるだけでよい設計([../shared/log-schema.md](../shared/log-schema.md)の「`board_before`は持たない」)なので、ここにあるのはリプレイの開始局面に使う初期配置の定数と、スコア表示のための石数カウントだけに限る。

## テスト方針

自動テスト(assertion付きのunit/component/e2eいずれも)は導入しない。表示専用で、扱う状態も「fetchしてきたJSONをそのまま表示する」程度のため、自動テストのメンテナンスコストがロジックの複雑さに見合わない。動作確認は、[engine/engine-architecture.md#ダミーデータ生成](../engine/engine-architecture.md#ダミーデータ生成)で`data/`に生成したダミーデータを使い、`npm run dev`で人間が画面を目視確認する方法で行う。このため実装順としては、`data/`にダミーデータが存在する状態でweb実装に着手する(engine実装・ダミーデータ生成 → web実装の順)。

- **`scripts/screenshot.mjs`(`npm run screenshot`)はassertionを持たない撮影専用ツール**で、上記の「自動テストは導入しない」方針とは矛盾しない。人間(またはコードを書くAI自身)がスマホ幅を含む複数ビューポートのレイアウトを画像で目視確認するための道具であり、`npm run build`・CIには組み込まない。実行にはPlaywright(devDependency)を使うが、追加のブラウザダウンロードを避けるためWindowsに標準搭載の`msedge`チャンネルを使う。
- レイアウト崩れはブラウザを実際に開かないと見えない(型チェック・SSRスモークテストでは検出できない)ため、スマホ幅の余白・タップ領域・横スクロール表の見え方を確認する際はこのスクリプトで撮影してから判断する。

## データ取り込み方式

- ビルド前処理(`scripts/copy-data.mjs`)で、リポジトリ直下の`data/`を丸ごと`web/public/data/`へ**コピー**する。シンボリックリンクはOS間の差異・CI環境での扱いが面倒なため避ける。
- `ranking.json`はアプリ起動時に1回fetchし、全画面(トップ・モデル詳細)で共有する。
- 個別対局JSON(`data/games/<game_id>.json`)は対局詳細ページを開いたときに初めてfetchする(全件の事前ロードはしない)。[../shared/metrics.md](../shared/metrics.md)の`ranking.json`が`games`配列(軽量インデックス)を持つ設計は、この遅延fetchを支えるためのもの。

## デザイン方針

実装時に決めた見た目の方針。

- **色はデータと盤面にしか使わない。** UIの装飾色(アクセントカラー)を持たず、リンク・選択状態はインク(黒/白)と罫線・下線で表す。色を大きく使う場所を盤面の緑1色に集約することで、provider色や対戦表の配色が「意味のある色」として読めるようにする。
- **配色は`dataviz`スキルの検証済みパレットから採り、検証スクリプトを通した組み合わせだけを使う。**
  - provider(OpenAI/Anthropic/Gemini)は識別(categorical)なので3スロット(aqua/orange/violet)。全ペア条件でCVD分離を満たす組み合わせを選んでいる。明度コントラストが3:1未満のスロットを含むため、**バッジは必ずラベル文字と併記**し色だけで識別させない。
  - 対戦表のセルは「行のモデルから見た勝ち越し度」という**極性**なので発散(diverging)配色(青↔赤、中央は無彩色)。provider色と用途がぶつからないよう、providerには青系を割り当てない。セルには常に「勝-分-負」の数値も表示する。
  - ランキング表のセル内バーは値の大きさ(magnitude)なので**無彩色**にする。順位ではなく値を表すものなので、色で意味を追加しない。
  - 反則理由の内訳は1〜2件しか出ない量なので、棒グラフにせず数値のチップで示す(少数のカウントを面積で見せると精度を装うため)。
- **数値・座標・対局IDは等幅フォント、見出しはゴシックの太字。** 棋譜(`d3`のような代数記法)を扱う画面なので、桁が揃うことと座標が読みやすいことを優先する。
- **ダークモードは既定で`prefers-color-scheme`に従うが、ヘッダーのボタンで手動上書きできる。** 初期値は端末設定どおり(明色を単純反転させず、暗い面用に選び直した値を使う点はdatavizスキルの方針のまま)。一度切り替えた後はその選択を`localStorage`に保持し、以後は端末設定の変化を追わない。実装は`<html data-theme="light"|"dark">`属性の有無で切り替え、CSS側は`:root`(既定)・`@media (prefers-color-scheme: dark)`配下の`:root:not([data-theme="light"])`・`:root[data-theme="dark"]`の3箇所にトークンを持つ(前者2つが「端末設定に従う」経路、3つ目が明示的な上書き)。index.htmlの初回描画前に`localStorage`を読んで属性を先に立てる小さなインラインスクリプトを置き、切り替え後の再訪問時に一瞬だけ元の配色が見えてしまう(FOUC)のを防ぐ。
- 盤面の石はCSSトランジションで色が変わるが、`prefers-reduced-motion`が指定されていればアニメーションしない。
- **ヘッダーのアイコン(GitHubリンク・テーマ切り替え)は外部アイコンライブラリを導入せず、インラインSVG(`components/Icons.tsx`)で持つ。** GitHubリンク1つ・テーマ切り替え1つのためだけに依存を増やすのは不釣り合いなため。
- **トップページのヒーローにキャッチコピー的な文言は置かない。** 想定読者はモデル比較を検討するエンジニアであり、外向けの惹句よりも「対局条件・指標の定義がどこで確認できるか」を優先する。見出しは機能名(「モデルランキング」)とし、指標・対局条件の説明は`/about`ページに独立させる(画面構成の「4. About」参照)。

## デプロイ

GitHub Actionsで以下を1ワークフローとして実行する(`.github/workflows/deploy-pages.yml`)。

1. リポジトリをcheckout
2. Node.jsセットアップ・`web/`で依存関係インストール
3. `data/`を`web/public/data/`へコピー(`copy-data.mjs`。`npm run build`の`prebuild`で自動実行される)
4. `npm run build`
5. ビルド成果物をGitHub Pagesへ公開

- 公開にはリポジトリ設定の Settings > Pages > Source を「GitHub Actions」にする必要がある。
- Viteの`base`は`"./"`(相対パス)にする。プロジェクトページ(`https://<user>.github.io/<repo>/`)でもリポジトリ名をビルド時に知らずに動かせるため。HashRouterと組み合わせるとリロード時の404も起きない。

## 実装に使うClaude Codeスキル

フロントエンド実装(このドキュメントの内容を元にコードを書くフェーズ)では、以下のスキルを使う。

- **`frontend-design`**(Anthropic公式プラグイン): デザイントークンやUIパターンを揃え、コンポーネントの見た目に一貫性を持たせるためのスキル。導入には`/plugin install`が必要。
- **`dataviz`**: グラフ・チャート・ダッシュボード作成のガイドスキル。モデルランキング表・対戦表・勝率比較などの可視化に使う。Claude Codeに標準搭載されており追加インストールは不要。

いずれもClaude Codeが自動判定して使う場合があるが、実装エージェントが確実に認識できるよう、実装を依頼する際はこの節を参照させること。

## 未決定事項

(現時点でなし)
