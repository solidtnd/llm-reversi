# 棋譜JSONスキーマ

`data/` に出力する、1対局分の棋譜JSONの構造。[../engine/rules.md](../engine/rules.md) で定義したルール・反則負けの扱いを反映する。

## ファイル形式(JSON / JSONL)

- **1対局分の棋譜ファイル自体は素のJSON**とする(1ファイル1オブジェクト)。Webは対局ごとにまるごとfetchして`JSON.parse`するだけで済むため。
- **リーグ実行中にengineが逐次書き出す結果ログはJSONL**(1行1対局の要約)とする。対局が完了するたびに1行追記するだけで済み、巨大なJSON配列を毎回書き直すより壊れにくいため。
- このJSONLはengine内部の実行ログであり、Webはこれを直接読まない。集計スクリプトがJSONLを読み込み、[metrics.md](metrics.md)の指標を計算した上で、Web用の`ranking.json`等の読みやすいJSONへ変換する。

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
  "retried": false,
  "response_time_ms": 1234,
  "forfeit_reason": "illegal_move | timeout | parse_failure | api_error | null",
  "error_detail": "string | null",
  "usage": { "prompt_tokens": 123, "completion_tokens": 45 }
}
```

- `type: "pass"` の場合、`position`はnull(LLMに問い合わせないため)。
- `type: "forfeit"` の場合、`forfeit_reason`に理由を記録し、その手で対局は終了する。
- `retried`は、パース失敗によるリトライが発生したかどうか。
- **`llm_raw_response`は、リトライがあった場合も最終的なレスポンス1件のみを記録する**(成功した場合はその成功レスポンス、リトライしても最後まで失敗した場合は最後の失敗レスポンス)。リトライ前の失敗レスポンスは保持しない。何回リトライが発生したか自体は`retried`で分かれば十分なため。
- `error_detail`は、`forfeit_reason`が`api_error`の場合、またはAPIエラーが原因で`timeout`になった場合に、例外メッセージ等のデバッグ情報を記録する([../engine/rules.md](../engine/rules.md#api呼び出しエラーの扱い)参照)。それ以外の場合はnull。モデルの応答内容である`llm_raw_response`とは区別する(APIエラー時はモデルからの応答自体が存在しないため)。
- `usage`は、LLMのAPIレスポンスに含まれるトークン数(input/output)をそのまま記録する。ほとんどのプロバイダのレスポンスに標準で含まれており記録の手間がないため。**コスト(金額)はここには記録しない**。プロバイダによってはレスポンスに金額が含まれず、含める場合は別途モデル別の単価テーブルをどこかに持つ必要が生じ、単価改定のたびにドキュメント・コードの更新が必要になる。金額が必要な場合は`data/`集計時に`usage`とモデル別単価表から都度算出する(単価表自体は本スキーマの対象外、集計スクリプト側の関心事)。レスポンスにトークン数が含まれないプロバイダの場合は`usage`全体を`null`とする。
- `board_before`は持たない。前の手の`board_after`(1手目の場合は標準初期配置)と常に同一で冗長なため。Web側では`board_after`を先頭から並べるだけで盤面推移を再現でき、独自にリバーシの反転ロジックを実装する必要がない。

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
