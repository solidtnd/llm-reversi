# モデル呼び出しAdapter IF

LLMごとの差異を吸収する薄い自作Adapter層のインターフェース定義。LangChain等のフレームワークは使わない([docs/architecture.md](architecture.md)参照)。

## 方針

- 1手ごとに「盤面+合法手一覧を渡し、着手をJSONで返させる」だけのシンプルな呼び出しに特化する。
- 各Adapterは「プロバイダ固有のAPI呼び出し」と「プロンプトへの整形」「応答のパース」を担当し、呼び出し元(engine側)にはプロバイダの違いを見せない。
- 対戦に使うプロバイダ・モデルの一覧はコードに埋め込まず、**設定ファイルで管理する**(例: `models.yaml`のようなファイルを`engine/`配下に配置する想定。具体的な配置場所・形式は`engine/`内部構成の検討時に決定)。

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
- タイムアウト・リトライは[docs/rules.md](rules.md)の規定に従い、Adapterの外側(呼び出し元)で制御する。Adapter自体はプロバイダAPIの呼び出しとレスポンスのパースに専念する。

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
- パースに失敗した場合、Adapterは例外を送出し、呼び出し元がリトライ制御を行う。
- `position`/`legal_moves`の表記は[docs/log-schema.md](log-schema.md#既存フォーマットとの関係)と同じ代数記法(`d3`等)で統一する。

`BoardState`(盤面をどう表現してLLMに渡すか)の具体的な形式は未決定([未決定事項](#未決定事項)参照)。

## プロンプト

- 全モデル共通のプロンプトテンプレートを使用する(実験の再現性・公平性のため)。
- プロンプト内容そのものは別途詰める(モデルへの指示文言、出力フォーマットの指定方法など)。

## 未決定事項

- [ ] `BoardState`の具体的な表現形式(盤面をテキスト/配列/FEN風文字列のどれでLLMに渡すか。`docs/log-schema.md`の`board_before`/`board_after`表現とも整合させる)
- [ ] 共通プロンプトテンプレートの具体的な文面
- [ ] 出力フォーマットの指定方法(JSON mode/Function calling/プレーンテキスト指示のいずれを使うか、モデルごとに変えるか)
- [ ] 対応するプロバイダ・モデルの一覧(初期スコープ。設定ファイルの具体的な形式・配置場所も含む)
- [ ] APIキー等のシークレット管理方法(環境変数か`.env`か)
