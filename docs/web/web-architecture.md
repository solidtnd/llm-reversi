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
│   └── copy-data.mjs        # data/をweb/public/data/へコピーするビルド前処理
├── public/
│   └── data/                 # copy-data.mjsの出力先(gitignore対象、ビルド時に生成)
└── src/
    ├── main.tsx               # エントリポイント(HashRouterのセットアップ)
    ├── App.tsx                # ルーティング定義(3ルート)
    ├── pages/
    │   ├── RankingPage.tsx        # トップ: ランキング表 + 対戦表
    │   ├── ModelDetailPage.tsx    # モデル指標 + 対局履歴
    │   └── GameDetailPage.tsx     # 棋譜リプレイ + 生ログパネル
    ├── components/
    │   ├── RankingTable.tsx
    │   ├── ModelSearchBox.tsx     # モデル名・provider名での検索/絞り込み(RankingTableで使用)
    │   ├── ProviderBadge.tsx      # provider(OpenAI/Anthropic/Gemini)ごとのバッジ表示
    │   ├── HeadToHeadMatrix.tsx
    │   ├── GameHistoryTable.tsx   # モデル詳細内の対局履歴(相手モデルで絞り込み可能)
    │   ├── Board.tsx              # 64文字盤面文字列→盤面グリッド描画。選ばれなかったlegal_movesの薄い表示も担当
    │   ├── ReplayControls.tsx     # 手送り・自動再生の操作
    │   └── MoveLogPanel.tsx       # 生ログ・反則理由・トークン数・応答時間の表示
    └── lib/
        ├── types.ts               # ranking.json・対局JSONの型定義([../shared/log-schema.md](../shared/log-schema.md)・[../shared/metrics.md](../shared/metrics.md)に対応)
        └── api.ts                 # ranking.jsonの取得・対局JSON個別取得のラッパ
```

## テスト方針

自動テスト(unit/component/e2eいずれも)は導入しない。表示専用で、扱う状態も「fetchしてきたJSONをそのまま表示する」程度のため、自動テストのメンテナンスコストがロジックの複雑さに見合わない。動作確認は、[engine/engine-architecture.md#ダミーデータ生成](../engine/engine-architecture.md#ダミーデータ生成)で`data/`に生成したダミーデータを使い、`npm run dev`で人間が画面を目視確認する方法で行う。このため実装順としては、`data/`にダミーデータが存在する状態でweb実装に着手する(engine実装・ダミーデータ生成 → web実装の順)。

## データ取り込み方式

- ビルド前処理(`scripts/copy-data.mjs`)で、リポジトリ直下の`data/`を丸ごと`web/public/data/`へ**コピー**する。シンボリックリンクはOS間の差異・CI環境での扱いが面倒なため避ける。
- `ranking.json`はアプリ起動時に1回fetchし、全画面(トップ・モデル詳細)で共有する。
- 個別対局JSON(`data/games/<game_id>.json`)は対局詳細ページを開いたときに初めてfetchする(全件の事前ロードはしない)。[../shared/metrics.md](../shared/metrics.md)の`ranking.json`が`games`配列(軽量インデックス)を持つ設計は、この遅延fetchを支えるためのもの。

## デプロイ

GitHub Actionsで以下を1ワークフローとして実行する。

1. リポジトリをcheckout
2. Node.jsセットアップ・`web/`で依存関係インストール
3. `data/`を`web/public/data/`へコピー(`copy-data.mjs`)
4. `npm run build`
5. ビルド成果物をGitHub Pagesへ公開

## 実装に使うClaude Codeスキル

フロントエンド実装(このドキュメントの内容を元にコードを書くフェーズ)では、以下のスキルを使う。

- **`frontend-design`**(Anthropic公式プラグイン): デザイントークンやUIパターンを揃え、コンポーネントの見た目に一貫性を持たせるためのスキル。導入には`/plugin install`が必要。
- **`dataviz`**: グラフ・チャート・ダッシュボード作成のガイドスキル。モデルランキング表・対戦表・勝率比較などの可視化に使う。Claude Codeに標準搭載されており追加インストールは不要。

いずれもClaude Codeが自動判定して使う場合があるが、実装エージェントが確実に認識できるよう、実装を依頼する際はこの節を参照させること。

## 未決定事項

(現時点でなし)
