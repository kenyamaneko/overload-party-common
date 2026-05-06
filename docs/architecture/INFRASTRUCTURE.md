# インフラ設計

関連ドキュメント: [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) / [APPLICATION.md](APPLICATION.md) / [DATA_DESIGN.md](DATA_DESIGN.md)

---

## 目次

1. [インフラ構成](#1-インフラ構成)
2. [CI/CD](#2-cicd)
3. [モニタリング](#3-モニタリング)

---

## 1. インフラ構成

### 1.1 インフラ管理 (Terraform)

Google Cloud リソースは Terraform で管理する。管理対象リソースの詳細は infra リポの README を参照。

| プロジェクト | 用途 |
|-------------|------|
| keyandnotes-platform | GKE, Artifact Registry, WIF, CI SA |
| overload-party-dev | Cloud SQL, IAM (dev 環境) |
| overload-party-stg | Cloud SQL, IAM (stg 環境) |
| overload-party-prod | Cloud SQL, IAM (prod 環境) |

dev/stg は毎日 2:00 JST に自動停止してコストを最小化する。詳細は ops リポの README を参照。

手動操作（環境起動・停止、DB 起動・停止）は ops リポの README を参照。

### 1.2 アセット配信

GCS + Cloudflare CDN で配信。詳細は assets リポの README を参照。

### 1.3 スケーリング指針

スケーリングの詳細（gateway の水平スケール、マルチノード化）は k8s リポの README を参照。

---

## 2. CI/CD

overload-party 全リポジトリの CI/CD に関する横断的な設計情報。各リポの CI 詳細は各リポの `.github/workflows/` を参照。

### 2.1 各リポのパイプライン概要

全サービスリポは以下の 3 ワークフロー構成に統一されている。

| ワークフロー | トリガー | 役割 |
|---|---|---|
| `ci.yaml` | PR + main push | Lint + テスト + Docker ビルド + AR push |
| `validate.yaml` | PR | codegen-sync（生成物と SSoT YAML の整合チェック） |
| `publish.yaml` | main push (paths) | Go / npm パッケージの自動 tag + publish |

| リポ | Lint | テスト | Docker ビルド | パッケージ publish |
|------|------|--------|--------------|-------------------|
| gateway | golangci-lint | go test -race | gateway イメージ | ws-constants, api-gateway (Go + npm) |
| battle | dotnet format | dotnet test | battle イメージ | game-state, game-logic-constants, api-battle-rpc (Go + C# + npm) |
| card | golangci-lint | go test -race | card イメージ | api-card (Go) |
| account | golangci-lint | go test -race | account イメージ | api-account (Go) |
| shop | golangci-lint | go test -race | shop イメージ | api-shop (Go) |
| scenario | golangci-lint | go test -race | scenario イメージ | api-scenario (Go) |
| matchmaking | golangci-lint | go test -race | matchmaking イメージ | api-matchmaking (Go) |
| newsfeed | ruff | pytest | newsfeed イメージ | newsfeed-constants (Go + npm) |
| news | — | — | — | — （CI 未整備） |
| support | — | — | — | — （CI 未整備） |
| common | — | — | — | game-design-constants (Go + C# + npm) |
| client | eslint | vitest | — | — |
| infra | — | — | — | — (terraform plan/apply のみ) |
| k8s | — | — | — | — (kustomize + kubectl のみ) |
| ops | — | — | 各ジョブイメージ | — |
| analytics | — | go test | — | — (gcloud functions deploy のみ) |

### 2.2 リポ間連携

| 送信側 | 受信側 | メカニズム | イベント |
|--------|--------|-----------|---------|
| common | ops | `repository_dispatch` | `db-migrate`（db/ 変更時） |
| common | GitHub Packages | `publish.yaml` | data/packages/ 変更時に自動 publish (patch bump) |
| 各サービスリポ | ops | `repository_dispatch` | `db-migrate`（db/ 変更時、dev 自動） |

### 2.3 認証

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
| `github-deploy` (Deploy) | infra | 同上 |
| WIF プール・プロバイダ | infra | 同上 |

### 2.4 GitHub Actions Variables

| 変数 | 用途 |
|------|------|
| `WIF_PROVIDER` | Workload Identity Provider URI |
| `CI_SERVICE_ACCOUNT` | ビルド・push 用 SA |
| `TF_SERVICE_ACCOUNT` | Terraform 用 SA |
| `DEPLOY_SERVICE_ACCOUNT` | K8s デプロイ用 SA |
| `PSC_SA_LINK_DEV` | PSC ServiceAttachment リンク (dev) |
| `PSC_SA_LINK_STG` | PSC ServiceAttachment リンク (stg) |
| `CLOUDFLARE_ZONE_ID` | Cloudflare Zone ID |
| `CLOUDFLARE_DNS_RECORD_ID_DEV` | Cloudflare DNS レコード ID (dev) |
| `CLOUDFLARE_DNS_RECORD_ID_STG` | Cloudflare DNS レコード ID (stg) |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare Account ID (Workers デプロイ用) |

### 2.5 GitHub Secrets

| シークレット | 保持リポ | 用途 |
|-------------|---------|------|
| `OPS_DISPATCH_TOKEN` | common, 各サービスリポ | ops への repository_dispatch |
| `DB_MIGRATE_TOKEN` | ops | service repo の sparse-checkout |
| `CLOUDFLARE_CDN_API_TOKEN` | infra | Cloudflare CDN 管理 |
| `CLOUDFLARE_DNS_API_TOKEN` | k8s, ops | Cloudflare DNS 更新 |
| `SLACK_WEBHOOK_URL` | k8s | Slack 通知 |
| `CLOUDFLARE_WORKERS_API_TOKEN` | ops | Cloudflare Workers デプロイ |

### 2.6 Artifact Registry

**レジストリ:** `asia-northeast1-docker.pkg.dev/keyandnotes-platform/overload-party/`

| イメージ | ビルド元リポ | タグ戦略 |
|---------|------------|---------|
| `gateway` | gateway | `{SHA}`, `latest` |
| `battle` | battle | `{SHA}`, `latest` |
| `card` | card | `{SHA}`, `latest` |
| `account` | account | `{SHA}`, `latest` |
| `matchmaking` | matchmaking | `{SHA}`, `latest` |
| `shop` | shop | `{SHA}`, `latest` |
| `scenario` | scenario | `{SHA}`, `latest` |
| `db-migrate` | ops | `{SHA}`, `latest` |
| `cost-monitor` | ops | `{SHA}`, `latest` |
| `drift-monitor` | ops | `{SHA}`, `latest` |
| `newsfeed` | newsfeed | `{SHA}`, `latest` |

### 2.7 デプロイ先と方式

| サービス | デプロイ先 | 自動/手動 |
|---------|----------|----------|
| gateway / battle / card / account / matchmaking / shop / scenario | GKE (kustomize + kubectl) | 手動 dispatch |
| news / support | GKE (kustomize + kubectl) | CI 未整備（ローカルビルド → 手動 push） |
| db-migrate | Cloud Run Job | dev 自動 / stg 手動 |
| cost-monitor / drift-monitor | GitHub Actions schedule | schedule (Cloud Run Job ではなくランナー上で実行) |
| newsfeed | Cloud Run Job | main push 自動 |
| analytics | Cloud Function Gen2 | main push 自動 |
| infra | Terraform apply | main push 自動 |

### 2.8 環境戦略

| 環境 | Google Cloud プロジェクト | デプロイ条件 |
|------|-----------------|------------|
| dev | overload-party-dev | main push 自動（ops ジョブ、infra）/ 手動 dispatch（GKE サービス） |
| stg | overload-party-stg | 手動 dispatch |
| prod | overload-party-prod | 手動 dispatch |

### ブランチ・環境戦略

| ブランチ | 環境 |
|---------|------|
| main | prod |
| release | stg |
| develop | dev |

現状: main がまだ安定していないので、まずは main を直接育てる。安定したら上記構成に移行。

---

## 3. モニタリング

- **メトリクス**: Cloud Monitoring。同時対戦数・キュー長・WS 接続数等のカスタムメトリクスを各サービスから送信
- **ログ**: Cloud Logging。構造化ログ（JSON）を使用し、`gameID` / `playerID` でフィルタ可能にする
- **アラート**: DLQ 深度、エラーレート、レイテンシに対してアラートポリシーを設定
