# ADR-017: shared.game_config の Cloud Firestore 移管

- Status: Accepted
- Date: 2026-04-13
- Deciders: kenyamaneko
- Related: ADR-011 (repository split), ADR-014 (DB schema split per service), ADR-016 (Testcontainers)

## Context

`shared.game_config` はゲーム運営中に調整が必要な動的な設定値（バトル上限数、経験値、タイムバンク等）を管理するストアとして設計された。当初は PostgreSQL の `shared` スキーマとして実装していたが、ADR-011 / ADR-014 によりリポジトリ・スキーマがサービス単位に完全分割された結果、以下の問題が顕在化した：

- 各サービスのリポジトリが分割されているため、`shared` スキーマの定義 SQL をどのサービスにどう配布するかが原理的に解決できない
- テスト時（ADR-016 の Testcontainers 戦略）に common リポのスキーマ定義を各サービスから参照する仕組みを作るコストが高い
- 設定値はサービス横断で参照されるため、特定のサービスの DB に属するべきデータでもない

`shared.game_config` は KV 構造（`key TEXT PRIMARY KEY, value TEXT`）であり、リレーショナルである必要はない。

## Decision Drivers

- スキーマ定義の配布／同期が運用負荷にならないこと
- Go / C# / Python の各言語から同等に扱えること（Testcontainers の方針と整合）
- ローカル開発と CI で本物に近い動作が再現できること
- サービス横断の共有状態を将来追加する際の置き場として拡張できること

## Options Considered

### A. common の SQL 定義を各リポジトリにコピーして持つ

却下。スキーマ変更のたびに全リポジトリ同期が必要になり、ADR-014 で排除した「サービスを跨いだ DDL 同期負荷」が再発する。

### B. GCS の JSON ファイルで管理する

却下。読み取りパフォーマンスが不透明で、サービス側にパース／キャッシュ層を持たせる必要がある。動的更新時のキャッシュ無効化も自前で組む必要がある。

### C. Cloud Firestore（採用）

KV 構造のデータを NoSQL で管理することで、スキーマ定義の配布問題が原理的に消える。各サービスは Firestore クライアントでキーを読むだけになる。Go / C# / Python 公式クライアントが揃っており、エミュレーターも公式に提供されている。

## Decision

- `shared.game_config` を **Cloud Firestore** に移管する
- コレクション設計：
  - コレクション `game_config`、ドキュメント ID = key、フィールド `value`（型は値ごとの実型: number / string / bool）
- PostgreSQL `shared.game_config` テーブルおよび `shared` スキーマは廃止する（`shared` スキーマ自体に他のテーブルが残らないため、スキーマごと削除）
- 各サービスは公式 Firestore クライアントから読み取る
  - Go: `cloud.google.com/go/firestore`
  - C#: `Google.Cloud.Firestore`
  - Python: `google-cloud-firestore`
- 書き込み（運営チューニング）は GCP Console / Firestore admin SDK 経由で行う

### Firestore モード

- **Native モード**を採用する（Datastore モードではない）。リアルタイム更新・サブコレクション・SDK 機能が揃っており、将来のサービス横断共有状態の置き場としても拡張余地が大きい
- dev / stg / prod の各 GCP プロジェクトで Firestore Native モードを有効化する（現時点で未有効化）
- ロケーション: `asia-northeast1`（Tokyo single-region）

### 読み取り失敗時の挙動

- キー不在は **fail-fast**（CLAUDE.md 方針準拠）。リポジトリは `port.ErrNotFound` を返し、サービス層は即座にエラーを伝播する
- 旧 PostgreSQL 実装は第 3 引数 `fallback` を取っていたが、本移行で interface を `GetInt64(ctx, key) (int64, error)` に変更し fallback を削除する

### パイロット戦略

- **account をパイロット**とする。理由: 現時点で game_config を runtime で読み取っている唯一のサービス（`PlayerService` の daily battle limit / exp formula coefficient / exp_win|loss|draw）。shop は構造体定義のみで dead code のため検証にならない
- account dev デプロイで問題無いことを確認してから、shop / battle / card / scenario / gateway に順次展開

### `shared.update_updated_at()` の扱い

`shared.update_updated_at()` トリガー関数は、現在 account / card / shop / scenario など複数サービスのテーブルが `BEFORE UPDATE` トリガーから参照している。`shared` スキーマ削除に際し、本関数は **各サービスのスキーマ内に再定義**する（例: `account.update_updated_at()`, `card.update_updated_at()` …）。各サービスの `db/schema.sql` 冒頭で関数を宣言し、トリガー側の参照名も置き換える。

