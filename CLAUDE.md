# CLAUDE.md - overload-party-common

## General Rules

- `docs/archive/`、`docs/adr/`、`docs/notes/` はユーザーが設計の変遷を振り返るためのものであり、Claude が参照する必要はない
- 設計変更を伴う作業の後は、memory ファイルを更新すること
- 不具合解消時はワークアラウンドではなく、設計から見直して根本解決をすること。根本解決が難しい場合はユーザーに相談する
- コードを修正した場合はドキュメントの更新の必要がないかを検討する
- ドキュメントを修正した場合は、テストコードの作成・更新が必要ないかを検討する
- コメントは意図（なぜそうしたか）が読み取りづらい場合のみ記述する。処理内容を説明するだけのコメントは書かない
- エラーは握りつぶさない。どうしてもそうする必要がある場合はユーザーに確認する

## Repository Role

- ゲームデザイン・カードデータ・定数の Single Source of Truth (SSoT)
- ドキュメントは全リポジトリ共通でここに集約する
- コード生成パイプライン: YAML → Go/TS/C#/JSON/Markdown → パッケージ publish

## Key Files

- `data/cards/*.yaml` - カード定義（5ファクション）
- `data/mock/` - 開発用モックデータ（news, products, starter_decks）
- `data/factions.yaml` - ファクションマスター SSoT（id / 表示名 / sort_order / is_collectible）
- `data/game_design_constants.yaml` - ゲームデザイン定数（zones, ranks, card_types, restrictions 等、全リポジトリ共通）
- `data/game_logic_constants.yaml` - ゲームロジック定数（phases, win_reasons, effect_ops 等、将来 battle リポへ）
- `data/gateway_ws_constants.yaml` - WS メッセージタイプ定数（将来 gateway リポへ）
- `data/shop_constants.yaml` - ショップ定数（product_types、将来 shop リポへ）
- `data/newsfeed_constants.yaml` - ニュースフィード定数（cloud_news_sources、将来 newsfeed リポへ）
- `data/event_schemas.yaml` - イベントデータスキーマ
- `data/models.yaml` - モデル定義（pkg: gamedata/api で振り分け）
- `db/schema_postgres.sql` - PostgreSQL DDL（全テーブルの SSoT、インラインコメントが DATA_DESIGN.md のカラム説明の SSoT）
- `db/grant_iam.sql` - IAM 認証権限付与
- `db/seed/cards_seed.sql` - カード定義の DB seed（自動生成）
- `db/seed/products.sql` - 商品定義の DB seed（自動生成）
- `db/seed/game_config.sql` - ゲーム定数の DB seed（budget, hand_limit, time_bank 等）
- `scripts/generate_cards.py` - カードデータ生成スクリプト（YAML → JSON/SQL/Markdown）
- `scripts/generate_products.py` - 商品データ生成スクリプト（YAML → JSON/SQL）
- `scripts/generate_constants.py` - 定数・型生成スクリプト（YAML → Go/C#/TS + ドキュメントのフィールドテーブル自動更新）
- `scripts/generate_schema_doc.py` - スキーマドキュメント生成スクリプト（DDL → DATA_DESIGN.md のカラムテーブル自動更新）
- `packages/game-design-constants/` - Go module（Faction / CardType / Restriction 等、全リポ共通）
- `packages/game-logic-constants/` - Go module（Phase / WinReason / TriggerType 等、将来 battle 移管）
- `packages/ws-constants/` - Go module（WSServerMsg / WSClientMsg、将来 gateway 移管）
- `packages/shop-constants/` - Go module（ProductType、将来 shop 移管）
- `packages/newsfeed-constants/` - Go module（CloudNewsSource、将来 newsfeed 移管）
- `packages/card-types/` - Go module（CardDefinition / CardStats / PassiveEffect / NpcModel）
- `packages/api-client/` - Go module（client ↔ gateway REST + WS 契約、将来 gateway 移管）
- `packages/api-battle-rpc/` - Go module（gateway ↔ battle 内部 RPC 契約、将来 battle 移管）
- `packages/devdata/` - Go module 開発用（カード・商品 JSON、ローカルモック用）
- `packages/gamedata-dotnet/` - NuGet パッケージ（battle 用、将来 Phase 4 で 4 分割予定）
- `packages/gamedata-npm/` - npm パッケージ gamedata（game-design / game-logic / ws / shop / newsfeed / eventData / variantTypes / models サブエントリポイント、将来 Phase 4 で分割予定）
- `packages/api-npm/` - npm パッケージ api（models, wsMessages、将来 Phase 4 で api-client-npm にリネーム予定）
- `go.work` - ローカル開発用の Go workspace (8 新 Go module + devdata をまとめる)
- `docs/architecture/API_REFERENCE.md` - REST API リファレンス
- `docs/architecture/WS_REFERENCE.md` - WebSocket API リファレンス
- `docs/architecture/` - システム設計ドキュメント（API, CI/CD, データ設計, i18n 等）
- `docs/game_design/` - ゲームデザインドキュメント（ルール, カード, UI, チュートリアル等）
- `docs/business/` - ビジネス・法務ドキュメント（法的表示, マーケ, 収益化, 企画書等）

