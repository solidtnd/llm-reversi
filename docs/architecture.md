# アーキテクチャ

## 目的

リバーシを打つアルゴリズム(強いAI)を作ることが目的ではない。リバーシのルール部分(合法手の列挙・石の反転・勝敗判定など)はアルゴリズムで実装し、**どこに石を置くかの意思決定は外部LLMに行わせて**、複数のLLMを同一条件で対戦させることでどのモデルが強いかを比較する。

## 全体構成

```
llm-reversi/
├── engine/   # 対戦エンジン(Python) — ローカル実行
├── web/      # 可視化用フロントエンド — 静的サイトとして配信
├── data/     # engineとwebの受け渡しデータ(棋譜JSON・リーグ結果)
└── docs/     # 設計・仕様ドキュメント
```

- **engine/web/data は完全に分離する。** 実行環境・依存関係管理が異なるため、コードレベルでは互いに依存しない。
- `data/` は「engineが書き出し、webが読み込む」ためだけの中立な受け渡し場所。engine/webどちらの所有物でもない。
- **`data/`はリポジトリにそのままコミットする(gitignoreしない)。** engineはローカル実行のみで、GitHub Pages公開用のビルドはCI上で対局を再生成できないため、公開に使うデータはリポジトリにコミットされている必要がある。
- 対局結果を絞り込んで公開する(いわゆる「ハイライト対局」の選定)ような**キュレーション工程は設けない**。`data/`の全量をそのまま公開対象とする。Web側には、必要に応じて生ログ(`llm_raw_response`等の診断情報)を閲覧できる機能を持たせる想定。

## engine (Python)

責務:
- 盤面管理(合法手判定・着手・終局判定)
- LLMプレイヤーの呼び出し(モデルごとのAdapter経由)
- リーグ運営(総当たり戦・先手後手入れ替え・勝敗集計)
- 棋譜・結果を`data/`へJSON出力

技術方針:
- LLM呼び出しの抽象化はLangChain等のフレームワークを使わず、**薄い自作Adapter層**で行う。1手ごとのシンプルな推論呼び出しには自作の方が開発速度・保守性で有利なため。フレームワーク導入はモデル追加や要件複雑化が進んだ場合に再検討する。
- 依存関係管理は `uv` を使用。

### モジュール構成

```
engine/
├── pyproject.toml
├── models.yaml
├── league.yaml
├── .env.example
└── reversi_engine/
    ├── board.py       # 盤面表現・合法手判定・着手・終局判定
    ├── game.py         # 1対局の進行(1手ごとの処理、パス/反則負け判定、タイムアウト)
    ├── adapters/
    │   ├── base.py      # LLMAdapter Protocol / MoveResponse
    │   ├── openai.py
    │   ├── anthropic.py
    │   └── gemini.py
    ├── league.py        # 総当たり組み合わせ生成・差分実行判定・並列実行制御
    ├── storage.py       # data/への棋譜JSON書き出し・JSONL追記(スレッドセーフ)
    ├── aggregate.py     # JSONL→ranking.json集計(docs/metrics.md参照)
    ├── config.py        # models.yaml / league.yaml 読み込み
    └── cli.py           # 試合実行(run-league)/集計実行(aggregate)の2コマンドのエントリポイント
```

薄いAdapter層の方針(1ファイル1プロバイダ)に合わせ、フラットな構成にする。

### 並列実行

