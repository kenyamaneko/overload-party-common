# ADR-016: リポジトリ層のテスト戦略に Testcontainers を採用

## ステータス

Accepted (2026-04-13)

## 結論

インメモリモックでは検証できない「DB との契約」をテストで担保するため、リポジトリ層のテストに **Testcontainers** を採用する。SQL / JOIN / トランザクションが本物の PostgreSQL（Cloud SQL と同バージョンのイメージ）で検証され、`db/schema.sql` とリポジトリ実装の乖離が CI で検知される。Go / C# / Python で統一された戦略を取れ、`go test ./...` / `dotnet test` / `pytest` 一コマンドでローカル・CI 両方でテストが完結する。

## 背景・課題

現状、各サービスのリポジトリ層はインメモリのモック実装を使用している。これにより以下の問題が生じている：

- SQL の正確性（クエリ、JOIN、トランザクション）が検証されない
- マイグレーション後のスキーマとの整合性がテストで担保されない
- モックが「動くこと」は確認できても「DB との契約が正しいこと」は確認できない
- リポジトリ層の品質に対する信頼性が低い状態が続いている

ローカル開発時点から DB を使った単体テストに移行し、リポジトリ層の品質を実際の PostgreSQL との契約レベルで担保したい。

また、CI でもリポジトリ層のテストを実行するため、テストの自己完結性が必要である。`go test ./...` / `dotnet test` / `pytest` 一コマンドでローカルと CI の両方で同じテストが動くことを優先し、テストにおいては Docker Compose による外部 DB 管理ではなく Testcontainers を採用する。

テスト以外のローカル動作確認（`cmd/local` からの起動など）は、別途 Docker Compose で起動した DB を使う運用に切り替える。

## 制約

- Go / C# / Python の各言語で統一的に使えること
- Cloud SQL (PostgreSQL 16) と同じ DB エンジンでテストできること
- テストコードが自己完結し、`go test ./...` / `dotnet test` / `pytest` 一発で CI・ローカル両方で動くこと
- パッケージ単位で並列実行可能であること

## 詳細

Testcontainers は Go / C# / Python のいずれも公式サポートがあり（`testcontainers-go`, `Testcontainers.NET`, `testcontainers-python`）、テストコードから直接コンテナのライフサイクルを制御でき、本物の PostgreSQL イメージを使用できる。ランダムポート割り当てにより複数サービスの並列テストも安全。

- 使用するイメージは **`postgres:16-alpine`**（Cloud SQL の `POSTGRES_16` と同バージョン。`overload-party-infra/modules/database/main.tf` 参照）
- 各サービスが独立した PostgreSQL コンテナを持つ
- コンテナはパッケージ単位（`TestMain` / xUnit Fixture / pytest session fixture）で 1 回だけ起動し、テスト間のリセットは **`TRUNCATE ... RESTART IDENTITY CASCADE`** で行う
- スキーマ適用は **各リポジトリの `db/schema.sql` を直接 raw SQL で流す**（ops/db-migrate の union 結果は使わない）
  - 例外: gateway テストは `battle.games` への app-level FK 参照があるため、battle の `db/schema.sql` も併せて適用する
- インメモリモックのリポジトリ実装（テスト用 `mem_*_repo.go` およびローカル動作確認用のインメモリ実装の両方）は段階的に削除する
- ローカル動作確認（`cmd/local` 起動など）は、各リポジトリに `docker-compose.yml` を置き、`docker compose up -d postgres` で起動した DB を使う運用に切り替える

### 対象リポジトリ

DB アクセスがある全てのサーバー系リポジトリ：

- `overload-party-account` (Go, pgx)
- `overload-party-card` (Go, pgx)
- `overload-party-shop` (Go, pgx)
- `overload-party-scenario` (Go, pgx)
- `overload-party-gateway` (Go, pgx): battle スキーマも併用
- `overload-party-battle` (C# / .NET 10, Dapper)

将来対象（視野）：

- `overload-party-newsfeed` (Python): スキーマが未固定のため一旦対象外。固まったタイミングで `testcontainers-python` により本 ADR に追従する

対象外：

- `overload-party-ops/db-migrate`: psqldef 自体が union 結果を適用する層であり、単体テスト対象外

### CI 実行環境

- GitHub Actions で実行する
- Linux runner 上の Docker daemon をそのまま使用（Docker-in-Docker / Service Containers は不要。Testcontainers が runner の `/var/run/docker.sock` を参照する）
- 初回実行時の `postgres:16-alpine` pull コストを抑えるため、image を actions cache に乗せることを検討

### トレードオフ

- **テスト実行時間の増加**: コンテナ起動オーバーヘッド（数秒〜十数秒／パッケージ）が発生する。パッケージ単位で再利用しテスト間は TRUNCATE で軽量リセットする方針で緩和
- **CI 初回の image pull コスト**: `postgres:16-alpine` のダウンロードで初回 CI ジョブが遅くなる。image キャッシュで緩和
- **Docker 依存**: ローカル開発で Docker Desktop（または互換ランタイム）が必須化する。CLAUDE.md / 各 README に明記する必要あり

## 不採用案

### 案A: インメモリモックの継続

却下。現状の問題を解決しない。

### 案B: PGlite（WebAssembly ベースの組み込み PostgreSQL）

却下。Node.js / ブラウザ向けであり、Go / C# / Python から利用できない。

### 案C: embedded-postgres 系ライブラリ

却下。Go / C# / Python でそれぞれ別のライブラリが必要になる。C# 側の NuGet パッケージは品質がまちまちで、統一的な運用が難しい。

### 案D: Docker コンテナ直接管理（docker-compose 等）

却下。本物の PostgreSQL を使える点は良いが、テストコードとコンテナのライフサイクル管理が分離するため、CI 環境での扱いが煩雑になりやすい。`go test ./...` 単体ではテストが成立せず、事前に compose up が必須になる。
