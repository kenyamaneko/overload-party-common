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

**原因**: Cloud SQL Proxy は SA が所属するプロジェクト（`keyandnotes-platform`）で `sqladmin.googleapis.com` API を呼ぶ。Cloud SQL インスタンスは `overload-party-dev` にあっても、**SA のプロジェクト側で API が有効でないと動かない**。

Proxy の起動時チェック（リスナーの開始）は API 呼び出しを行わないため、`ready for new connections!` と表示されても実際の接続は失敗する。

**修正**:

```bash
gcloud services enable sqladmin.googleapis.com --project=keyandnotes-platform
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
PROJECT_NUMBER=$(gcloud projects describe keyandnotes-platform --format='value(projectNumber)')
gcloud projects add-iam-policy-binding keyandnotes-platform \
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

---

## 10. Homebrew 版 .NET SDK で VS Code C# Dev Kit が起動しない (macOS)

**症状**: VS Code で C# Dev Kit の Solution Explorer が表示されず、F12 (Go to Definition) がクロスプロジェクトで効かない。Output ログに以下のエラー:

```
.NET server STDERR: Failed to load /opt/homebrew/Cellar/dotnet/10.0.103/libexec/host/fxr/10.0.3/libhostfxr.dylib,
error: dlopen(...): code signature in '...' not valid for use in process:
mapping process and mapped file (non-platform) have different Team IDs
```

C# Dev Kit サーバーが exit code 130 で即死する。

**原因**: Homebrew でビルドされた .NET SDK のバイナリ (`libhostfxr.dylib`) のコード署名 Team ID と、VS Code 拡張機能プロセスの Team ID が一致しない。macOS のコード署名検証でロードが拒否される。

C# 言語サーバー (Roslyn) 側はソリューションなしでも単体ファイルとして動くため、エディタ上で構文ハイライトや基本補完は動作する。しかし C# Dev Kit サーバーが起動しないため、Solution Explorer やクロスプロジェクト参照 (F12) は一切使えない。

**修正**: Homebrew 版をアンインストールし、Microsoft 公式インストーラー (`.pkg`) で再インストール。

```bash
brew uninstall dotnet
# https://dotnet.microsoft.com/download から .pkg をダウンロードしてインストール
dotnet --version  # /usr/local/share/dotnet/dotnet から実行されることを確認
```

**ハマりポイント**:

- C# の構文ハイライトと基本補完は動くため、C# Dev Kit が死んでいることに気付きにくい
- Output パネルのドロップダウンで `C#` と `C# Dev Kit` は別チャネル。`C# Dev Kit` 側を確認しないとエラーが見えない
- `.NET: Open Solution` コマンドも無反応になるため、ソリューション設定の問題と誤診しやすい

