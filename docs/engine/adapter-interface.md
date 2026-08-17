# モデル呼び出しAdapter IF

LLMごとの差異を吸収する薄い自作Adapter層のインターフェース定義。LangChain等のフレームワークは使わない([engine-architecture.md](engine-architecture.md)参照)。

## 方針

- 1手ごとに「盤面+合法手一覧を渡し、着手をJSONで返させる」だけのシンプルな呼び出しに特化する。
- 各Adapterは「プロバイダ固有のAPI呼び出し」と「プロンプトへの整形」「応答のパース」を担当し、呼び出し元(engine側)にはプロバイダの違いを見せない。
- 対戦に使うプロバイダ・モデルの一覧はコードに埋め込まず、`engine/models.yaml`で管理する(詳細は[モデル一覧設定ファイル](#モデル一覧設定ファイルenginemodelsyaml)を参照)。

## 対応プロバイダ

初期スコープは **OpenAI / Anthropic / Google Gemini** の3社(ユーザーがAPIキーを保有)。各プロバイダにつき、性能の高いモデルと古いモデルを混在させて複数モデルを登録する想定。

## モデル一覧設定ファイル(`engine/models.yaml`)

`engine/models.yaml`に、1エントリ1モデルのフラットなリストで記述する。

```yaml
models:
  - id: gpt-4o                  # ログ上のプレイヤー識別子(一意)
    provider: openai            # APIリクエストに指定する識別名と同一
    model: gpt-4o               # API呼び出し時のモデル名
    display_name: "GPT-4o"      # Web表示用の説明文字列
    config: {}                  # モデル固有パラメータ(自由形式、そのまま棋譜JSONのconfigに転記)
  - id: claude-opus-4-1-thinking
    provider: anthropic
    model: claude-opus-4-1-20250805
    display_name: "Claude Opus 4.1 (Thinkあり)"
    config:
      thinking: true
```

- `id`はモデル名と1対1とは限らない(同じ`model`でも`config`違いのvariant、例えばthinkingあり/なしを別プレイヤーとして対戦させたい場合を想定し、`id`を分ける)。
- 新モデル追加はリスト末尾に1エントリ追記するだけでよく、[rules.md](rules.md#リーグ運営)の「未実施カードのみ実行する」差分実行の運用と整合する。
- `display_name`は対局実行時に棋譜JSON側にもコピーする([../shared/log-schema.md](../shared/log-schema.md)の`players`オブジェクト参照)。Webは`data/`のJSONのみを読み、`models.yaml`自体には依存しない([../shared/architecture.md](../shared/architecture.md)の方針)。
- 具体的にどのモデルを何個登録するか(実際のモデル名一覧)は運用開始時に決定する(コード・スキーマ側はモデル数・名称に依存しないため、実装のブロッカーにはならない)。リポジトリの`engine/models.yaml`には初期の叩き台としてOpenAI/Anthropic/Geminiから数モデルを記載してある。

### `config`の受け渡し

`config`のキーは**そのままプロバイダAPIのリクエストパラメータとして渡す**(`temperature`、`reasoning_effort`、`max_tokens`など)。Adapter側にモデル間で共通の正規化レイヤを作らないことで、プロバイダ側のパラメータ追加・廃止に本スキーマ・コードの変更なしで追従できる([../shared/log-schema.md](../shared/log-schema.md)の`config`と同じ理由)。例外は以下の3点のみで、いずれも「YAMLに素直に書ける形」と「APIが要求する形」の差を埋めるための最小限の変換に留める。

- **Anthropic**: `thinking: true` / `false` と真偽値で書いた場合のみ、APIの形式(`{"type": "adaptive"}` / `{"type": "disabled"}`)へ変換する。辞書で書いた場合はそのまま渡す。`max_tokens`はAnthropic APIで必須のため、`config`に無ければAdapter側の既定値(4096)を使う。`output_config`(例: `effort`を指定する場合)は、構造化出力用の`format`(下記[出力フォーマットの強制](#出力フォーマットの強制)参照)とマージして渡す。単純に`config`全体を上書きすると`format`が消えて構造化出力自体が壊れるため、`format`キーは常にAdapter側の値が優先される(`config`側で`format`を指定しても無視される)。
- **Gemini**: 共通スキーマから`additionalProperties`を外して渡す(後述の[出力フォーマットの強制](#出力フォーマットの強制)参照)。

## シークレット管理

APIキーは`engine/.env`に配置し`python-dotenv`で読み込む(`OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GOOGLE_API_KEY`)。`.env`は既に`.gitignore`済み。キー名だけ共有する`.env.example`(値は空)をリポジトリにコミットする。

## 共通インターフェース(イメージ)

```python
class LLMAdapter(Protocol):
    provider: str   # "openai" | "anthropic" | "gemini" など
    model: str      # "gpt-4o" など具体モデル名

    def request_move(
        self,
        board: BoardState,
        legal_moves: list[str],
        player: Literal["black", "white"],
        retry_reason: str | None = None,
    ) -> MoveResponse:
        ...
```

- `request_move`は同期呼び出しとする(1手ごとに逐次進行するゲームのため、非同期化のメリットが薄い)。
- タイムアウト・リトライは[rules.md](rules.md)の規定に従い、Adapterの外側(呼び出し元)で制御する。Adapter自体はプロバイダAPIの呼び出しとレスポンスのパースに専念する。
- `retry_reason`は、[rules.md](rules.md#1手ごとの処理)のパース失敗による再試行(1手あたり1回まで)でのみ使う。初回呼び出しおよびAPIエラーによる再試行(同一内容で再送するため)では常に`None`を渡す。呼び出し元(engine側)は、直前に送出された`AdapterParseError.message`をそのまま`retry_reason`に渡して再試行する。Adapterはこれをプロンプトに追記し、モデルに前回の失敗を伝える(具体的な文言は[`retry_reason`挿入時のプロンプト](#retry_reason挿入時のプロンプト)参照)。

## 入出力

**入力**: 盤面状態、合法手一覧、手番(黒/白)、`retry_reason`(パース失敗による再試行時のみ、詳細は[共通インターフェース](#共通インターフェースイメージ)参照)

**出力(`MoveResponse`)**:

```json
{
  "position": "d3",
  "llm_raw_response": "モデルの生応答(ログ用)",
  "usage": { "prompt_tokens": 123, "completion_tokens": 45 }
}
```

- 出力の`position`が合法手に含まれるかの検証は呼び出し元(engine側)が行う。Adapterはパース済みの値を返すのみ。
- `position`/`legal_moves`の表記は[../shared/log-schema.md](../shared/log-schema.md#既存フォーマットとの関係)と同じ代数記法(`d3`等)で統一する。
- `llm_raw_response`には、構造化出力部分(`position`)だけでなくAPIレスポンス全体(thinkingモード使用時は思考過程のブロック/パートを含む)を格納する。実装上は各社SDKのレスポンスオブジェクトを**JSON文字列にシリアライズしたもの**を入れる(`model_dump_json()`等)。プロバイダごとに項目を取捨選択すると「レスポンス全体を残す」という目的が崩れるため、加工はしない。各社ともthinkingの思考過程は構造化出力とは別要素として返る(Claude: `content`配列内の別ブロック、Gemini: `thought: true`が付いた別パート)ため、構造化出力のスキーマ自体に思考用の項目を追加する必要はない。フィールド名は[../shared/log-schema.md](../shared/log-schema.md#move1手ごとの記録)の`Move.llm_raw_response`とそのまま対応させ、engine側で書き出す際に名称変換が不要なようにする。
- `usage`には、APIレスポンスに含まれるプロンプト/completionトークン数を`{"prompt_tokens": int, "completion_tokens": int}`の形で格納する。レスポンスにトークン数が含まれないプロバイダの場合は`usage`全体を`None`とする([../shared/log-schema.md](../shared/log-schema.md#move1手ごとの記録)の`Move.usage`にそのまま転記される)。

## エラー通知

Adapterが送出する例外は、以下の2種類に限定する。OpenAI/Anthropic/Gemini各社のSDKはそれぞれ独自の例外クラス体系を持つため、Adapter内部でこの2種類のどちらかにラップして送出し、呼び出し元(engine側)には各社SDKの例外を露出させない。

- `AdapterParseError`: APIレスポンス自体は受信できたが、構造化出力の内容が期待する形式(JSON Schema準拠)でパースできなかった場合(レスポンス欠落・refusal応答など)。
  - `message: str`: パースに失敗した理由の説明。再試行時に`request_move`の`retry_reason`へそのまま渡され、モデルへのフィードバックに使われる。反則負けが`parse_failure`または`timeout`として確定した場合は、棋譜の`error_detail`にもそのまま記録される([../shared/log-schema.md](../shared/log-schema.md#move1手ごとの記録)参照)。
  - `llm_raw_response: str`: パースできなかった生レスポンス文字列。棋譜の`llm_raw_response`用に保持する。
- `AdapterAPIError`: APIへのリクエスト自体が失敗した場合(レート制限・5xxエラー・ネットワークエラー等)。
  - `message: str`: 失敗理由の説明。反則負けが`api_error`または`timeout`として確定した場合、棋譜の`error_detail`にそのまま記録される。
  - `original_exception: Exception`: 元の例外(SDK例外)。`error_detail`用に保持する。

呼び出し元(engine側)は、この2つの例外の型を見て[rules.md](rules.md#1手ごとの処理)のリトライ制御・`forfeit_reason`(`parse_failure`/`api_error`)の判定を行う。一方、合法手検証(→`illegal_move`)とタイムアウト判定(→`timeout`)はAdapterの関知するところではなく、呼び出し元(engine側)のロジックで行う([rules.md](rules.md#エラー種別とadapterの例外設計)参照)。

### `message`の文言

`message`は`retry_reason`(モデルへのフィードバック)と`error_detail`(棋譜上でのデバッグ用)の両方に使われるため、その文言が実質的な決定事項になる。以下を確定版として実装する(`engine/reversi_engine/adapters/base.py`に定数として1箇所だけ持ち、3社のAdapterが共有する)。実際の失敗パターンを見て調整が必要になった場合は、この表とコードの定数を合わせて更新する。

**`AdapterParseError.message`**(`retry_reason`としてそのままモデルに渡るため、モデルに向けた自然な文章にする):

| 失敗パターン | `message`の例 |
|---|---|
| refusal応答(モデルが応答を拒否) | モデルが応答を拒否しました |
| 空応答・構造化出力なし | 応答に有効な構造化出力が含まれていませんでした |
| max_tokens到達による途中切断 | 応答が途中で切断され、有効なJSONになりませんでした |
| 構造化出力機能を使っていてもなお形式が不一致(防御的なケース) | 応答が期待する形式(`position`を含むJSON)と一致しませんでした |

**`AdapterAPIError.message`**(モデルには渡らず、人間が棋譜を見て原因を把握するためのものなので、日本語での簡潔な要約でよい):

| 失敗パターン | `message`の例 |
|---|---|
| レート制限(429) | レート制限に達しました |
| サーバーエラー(5xx) | APIサーバーエラーが発生しました(HTTP {status}) |
| ネットワークエラー | ネットワークエラーが発生しました |
| その他(想定外のSDK例外) | {SDK例外のクラス名}: {メッセージ} |

- どちらの例外も、`message`だけでは分からない詳細(HTTPステータスの生値・SDK例外そのもの)は別属性(`AdapterParseError`は`llm_raw_response`、`AdapterAPIError`は`original_exception`)で保持する。`message`は失敗の種類を一言で伝える短い説明にとどめる。
- 各失敗パターンの判定は、プロバイダごとに以下の材料で行う。判定材料が無いプロバイダでも「構造化出力が取り出せなかった」ケースには必ず落ちるため、`AdapterParseError`にならず素通しされることはない。
  - refusal: OpenAIは`message.refusal`、Anthropicは`stop_reason == "refusal"`、Geminiは`finish_reason`が安全性由来の値(`SAFETY`等)またはプロンプトのブロック。
  - max_tokens到達: OpenAIは`finish_reason == "length"`、Anthropicは`stop_reason == "max_tokens"`、Geminiは`finish_reason == "MAX_TOKENS"`。
  - 空応答・構造化出力なし: 上記に当てはまらず、テキスト本文が取り出せなかった場合。
  - 形式不一致: テキストは取れたがJSONとして読めない、または`position`が文字列で含まれない場合。
- **HTTPステータスの扱い**: 429を「レート制限」、5xxを「APIサーバーエラー(HTTP {status})」とし、それ以外のステータス(4xx等)は`{SDK例外のクラス名}: {メッセージ}`として扱う。4xxはリクエスト内容の誤りであり「サーバーエラー」と記録すると原因調査を誤らせるため。

### 出力フォーマットの強制

全プロバイダで、各社のJSON Schema制約付き構造化出力機能を使う(OpenAI: Structured Outputs、Anthropic: `output_config.format`、Google Gemini: `responseSchema`)。3社とも同等の機能を持つため、特定モデルが有利になることはない。共通スキーマは以下の通りシンプルにし、`legal_moves`(手ごとに変わる)はスキーマに反映しない(合法手検証は引き続きengine側で行う)。

```json
{
  "type": "object",
  "properties": { "position": { "type": "string" } },
  "required": ["position"],
  "additionalProperties": false
}
```

Geminiのみ、この共通スキーマから`additionalProperties`を外して渡す。`responseJsonSchema`が受け付けるJSON Schemaキーワードの範囲がOpenAI/Anthropicより狭く、未対応キーでリクエストが失敗する可能性があるため。`position`が必須の文字列であるという制約は3社で同一であり、余分なキーが来た場合もパース処理が無視するため、モデル間の有利不利は生じない。

`BoardState`は[../shared/log-schema.md](../shared/log-schema.md)の`board_after`と同じ64文字文字列(`.`=空/`b`=黒/`w`=白)をそのまま内部表現として使う(独自の2次元配列やFEN風文字列は作らない)。プロンプトへ渡す際のみ、Adapter層でLLMが読みやすい列(a-h)・行(1-8)ラベル付きのグリッド表記に変換する。この変換はプロンプト整形の関心事であり、`BoardState`自体のデータ形式には影響しない。

## プロンプト

- 全モデル共通のプロンプトテンプレートを使用する(実験の再現性・公平性のため)。テンプレートは`engine/reversi_engine/adapters/base.py`の`build_prompt()`に1箇所だけ置き、3社のAdapterが同じ関数を呼ぶ(プロバイダごとに文面が分岐すると公平性が崩れるため)。
- 以下を確定版として実装する。応答の安定性を見て調整が必要になった場合は、この節と`build_prompt()`を合わせて更新する。

```
あなたはリバーシ(オセロ)の対局者です。あなたは{黒 | 白}です。

## 盤面
現在の盤面は以下の通りです(列はa-h、行は1-8)。
"."は空きマス、"b"は黒石、"w"は白石を表します。

    a b c d e f g h
  1 . . . . . . . .
  2 . . . . . . . .
  3 . . . . . . . .
  4 . . . w b . . .
  5 . . . b w . . .
  6 . . . . . . . .
  7 . . . . . . . .
  8 . . . . . . . .

## 合法手
あなたが打てる合法手は以下の通りです: d3, c4, f5, e6

## 指示
上記の合法手の中から1つを選び、着手位置を指定してください。
```

- 出力形式そのものは[出力フォーマットの強制](#出力フォーマットの強制)の通り、JSON Schema制約付き構造化出力機能で強制するため、プロンプト文中に「JSON形式で出力せよ」等の指示は入れない(構造化出力機能が保証するため、重複した指示は情報量を持たない)。特定モデルで応答が安定しない場合に初めて追記を検討する。
- 盤面のグリッド表記は[共通インターフェース](#共通インターフェースイメージ)節の`BoardState`→プロンプト変換の説明に対応する。上記は標準初期配置(d4/e5に白、d5/e4に黒)で、このとき黒の合法手が`d3, c4, f5, e6`になる。
- 合法手一覧は代数記法をカンマ+スペース区切りで、盤面index昇順(a1→h8の順)に並べる。順序を固定するのは、モデルへの提示順が対局ごとにぶれないようにするため。
- システムプロンプトは使わず、上記の全文を1つのユーザーメッセージとして送る。3社で分割方法の対応状況が微妙に異なるため、最も差が出ない形に揃える。

### `retry_reason`挿入時のプロンプト

`retry_reason`が渡された場合(パース失敗による再試行時、[共通インターフェース](#共通インターフェースイメージ)参照)は、`## 合法手`と`## 指示`の間に「## 前回の応答について」節を追加する。盤面・合法手一覧など他の内容は初回呼び出しと同一のまま追加するだけで、置き換えない([rules.md](rules.md#1手ごとの処理)の「単純な同一プロンプトの再送はしない」に対応)。

```
あなたはリバーシ(オセロ)の対局者です。あなたは{黒 | 白}です。

## 盤面
(...初回と同一...)

## 合法手
あなたが打てる合法手は以下の通りです: d3, c4, f5, e6

## 前回の応答について
前回の応答は次の理由により受け付けられませんでした: {retry_reason}
上記の合法手の中から、有効な形式で選び直してください。

## 指示
上記の合法手の中から1つを選び、着手位置を指定してください。
```

- `{retry_reason}`には`AdapterParseError.message`の内容がそのまま入る。

## 未決定事項

(現時点でなし)
