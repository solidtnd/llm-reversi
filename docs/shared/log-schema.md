# 棋譜JSONスキーマ

`data/` に出力する、1対局分の棋譜JSONの構造。[../engine/rules.md](../engine/rules.md) で定義したルール・反則負けの扱いを反映する。

## ファイル形式(JSON / JSONL)

- **1対局分の棋譜ファイル自体は素のJSON**とする(1ファイル1オブジェクト)。Webは対局ごとにまるごとfetchして`JSON.parse`するだけで済むため。
- **リーグ実行中にengineが逐次書き出す結果ログはJSONL**(1行1対局の要約)とする。対局が完了するたびに1行追記するだけで済み、巨大なJSON配列を毎回書き直すより壊れにくいため。
- このJSONLはengine内部の実行ログであり、Webはこれを直接読まない。**集計スクリプト(`aggregate.py`)はこのJSONLのみを読み込み**、[metrics.md](metrics.md)の指標を計算した上で、Web用の`ranking.json`等の読みやすいJSONへ変換する(対局ごとの完全な棋譜JSON本体は集計時に読まない。行スキーマは[対局結果ログ(`data/results.jsonl`)](#対局結果ログdataresultsjsonl)を参照)。[../engine/rules.md](../engine/rules.md#リーグ運営)の差分実行判定(対戦済みモデル組み合わせの判定)にも、このJSONLの`black.id`/`white.id`を使う。

## トップレベル構造

```json
{
  "game_id": "string",
  "players": {
    "black": {
      "id": "string",
      "model": "string",
      "provider": "string",
      "display_name": "string",
      "config": { "temperature": 0.0, "thinking_effort": "..." }
    },
    "white": {
      "id": "string",
      "model": "string",
      "provider": "string",
      "display_name": "string",
      "config": { "...": "..." }
    }
  },
  "result": {
    "winner": "black | white | draw",
    "reason": "score | forfeit",
    "score": { "black": 0, "white": 0 } | null
  },
  "moves": [ /* Move[] (下記) */ ],
  "started_at": "ISO8601 string",
  "ended_at": "ISO8601 string"
}
```

- `game_id`は、対局開始時刻を元にした文字列とする。フォーマットは`{開始時刻(UTC, YYYYMMDDTHHMMSSffffff)}-{6桁のランダムhex}`(例: `20260803T143205123456-a1b2c3`)。文字列としてソートすれば時系列順になる。並列実行時に同一マイクロ秒で対局が開始してもファイル名(`data/games/<game_id>.json`)が衝突しないよう、ランダムサフィックスを付与する。コロン(`:`)はWindowsのファイル名に使えないため使用しない。
- `result.score`は、`reason: "score"`(通常の終局)の場合のみ石数を記録し、`reason: "forfeit"`の場合は`null`とする(詳細・理由は[../engine/rules.md](../engine/rules.md#1手ごとの処理)参照)。反則発生時点の盤面が必要な場合は`moves`配列の最後の要素の`board_after`を参照する。
- `id`は、[../engine/adapter-interface.md](../engine/adapter-interface.md)の`models.yaml`で定義したプレイヤー識別子をそのまま転記する。同じ`model`でも`config`違い(thinkingあり/なし等)を別プレイヤーとして対戦させる運用のため、集計時にモデルの同一性を判定する一意なキーとして`model`ではなく`id`を使う([metrics.md](metrics.md#ランキング指標)のBradley-Terry推定・リーグ結果JSONの集計で使用)。
- `provider`は、[../engine/adapter-interface.md](../engine/adapter-interface.md)のAdapterがラップするAPI/SDKの識別名をそのまま使う(例: `"openai"`, `"anthropic"`, `"gemini"`)。APIリクエスト時に指定する値と同一にすることで、変換表を別途持たずに済む。
- `display_name`は、[../engine/adapter-interface.md](../engine/adapter-interface.md#モデル一覧設定ファイルenginemodelsyaml)の`models.yaml`に定義した表示用文字列(例: `"Claude Opus 4.1 (Thinkあり)"`)をそのまま転記する。Web側はこの値をそのまま表示に使い、`models.yaml`自体には依存しない([architecture.md](architecture.md)のengine/web分離方針)。
- `config`は、対局に使ったモデル固有の設定値をそのまま記録する自由形式のオブジェクト(thinkingモードの有無・reasoning effort・temperature等)。モデル間で項目名を統一・正規化することはしない。将来的にプロバイダ側でパラメータが追加・廃止されても、本スキーマ側の変更なしに追従できるようにするため、キーはモデル/Adapter依存のまま素通しする。実験の再現性を担保するための情報であり、[../engine/adapter-interface.md](../engine/adapter-interface.md)の設定ファイル(モデル一覧)の値をそのまま転記する想定。

## Move(1手ごとの記録)

```json
{
  "turn": 1,
  "player": "black | white",
  "type": "move | pass | forfeit",
  "position": "d3 | null",
  "board_after": "64文字の盤面文字列(例: '.'=空, 'b'=黒, 'w'=白)",
  "legal_moves": ["d3", "c4", "..."],
  "llm_raw_response": "string | null",
  "retried": "none | parse_failure | api_error",
  "response_time_ms": 1234,
  "forfeit_reason": "illegal_move | timeout | parse_failure | api_error | null",
  "error_detail": "string | null",
  "usage": { "prompt_tokens": 123, "completion_tokens": 45 }
}
```

- `type: "pass"` の場合、`position`はnull(LLMに問い合わせないため)。同じ理由で`legal_moves`は空配列、`llm_raw_response`・`usage`はnull、`retried`は`"none"`、`response_time_ms`は`0`になる。
- `response_time_ms`は、**その手の処理全体(初回呼び出し + リトライ + その間の処理)の経過時間**をミリ秒で記録する。Adapter呼び出し1回だけの時間にしないのは、[../engine/rules.md](../engine/rules.md#タイムアウトの扱い)のタイムアウトが「1手あたりの処理全体の予算」として定義されており、同じ尺度で記録しておくと予算超過との突き合わせができるため。
- `type: "forfeit"` の場合、`forfeit_reason`に理由を記録し、その手で対局は終了する。`position`は`forfeit_reason: "illegal_move"`のときのみ**モデルが返した非合法な着手位置**を記録し、それ以外の理由(`timeout`/`parse_failure`/`api_error`)では着手位置が確定していないためnullとする。`illegal_move`の`error_detail`が常にnullなのは「原因は`position`・`legal_moves`を見れば分かる」という前提に立つためで、ここをnullにすると原因が追えなくなる。
- `retried`は、この手でリトライが発生したかどうかと、発生した場合の原因を表す([../engine/rules.md](../engine/rules.md#1手ごとの処理)参照)。**1手あたりのリトライは原因(パース失敗/APIエラー)を問わず通算1回までなので、`retried`は「リトライ有無」と「その1回の原因」をまとめて表現できるenumとし、`parse_failure`と`api_error`が同時に発生したことを表す値(`"both"`のような)は持たない**。値は以下の3つ。
  - `"none"`: リトライは発生しなかった(1回目の応答で成功、またはリトライ前に反則負けが確定した)。
  - `"parse_failure"`: パース失敗が原因でリトライが発生した。
  - `"api_error"`: APIエラーが原因でリトライが発生した。
  - リトライ後に(原因を問わず)再度失敗した場合、その最終結果は`forfeit_reason`に記録される。`retried`はあくまで「リトライを使ったか・何が引き金だったか」を示すフィールドであり、`forfeit_reason`とは独立している(例: `api_error`でリトライ後、2回目はパース失敗で反則負けした場合、`retried: "api_error"`かつ`forfeit_reason: "parse_failure"`になる)。
- **`llm_raw_response`は、リトライがあった場合も最終的なレスポンス1件のみを記録する**(成功した場合はその成功レスポンス、リトライしても最後まで失敗した場合は最後の失敗レスポンス)。リトライ前の失敗レスポンスは保持しない。リトライが発生したこと自体は`retried`で分かれば十分なため。
- `error_detail`は、モデルの応答内容である`llm_raw_response`とは区別し、**Adapterが送出した例外([../engine/adapter-interface.md](../engine/adapter-interface.md#エラー通知)の`AdapterParseError`/`AdapterAPIError`)由来のデバッグ情報**を記録するフィールドとする。`forfeit_reason`ごとの扱いは以下の通り。
  - `illegal_move`: 常に`null`。パース自体は成功しており例外が関与しないため(原因は`position`・`legal_moves`を見れば分かる)。
  - `parse_failure` / `api_error`: 反則負けを確定させた例外の`message`(`api_error`の場合は`original_exception`も)を記録する。
  - `timeout`: この手の処理中(初回またはリトライ時)に例外が1件でも発生していれば、直近に発生した例外の`message`(`AdapterAPIError`なら`original_exception`も)を記録する。何の例外も発生せずに(単に応答が遅く)予算超過した場合は`null`とする。
  - この規則は[../engine/rules.md](../engine/rules.md#1手ごとの処理)の`retried`(リトライの引き金)と整合する。`retried`が「どの例外でリトライしたか」を示す一方、`error_detail`はその例外(または最終的に反則負けを確定させた例外)の詳細メッセージを示す。
- `usage`は、LLMのAPIレスポンスに含まれるトークン数(input/output)をそのまま記録する。ほとんどのプロバイダのレスポンスに標準で含まれており記録の手間がないため。**コスト(金額)はここには記録しない**。プロバイダによってはレスポンスに金額が含まれず、含める場合は別途モデル別の単価テーブルをどこかに持つ必要が生じ、単価改定のたびにドキュメント・コードの更新が必要になる。金額が必要な場合は`data/`集計時に`usage`とモデル別単価表から都度算出する(単価表自体は本スキーマの対象外、集計スクリプト側の関心事)。レスポンスにトークン数が含まれないプロバイダの場合は`usage`全体を`null`とする。
- `board_before`は持たない。前の手の`board_after`(1手目の場合は標準初期配置)と常に同一で冗長なため。Web側では`board_after`を先頭から並べるだけで盤面推移を再現でき、独自にリバーシの反転ロジックを実装する必要がない。

## 対局結果ログ(`data/results.jsonl`)

1行1対局の要約。集計スクリプト(`aggregate.py`)の唯一の入力であり、[../engine/rules.md](../engine/rules.md#リーグ運営)の差分実行判定(対戦済みモデル組み合わせの判定)にも使う。

```json
{
  "game_id": "string",
  "black": { "id": "string", "provider": "string", "display_name": "string", "avg_response_time_ms": 1234 },
  "white": { "id": "string", "provider": "string", "display_name": "string", "avg_response_time_ms": 1500 },
  "winner": "black | white | draw",
  "reason": "score | forfeit",
  "forfeit_reason": "illegal_move | timeout | parse_failure | api_error | null",
  "ended_at": "ISO8601 string"
}
```

- 対局本体の棋譜JSON(上記[トップレベル構造](#トップレベル構造))から、[metrics.md](metrics.md)の指標計算・表示に必要な値だけを抜き出した要約。`black`/`white`はそれぞれ`players`の`id`・`provider`・`display_name`と、その対局における平均応答時間(`Move.response_time_ms`の単純平均)を持つ。**パス(`type: "pass"`)の手は平均から除外する**(LLMを呼ばず応答時間を持たない手を0msとして混ぜると、パスが多い対局ほど平均が不当に短くなるため)。
- **`provider`・`display_name`を指標計算に使わないにもかかわらずこの要約に含めるのは、集計を`models.yaml`から独立させるため。** これらを持たせないと、集計時に表示名を`models.yaml`(設定ファイル)から引く必要が生じ、「APIエラーで対戦をやめたモデルを`models.yaml`から削除する」といった通常の運用をしただけで、そのモデルの過去の対局の表示名が失われてしまう(`models.yaml`は「今後どのモデルを対戦させるか」を宣言する設定であり、過去に何が対戦したかの記録ではない)。棋譜JSON本体(`data/games/*.json`)も同じ値を持つが、集計時にそちらを読みには行かない([ファイル形式](#ファイル形式json--jsonl)の「集計スクリプトはこのJSONLのみを読み込む」方針を維持するため。表示名という小さな文字列のために、全手・LLMの生応答を含む重いファイルを対局数分開くのは本末転倒)。要約行なので`id`と同様に対局ごとに値が重複するが、正規化はしない。
- `provider`・`display_name`には**その対局を行った時点の値**が入る。同一`id`のまま`display_name`を後から変更した場合、`ranking.json`の`models[]`は1モデル1エントリなので代表値を1つ選ぶ必要があり、**行を読み進めた順で後勝ち**(=最後に対戦した時点の値)とする。`results.jsonl`は追記専用でファイル内が時系列順に並ぶため、単純に上書きしていくだけで最新の表示名になる。手数による加重平均は行わない(平均応答時間は[metrics.md](metrics.md#安定性の指標)の通り参考情報の位置づけであり、そこまでの精度を必要としないと判断したため)。
- `Move.retried`(リトライ)に関する集計値は持たない。リトライは最終的に成功すれば対局結果に影響しない一時的な事象であり、モデルの安定性は`forfeit_reason`の集計だけで測れると判断したため([metrics.md](metrics.md#安定性の指標)参照)。特定の対局でリトライが起きたかどうかを確認したい場合は、棋譜JSON本体の`Move.retried`を見る(この要約には出てこない)。
- `score`(石数)は持たない。[metrics.md](metrics.md)で定義する指標に石数差は含まれないため。
- この1行は、そのまま`ranking.json`の`games`配列の要素(の一部)になる([metrics.md](metrics.md)参照)。

## 未決定事項

(現時点でなし)

## 既存フォーマットとの関係

オセロには既存の棋譜フォーマット(WTHOR形式、GGF形式など)が存在するが、以下の理由から独自JSONを採用する。

- **WTHOR形式**: バイナリ形式で、大量対局のアーカイブ用途向け。JSONベースのWeb可視化と相性が悪い。
- **GGF形式**: プレイヤー名・結果・着手リストを持つテキスト形式だが、本プロジェクトで必要な「LLMの生応答」「反則理由」「リトライ有無」「応答時間」といったLLM対戦特有の情報を持つ余地がない。
- **SGF形式**: 手ごとのコメント(`C`)や、標準にないプロパティを追加できる拡張規定があり、GGFより自由度は高い。ただし(a)公式仕様でオセロが正式サポートされているわけではなくEdax/WZebra等が独自対応している状況、(b)拡張プロパティは非標準のため他のSGF対応ツールとの互換性はなく、独自JSONスキーマを設計するのと実質的な手間は変わらない、(c)ツリー構造のテキスト形式でありVite製Webフロントエンドから見ると素のJSONより扱いにくい、という理由で採用しない。SGF最大の利点(既存ビューアで開ける)は、本プロジェクトが自作Webビューアを作る前提のため活きない。

ただし、着手の表記(`d3`のような列+行の代数記法)はこれらの既存フォーマット・オセロ関連ツール全般で共通の慣習であり、本スキーマでもそのまま採用する。

## リーグ結果JSON

複数対局を集計した結果は別ファイルとする(棋譜本体とは分離)。詳細な指標定義は [metrics.md](metrics.md) で扱う。
