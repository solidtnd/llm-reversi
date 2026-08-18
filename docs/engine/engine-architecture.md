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
├── reversi_engine/
│   ├── board.py       # 盤面表現・合法手判定・着手・終局判定
│   ├── game.py         # 1対局の進行(1手ごとの処理、パス/反則負け判定、タイムアウト)
│   ├── adapters/
│   │   ├── base.py      # LLMAdapter Protocol / MoveResponse
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   └── gemini.py
│   ├── league.py        # 総当たり組み合わせ生成・差分実行判定・並列実行制御
│   ├── storage.py       # data/への棋譜JSON書き出し・JSONL追記(スレッドセーフ)
│   ├── aggregate.py     # JSONL→ranking.json集計(../shared/metrics.md参照)
│   ├── config.py        # models.yaml / league.yaml 読み込み
│   └── cli.py           # 試合実行(run-league)/集計実行(aggregate)の2コマンドのエントリポイント
└── tests/
    ├── conftest.py       # tests/をsys.pathに追加(サブディレクトリからも`import fakes`できるように)
    ├── fakes.py          # LLMAdapter Protocolを実装したFakeAdapter(テストダブル)
    ├── test_board.py
    ├── test_game.py
    ├── test_league.py
    ├── test_storage.py
    ├── test_config.py
    ├── test_aggregate.py
    ├── test_cli.py
    ├── adapters/         # 各プロバイダAdapterのプロンプト整形・パース処理の単体テスト
    │   ├── test_openai.py
    │   ├── test_anthropic.py
    │   └── test_gemini.py
    ├── live/             # 実APIに接続して動作確認するテスト(下記「テスト方針」参照)
    │   └── test_live_adapters.py
    └── generate_dummy_data.py  # FakeAdapterを使いdata/へダミー対局データを生成するスクリプト(下記「ダミーデータ生成」参照。`test_`接頭辞を付けずpytestの収集対象外にする)
