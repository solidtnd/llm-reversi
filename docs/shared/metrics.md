# 集計指標

[log-schema.md](log-schema.md#対局結果ログdataresultsjsonl) の`data/results.jsonl`から算出する、モデル比較のための指標(対局ごとの完全な棋譜JSON本体は集計時に読まない)。

## モデル単位の指標

- 勝率(全体)
- 勝率(先手時 / 後手時、それぞれ別集計)
- 反則負け率、および反則理由(非合法手/タイムアウト/パース失敗/APIエラー)ごとの内訳
- 平均応答時間(1手あたり)

## モデル間(対戦カード)の指標

- 直接対戦成績(モデルA vs モデルB の勝敗数)
- 対戦表(全モデル総当たりのマトリクス)

## ランキング指標

以下の2方式を**併記**する(片方に絞らない)。

- **勝点方式**: 勝ち=1点、引き分け=0.5点、負け=0点として合計する単純集計。
- **Bradley-Terryモデルによる強さ推定**: 全対局結果から相手の強さを考慮した強さパラメータを推定する統計モデル。ELOのような逐次更新(1局ごとにレートを更新していく方式)とは異なり、**全対局データを一括で最尤推定するため、対局を処理する順序に結果が依存しない**。この順序依存性を避けるためにELOではなくBradley-Terryを採用する。
  - 実装はスクラッチではなく既存ライブラリ`choix`を使う。`choix.ilsr_pairwise(n_items, data, alpha=0.01)`で強さパラメータ(対数スケール)を推定する。`ilsr_pairwise`は反復法による近似最尤推定で、`opt_pairwise`(勾配法による厳密最尤推定)よりライブラリ内で高速・軽量なため採用する(対局数の規模であればどちらでも精度上の実用的な差はない想定だが、実装のシンプルさを優先する)。
  - `alpha`は正則化項。全勝または全敗のモデルが1体でもいると正則化なしのBradley-Terry推定は強さが無限大(または0)に発散するため、小さな正則化を入れて有限の値に収める。
  - `n_items`はリーグに参加した全モデルの数、`data`は`(winner_idx, loser_idx)`のタプルのリスト。モデルは識別子でソートした順に`0`始まりのindexを割り当てる。
  - モデルの識別には`players.model`(モデル名文字列)ではなく、[../engine/adapter-interface.md](../engine/adapter-interface.md)の`models.yaml`で定義する`id`を使う。同じ`model`でも`config`違い(thinkingあり/なし等)を別プレイヤーとして対戦させる運用のため、`model`文字列だけでは同一モデルの別variantを区別できない。この識別のため、**棋譜JSONの`players`オブジェクトに`id`フィールドを追加する**([log-schema.md](log-schema.md)を参照、集計スクリプトが`model`文字列とconfigの組み合わせから同一性を推測するような曖昧な実装を避けるため)。
  - 集計元は`data/`配下の各対局JSONの`result.winner`と`players[].id`から、勝者側の`id`→敗者側の`id`のタプルを1件生成する。引き分けは上述の通り両者に半勝ちを1回ずつ追加する(`(a, b)`と`(b, a)`を1回ずつdataに追加する)。反則負けも通常の負けと同様に1勝1敗として扱う(反則負けを集計対象から除外しない方針は[../engine/rules.md](../engine/rules.md)と同じ)。
  - `choix.ilsr_pairwise`が返す値は対数スケールの強さパラメータで、そのままでは大小関係はわかっても値の意味が直感的でない。Web表示用には`ranking.json`格納時に`exp()`を取り全モデル合計が1になるよう正規化した値(相対的な強さの割合)を`bt_strength`として持たせる(詳細は下記スキーマ節)。

## 安定性の指標

「安定性」を測る指標としては**反則負け率のみを採用し、応答時間のばらつき・リトライ発生率は指標としない**。応答時間はモデルのAPI応答特性(推論の深さ・サーバ側の混雑等)に左右される要素が大きく、モデルの対局における「安定性」(=ルールを守って対局を成立させ続けられるか)とは性質が異なるため。平均応答時間自体は(モデル単位の指標)に既にあるが、これは参考情報であり安定性の指標としては扱わない。

リトライ(`Move.retried`、[log-schema.md](log-schema.md)参照)についても同様の理由で指標化しない。リトライは最終的に成功すれば対局結果に影響しない一時的な事象であり、それ自体を安定性指標に含める必要はなく、実害があったかどうかは反則負け率(特に`parse_failure`/`api_error`理由の内訳)で十分測れると判断したため。個々の対局でリトライが起きたかどうかは棋譜JSON本体の`Move.retried`に残るが、`data/results.jsonl`・`ranking.json`には集計しない。

## リーグ結果JSON(`ranking.json`)スキーマ

[log-schema.md](log-schema.md#リーグ結果json)で「別ファイルとする」とした集計結果の具体的な構造。集計スクリプトが`data/results.jsonl`を読み込むたびに**全量を再生成する**(差分更新は行わない。モデル数・対局数に比例するサマリ情報のみのため、再生成コストは現実的な範囲に収まる想定)。

```json
{
  "generated_at": "ISO8601 string",
  "models": [
    {
      "id": "string",
      "display_name": "string",
      "provider": "string",
      "games": 20,
      "wins": 10,
      "losses": 8,
      "draws": 2,
      "win_rate": 0.55,
      "win_rate_as_black": 0.6,
      "win_rate_as_white": 0.5,
      "forfeit_loss_rate": 0.1,
      "forfeit_reasons": { "illegal_move": 1, "timeout": 0, "parse_failure": 1, "api_error": 0 },
      "avg_response_time_ms": 1234,
      "points": 10.5,
      "bt_strength": 0.28
    }
  ],
  "head_to_head": [
    {
      "a": "string (id, aとbはid昇順)",
      "b": "string (id)",
      "a_wins": 1,
      "b_wins": 1,
      "draws": 0,
      "game_ids": ["string", "..."]
    }
  ],
  "games": [
    {
      "game_id": "string",
      "black": "string (id)",
      "white": "string (id)",
      "winner": "black | white | draw",
      "reason": "score | forfeit",
      "forfeit_reason": "illegal_move | timeout | parse_failure | api_error | null",
      "ended_at": "ISO8601 string"
    }
  ]
}
```

- `models`配列は事前にソートしない(順位はランキング方式によって`points`降順/`bt_strength`降順のどちらでも変わるため)。Web側が表示したい列でソートする。
- `head_to_head`は「対戦表(マトリクス)」用。モデル数を`n`とすると`n×(n-1)/2`件(同一カードの重複を避けるため`a<b`のみ持つ)。先手後手別の内訳は個々のカードではなくモデル単位の指標(`win_rate_as_black`等)側で扱うため、ここでは先手後手を合算した勝敗数のみ持つ。`game_ids`は、対戦表のセルから該当カードの対局一覧・棋譜リプレイへドリルダウンするWeb側の導線のために持たせる。
- `games`は全対局の要約一覧。Web側の対局一覧画面(モデル別・反則負けのみ、等でのフィルタ表示)が、対局ごとの完全な棋譜JSON(手順・生応答を含む重いファイル)を全件fetchせずに一覧表示を完結できるようにするため。個別対局のリプレイ・生ログ閲覧時に、初めて該当`game_id`の棋譜JSON本体をfetchする想定。

## 未決定事項

現時点でなし。