- [docs/adapter-interface.md](adapter-interface.md)で`request_move`は同期呼び出しと定義済み(1対局内の手は逐次進行)。この上で、**対局単位**をスレッドプールで並列実行する(Adapter呼び出しはI/O待ちが中心のため、スレッドで十分な並列度が得られる。非同期化やマルチプロセス化は行わない)。
- 同時実行数は`league.yaml`の`concurrent_games`で管理する([docs/rules.md](rules.md#調整可能な値の管理方針)参照)。デフォルトは**4**。大きすぎると不具合発生時に原因の対局を特定しづらくなるため、無制限の並列化はしない。
- `data/results.jsonl`への追記は複数スレッドから発生するため、書き込みをロックで直列化し、行の破損・競合を防ぐ。
- **試合実行と集計実行は別コマンドとする。** 集計(`ranking.json`生成)は対局が完了するたびに自動実行するのではなく、全対局が終わった後に利用者が任意のタイミングで`aggregate`コマンドを実行する想定(docs/metrics.mdで決定済みの「集計スクリプトが全量を再生成する」方式と整合)。

### 最低限のガード(信頼性確保のため)

- LLM応答のJSONパース失敗時は1回リトライする。
- 非合法手を指した場合は失格、または当該試合を無効化する。
- 1手あたりの最大待ち時間を設ける。

## web (フロントエンド)

責務:
- モデルランキング表示(勝点方式・Bradley-Terry方式を併記)・対戦表(総当たりマトリクス)表示
- モデル詳細(個別指標・対局履歴)表示
- 棋譜リプレイ(手順再生)・生ログ閲覧(反則理由・LLMの生応答・トークン数など、`data/`が持つ診断情報を必要に応じて見られる機能)

技術方針:
- **React + Vite**を採用する。素のTypeScriptだと棋譜リプレイのような状態を伴うUIでコード量が増えがちなため避け、Vue/Svelteよりも情報量・実績が多くAI駆動開発(コード生成)と相性が良いReactを選ぶ。
- ルーティングは`react-router`の**`HashRouter`**を使う(例: `#/models/<id>`)。GitHub Pagesは素の静的ホスティングのため、パス型ルーティング(`BrowserRouter`)は直接アクセス・リロード時に404になる問題があり、回避には`404.html`にリダイレクトを仕込む工夫が必要になる。この工夫を丸ごと不要にするため`HashRouter`を選ぶ。
- 状態管理ライブラリ(Redux/Zustand等)は導入しない。表示専用アプリで、扱う状態は「fetchしてきたJSONをそのまま表示する」程度のため、Reactの標準的な`useState`/`useEffect`で十分。
- `data/`のJSONを表示専用で読み込む。engine側のロジックには依存しない。
- **GitHub Pagesでデプロイできる静的ファイル構成**を維持する(ビルド成果物のみで完結し、サーバーサイド処理を持たない)。キュレーションや絞り込みは行わず、`data/`の全量をそのままビルド成果物に取り込む。
- レスポンシブはCSS(flexbox/grid + メディアクエリ)のみで対応し、PC/スマホ専用の別コンポーネント・別ルートには分岐しない。対戦表のような横に長い表は、スマホでは横スクロールさせる。

### 画面構成

1. **トップ**: モデルランキング表(勝点方式/Bradley-Terry方式でソート切替、モデル名・provider名で検索/絞り込み可) + 対戦表(総当たりマトリクス)
2. **モデル詳細**(`#/models/<id>`): そのモデルの指標(勝率・先手後手別勝率・反則負け率とその内訳・平均応答時間・リトライ発生率) + 対局履歴(相手モデル・勝敗等で絞り込み可、対局詳細へのリンク付き)
3. **対局詳細**(`#/games/<game_id>`): 棋譜リプレイ(盤面 + 手送り操作、その時点の`legal_moves`のうち選ばれなかった手も盤面上に薄く表示) + 手ごとの生ログパネル(`llm_raw_response`・反則理由・トークン数・応答時間)

モデル名を表示する箇所(ランキング表・モデル詳細・対局詳細の対局者表示など)では、provider(OpenAI/Anthropic/Gemini)ごとのバッジを共通して表示する。

対局への導線は「モデル詳細ページの対局履歴」に統一する。対戦表のセルは、相手モデルで絞り込み済みの状態でモデル詳細ページ(例: `#/models/<id>?opponent=<other_id>`)へ遷移する形にし、「全対局を時系列で並べた一覧」のような独立ページは持たない。対局は常に「どのモデルの対局か」という文脈と共に閲覧する想定のため。

### モジュール構成

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
        ├── types.ts               # ranking.json・対局JSONの型定義([docs/log-schema.md](log-schema.md)・[docs/metrics.md](metrics.md)に対応)
        └── api.ts                 # ranking.jsonの取得・対局JSON個別取得のラッパ
```

### データ取り込み方式

- ビルド前処理(`scripts/copy-data.mjs`)で、リポジトリ直下の`data/`を丸ごと`web/public/data/`へ**コピー**する。シンボリックリンクはOS間の差異・CI環境での扱いが面倒なため避ける。
- `ranking.json`はアプリ起動時に1回fetchし、全画面(トップ・モデル詳細)で共有する。
- 個別対局JSON(`data/games/<game_id>.json`)は対局詳細ページを開いたときに初めてfetchする(全件の事前ロードはしない)。[docs/metrics.md](metrics.md)の`ranking.json`が`games`配列(軽量インデックス)を持つ設計は、この遅延fetchを支えるためのもの。

### デプロイ

GitHub Actionsで以下を1ワークフローとして実行する。

1. リポジトリをcheckout
2. Node.jsセットアップ・`web/`で依存関係インストール
3. `data/`を`web/public/data/`へコピー(`copy-data.mjs`)
4. `npm run build`
5. ビルド成果物をGitHub Pagesへ公開

## data (受け渡しデータ)

- 棋譜JSON、リーグ集計結果を格納。**リポジトリにコミットする。**
- スキーマは別途 `docs/log-schema.md` で定義する。
- ディレクトリ構成:

  ```
  data/
  ├── games/
  │   ├── <game_id>.json   # 棋譜JSON(1対局1ファイル)
  │   └── ...
  ├── results.jsonl         # 全対局の要約ログ(対局完了ごとに1行追記)
  └── ranking.json          # 集計結果(aggregateコマンド実行時に全量再生成)
  ```

  差分実行の方針([docs/rules.md](rules.md#リーグ運営)参照)上、リーグは実行のたびに増えていく1つの継続的な状態であり、実行日時・実行回ごとのフォルダ分けは行わない。

## 未決定事項

- [ ] フロントエンド実装を進めるためのスキル(何を使って実装するか)を検討する
