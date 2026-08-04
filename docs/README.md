# docs 一覧

設計・仕様ドキュメントの索引。AIエージェントに実装を任せる前提で、**engineを実装するときに読むべきファイル**と**webを実装するときに読むべきファイル**を分けて整理している。各ドキュメント本文が「その時点で合意済みの事項」、末尾の「未決定事項」節が「まだ決まっていないこと」を示す(詳細は[CLAUDE.md](../CLAUDE.md)参照)。

## ディレクトリ構成

```
docs/
├── shared/    # engine・web両方が前提とする共通仕様(全体構成・データ形式)
├── engine/    # engine実装時のみ関係する仕様
└── web/       # web実装時のみ関係する仕様
```

## 共通(engine・web どちらの実装でも先に読む)

| ファイル | 内容 |
| --- | --- |
| [shared/architecture.md](shared/architecture.md) | プロジェクトの目的、engine/web/dataの全体構成・分離方針 |
| [shared/log-schema.md](shared/log-schema.md) | `data/`に置く棋譜JSON・リーグ結果JSONのスキーマ(engineが書き出し、webが読み込む) |
| [shared/metrics.md](shared/metrics.md) | 棋譜JSONから算出する集計指標・ランキング方式の定義 |

## engineを実装するときに読むファイル

上記「共通」に加えて:

| ファイル | 内容 |
| --- | --- |
| [engine/engine-architecture.md](engine/engine-architecture.md) | engineのモジュール構成・並列実行方針・テスト方針 |
| [engine/rules.md](engine/rules.md) | リバーシの対戦ルール、1手ごとの処理・反則負けの扱い、リーグ運営方針 |
| [engine/adapter-interface.md](engine/adapter-interface.md) | LLMごとの差異を吸収するAdapter層のインターフェース定義、`models.yaml`の形式 |

## webを実装するときに読むファイル

上記「共通」に加えて:

| ファイル | 内容 |
| --- | --- |
| [web/web-architecture.md](web/web-architecture.md) | webのモジュール構成・画面構成・データ取り込み方式・デプロイ方針 |

## 未決定事項

各ドキュメント末尾の「未決定事項」節を参照。実装に着手する前に、そのドキュメントに関係する未決定事項が実装のブロッカーになっていないか確認すること。