```

薄いAdapter層の方針(1ファイル1プロバイダ)に合わせ、フラットな構成にする。

## テスト方針

- `game.py`・`league.py`の単体テストは、実プロバイダのSDKを呼ばず、`LLMAdapter` Protocol([adapter-interface.md](adapter-interface.md#共通インターフェースイメージ))を実装した`tests/fakes.py`の`FakeAdapter`を注入して行う。反則負け判定・タイムアウト処理・リトライ制御([rules.md](rules.md#1手ごとの処理))を、実際にAPIを呼ばずに検証できるようにするため。SDKを`unittest.mock`でpatchするのではなく、Protocolを満たす専用のテストダブルを使うことで、テストがプロバイダの違いに依存しなくなる。
  - `FakeAdapter`は、呼び出しごとに異なる応答/例外を返せる(例: 1回目は`AdapterParseError`、2回目は成功)、応答を遅延させられる(タイムアウト検証用)、呼び出し引数(`retry_reason`を含む)を記録できる、という機能を持つ。
  - タイムアウト検証では、実際に60秒待つのではなく、テスト実行時の`league.yaml`相当の設定(`timeout_seconds`)を短い値に差し替えて使う。
  - 加えて、`legal_moves`からランダムに1つ選んで返す「ランダムモード」も持つ。単体テストの決定的な検証には使わないが、[ダミーデータ生成](#ダミーデータ生成)で1手ごとに合法手を選び続けて対局を最後まで進めるために使う。LLMAdapter Protocolを満たす実装をテスト用・データ生成用で二重に持たないための選択。
- `adapters/*.py`(各プロバイダ実装)の単体テストは、プロバイダSDKのレスポンスを模したオブジェクトをテスト内で構築し、プロンプト整形・レスポンスのパース・`AdapterParseError`/`AdapterAPIError`への例外変換を検証する。実APIは呼ばない。
- 実際のプロバイダAPIに接続して動作確認するテストは`tests/live/`に分離し、通常の単体テスト実行には含めない(開発中に不要なAPI費用を発生させないため)。少数モデル・少数手数での手動実行を想定する。
  - 「含めない」の実現方法は、pytestの収集対象から外すのではなく**APIキーが未設定なら`pytest.skip`する**方式とする。`uv run pytest`を素で叩いたときに勝手にAPIを呼ばない一方で、テストの存在自体は実行結果(skip表示)から見えるため、テストが腐っていることに気付けるようにするため。実行時は`engine/.env`にキーを設定して`uv run pytest tests/live -v`のように明示的に呼ぶ。
  - 内容は「`models.yaml`のそのproviderの先頭モデルに、初期局面で1手だけ問い合わせ、合法手が返るか」を確認するものに留める(1テスト=1手なので費用も最小限)。リトライ用プロンプト(`retry_reason`付き)でも合法手が返るかも同様に確認する。

## ダミーデータ生成

web実装(表示確認)には実際のAPI呼び出しなしで`data/`にスキーマ準拠のデータが必要になる。手書きのJSONは64文字の`board_after`や着手履歴の整合性を壊しやすいため、`tests/generate_dummy_data.py`から`FakeAdapter`のランダムモードを使って実際に`League`/`Game`を走らせ、`data/`へ出力させる。

- `models.yaml`のprovider解決(`config.py`)は経由せず、スクリプト内で`FakeAdapter`インスタンスを直接組み立てる。カードの組み合わせ生成は`league.build_cards()`を再利用するが、対局ごとに別の応答パターンを仕込むため`League`は使わず`Game`を直接回す(`League`はモデルごとに1つのAdapterを共有するため、対局単位で振る舞いを変えられない)。
- 反則負け(`parse_failure`/`timeout`/`api_error`/`illegal_move`)・リトライ発生・複数provider混在・`usage`がnullのプロバイダなど、web側の表示確認で必要になるケースが最低1件ずつ含まれるよう、対局ごとに`FakeAdapter`の応答パターンを変えて生成する。**生成後にこれらの充足を検証し、欠けていたら異常終了する**(シナリオを変えた結果ケースが消えたことに気付けるようにするため)。
- pytestのテストスイートには含めない(`test_`接頭辞を付けないファイル名にすることで自動収集を避ける)、手動実行するスクリプトという位置付け。
- **出力は決定論的にする。** 着手のランダムシード・対局開始時刻・`game_id`のランダムサフィックスをすべて固定値から導出し、再実行しても同一内容が生成されるようにする。`data/`はコミット対象なので、再生成のたびに全ファイルが差分になるのを避けたいため。
- **応答時間は擬似時計で作る。** `Game`に注入する`clock`を「呼び出しごとに一定時間進む擬似時計」にして、実時間で待つことなく現実的な`response_time_ms`(数百ms〜)を持たせる。タイムアウトのケースも、実際に60秒待つのではなく擬似時計を特定の手だけ大きく進めて予算超過を再現する。
- **生ログ(`llm_raw_response`)はプロバイダのレスポンス形に似せる。** web側の生ログパネルの表示確認(thinkingブロックを含むレスポンス全体が入っている前提のUI)がダミーデータでも成立するようにするため、`FakeAdapter`を薄く継承して生ログだけ各社のレスポンス形のJSONに差し替える。着手の決め方は`FakeAdapter`のまま変えない。
- **既存データとの混在を防ぐ。** `data/results.jsonl`が既にある場合は中断し、`--reset`が指定されたときだけ既存の`games/`・`results.jsonl`・`ranking.json`を消してから生成する。

## 並列実行

- [adapter-interface.md](adapter-interface.md)で`request_move`は同期呼び出しと定義済み(1対局内の手は逐次進行)。この上で、**対局単位**をスレッドプールで並列実行する(Adapter呼び出しはI/O待ちが中心のため、スレッドで十分な並列度が得られる。非同期化やマルチプロセス化は行わない)。
- 同時実行数は`league.yaml`の`concurrent_games`で管理する([rules.md](rules.md#調整可能な値の管理方針)参照)。デフォルトは**4**。大きすぎると不具合発生時に原因の対局を特定しづらくなるため、無制限の並列化はしない。
- `data/results.jsonl`への追記は複数スレッドから発生するため、書き込みをロックで直列化し、行の破損・競合を防ぐ。
- **試合実行と集計実行は別コマンドとする。** 集計(`ranking.json`生成)は対局が完了するたびに自動実行するのではなく、全対局が終わった後に利用者が任意のタイミングで`aggregate`コマンドを実行する想定(../shared/metrics.mdで決定済みの「集計スクリプトが全量を再生成する」方式と整合)。

