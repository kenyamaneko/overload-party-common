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
- `data/constants.json` - ゲーム定数
- `data/event_schemas.json` - イベントデータスキーマ
- `data/models.yaml` - Go モデル定義
- `db/schema_postgres.sql` - PostgreSQL DDL（全テーブルの SSoT）
- `db/grant_iam.sql` - IAM 認証権限付与
- `db/seed/` - 初期データ（dev/stg 用）
- `packages/generate_from_yaml.py` - コード生成スクリプト
- `packages/gamedata/` - Go パッケージ（gateway 用、`go get` でインストール）
- `packages/dotnet/` - NuGet パッケージ（battle 用、GitHub Packages で publish）
- `packages/npm/` - npm パッケージ（client 用、GitHub Packages で publish）
- `docs/architecture/` - システム設計ドキュメント（API, CI/CD, データ設計, i18n 等）
- `docs/game_design/` - ゲームデザインドキュメント（ルール, カード, UI, チュートリアル等）
- `docs/business/` - ビジネス・法務ドキュメント（法的表示, マーケ, 収益化, 企画書等）

## Workflow

- カード・定数を変更したら `python3 packages/generate_from_yaml.py --gen-dir packages/` を実行
- main への push 時に CI が自動でパッケージを publish する（patch bump。minor/major は手動 dispatch で指定）
- codegen は CI では実行しない。PR の codegen-check で同期を保証
- CARDS.md は自動生成なので直接編集しない
- DB スキーマを変更したら `db/schema_postgres.sql` のみ編集する（server リポの schema は廃止）
- 各リポはパッケージをインストールして生成コードを使う:
  - gateway: `go get github.com/kenyamaneko/overload-party-common/packages/gamedata@latest`
  - battle: NuGet `OverloadParty.GameData` パッケージ
  - client: npm `@kenyamaneko/overload-party-gamedata` パッケージ
