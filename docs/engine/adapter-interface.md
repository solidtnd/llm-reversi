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
- 具体的にどのモデルを何個登録するか(実際のモデル名一覧)は運用開始時に決定する(コード・スキーマ側はモデル数・名称に依存しないため、実装のブロッカーにはならない)。

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
    ) -> MoveResponse:
        ...
```

- `request_move`は同期呼び出しとする(1手ごとに逐次進行するゲームのため、非同期化のメリットが薄い)。
- タイムアウト・リトライは[rules.md](rules.md)の規定に従い、Adapterの外側(呼び出し元)で制御する。Adapter自体はプロバイダAPIの呼び出しとレスポンスのパースに専念する。

## 入出力

**入力**: 盤面状態、合法手一覧、手番(黒/白)

**出力(`MoveResponse`)**:

```json
{
  "position": "d3",
  "raw_response": "モデルの生応答(ログ用)"
}
```

- 出力の`position`が合法手に含まれるかの検証は呼び出し元(engine側)が行う。Adapterはパース済みの値を返すのみ。
- `position`/`legal_moves`の表記は[../shared/log-schema.md](../shared/log-schema.md#既存フォーマットとの関係)と同じ代数記法(`d3`等)で統一する。
- `raw_response`には、構造化出力部分(`position`)だけでなくAPIレスポンス全体(thinkingモード使用時は思考過程のブロック/パートを含む)を格納する。各社ともthinkingの思考過程は構造化出力とは別要素として返る(Claude: `content`配列内の別ブロック、Gemini: `thought: true`が付いた別パート)ため、構造化出力のスキーマ自体に思考用の項目を追加する必要はない。

## エラー通知

Adapterが送出する例外は、以下の2種類に限定する。OpenAI/Anthropic/Gemini各社のSDKはそれぞれ独自の例外クラス体系を持つため、Adapter内部でこの2種類のどちらかにラップして送出し、呼び出し元(engine側)には各社SDKの例外を露出させない。

- `AdapterParseError`: APIレスポンス自体は受信できたが、構造化出力の内容が期待する形式(JSON Schema準拠)でパースできなかった場合(レスポンス欠落・refusal応答など)。
- `AdapterAPIError`: APIへのリクエスト自体が失敗した場合(レート制限・5xxエラー・ネットワークエラー等)。元の例外(SDK例外)は`error_detail`用に保持する。

呼び出し元(engine側)は、この2つの例外の型を見て[rules.md](rules.md#1手ごとの処理)のリトライ制御・`forfeit_reason`(`parse_failure`/`api_error`)の判定を行う。一方、合法手検証(→`illegal_move`)とタイムアウト判定(→`timeout`)はAdapterの関知するところではなく、呼び出し元(engine側)のロジックで行う([rules.md](rules.md#エラー種別とadapterの例外設計)参照)。

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

`BoardState`は[../shared/log-schema.md](../shared/log-schema.md)の`board_after`と同じ64文字文字列(`.`=空/`b`=黒/`w`=白)をそのまま内部表現として使う(独自の2次元配列やFEN風文字列は作らない)。プロンプトへ渡す際のみ、Adapter層でLLMが読みやすい列(a-h)・行(1-8)ラベル付きのグリッド表記に変換する。この変換はプロンプト整形の関心事であり、`BoardState`自体のデータ形式には影響しない。

## プロンプト

- 全モデル共通のプロンプトテンプレートを使用する(実験の再現性・公平性のため)。
- プロンプト内容そのものは別途詰める(モデルへの指示文言、出力フォーマットの指定方法など)。

### 叩き台(雰囲気把握用・実装時に文言調整が前提)

以下は方向性を確認するための叩き台であり、**実際の精度・応答の安定性を見ながら実装時に文言を調整することを前提とする**(未決定事項として残す)。

```
あなたはリバーシ(オセロ)の対局者です。あなたは{color}(黒 | 白)です。

## 盤面
現在の盤面は以下の通りです(列はa-h、行は1-8)。
"."は空きマス、"b"は黒石、"w"は白石を表します。

    a b c d e f g h
  1 . . . . . . . .
  2 . . . . . . . .
  3 . . . . . . . .
  4 . . . b w . . .
  5 . . . w b . . .
  6 . . . . . . . .
  7 . . . . . . . .
  8 . . . . . . . .

## 合法手
あなたが打てる合法手は以下の通りです: d3, c4, f5, e6

## 指示
上記の合法手の中から1つを選び、着手位置を指定してください。
```

- 出力形式そのものは[出力フォーマットの強制](#出力フォーマットの強制)の通り、JSON Schema制約付き構造化出力機能で強制するため、プロンプト文中に「JSON形式で出力せよ」等の指示は基本的に不要(構造化出力機能が保証する)。ただし、モデルによっては指示を明示した方が安定する可能性があり、実装時に検証する。
- 盤面のグリッド表記は[共通インターフェース](#共通インターフェース イメージ)節の`BoardState`→プロンプト変換の説明に対応する。
- 合法手一覧の書式(カンマ区切り等)、指示文の詳細な言い回し、システムプロンプト/ユーザープロンプトの分割方法などは、実際にモデルへ投げて応答の質を見ながら詰める。

## 未決定事項

- [ ] 共通プロンプトテンプレートの具体的な文面(叩き台は上記「プロンプト」節に記載。実装時に精度・安定性を見ながら調整する前提で、まだ確定ではない)