**参考**: [microsoft/vscode-dotnettools#1002](https://github.com/microsoft/vscode-dotnettools/issues/1002), [Homebrew/homebrew-core#168205](https://github.com/Homebrew/homebrew-core/issues/168205)

---

## 11. WIF の attribute_condition 更新後も認証が通らない

**症状**: WIF の `attribute_condition` にリポを追加し、SA の WIF binding も追加したのに、GitHub Actions で `iam.serviceAccounts.getAccessToken denied` が出る。

**原因**: IAM binding の反映に数分かかる（eventual consistency）。特に WIF provider の `attribute_condition` 更新と SA binding の追加を同時に行った場合、binding が反映されるまでのラグで失敗する。

**対処**: 数分待って CI を再実行すれば通る。WIF 周りの変更直後は 1 回目の失敗を想定しておく。

---

## 12. Terraform CI の鶏と卵問題 — SA の権限を Terraform 自身が付与する

**症状**: infra リポの CI が `terraform-deployer` SA で apply しようとするが、各環境プロジェクト（dev/stg/prod）で権限がなく失敗する。

**原因**: `terraform-deployer` SA に `roles/editor` を付与するのは infra の Terraform 自身（`module.iam.terraform_editor`）。初回は SA に権限がないため CI では apply できない。

**対処**: 各環境の初回 apply はローカルから実行する。`terraform_editor` binding が作成された後は CI で apply 可能になる。destroy すると binding も消えるため、再度ローカル apply が必要。

**構造**:

```
ローカル apply → terraform_editor binding 作成 → CI の terraform-deployer SA が権限取得 → 以降は CI で apply 可能
```

---

## 13. Terraform state bucket が別プロジェクトにある場合の権限

**症状**: infra CI が `terraform init` で `storage.objects.list access denied` になる。

**原因**: Terraform state bucket (`keyandnotes-tf-state`) が `overload-party-stg` プロジェクトに作成されていたが、`terraform-deployer` SA は `keyandnotes-platform` プロジェクトに所属。SA にプロジェクトレベルの editor があっても、**別プロジェクトの bucket にはアクセスできない**。

**修正**: bucket レベルで SA に `objectAdmin` を直接付与。

```bash
gsutil iam ch serviceAccount:terraform-deployer@keyandnotes-platform.iam.gserviceaccount.com:objectAdmin \
  gs://keyandnotes-tf-state
```

**教訓**: state bucket の所在プロジェクトと SA の所属プロジェクトが異なる場合、プロジェクト IAM では不足。bucket-level IAM が必要。

---

## 14. Cloud Resource Manager API が SA のプロジェクトで必要

**症状**: Terraform CI が `google_project_iam_member` の読み取りで `Cloud Resource Manager API has not been used in project 948329072347` エラー。

**原因**: SA が所属するプロジェクト（shared）で `cloudresourcemanager.googleapis.com` が無効だった。Terraform が別プロジェクトの IAM を操作する場合でも、**API 呼び出しは SA が所属するプロジェクト経由**で行われる。

**修正**:

```bash
gcloud services enable cloudresourcemanager.googleapis.com --project=keyandnotes-platform
```

これは Cloud SQL Proxy のパターン（#2）と同じ。**GCP の API 呼び出しは、対象リソースのプロジェクトではなく SA のプロジェクトで API が有効である必要がある**。

---

## 15. `terraform destroy` で Service Networking Connection が削除できない

**症状**: `terraform destroy` が `Failed to delete connection; Producer services are still using this connection` で失敗。

**原因**: Cloud SQL インスタンスを削除した直後でも、GCP 側の VPC peering 解放に時間がかかる。`google_service_networking_connection` の削除が Cloud SQL 削除の直後だとまだ「使用中」と判定される。

**対処**: state から除外して残りを先に削除する。peering 自体は GCP 側で自然に解放される。

```bash
terraform state rm google_service_networking_connection.private
terraform destroy -auto-approve
```

**注意**: これは verify → destroy のような一時的な操作での対処法。本番運用で destroy する場合は、Cloud SQL 削除後に数分待ってから再実行するほうが安全。

---

## 16. Cloud Run Job が別プロジェクトの AR イメージを pull できない

**症状**: Cloud Run Job の作成が `Permission 'artifactregistry.repositories.downloadArtifacts' denied` で失敗。

**原因**: Cloud Run は内部的に **Cloud Run Service Agent** (`service-{PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com`) を使ってイメージを pull する。このエージェント SA は各プロジェクトに自動作成されるが、**別プロジェクトの AR にはデフォルトでアクセス権がない**。

**修正**: 対象プロジェクトの Cloud Run Service Agent に AR の reader 権限を付与。

```bash
gcloud artifacts repositories add-iam-policy-binding overload-party \
  --project=keyandnotes-platform \
  --location=asia-northeast1 \
  --member="serviceAccount:service-{PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.reader"
```

**教訓**: Cloud Run Job / Service の image pull には、ユーザーの SA ではなく Google 管理の Service Agent が使われる。GKE の Compute Engine default SA (#4) と同じパターン。

---

## 17. GitHub Actions の secret 値にコロンが含まれていて gcloud が誤解釈

**症状**: ops CI の `gcloud sql instances patch` が `Instance names cannot contain the ':' character` で失敗。

**原因**: `CLOUDSQL_INSTANCE_NAME` シークレットに Cloud SQL の接続名形式（`project:region:instance`）がセットされていた。`gcloud sql instances patch` が期待するのはインスタンス名（`overload-party-db`）のみ。

**対処**: シークレットをインスタンス名のみに修正。

```bash
gh secret set CLOUDSQL_INSTANCE_NAME --body "overload-party-db"
```

**教訓**: Cloud SQL には「接続名」(`project:region:instance`) と「インスタンス名」(`instance`) の 2 つの識別子がある。Terraform output の `connection_name` をそのままシークレットにセットしがち。

---

## 18. GCS + CDN はトラフィック規模で判断する

**検討**: BGM (MP3, 10 曲 × 1-2 分 ≈ 15-20MB) + SE + カードイラストの配信に CDN が必要か。

**結論**: 東京リージョンの GCS 直配信で十分。

- GCS の Egress: ~$0.12/GB (Asia)
- 1000 ユーザーが全 BGM ダウンロード → 20GB → $2.4/月
- CDN (Cloudflare Pro) は $20/月 — トラフィックが少ない段階ではコスト逆転
- GCS は東京リージョンなので国内レイテンシは十分低い

**CDN を入れるタイミングの目安**:
- 月間 Egress が 100GB を超える（ユーザー数千〜万単位）
- グローバル配信が必要になった
- DDoS 対策や WAF が欲しい

静的アセットは GCS の既存バケット (`{project}-assets`) にプレフィックスで整理すれば十分。CDN レイヤーは後から被せられる。