### IAM / 環境分離

- プロジェクト単位で Firestore を分離（dev / stg / prod）
- 各サービスのワークロード ID に `roles/datastore.user`（Firestore Native モードでも本ロールを使用）を付与
- 書き込みは運営オペレーター + ops サービスアカウントのみに限定

## Local / Testing

### ローカル開発

- `gcloud emulators firestore start --host-port=localhost:9041` でエミュレーターを起動
- `FIRESTORE_EMULATOR_HOST=localhost:9041` を環境変数で渡すと、Go / C# / Python のいずれの公式クライアントも自動的にエミュレーターに接続する
- Python スクリプト（`scripts/` 配下）からも同じエミュレーターに繋がるため、constants codegen 系のスクリプトも本番／ローカルでコードを変えずに済む

### テスト

- ADR-016 の Testcontainers と整合させるため、Firestore エミュレーターも CI で起動する
- テスト間のリセットはエミュレーターの REST API（`DELETE http://${FIRESTORE_EMULATOR_HOST}/emulator/v1/projects/<project>/databases/(default)/documentData`）で実施
- Firestore エミュレーター本体は Java で実装されているため、**CI runner に Java 21 以上のセットアップが必要**（GitHub Actions 標準の `actions/setup-java@v3` を利用）
  - エミュレーターを動かすランタイムとして Java が必要なだけで、Java コードを書く必要は無い
- Testcontainers のように「テストコードがコンテナを自動起動する」モデルではなく、ジョブ前段で `gcloud emulators firestore start` を立てておく構成

```yaml
# GitHub Actions ステップ例
- uses: actions/setup-java@v3
  with:
    java-version: '21'
- name: Start Firestore emulator
  run: gcloud emulators firestore start --host-port=localhost:9041 &
- name: Wait for emulator
  run: until curl -sf http://localhost:9041; do sleep 0.2; done
```

ポート 9041 を採用（8080 は他用途と衝突しやすいため回避）。

## Consequences

### Positive

- スキーマ定義配布問題が原理的に解消する（NoSQL なので各サービスに DDL を配る必要が無い）
- 各サービスは Firestore クライアントでキー名指定で読むだけ。サービス追加時の追従コストがほぼゼロ
- 運営チューニングが GCP Console から即時反映可能になり、PostgreSQL マイグレーション経由の更新フローから解放される
- Python スクリプトからも同じエミュレーターに繋げるため、constants codegen 等の運用ツールも統一できる
- 将来のサービス横断共有状態の置き場として拡張可能

### Negative / Trade-offs

- 新規インフラ（Firestore）が増える。dev / stg / prod の 3 プロジェクトに有効化が必要
- CI runner に Java 21+ のセットアップステップが追加で必要（Java コード自体は不要）
- PostgreSQL（Cloud SQL）と Firestore の 2 つのデータストアを運用することになる
- Firestore は強い結整合性こそあるが、SQL 的な集計／JOIN は不可。`game_config` は KV のため問題にならないが、将来追加するデータの種類は注意が必要
- エミュレーターは Testcontainers のような「テストコードからの自動起動」モデルではないため、ジョブ前段での起動／待機ステップが必要

## Migration Plan

### account パイロット（先行）

1. **infra**: `modules/firestore/` 追加。Firestore Native モード有効化 + account SA に `roles/datastore.user` 付与。dev から適用
2. **ops**: `ops/firestore-seed/seed_game_config.py` 追加。現行 `db/seed/game_config.sql` の 7 キーを number で投入
3. **account**: `internal/repository/firestore_game_config_repo.go` 追加、`pg_game_config_repo.go` / `internal/model/player.go` (dead) 削除、`port.GameConfigRepo.GetInt64` から fallback 引数を削除 (fail-fast)
4. **account**: `db/schema.sql` の `shared.update_updated_at()` を `account.update_updated_at()` に改名、`CREATE SCHEMA IF NOT EXISTS shared` 削除
5. **account CI**: `actions/setup-java@v4` + `gcloud emulators firestore start --host-port=localhost:9041` を追加。`firestore_game_config_repo_test.go` を emulator 経由で走らせる
6. **ops/db-migrate**: account の git ref を `schemas.lock.yaml` で pin 更新
7. account を dev デプロイ → daily battle limit / exp 計算が正しく動くことを確認。1 週間程度観測

