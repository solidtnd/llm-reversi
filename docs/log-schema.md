# 棋譜JSONスキーマ

`data/` に出力する、1対局分の棋譜JSONの構造。[docs/rules.md](rules.md) で定義したルール・反則負けの扱いを反映する。

## ファイル形式(JSON / JSONL)

- **1対局分の棋譜ファイル自体は素のJSON**とする(1ファイル1オブジェクト)。Webは対局ごとにまるごとfetchして`JSON.parse`するだけで済むため。
- **リーグ実行中にengineが逐次書き出す結果ログはJSONL**(1行1対局の要約)とする。対局が完了するたびに1行追記するだけで済み、巨大なJSON配列を毎回書き直すより壊れにくいため。
- このJSONLはengine内部の実行ログであり、Webはこれを直接読まない。集計スクリプトがJSONLを読み込み、[docs/metrics.md](metrics.md)の指標を計算した上で、Web用の`ranking.json`等の読みやすいJSONへ変換する。

## トップレベル構造

```json
{
  "game_id": "string",
  "players": {
    "black": {
      "model": "string",
      "provider": "string",
      "config": { "temperature": 0.0, "thinking_effort": "..." }
    },
    "white": {
      "model": "string",
      "provider": "string",
      "config": { "...": "..." }
    }
  },
  "result": {
    "winner": "black | white | draw",
    "reason": "score | forfeit",
    "score": { "black": 0, "white": 0 }
  },
  "moves": [ /* Move[] (下記) */ ],
  "started_at": "ISO8601 string",
  "ended_at": "ISO8601 string"
}
```

- `config`は、対局に使ったモデル固有の設定値をそのまま記録する自由形式のオブジェクト(thinkingモードの有無・reasoning effort・temperature等)。モデルごとに項目が異なるため、キーはモデル/Adapter依存とする。実験の再現性を担保するための情報であり、[docs/adapter-interface.md](adapter-interface.md)の設定ファイル(モデル一覧)の値をそのまま転記する想定。

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
  "forfeit_reason": "illegal_move | timeout | parse_failure | null"
}
```

- `type: "pass"` の場合、`position`はnull(LLMに問い合わせないため)。
- `type: "forfeit"` の場合、`forfeit_reason`に理由を記録し、その手で対局は終了する。
- `retried`は、パース失敗によるリトライが発生したかどうか。
- **`llm_raw_response`は常に記録する**(成功・失敗を問わない)。各モデルの思考内容の分析に使えるため。thinkingモード等で生応答が肥大化する可能性はあるが、`data/`は全量そのままリポジトリにコミットし公開する方針([docs/architecture.md](architecture.md)参照)のため、リポジトリサイズの増加は許容する。
- `board_before`は持たない。前の手の`board_after`(1手目の場合は標準初期配置)と常に同一で冗長なため。Web側では`board_after`を先頭から並べるだけで盤面推移を再現でき、独自にリバーシの反転ロジックを実装する必要がない。

## 未決定事項

- [ ] モデルのトークン数・コストを記録するか
- [ ] リトライ発生時、1回目の失敗レスポンスも記録するか(現状は最終的な`llm_raw_response`のみ)
- [ ] `provider`(openai/anthropic/gemini等)の命名規則
- [ ] `config`オブジェクトの項目名の統一方針(モデル間で共通化できる項目とモデル固有項目の切り分け)

## 既存フォーマットとの関係

オセロには既存の棋譜フォーマット(WTHOR形式、GGF形式など)が存在するが、以下の理由から独自JSONを採用する。

- **WTHOR形式**: バイナリ形式で、大量対局のアーカイブ用途向け。JSONベースのWeb可視化と相性が悪い。
- **GGF形式**: プレイヤー名・結果・着手リストを持つテキスト形式だが、本プロジェクトで必要な「LLMの生応答」「反則理由」「リトライ有無」「応答時間」といったLLM対戦特有の情報を持つ余地がない。
- **SGF形式**: 手ごとのコメント(`C`)や、標準にないプロパティを追加できる拡張規定があり、GGFより自由度は高い。ただし(a)公式仕様でオセロが正式サポートされているわけではなくEdax/WZebra等が独自対応している状況、(b)拡張プロパティは非標準のため他のSGF対応ツールとの互換性はなく、独自JSONスキーマを設計するのと実質的な手間は変わらない、(c)ツリー構造のテキスト形式でありVite製Webフロントエンドから見ると素のJSONより扱いにくい、という理由で採用しない。SGF最大の利点(既存ビューアで開ける)は、本プロジェクトが自作Webビューアを作る前提のため活きない。

ただし、着手の表記(`d3`のような列+行の代数記法)はこれらの既存フォーマット・オセロ関連ツール全般で共通の慣習であり、本スキーマでもそのまま採用する。

## リーグ結果JSON

複数対局を集計した結果は別ファイルとする(棋譜本体とは分離)。詳細な指標定義は [docs/metrics.md](metrics.md) で扱う。
