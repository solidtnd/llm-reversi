# LLM Reversi

複数のLLMにリバーシを対戦させ、モデル間の強さを比較するアプリケーション。

社内レク企画として、AI駆動開発(バイブコーディング)を試すプロジェクトでもある。実装のほとんどをAIに書かせて開発を進める。

## 構成

| フォルダ | 役割 |
| --- | --- |
| [`engine/`](engine/) | 対戦エンジン(Python)。盤面管理・LLM呼び出し・リーグ運営・棋譜出力を担当。 |
| [`web/`](web/) | 可視化用フロントエンド。ランキング・対戦表・棋譜リプレイを表示する静的サイト。 |
| [`data/`](data/) | `engine/`が書き出し`web/`が読み込む棋譜JSON・リーグ結果(受け渡し用)。 |
| [`docs/`](docs/) | 設計・仕様ドキュメント。 |

詳細な設計方針は [`docs/`](docs/) を参照(読むべきファイルの索引は [`docs/README.md`](docs/README.md))。

## セットアップ

必要なもの: [uv](https://docs.astral.sh/uv/)(engine)、Node.js 20以上(web)。

### engine(対戦エンジン)

```sh
cd engine
uv sync                      # 依存関係のインストール
cp .env.example .env         # APIキーを設定(OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY)

uv run pytest                # テスト(tests/live/はAPIキー未設定ならskip)
uv run reversi-engine run-league --dry-run   # 実行予定のカードを確認(APIキー不要)
uv run reversi-engine run-league             # 未実施カードの対局を実行
uv run reversi-engine aggregate              # data/results.jsonl から ranking.json を生成
```

出場モデルは [`engine/models.yaml`](engine/models.yaml)、タイムアウトや同時実行数は [`engine/league.yaml`](engine/league.yaml) で設定する。実行済みのカードは再実行されないので、モデルを追加したらもう一度 `run-league` を実行すればよい。

APIを呼ばずに画面を確認したい場合は、ダミーの対局データを生成できる。

```sh
cd engine
uv run python tests/generate_dummy_data.py --reset   # data/ を作り直す
```

### web(可視化)

```sh
cd web
npm install
npm run dev      # http://localhost:5173/ (data/ のコピーは自動実行される)
npm run build    # 型チェック + 静的ファイルの生成(dist/)
```

`main`ブランチへのpushでGitHub Pagesへ公開される([`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml))。初回のみリポジトリ設定の Settings > Pages > Source を「GitHub Actions」にする必要がある。
