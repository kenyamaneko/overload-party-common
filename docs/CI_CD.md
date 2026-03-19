# CI/CD 設計

overload-party 全リポジトリの CI/CD ワークフローと、リポ間連携の全体像。

## 全体フロー

```
overload-party-common
  │
  ├─ db/ push (main) ──── repository_dispatch ────→ ops/db-migrate-on-push.yaml
  │                                                    └→ build → AR push → Cloud Run Job 実行 (dev)
  │
  ├─ data/ push (main) ──── publish-packages.yaml (workflow_dispatch 対応)
  │                           └→ 前回タグとの差分検出 → Go tag + NuGet push + npm publish
  │
  └─ data/ push (PR) ──── codegen-check.yaml
                            └→ packages/ 内の整合性チェック（クロスリポ不要）

overload-party-gateway
  └─ push (main) ──── ci.yaml
                        ├→ lint (golangci-lint)
                        ├→ test (go test -race)
                        └→ build + push → Artifact Registry (SHA + latest)

overload-party-battle
  └─ push (main) ──── ci.yaml
                        ├→ test (dotnet test)
                        └→ build + push → Artifact Registry (SHA + latest)

overload-party-client
  └─ push / PR ──── ci.yml
  │                   ├→ lint (eslint)
  │                   ├→ typecheck (tsc)
  │                   └→ test (vitest)
  └─ push / PR ──── e2e.yaml
                      └→ Playwright E2E (docker-compose で gateway+battle 起動)

overload-party-infra
  └─ push / PR ──── terraform.yaml
                      ├→ PR: terraform plan (変更環境のみ)
                      └→ main: terraform apply (順次実行)

overload-party-k8s
  ├─ workflow_dispatch ──── deploy.yaml
  │                          └→ kustomize edit set image → kubectl apply
  ├─ workflow_dispatch ──── startup.yaml
  │                          └→ Pod スケール 1 → Ingress 適用 → Cloudflare DNS 更新
  ├─ cron (2:00 JST) ──── nightly-shutdown.yaml
  │                          └→ Ingress 削除 → IP 解放 → DNS 無効化 → Pod スケール 0
  └─ push / PR ──── terraform.yaml
                      └→ GKE / AR / WIF の Terraform plan/apply

overload-party-ops
  ├─ workflow_dispatch ──── db-migrate.yaml
  │                          └→ schema_check → build → AR push → Cloud Run Job 実行
  ├─ repository_dispatch ── db-migrate-on-push.yaml (common から自動)
  ├─ push (main) ──── nightly-review.yaml  (nightly-review/** 変更時)
  ├─ push (main) ──── cost-monitor.yaml    (cost-monitor/** 変更時)
  ├─ push (main) ──── drift-monitor.yaml   (drift-monitor/** 変更時)
  │     └→ 共通: build-deploy-job.yaml (reusable workflow)
  │          └→ build → AR push → Cloud Run Job イメージ更新
  └─ push (main) ──── slack-commands.yaml  (slack-commands/** 変更時)
        └→ build-deploy-service.yaml (reusable workflow)
             └→ build → AR push → Cloud Run Service イメージ更新

overload-party-newsfeed
  └─ push (main) ──── ci.yaml
                        ├→ build + push → Artifact Registry (SHA + latest)
                        └→ Cloud Run Job イメージ更新 (dev)

overload-party-analytics
  └─ push / PR ──── ci.yaml
                      ├→ PR: go vet + go build
                      └→ main: gcloud functions deploy (dev)
```

## リポ間連携

| 送信側 | 受信側 | メカニズム | イベント |
|--------|--------|-----------|---------|
| common | ops | `repository_dispatch` | `db-migrate`（db/ 変更時） |
| common | GitHub Packages | `publish-packages.yaml` | data/ 変更時にパッケージ publish (Go tag, NuGet, npm) |

`repository_dispatch` は GitHub API 経由でワークフローを起動する仕組み。common の ci.yaml が ops リポに POST し、ops 側の `db-migrate-on-push.yaml` が受信して dev 環境のマイグレーションを自動実行する。

## 認証

全リポ共通で **Workload Identity Federation (WIF)** を使用。

```
GitHub Actions (OIDC token)
    │
    ▼
Workload Identity Provider (keyandnotes-platform)
    │
    ▼
Service Account (用途別)
    ├─ CI_SERVICE_ACCOUNT      — イメージビルド・AR push・Cloud Run Jobs 更新・Cloud Functions deploy
    ├─ TF_SERVICE_ACCOUNT      — Terraform plan/apply
    └─ DEPLOY_SERVICE_ACCOUNT  — kubectl apply (GKE)
```