### 横展開（パイロット問題なし確認後）

8. shop / battle / card / scenario / gateway に順次展開。各サービスの CI ステップは `.github/actions/firestore-emulator/` composite action に共通化
9. 全サービスの切り替え完了後、common の `db/schema_postgres.sql` / `db/seed/game_config.sql` を削除。ops/db-migrate の dependency order からも `shared` を除外
10. CLAUDE.md / 各 README にローカル開発時の `gcloud emulators firestore start --host-port=localhost:9041` 手順を追記

## 横展開の運用マニュアル（次サービス対応の手順）

account パイロット完了後、別サービス S を Firestore 対応させる際の標準手順：

### S リポジトリ
1. **interface 追加**: `internal/port/repository.go` に `GameConfigRepo interface { GetInt64(ctx, key) (int64, error) }` を追加（既存があれば fallback 引数を削除）
2. **Firestore 実装**: `internal/repository/firestore_game_config_repo.go` を追加。account の同名ファイルから移植。`google.golang.org/grpc/codes.NotFound` を `port.ErrNotFound` でラップ
3. **mock**: `internal/repository/mock_game_config_repo.go` を fail-fast 化（不在で `port.ErrNotFound` を返す）
4. **config**: `FIRESTORE_PROJECT_ID` を required env で追加
5. **main.go**: `firestore.NewClient(ctx, cfg.FirestoreProjectID)` 初期化、サービスにリポを注入
6. **go.mod**: `GOWORK=off go get cloud.google.com/go/firestore@latest`
7. **dead code 削除**: 旧 PG 実装、未使用 model.GameConfig、shared.game_config 参照を全削除
8. **schema**: `db/schema.sql` の `CREATE SCHEMA IF NOT EXISTS shared` と `CREATE OR REPLACE FUNCTION shared.update_updated_at()` を削除し、サービス自身のスキーマに `<service>.update_updated_at()` を再定義。トリガー参照も `<service>.update_updated_at()` に置換
9. **CI** (`.github/workflows/ci.yaml` test ジョブ):
   - `actions/setup-java@v4` (java-version: 21)
   - `google-github-actions/setup-gcloud@v2` + `gcloud components install cloud-firestore-emulator beta --quiet`
   - `gcloud emulators firestore start --host-port=localhost:9041 &` + 30 秒の curl wait ループ
   - test step に `FIRESTORE_EMULATOR_HOST=localhost:9041` と `FIRESTORE_PROJECT_ID=overload-party-test` を env で渡す
10. **integration test**: `firestore_game_config_repo_test.go` を追加（account の同名ファイルから移植）。`FIRESTORE_EMULATOR_HOST` 未設定時は skip、設定時は emulator REST API でリセット → seed → assert

### infra リポ
11. `modules/main.tf` の `module "firestore" { reader_service_account_emails = { ... } }` map にサービスを追記。dev/stg/prod 全環境で `terraform apply -target=module.infra.module.firestore` で IAM 付与のみ反映

### k8s リポ
12. サービス Deployment manifest に env `FIRESTORE_PROJECT_ID=overload-party-{env}` を追加

### 注意事項
- **`shared.update_updated_at()` は最後に削除**: 全サービスがスキーマ自前定義に切り替わるまで common の `db/schema_postgres.sql` を残す。最後の 1 サービスが完了した時点で common 側のファイルを削除し、ops/db-migrate dependency order からも `shared` を除外
- **interface 引数を変える破壊的変更**: `GetInt64(ctx, key, fallback)` → `GetInt64(ctx, key)` はサービス内部の呼び出し全てを修正する必要あり。1 サービス内で完結するので各サービス独立に進められる
- **port 9041 厳守**: ローカル/CI で他サービスと衝突しないよう全サービスで同一ポートを使う
- **dev で動作確認した上で stg/prod に展開**: dev seed → サービスデプロイ → 該当エンドポイントで設定値が反映されているかを確認してから次環境
- **runtime で読み取っていないサービス（例: shop は dead model のみ）** はパイロット検証にならないため、Firestore 統合だけ入れて疎通確認に留める
- **`FIRESTORE_EMULATOR_HOST` 環境変数**: 公式クライアントが自動認識し emulator にルーティングするため、production コードに分岐は書かない（fail-fast 原則）
- **シード再投入が必要なら `python3 ops/firestore-seed/seed_game_config.py --project overload-party-{env}` を実行**（既存はスキップ、`--overwrite` で上書き可）
