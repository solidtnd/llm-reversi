# 出場モデルの選定

`engine/models.yaml`に実際に登録するモデルを、2026-08-17時点で選定した記録。選定の元になった調査内容(各社の呼び出し可能モデル一覧・価格・構造化出力対応状況)と、選定理由・運用上の注意点をまとめる。

## 選定方針

[adapter-interface.md](adapter-interface.md#対応プロバイダ)の「性能の高いモデルと古いモデルを混在させて複数モデルを登録する」という方針を具体化するにあたり、以下を優先する。

- **構造化出力(JSON Schema制約付き出力)に対応していること。** [adapter-interface.md](adapter-interface.md#出力フォーマットの強制)の方針上、全モデルがこの機能に対応している必要があり、対応していないモデルは選定対象から機械的に除外する。
- **古い/性能が控えめなモデルと、新しい/強力なモデルの両方を含める。** ただし後述の通り、この制約により「古い」側は各社ともかなり限定される。
- **コストとのバランスを取り、カタログの全量登録は避ける。** 特に近年のモデルは推論(reasoning/thinking)機能が既定で有効なものが多く、古い非reasoningモデルに比べて1手あたりのコストが大きく跳ね上がりうる。

## 調査結果: 各社の呼び出し可能モデル一覧

APIキーで`GET /v1/models`(OpenAI・Anthropic)・`ListModels`(Gemini)を実際に叩いて取得した、2026-08-17時点でこのアカウントから呼び出せるモデルの一覧を基に調査した。

### OpenAI

主要モデルの構造化出力(`response_format: json_schema`)対応状況と価格(100万トークンあたりUSD、公式pricingページ調べ)。

| モデル | 構造化出力 | Input | Output | 備考 |
| --- | --- | --- | --- | --- |
| gpt-3.5-turbo | ✗ 非対応 | - | - | shutdown 2026-10-23予定。JSON modeのみでjson_schema非対応のため選定不可 |
| gpt-4 / gpt-4-turbo | ✗ 非対応 | - | - | 同上、shutdown 2026-10-23予定 |
| gpt-4o (2024-08-06以降) | ○ | $2.50 | $10.00 | 2024-05-13時点のsnapshotは非対応 |
| gpt-4o-mini | ○ | $0.15 | $0.60 | |
| gpt-4.1 / mini / nano | ○ | $2.00 / $0.40 / $0.10 | $8.00 / $1.60 / $0.40 | nanoはshutdown 2026-10-23予定 |
| o1 | ○ | $15.00 | $60.00 | shutdown 2026-10-23予定 |
| o1-pro | ○(条件付き) | - | - | **Responses API専用**(`text.format`)。本エンジンはChat Completions APIを使うため選定対象外 |
| o3-mini / o4-mini | ○ | $1.10 | $4.40 | いずれもshutdown 2026-10-23予定 |
| o3 | ○ | $2.00 | $8.00 | shutdown無し |
| gpt-5 / mini / nano | ○ | $1.25 / $0.25 / $0.05 | $10.00 / $2.00 / $0.40 | |
| gpt-5.1 〜 gpt-5.5 | ○ | $1.25 〜 $5.00 | $10.00 〜 $30.00 | 世代を追うごとに値上がり傾向 |
| gpt-5.6-sol / terra / luna | ○ | $5.00 / $2.00 / $0.20 | $30.00 / $12.00 / $1.20 | 2026-07-09 GA。世代番号+ティア名(Sol=最上位, Terra=中位, Luna=最速最安)という新命名規則 |

**reasoning系パラメータの注意点**: o-series・gpt-5系はreasoningモデルであり、`temperature`等のサンプリングパラメータを受け付けない(エラーになる)。代わりに`reasoning_effort`(low/medium/high)で深さを制御する。gpt-5.1以降は`reasoning_effort: "none"`の場合に限り`temperature`等を受理する例外があるが、本プロジェクトでは使わない想定。

**近い将来の退役に注意**: `gpt-3.5-turbo`・`gpt-4`・`gpt-4-turbo`・`o1`・`o3-mini`・`o4-mini`・`gpt-4.1-nano`は2026-10-23に一斉shutdown予定(今日から約2ヶ月後)。退役予定のモデルは選定から除外した。

### Anthropic

`GET /v1/models`で取得できたのは以下の10モデルのみ(Claude 3系・Sonnet 3.7以前は既に完全retire済みで一覧に出てこない)。

| モデル | 構造化出力 | Input | Output | 備考 |
| --- | --- | --- | --- | --- |
| claude-fable-5 | ○ | $10.00 | $50.00 | 最上位。**thinkingを無効化できない**(常時オン) |
| claude-opus-5 | ○ | $5.00 | $25.00 | thinkingは省略時オン(Opus 4.8/4.7と異なる) |
| claude-opus-4-8 | ○ | $5.00 | $25.00 | thinkingは省略時オフ |
| claude-opus-4-7 | ○ | $5.00 | $25.00 | |
| claude-opus-4-6 | ○ | $5.00 | $25.00 | |
| claude-sonnet-5 | ○ | $2.00 | $10.00 | 導入価格($3/$15)がそのまま現行価格になっている可能性あり。要ウォッチ |
| claude-sonnet-4-6 | ○ | $3.00 | $15.00 | |
| claude-opus-4-5 | ○ | $5.00 | $25.00 | レガシー |
| claude-haiku-4-5 | ○ | $1.00 | $5.00 | |
| claude-sonnet-4-5 | ○ | $3.00 | $15.00 | adaptive thinking非対応(拡張thinkingのみ、省略時オフ) |

構造化出力(`output_config.format`)は上記10モデル**全て**が対応していることを公式ドキュメント([Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs))で確認済み(手元で参照したスキルのキャッシュ情報ではOpus 4.6/4.7・Sonnet 4.6/4.5が対応表から漏れていたが、最新のドキュメントでは対応と明記されていた)。

**このプロジェクトにとって重要な制約**: Anthropicには2025年9月(Sonnet 4.5)より前のモデルが実質的に存在しない(それ以前は全てretire済み)。そのため「古くて性能が悪いモデル」に相当するものが用意できない。最も古い/軽量なものとして`claude-haiku-4-5`・`claude-sonnet-4-5`を代替とした。

### Google Gemini

`ListModels`で`generateContent`に対応するモデルのうち、テキスト生成用途のものを中心に調査した。

| モデル | 構造化出力(responseSchema) | Input | Output | 備考 |
| --- | --- | --- | --- | --- |
| gemini-2.5-flash-lite | ○ | $0.10 | $0.40 | `ListModels`には`generateContent`対応として載っているが、実際に呼ぶと404(「新規ユーザーには提供終了、`gemini-3.5-flash-lite`へ」)。カタログ掲載と実呼び出し可否が一致しない例(2026-08-18確認、後述) |
| gemini-2.5-flash | ○ | $0.30 | $2.50 | |
| gemini-2.5-pro | ○ | $1.25(20万トークン超は$2.50) | $10.00(同$15.00) | thinkingを完全には無効化できない |
| gemini-3.1-flash-lite | ○ | $0.25 | $1.50 | |
| gemini-3.5-flash | ○ | $1.50 | $9.00 | |
| gemini-3.1-pro-preview | ○ | $2.00(20万トークン超は$4.00) | $12.00(同$18.00) | preview版のみでGemini 3系のPro正式版はまだ存在しない。現状の事実上の最上位モデル |
| gemini-3-flash-preview / 3.6-flash / 3.7-flash | 不明 | - | - | 公式の構造化出力対応表に記載がなく確証が取れなかったため選定から除外(将来検証の上で追加候補) |
| gemma-4-26b-a4b-it / gemma-4-31b-it | **非対応の可能性大** | 無料 | 無料 | オープンウェイトのGemmaモデル。公式ドキュメントに`responseSchema`への言及が一切なく、対応表にも登場しないため除外 |

**このプロジェクトにとって重要な制約**: Geminiも同様に2024年以前の世代(1.5/2.0系)が一覧から姿を消しており、最も古いモデルでも2025年半ばのGemini 2.5系となる。加えて、無料で使える軽量なGemmaモデルは構造化出力の対応が確認できず、"古くて弱いモデル"の候補として使えない。

## 全体としての気づき: 「古くて弱いモデル」は3社とも用意できない

当初の要望である「古くて性能悪めのモデルも欲しい」は、**構造化出力必須という設計上の制約と、3社とも1年以上前の世代のモデルを退役させている実情**の組み合わせにより、額面通りには実現できなかった。

- OpenAI: `gpt-3.5-turbo`等は現存するが構造化出力非対応。
- Anthropic: 2025年9月以前のモデルは既に退役済み。
- Gemini: 2024年以前の世代は退役済み、かつ無料のGemmaは構造化出力対応が未確認。

そのため、今回の選定では各社の**最も軽量・安価なティア**(gpt-4o-mini、Claude Haiku 4.5、Gemini 2.5 Flash-Lite)と、**世代がやや前のモデル**(gpt-4o、Claude Sonnet 4.5、Gemini 2.5系)を組み合わせて「相対的に古い/弱い」枠として代用している。真に古いモデル同士の対戦を見たい場合は、構造化出力を使わない代替実装(プロンプトでJSON形式を指示し正規表現でパースする等)が別途必要になるが、これは[adapter-interface.md](adapter-interface.md#出力フォーマットの強制)の「3社とも同等の機能を持つため、特定モデルが有利になることはない」という設計方針そのものに関わる変更のため、今回は行わない。

## 選定結果: 2段階アプローチ

対戦させる量をいきなり最大化せず、**まず最小限のコア構成で実際に対戦させてから、結果を見て追加を検討する**方針に変更した。当初は18モデル選定していたが、対局実績が無い状態で量を決め打ちするより、少数で運用してから広げる方が判断材料を得やすいため。

### 第1段階: 最小コア(9モデル)

各社とも「旧世代/廉価アンカー・新世代中位・新世代最上位」の3層のみに絞った。同世代内の複数サイズ(nano/mini/mid等)や別アーキテクチャ(o3等)は、この段階ではあえて入れていない(理由は次節「第2段階候補」参照)。

#### OpenAI(3モデル)

| id | model | 位置づけ |
| --- | --- | --- |
| gpt-4o-mini | gpt-4o-mini-2024-07-18 | 旧世代・軽量(基準点) |
| gpt-5.6-luna | gpt-5.6-luna | 新世代・最小/最安ティア |
| gpt-5.6-sol | gpt-5.6-sol | 新世代・最上位(フラッグシップ) |

#### Anthropic(3モデル)

| id | model | 位置づけ |
| --- | --- | --- |
| claude-haiku-4-5 | claude-haiku-4-5-20251001 | 最安/最速ティア(基準点) |
| claude-sonnet-5 | claude-sonnet-5 | 新世代・中位、導入価格が魅力的 |
| claude-opus-5 | claude-opus-5 | 新世代・最上位 |

#### Gemini(2モデル)

| id | model | 位置づけ |
| --- | --- | --- |
| gemini-3.1-flash-lite | gemini-3.1-flash-lite | 最安ティア(基準点) |
| gemini-3.5-flash | gemini-3.5-flash | 新世代・中位 |

**`gemini-2.5-flash-lite`→`gemini-3.1-flash-lite`への差し替え(2026-08-18)**: 当初選定した`gemini-2.5-flash-lite`は、`models.yaml`に反映した後の動作確認(`request_move`を1回実際に呼ぶ)で404エラーになった。`ListModels`のレスポンスには`generateContent`対応モデルとして今も載っており、Web上の情報でも有効に見えるが、実際に`generateContent`を呼ぶと`This model models/gemini-2.5-flash-lite is no longer available to new users. Please update your code to use models/gemini-3.5-flash-lite for the latest features and improvements.`という404が返ってくることを確認した。カタログ一覧(`ListModels`)と実際の呼び出し可否がAPIキー(プロジェクト)の作成時期等に応じて食い違うことがある、という実例。エラーメッセージが案内する代替は`gemini-3.5-flash-lite`だが、価格・位置づけの面では表中の投資調査結果(前節)にある`gemini-3.1-flash-lite`(旧世代寄りでより安価)を選び、実際に1手問い合わせて合法手が返ることを確認した上で採用した。これにより第1段階のGeminiラインナップは3モデルとも実質的に「Gemini 3系」となり、Anthropicと同様に「旧世代アンカー」を用意できていない状態になった(前節「「古くて弱いモデル」は3社とも用意できない」参照)。

**GeminiのProティアは撤退・不採用に決定(2026-08-21)**: 当初`gemini-3.1-pro-preview`を選定していたが、レート制限が厳しく本番72局の実行で該当カードの多くがAPIエラーによる反則負けになったため、2026-08-19に`gemini-2.5-pro`(旧世代最上位)へ差し替えた。しかし差し替え後の本番実行でも改善せず、`gemini-2.5-pro`は16局中12局がAPIエラーによる反則負けとなり、スコアで決着した対局はわずか2局(いずれも敗け)に留まった。対局ログ(`data/games/`)のエラー詳細を確認したところ、原因は`generativelanguage.googleapis.com/generate_requests_per_model`のクォータ超過(`GenerateRequestsPerMinutePerProjectPerModel`、上限150 req/min/model)によるHTTP 429であり、`gemini-3.1-pro-preview`のときと同一種類の問題だった。[engine/reversi_engine/game.py](../../engine/reversi_engine/game.py)の`api_error`時リトライは待機なしで同一内容を即再送する実装であり、エラーメッセージが案内する「30秒待ってリトライ」を尊重できていない点も、反則負けが減らなかった一因と見られる。`concurrent_games`を4→20に引き上げた変更(`league.yaml`)も、Gemini Proへの同時リクエスト数を増やす方向に働いた可能性がある。

以上より、**Gemini Pro系ティアはこのプロジェクトの実行規模(同時実行数20・バックオフ無しリトライ)に対してレート制限が厳しすぎると判断し、`gemini-2.5-pro`を`models.yaml`から削除、対局データ(`data/games/`・`data/results.jsonl`)からも該当局を除去した**(残っていた非APIエラーの対局7局は実質的な対局数が少なすぎて統計的意味が薄いため合わせて除去)。`gemini-3.1-pro-preview`の対局データも同様の理由で既に除去済み。Gemini FlashティアはPro系ほど厳しいクォータ制限を受けておらず(`gemini-3.1-flash-lite`・`gemini-3.5-flash`はAPIエラーによる反則負けが0件)、この問題はProティア固有と判断している。リトライにバックオフを実装する、または`concurrent_games`を下げるなどの対応を行わない限り、Gemini Pro系モデルは今後も候補から除外する方針とする。

### 第2段階: 追加(4モデル、2026-08-21)

第1段階の対局結果(勝率・反則負け率・実際のコスト)を踏まえて、以下の4モデルを追加した。`claude-fable-5`は前回の判断通り、コスト超過のため引き続き対象外。

| id | model | 追加理由(観点A・B) |
| --- | --- | --- |
| gpt-5.6-terra | gpt-5.6-terra | **観点B**: `gpt-5.6-luna`(bt_strength 0.071)と`gpt-5.6-sol`(同0.416)の差が大きすぎたため、中間ティアで補間する |
| claude-sonnet-4-5 | claude-sonnet-4-5-20250929 | **観点A**: Anthropicで現存する最古世代。`claude-haiku-4-5`との世代内比較 |
| gpt-4o | gpt-4o-2024-08-06 | **観点A**: `gpt-4o-mini`との価格差(同世代内のティア差)がどの程度勝率に効くか |
| gemini-2.5-flash | gemini-2.5-flash | **観点A**: Gemini旧世代の中位ティア。Proティア撤退(前節参照)によりGeminiの層が2つに減っていたための補充 |

いずれも`models.yaml`への追記後、`request_move`を1回実際に呼んで合法手が返ることを確認済み(2026-08-21)。`gpt-4o`のsnapshot IDは構造化出力対応が確認されている`gpt-4o-2024-08-06`を採用した(「モデルIDの固定方針」参照)。`claude-sonnet-4-5`は無日付エイリアスが日付付きIDへの互換ポインタのため、`GET /v1/models`で実際に確認した`claude-sonnet-4-5-20250929`を明示した。

### 見送った候補(引き続き未決定)

**観点B(その他)**: `claude-opus-4-8`(`claude-opus-5`と同価格帯($5/$25)での世代差のみの比較)は今回見送り。優先度は`gpt-5.6-terra`より低いと判断した。

**観点C: 設定のバリエーション(config違い)を持たせる意義があるか**

新しいモデルではなく、同一モデルのconfig違いを別`id`として参加させる案(前回提示、未実施)。

1. `claude-opus-5`のthinkingあり版(現行はthinking: false) — 同価格でthinkingの有無だけを比較
2. Geminiの`thinking_budget`違い(0 vs 動的) — 同上
3. OpenAIの`reasoning_effort`違い(low vs high) — 同上

**観点D: 別アーキテクチャを追加する意義があるか**

| 候補 | 追加する意義 |
| --- | --- |
| o3 | OpenAIの専用reasoningモデル。gpt-5系の統合reasoningアーキテクチャとの比較 |

## モデルIDの固定方針

OpenAIの`gpt-4o`・`gpt-4o-mini`のような無日付エイリアスは将来的に指す先が変わりうる(実際に過去`gpt-4o`は複数回repointingされている)ため、日付付きの具体的なsnapshot ID(`gpt-4o-2024-08-06`等)を`model`欄に指定した。一方、`gpt-5.6-sol`等の新命名規則のモデルには日付付きsnapshotが存在せず、また日付付きsnapshotが存在するgpt-5系(`gpt-5-nano-2025-08-07`等)は2026-12-11にshutdown予定である一方、無日付エイリアス(`gpt-5-nano`等)にはshutdown予定が無いため、**あえて無日付エイリアスを採用**した(すぐに死ぬ固定IDより、多少の再現性を犠牲にしても動き続けるエイリアスを優先)。

Anthropicは[Model IDs and versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)の方針により、Claude 4.6世代以降は無日付のIDでも固定snapshotとして扱われる(将来変わらない)。それ以前の世代(Haiku 4.5・Sonnet 4.5)は無日付エイリアスが日付付きIDを指すだけの互換用ポインタのため、`model`欄には日付付きIDを明示した。

Geminiは`gemini-2.5-flash`のようなID自体は固定だが、内部的にpoint releaseで中身が更新されうる(`ListModels`のレスポンスに`version`フィールドが存在する)。挙動が変わっても検知しづらい点は留意事項として残す。

## config方針(thinking/reasoning_effort)

2025〜2026年にかけて登場したモデルの多くは推論(reasoning/thinking)機能を内蔵しており、**これを無効化できるかどうか・どこまで抑制できるかがコストに直結する**。リバーシの1手選択は合法手の列挙から1つを選ぶだけの単純なタスクであり、深い推論を必要としないと考え、以下の方針でコストを抑えた。

| 状況 | 対応 |
| --- | --- |
| thinkingを完全に無効化できるモデル(Claude Opus 5・Sonnet 5、Gemini Flash系) | 無効化する(`thinking: false` / `thinking_config.thinking_budget: 0`) |
| reasoningを完全には無効化できず、深さのみ調整できるモデル(OpenAI o3・gpt-5系、Gemini Pro系) | 最も浅い設定にする(`reasoning_effort: "low"` / `thinking_config.thinking_budget`を最小値) |

thinkingを一切無効化・抑制できないモデル(`claude-fable-5`)は、上記の抑制策が効かずコストが突出する見込みだったため、今回は候補から除外した(前節参照)。

**Anthropicの`effort`制御について**: 当初`engine/reversi_engine/adapters/anthropic.py`の`request_move`は`output_config`を`params.update(extra)`で丸ごと上書きしており、`config`に`output_config: {effort: "low"}`を書くと構造化出力用の`format`ごと消えてしまう不具合があったが、`output_config`をマージするように修正済み(`format`は常にAdapter側の値が優先される、[adapter-interface.md](adapter-interface.md#configの受け渡し)参照)。これにより`config: {output_config: {effort: "low"}}`のような形でAnthropicモデルの`effort`もコスト制御に使えるようになったが、今回の選定では`thinking`の有効/無効のみで制御しており、`effort`は未使用のまま(必要になれば追加で調整可能)。

Geminiの`thinking_config`のキー名(google-genai SDKのスネークケース表記に合わせた想定)は、2026-08-18に`gemini-3.1-flash-lite`・`gemini-3.5-flash`(`thinking_budget: 0`)、2026-08-19に`gemini-2.5-pro`(`thinking_budget: 128`)へ実際に1手ずつ問い合わせて動作確認済み。いずれも合法手を含む構造化出力が返ってきている。

## 大まかなコスト試算(参考値)

[rules.md](rules.md#リーグ運営)の通り、全カード総当たり・各カード2局(先後入替)で対戦する。第1段階の9モデルの場合:

- 総カード数: 9×8÷2 = 36
- 総対局数: 36×2 = 72局
- 1局あたりの平均手数を仮に58手とすると、総API呼び出し回数は約4,200回

対局数は18モデル時点の試算(306局)の約1/4であり、費用も比例して1/4程度(数ドル未満〜数ドル程度)に収まる見込み。正確な金額は実際のトークン消費量に強く依存するため、この数字はあくまで「オーダー感」の参考値。第2段階でモデルを追加する際は、対局数がモデル数のほぼ2乗で増える(`n×(n-1)`)点に留意する。

**第2段階適用後(12モデル、2026-08-21)**: Proティア撤退で9→8モデルに減った後、4モデル追加して12モデルとなった。カード数は12×11÷2 = 66、総対局数は66×2 = 132局(第1段階の72局の約1.8倍)。

コストが気になる場合の調整案:
- モデル数自体を絞る(このドキュメントの表から一部を`models.yaml`にコピーしない)。
- `engine/league.yaml`の`concurrent_games`は並列度であり総コストには影響しないため、コスト調整には使えない。

## 未決定事項

- `gpt-5.6-sol`等の新命名規則モデルが今後もこのIDのまま存続するか(2026-07-09 GAとまだ新しいため実績が少ない)。
- Claude Sonnet 5の価格が導入価格($2/$10)のまま定着するか、2026-08-31以降に$3/$15へ変わるか。
- `gemini-3-flash-preview`・`gemini-3.6-flash`・`gemini-3.7-flash`の構造化出力対応が確認でき次第、追加候補とする。
