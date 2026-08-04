# engineアーキテクチャ

engine(Python)の構成方針。全体構成・engine/web/dataの分離方針は[../shared/architecture.md](../shared/architecture.md)を参照。

## 責務

- 盤面管理(合法手判定・着手・終局判定)
- LLMプレイヤーの呼び出し(モデルごとのAdapter経由)
- リーグ運営(総当たり戦・先手後手入れ替え・勝敗集計)
- 棋譜・結果を`data/`へJSON出力

## 技術方針

- LLM呼び出しの抽象化はLangChain等のフレームワークを使わず、**薄い自作Adapter層**で行う。1手ごとのシンプルな推論呼び出しには自作の方が開発速度・保守性で有利なため。フレームワーク導入はモデル追加や要件複雑化が進んだ場合に再検討する。
- 依存関係管理は `uv` を使用。

## モジュール構成

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
    ├── aggregate.py     # JSONL→ranking.json集計(../shared/metrics.md参照)
    ├── config.py        # models.yaml / league.yaml 読み込み
    └── cli.py           # 試合実行(run-league)/集計実行(aggregate)の2コマンドのエントリポイント
```

薄いAdapter層の方針(1ファイル1プロバイダ)に合わせ、フラットな構成にする。

## 並列実行

- [adapter-interface.md](adapter-interface.md)で`request_move`は同期呼び出しと定義済み(1対局内の手は逐次進行)。この上で、**対局単位**をスレッドプールで並列実行する(Adapter呼び出しはI/O待ちが中心のため、スレッドで十分な並列度が得られる。非同期化やマルチプロセス化は行わない)。
- 同時実行数は`league.yaml`の`concurrent_games`で管理する([rules.md](rules.md#調整可能な値の管理方針)参照)。デフォルトは**4**。大きすぎると不具合発生時に原因の対局を特定しづらくなるため、無制限の並列化はしない。
- `data/results.jsonl`への追記は複数スレッドから発生するため、書き込みをロックで直列化し、行の破損・競合を防ぐ。
- **試合実行と集計実行は別コマンドとする。** 集計(`ranking.json`生成)は対局が完了するたびに自動実行するのではなく、全対局が終わった後に利用者が任意のタイミングで`aggregate`コマンドを実行する想定(../shared/metrics.mdで決定済みの「集計スクリプトが全量を再生成する」方式と整合)。

## 最低限のガード(信頼性確保のため)

- LLM応答のJSONパース失敗時は1回リトライする。
- 非合法手を指した場合は失格、または当該試合を無効化する。
- 1手あたりの最大待ち時間を設ける。