## Workflow

- カードデータを変更したら `python3 scripts/generate_cards.py` を実行
- 商品データを変更したら `python3 scripts/generate_products.py` を実行
- 定数（`data/*_constants.yaml`）・ファクション（`data/factions.yaml`）・イベントスキーマ・モデル定義を変更したら `python3 scripts/generate_constants.py` を実行
- 定数は 5 分類 (game_design / game_logic / ws / shop / newsfeed) に分かれており、それぞれが独立したパッケージ（Go: `packages/{category}-constants/` トップレベルモジュール、C#: `OverloadParty.GameData.{Category}` namespace、npm: `@kenyamaneko/overload-party-gamedata/{category}` サブエントリポイント）に生成される
- main への push 時に CI が自動でパッケージを publish する（patch bump。minor/major は手動 dispatch で指定）
- **git tag を手動で打ってはいけない。** タグは CI が自動で作成する。手動タグは二重 publish やバージョン不整合の原因になる
- 生成スクリプトは CI では実行しない。PR の codegen-check で同期を保証
- CARDS.md、products.sql、cards_seed.sql は自動生成なので直接編集しない
- API_REFERENCE.md / WS_REFERENCE.md の `<!-- BEGIN/END GENERATED: TypeName -->` マーカー間は自動生成。フィールド説明を変更する場合は `data/models.yaml` の `doc` フィールドを編集して `python3 scripts/generate_constants.py` を実行する
- DB スキーマを変更したら `db/schema_postgres.sql` のみ編集する（server リポの schema は廃止）。カラムのインラインコメント（`-- 説明`）も必ず記述する
- DB スキーマを変更したら `python3 scripts/generate_schema_doc.py` を実行して DATA_DESIGN.md を更新する
- DATA_DESIGN.md の `<!-- BEGIN/END GENERATED: table_name -->` マーカー間は自動生成。カラム説明を変更する場合は `db/schema_postgres.sql` のインラインコメントを編集して `python3 scripts/generate_schema_doc.py` を実行する
- 各リポはパッケージをインストールして生成コードを使う:
  - Go サービス (gateway / 将来の account / matchmaking / shop / scenario / card): 必要な module だけを `go get` する。例:
    - gateway: game-design-constants + game-logic-constants + ws-constants + card-types + api-client + api-battle-rpc + devdata
    - card (将来): game-design-constants + card-types + api-client
    - matchmaking (将来): ws-constants + api-client
  - battle: NuGet `OverloadParty.GameData` パッケージ (Phase 4 で 4 分割予定)
  - client: npm `@kenyamaneko/overload-party-gamedata` + `@kenyamaneko/overload-party-api` (Phase 4 で複数分割予定)
- common 内で Go module 間の相互参照がある場合は `go.work` が local 開発時に自動解決する (CI では `GOWORK=off` で独立ビルド)