**SA の管理場所:**

| SA | 管理リポ | Terraform パス |
|----|---------|---------------|
| `github-ci` (CI) | infra | `environments/platform/` → `modules/ci-cd/` |
| `terraform-deployer` (TF) | infra | 同上 |
| `github-deploy` (Deploy) | k8s | `terraform/environments/platform/` → `modules/ci-cd/` |
| WIF プール・プロバイダ | infra | 同上 |

**GitHub Secrets（全リポ共通）:**

| シークレット | 用途 |
|-------------|------|
| `WIF_PROVIDER` | Workload Identity Provider URI |
| `CI_SERVICE_ACCOUNT` | ビルド・push 用 SA |
| `TF_SERVICE_ACCOUNT` | Terraform 用 SA |
| `DEPLOY_SERVICE_ACCOUNT` | K8s デプロイ用 SA |

**リポ間アクセス用トークン:**

| シークレット | 保持リポ | 用途 |
|-------------|---------|------|
| `OPS_DISPATCH_TOKEN` | common | ops への repository_dispatch |
| `COMMON_REPO_TOKEN` | ops | common の sparse-checkout |
| `CROSS_REPO_TOKEN` | common | ~~廃止予定~~ 旧 codegen-check 用（現在は不要） |
| `CF_API_TOKEN` | k8s | Cloudflare DNS 更新 |

## Artifact Registry

**レジストリ:** `asia-northeast1-docker.pkg.dev/keyandnotes-platform/overload-party/`

| イメージ | ビルド元リポ | タグ戦略 |
|---------|------------|---------|
| `overload-party-gateway` | gateway | `{SHA}`, `latest` |
| `overload-party-battle` | battle | `{SHA}`, `latest` |
| `db-migrate` | ops | `{SHA}`, `latest` |
| `nightly-review` | ops | `{SHA}`, `latest` |
| `cost-monitor` | ops | `{SHA}`, `latest` |
| `drift-monitor` | ops | `{SHA}`, `latest` |
| `slack-commands` | ops | `{SHA}`, `latest` |
| `newsfeed` | newsfeed | `{SHA}`, `latest` |

## デプロイ先と方式

| サービス | デプロイ先 | 方式 | 自動/手動 |
|---------|----------|------|----------|
| gateway | GKE (dev/stg/prod namespace) | kustomize + kubectl apply | 手動 dispatch |
| battle | GKE (dev/stg/prod namespace) | kustomize + kubectl apply | 手動 dispatch |
| db-migrate | Cloud Run Job | gcloud run jobs update + execute | dev 自動 / stg 手動 |
| nightly-review | Cloud Run Job | gcloud run jobs update | main push で自動 |
| cost-monitor | Cloud Run Job | gcloud run jobs update | main push で自動 |
| drift-monitor | Cloud Run Job | gcloud run jobs update | main push で自動 |
| slack-commands | Cloud Run Service | gcloud run services update | main push で自動 |
| newsfeed | Cloud Run Job | gcloud run jobs update | main push で自動 |
| analytics | Cloud Function Gen2 | gcloud functions deploy | main push で自動 |
| infra | Terraform | terraform apply | main push で自動 |

## スケジュールジョブ

Cloud Scheduler が Cloud Run Job を起動する。イメージ更新は CI で行い、実行はスケジューラ任せ。

| ジョブ | スケジュール (JST) | 管理 |
|--------|-------------------|------|
| nightly-review | 3:00 (毎日) | ops terraform |
| cost-monitor | 8:00 (毎日) | ops terraform |
| drift-monitor | 7:00 (毎日) | ops terraform |
| newsfeed | 2時間ごと | infra terraform |
| Cloud SQL 停止 (dev/stg) | 2:00 | infra terraform |
| K8s シャットダウン (dev/stg) | 2:00 | k8s cron workflow |

## 環境戦略

| 環境 | GCP プロジェクト | デプロイ条件 |
|------|-----------------|------------|
| dev | overload-party-dev | main push で自動（ops ジョブ、infra）/ 手動 dispatch（gateway, battle） |
| stg | overload-party-stg | 手動 dispatch |
| prod | overload-party-prod | 手動 dispatch（将来的に承認ゲート追加） |

### ブランチ・環境戦略まとめ

| ブランチ | 環境 | 備考 |
|---------|------|------|
| main | prod | |
| release | stg | long-lived で運用開始、将来的にバージョン管理が必要になったら short-lived（release/1.0.0）に移行 |
| develop | dev | |
| feature/* | なし | |

現状：main がまだ安定していないので、まずは main を直接育てる。安定したら上記構成に移行。
