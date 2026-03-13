# Project Migration TODO

## 現在の状況 (2026-02-19)

**使用中のプロジェクト**: `overload-party-stg`

**理由**:
- 本来使用予定だった `overload-party-dev` のプロジェクトIDが、別組織のGoogleアカウントで取得済み
- GCP プロジェクトIDは削除後30日間予約される
- その間は同じIDで新規プロジェクトを作成できない

---

## 移行が必要な時期

**元のプロジェクトが完全に削除されたら（削除から30日後）**

---

## 移行手順

### 1. 新しい `overload-party-dev` プロジェクトを作成

```bash
# プロジェクト作成
gcloud projects create overload-party-dev --name="Overload Party Dev"

# 課金アカウントを紐付け
gcloud billing accounts list
gcloud billing projects link overload-party-dev --billing-account=BILLING_ACCOUNT_ID

# 必要なAPIを有効化
gcloud services enable cloudbuild.googleapis.com --project=overload-party-dev
gcloud services enable run.googleapis.com --project=overload-party-dev
gcloud services enable containerregistry.googleapis.com --project=overload-party-dev
gcloud services enable iam.googleapis.com --project=overload-party-dev
```

### 2. 設定ファイルを更新

#### `terraform/environments/dev/main.tf`

```diff
 locals {
-  # TEMPORARY: Using staging project because 'overload-party-dev' ID is reserved
-  # by a previous organization account (30-day deletion period).
-  # TODO: Switch back to 'overload-party-dev' once the original project is fully deleted.
-  # Original intention: project_id = "overload-party-dev"
-  project_id     = "overload-party-stg"
+  project_id     = "overload-party-dev"
   gke_project_id = "keyandnotes-platform"
   region         = "asia-northeast1"
 }
```

#### `Makefile`

```bash
# 一括置換
sed -i '' 's/overload-party-stg/overload-party-dev/g' Makefile

# または手動で --project=overload-party-stg を --project=overload-party-dev に変更
```

### 3. Terraform で新環境をデプロイ

```bash
# Terraform の state をクリーンアップ（新環境なので）
make terraform-clean

# 新しいプロジェクトにデプロイ
make cloud-job-build
make terraform-deploy-balance

# テスト実行
make cloud-job-run
make cloud-job-logs
```

### 4. 旧環境（stg）のクリーンアップ

```bash
# 旧プロジェクト（overload-party-stg）のリソースを削除
gcloud config set project overload-party-stg

# Cloud Run Job 削除
gcloud run jobs delete balance-test --region=asia-northeast1 --quiet

# Service Account 削除（必要に応じて）
gcloud iam service-accounts delete game-server-dev@overload-party-stg.iam.gserviceaccount.com --quiet

# Container Registry のイメージ削除（任意）
gcloud container images list --repository=gcr.io/overload-party-stg
gcloud container images delete gcr.io/overload-party-stg/balance-job:latest --quiet
```

---

## チェックリスト

移行時に以下を確認：

- [ ] 新しい `overload-party-dev` プロジェクトが作成可能になった
- [ ] `terraform/environments/dev/main.tf` の project_id を更新
- [ ] `Makefile` の --project フラグをすべて更新
- [ ] Terraform で新環境をデプロイ
- [ ] Cloud Run Job が正常に動作することを確認
- [ ] 旧環境（stg）のリソースを削除
- [ ] このドキュメントを削除または Archive

---

## 影響を受けるファイル

1. **terraform/environments/dev/main.tf** - locals.project_id
2. **Makefile** - cloud-job-build, cloud-job-run, cloud-job-logs, cloud-job-update-env の --project フラグ

以上の2ファイルのみ変更すれば移行完了。
