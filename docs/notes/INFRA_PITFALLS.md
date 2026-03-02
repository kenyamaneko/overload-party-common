# インフラ構築時のつまずきポイント

GKE Autopilot + Cloud SQL + GitHub Actions CI の構築で遭遇した問題と解決策。

---

## 1. `.gitignore` のベアパターンがサブディレクトリにもマッチする

**症状**: `cmd/api/` と `cmd/ws/` が git に追加されない。CI の `docker build` で `cmd/api` が見つからずに失敗。

**原因**: `.gitignore` に `api` や `ws` をベアパターンで記載していたため、`cmd/api/` や `cmd/ws/` にもマッチした。

**修正**: ルート直下のビルド成果物のみ除外するようにスラッシュ付きに変更。

```diff
- api
- ws
+ /api
+ /ws
```

---

## 2. Cloud SQL Proxy が SA のプロジェクトで Cloud SQL Admin API を呼ぶ

**症状**: Cloud SQL Proxy が `The proxy has started successfully` と表示されるのに、接続すると `connection reset by peer` になる。

**原因**: Cloud SQL Proxy は SA が所属するプロジェクト（`overload-party-shared`）で `sqladmin.googleapis.com` API を呼ぶ。Cloud SQL インスタンスは `overload-party-dev` にあっても、**SA のプロジェクト側で API が有効でないと動かない**。

Proxy の起動時チェック（リスナーの開始）は API 呼び出しを行わないため、`ready for new connections!` と表示されても実際の接続は失敗する。

**修正**:

```bash
gcloud services enable sqladmin.googleapis.com --project=overload-party-shared
```

**教訓**: Cloud SQL Proxy のエラーは background プロセスの stderr に出力されるため、CI では必ずログをファイルに出力してエラー時に表示するようにする。

---

## 3. psqldef が PL/pgSQL の `DO $$ ... END $$` を解析できない

**症状**: `psqldef --dry-run` が `syntax error near 'DO'` で失敗。

**原因**: psqldef は DDL (CREATE TABLE, ALTER TABLE 等) を解析・差分適用するツールであり、`DO $$` ブロック（PL/pgSQL の無名ブロック）はサポートしていない。

**修正**: `DO $$ ... END $$` ブロックを `db/grant_iam.sql` に分離し、CI で psqldef の後に `psql -f db/grant_iam.sql` として別途実行。

---

## 4. GKE Autopilot で AR からのイメージ pull に 403

**症状**: Pod が `ImagePullBackOff` になり、`failed to authorize: failed to fetch oauth token: 403 Forbidden` と表示される。

**原因**: GKE Autopilot ではイメージ pull にノードの SA（Compute Engine default SA）が使われる。同一プロジェクト内の AR でも、Compute Engine default SA に明示的に権限が付与されていない場合は 403 になる。

**修正**:

```bash
PROJECT_NUMBER=$(gcloud projects describe overload-party-shared --format='value(projectNumber)')
gcloud projects add-iam-policy-binding overload-party-shared \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/artifactregistry.reader"
```

**注意**: IAM ロールの変更が反映されるまで数分かかることがある。Pod を削除して再作成が必要。

---

## 5. Cloud SQL `db-g1-small` には `edition = "ENTERPRISE"` が必要

**症状**: `terraform apply` が Cloud SQL インスタンス作成でエラー。

**原因**: Terraform の `google_sql_database_instance` で `db-g1-small` を使う場合、`edition = "ENTERPRISE"` を明示指定しないと `ENTERPRISE_PLUS` がデフォルトになり、互換性エラーが発生する。

```hcl
settings {
  tier    = "db-g1-small"
  edition = "ENTERPRISE"  # 必須
}
```

---

## 6. DB パスワードを Terraform state に残さない

**問題**: `random_password` + `google_sql_user` を Terraform で管理すると、パスワードが state ファイルに平文で残る。

**解決**: DB ユーザーとパスワードは gcloud で直接管理し、Terraform の管理対象から除外。

```bash
# ユーザー作成
gcloud sql users create game-server \
  --instance=overload-party-db \
  --project=overload-party-dev \
  --password='<password>'

# パスワード変更
gcloud sql users set-password game-server \
  --instance=overload-party-db \
  --project=overload-party-dev \
  --password='<new-password>'
```

既に Terraform state に入ってしまった場合:

```bash
terraform state rm 'module.cloudsql.random_password.db_password'
terraform state rm 'module.cloudsql.google_sql_user.main'
```

---

## 7. `/healthz` は GFE 予約パス

**症状**: ヘルスチェックエンドポイント `/healthz` に対して Google の 404 ページが返される。

**原因**: Cloud Run、App Engine、GKE Ingress 経由の場合、Google Front End (GFE/ロードバランサー層) が `/healthz` をインターセプトし、コンテナに到達しない。

**修正**: ヘルスチェックパスを `/health` に変更。

---

## 8. GKE Autopilot + Workload Identity での SA 権限設計

**ポイント**: GKE Autopilot では以下の SA が異なる用途で使われる。混同しやすいので注意。

| SA | 用途 | 権限例 |
|---|---|---|
| Compute Engine default SA | ノード管理、**イメージ pull** | `roles/artifactregistry.reader` |
| KSA (game-server) → GSA (overload-party-server@dev) | **アプリケーション** (Cloud SQL 接続等) | `roles/cloudsql.client`, `roles/cloudsql.instanceUser` |
| CI SA (github-ci@shared) | **GitHub Actions CI** (ビルド、push、db-migrate) | `roles/artifactregistry.writer`, `roles/cloudsql.client` |
| Deploy SA (github-deploy@shared) | **GitHub Actions Deploy** (kubectl) | `roles/container.developer`, `roles/cloudsql.admin` |

---

## 9. golangci-lint の errcheck: `defer tx.Rollback()` がエラーになる

**症状**: `golangci-lint` の errcheck が `tx.Rollback(ctx)` のエラー戻り値を無視していると警告。

**修正**: `defer` 内でエラーを明示的に無視する。

```go
// Before
defer tx.Rollback(ctx)

// After
defer func() { _ = tx.Rollback(ctx) }()
```

---

## GCP Tips

- **Cloud SQL の起動/停止**: `gcloud sql instances patch <name> --activation-policy=ALWAYS|NEVER` で制御。起動に 1-2 分かかる
- **GKE Autopilot の課金**: Pod が 0 なら $0。ノードは自動管理
- **IAM 変更の反映**: 最大 5 分程度かかることがある。`kubectl delete pod` で再作成して反映確認
- **Cloud SQL Proxy v2 起動時間**: CI 環境では 30 秒以上かかることがある。`sleep 5` では不十分。ポートの readiness をポーリングすべき