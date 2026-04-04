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
- `data/products.yaml` - ショップ商品定義（SSoT）
- `data/constants.yaml` - ゲーム定数
- `data/event_schemas.yaml` - イベントデータスキーマ
- `data/models.yaml` - モデル定義（pkg: gamedata/api で振り分け）
- `db/schema_postgres.sql` - PostgreSQL DDL（全テーブルの SSoT）
- `db/grant_iam.sql` - IAM 認証権限付与
- `db/seed/cards_seed.sql` - カード定義の DB seed（自動生成）
- `db/seed/products.sql` - 商品定義の DB seed（自動生成）
- `db/seed/game_config.sql` - ゲーム定数の DB seed（budget, hand_limit, time_bank 等）
- `scripts/generate_cards.py` - カードデータ生成スクリプト（YAML → JSON/SQL/Markdown）
- `scripts/generate_products.py` - 商品データ生成スクリプト（YAML → JSON/SQL）
- `scripts/generate_constants.py` - 定数・型生成スクリプト（YAML → Go/C#/TS）
- `packages/gamedata/` - Go パッケージ（ゲームデータ: カード定義・定数・エフェクト型）
- `packages/api/` - Go パッケージ（API コントラクト: REST 型・WS メッセージ・デッキ型）
- `packages/devdata/` - Go パッケージ 開発用（カード・商品 JSON、ローカルモック用）
- `packages/dotnet/` - NuGet パッケージ（battle 用、GitHub Packages で publish）
- `packages/npm/` - npm パッケージ gamedata（constants, eventData, variantTypes）
- `packages/npm-api/` - npm パッケージ api（models, wsMessages）
- `docs/architecture/` - システム設計ドキュメント（API, CI/CD, データ設計, i18n 等）
- `docs/game_design/` - ゲームデザインドキュメント（ルール, カード, UI, チュートリアル等）
- `docs/business/` - ビジネス・法務ドキュメント（法的表示, マーケ, 収益化, 企画書等）

## Workflow

- カードデータを変更したら `python3 scripts/generate_cards.py` を実行
- 商品データを変更したら `python3 scripts/generate_products.py` を実行
- 定数・イベントスキーマ・モデル定義を変更したら `python3 scripts/generate_constants.py` を実行
- main への push 時に CI が自動でパッケージを publish する（patch bump。minor/major は手動 dispatch で指定）
- codegen は CI では実行しない。PR の codegen-check で同期を保証
- CARDS.md、products.sql、cards_seed.sql は自動生成なので直接編集しない
- DB スキーマを変更したら `db/schema_postgres.sql` のみ編集する（server リポの schema は廃止）
- 各リポはパッケージをインストールして生成コードを使う:
  - gateway: `go get .../packages/gamedata@latest` + `go get .../packages/api@latest`
  - gateway 開発用: `go get .../packages/devdata@latest`
  - battle: NuGet `OverloadParty.GameData` パッケージ
  - client: npm `@kenyamaneko/overload-party-gamedata` + `@kenyamaneko/overload-party-api`
