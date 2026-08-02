# インフラ設計

関連ドキュメント: [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) / [APPLICATION.md](APPLICATION.md) / [DATA_DESIGN.md](DATA_DESIGN.md)

---

## 目次

- [インフラ構成](#インフラ構成)
- [CI/CD](#cicd)
- [モニタリング](#モニタリング)

---

## インフラ構成

### インフラ管理 (Terraform)

Google Cloud リソースは Terraform で管理する。管理対象リソースの詳細は infra リポの README を参照。

| プロジェクト | 用途 |
|-------------|------|
| keyandnotes-platform | GKE, Artifact Registry, WIF, CI SA |
| overload-party-dev | Cloud SQL, IAM (dev 環境) |
| overload-party-stg | Cloud SQL, IAM (stg 環境) |
| overload-party-prod | Cloud SQL, IAM (prod 環境) |

dev/stg は毎日 2:00 JST に自動停止してコストを最小化する。詳細は ops リポの README を参照。

手動操作（環境起動・停止、DB 起動・停止）は ops リポの README を参照。

### アセット配信

GCS + Cloudflare CDN で配信。詳細は assets リポの README を参照。

### スケーリング指針

スケーリングの詳細（gateway の水平スケール、マルチノード化）は k8s リポの README を参照。

---

## CI/CD

overload-party 全リポジトリの CI/CD に関する横断的な設計情報。各リポの CI 詳細は各リポの `.github/workflows/` を参照。

### 各リポのパイプライン概要

全サービスリポは以下の 3 ワークフロー構成に統一されている。

| ワークフロー | トリガー | 役割 |
|---|---|---|
| `ci.yaml` | PR | Lint + テスト + codegen-sync |
| `deploy.yaml` | main push (dev) / `v*.*.*` タグ push (stg) / workflow_dispatch (prod) | Docker ビルド + AR push + Cloud Run への反映 |
| `publish.yaml` | main push (paths) | Go / npm パッケージの自動 tag + publish |

| リポ | Lint | テスト | Docker ビルド | パッケージ publish |
|------|------|--------|--------------|-------------------|
| gateway | golangci-lint | go test -race | gateway イメージ | ws-constants, api-gateway, internalauth-go (Go + npm) |
| battle | dotnet format | dotnet test | battle イメージ | game-state, game-logic-constants, api-battle-rpc (Go + npm) |
| card | golangci-lint | go test -race | card イメージ | api-card (Go + npm + NuGet) |
| account | golangci-lint | go test -race | account イメージ | api-account (Go + npm) |
| shop | golangci-lint | go test -race | shop イメージ | api-shop (Go + npm) |
| scenario | golangci-lint | go test -race | scenario イメージ | api-scenario (Go + npm) |
| matchmaking | golangci-lint | go test -race | matchmaking イメージ | api-matchmaking (Go) |
| news | golangci-lint | go test -race | news イメージ | api-news (Go + npm) |
| support | golangci-lint | go test -race | support イメージ | api-support (Go + npm) |
| newsfeed | ruff | pytest | newsfeed イメージ | newsfeed-constants (Go + npm) |
| common | — | — | — | game-design-constants (Go + npm) |
| client | eslint | vitest | — | — |
| infra | — | — | — | — (terraform plan/apply のみ) |
| k8s | — | — | — | — (env-lifecycle のみ) |
| ops | — | — | 各ジョブイメージ | — |
| analytics | — | go test | — | — (gcloud functions deploy のみ) |

### リポ間連携

| 送信側 | 受信側 | メカニズム | イベント |
|--------|--------|-----------|---------|
| common | ops | `repository_dispatch` | `db-migrate`（db/ 変更時） |
| common | Go module proxy / Cloudsmith | `publish.yaml` | data/packages/ 変更時に自動 publish (patch bump) |
| 各サービスリポ | ops | `repository_dispatch` | `db-migrate`（db/ 変更時、dev 自動） |

### 認証

#### Google Cloud (Workload Identity Federation)

GitHub Actions から Google Cloud リソースへアクセスする認証は、全リポ共通で **Workload Identity Federation (WIF)** を使用する。

```
GitHub Actions (OIDC token)
    │
    ▼
Workload Identity Provider (keyandnotes-platform)
    │
    ▼
Service Account (用途別)
    ├─ CI_SERVICE_ACCOUNT      — イメージビルド・AR push・Cloud Run サービス / Jobs 更新・Cloud Functions deploy
    └─ TF_SERVICE_ACCOUNT      — Terraform plan/apply
```

**SA の管理場所:**

| SA | 管理リポ | Terraform パス |
|----|---------|---------------|
| `github-ci` (CI) | infra | `environments/platform/` → `modules/ci-cd/` |
| `terraform-deployer` (TF) | infra | 同上 |
| WIF プール・プロバイダ | infra | 同上 |

#### Cross-repo / 自動化 (GitHub App)

リポ間連携・自動化の認証から **個人 PAT を排除する**。PAT は (a) 期限切れに気付くのが事故時、(b) 一人の権限と密結合するため離脱・権限見直しのコストが高い、(c) scope が粗く 1 トークンあたりの権限が肥大化しがち、という構造的問題を抱える。これを **用途別の GitHub App** に置き換え、permission を最小化しつつ漏洩時の blast radius を分割する（[ADR-033](../adr/033-cross-repo-auth-github-app-migration.md)）。

設計上の選択:

- **読み取りと書き込みを別 App に分ける**: 広くインストールされる Read 系と、影響範囲を絞りたい Write 系を一緒にしない
- **organization 配信で設定漏れを排除**: App ID は organization variable、private key は organization secret に置き、新リポ作成時の貼り直し運用を不要にする
- **rotation を運用から切り離す**: GitHub App private key は無期限のため定期 rotate を廃止し、漏洩疑い・key 保有者離脱時のみ revoke + 差し替える（複数 key の同時発行が可能なためダウンタイムなし）
- **fetch 系セットアップは composite action に集約**: 全サービスリポが共通の Go private module fetch ロジックを抱えないよう、`overload-party-common/.github/actions/setup-go-private-modules` を経由して使う

App 構成・permissions の詳細・既知の制約は ADR-033 を参照。

### GitHub Actions Variables

| 変数 | 用途 |
|------|------|
| `WIF_PROVIDER` | Workload Identity Provider URI |
| `CI_SERVICE_ACCOUNT` | ビルド・push 用 SA |
| `TF_SERVICE_ACCOUNT` | Terraform 用 SA |
| `PSC_SA_LINK_DEV` | PSC ServiceAttachment リンク (dev) |
| `PSC_SA_LINK_STG` | PSC ServiceAttachment リンク (stg) |
| `CLOUDFLARE_ZONE_ID` | Cloudflare Zone ID |
| `CLOUDFLARE_DNS_RECORD_ID_DEV` | Cloudflare DNS レコード ID (dev) |
| `CLOUDFLARE_DNS_RECORD_ID_STG` | Cloudflare DNS レコード ID (stg) |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare Account ID (Workers デプロイ用) |

### GitHub Secrets

GitHub 内のリソースへアクセスする認証情報は「Cross-repo / 自動化 (GitHub App)」の GitHub App private key（organization secret）に集約する。本表は Google Cloud / 外部 SaaS 向けのシークレットのみを対象とする。

| シークレット | 保持リポ | 用途 |
|-------------|---------|------|
| `CLOUDFLARE_CDN_API_TOKEN` | infra | Cloudflare CDN 管理 |
| `CLOUDFLARE_DNS_API_TOKEN` | k8s, ops | Cloudflare DNS 更新 |
| `CLOUDFLARE_WORKERS_API_TOKEN` | ops | Cloudflare Workers デプロイ |
| `SLACK_WEBHOOK_URL` | k8s | Slack 通知 |

### Artifact Registry

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
| `news` | news | `{SHA}`, `latest` |
| `support` | support | `{SHA}`, `latest` |
| `db-migrate` | ops | `{SHA}`, `latest` |
| `cost-monitor` | ops | `{SHA}`, `latest` |
| `drift-monitor` | ops | `{SHA}`, `latest` |
| `newsfeed` | newsfeed | `{SHA}`, `latest` |

### デプロイ先と方式

デプロイ (artifact 出力と環境反映) は CI (品質ゲート) と別の workflow に分ける（[ADR-041](../adr/041-ci-deploy-trigger-separation.md)）。9 サービスは Cloud Run で動き（[ADR-056](../adr/056-retire-gke-gitops-return-to-cloudrun.md)、[ADR-058](../adr/058-gateway-on-cloudrun-single-instance.md)）、各リポの `deploy.yaml` は common の reusable workflow `go-service-deploy.yaml` を呼ぶだけの caller である（[ADR-054](../adr/054-go-service-reusable-workflows.md)）。dev はイメージをビルドして AR に push した上で反映し、stg / prod は指定されたタグが指すコミットのイメージをビルドせずそのまま反映する。

| サービス | デプロイ先 | 環境反映 |
|---------|----------|----------|
| gateway / battle / card / account / matchmaking / shop / scenario / news / support | Cloud Run | dev: main push 自動 / stg: `v*.*.*` タグ push 自動 / prod: 手動 dispatch |
| db-migrate | Cloud Run Job | dev 自動 / stg 手動 |
| cost-monitor / drift-monitor | GitHub Actions schedule | schedule (Cloud Run Job ではなくランナー上で実行) |
| newsfeed | Cloud Run Job | 手動 dispatch（lint/test green を `needs:` で待つ） |
| analytics | Cloud Function Gen2 | 手動 dispatch（同上） |
| infra | Terraform apply | main push 自動 |

### 環境戦略

全サービスリポは GitHub Flow（main + feature ブランチ + PR）で運用し、環境反映はブランチではなく main へのマージ・タグ・手動実行で制御する。リポごとにどのデプロイ戦略を採るかは `rules/repos.yaml` の `deploy` で解決する（[ADR-050](../adr/050-branch-and-deploy-strategy-separation.md)）。

| 環境 | Google Cloud プロジェクト | 環境反映 |
|------|-----------------|------------|
| dev | overload-party-dev | 9 サービス・ops ジョブ・infra とも main push 自動 |
| stg | overload-party-stg | 9 サービスは `v*.*.*` タグ push 自動 / ops ジョブは手動 dispatch |
| prod | overload-party-prod | 手動 dispatch でタグを指定 |

### CI 標準設定

CI のコスト管理は **構造的な無駄削減** で行う方針を採る。不要トリガーの抑制 (`paths-ignore`) / ハング上限の固定 (`timeout-minutes`) / 古い workflow の自動キャンセル (`concurrency`) を全リポ標準として強制し、新リポ立ち上げ時に初期不備が混入しない構造にする（[ADR-038](../adr/038-ci-execution-time-reduction.md)）。runner はその後の超過課金の圧を受けて GitHub-hosted から `ubicloud-standard-2` に切り替えた（[ADR-040](../adr/040-ci-runner-migration-to-ubicloud.md)）。

具体値・適用対象・job 種別ごとの timeout 上限は ADR-038、運用ルールは keyandnotes-rules の `rules/principles.md` `[base] CI方針` を参照。

---

## モニタリング

- **メトリクス**: Cloud Monitoring。同時対戦数・キュー長・WS 接続数等のカスタムメトリクスを各サービスから送信
- **ログ**: Cloud Logging。構造化ログ（JSON）を使用し、`gameID` / `playerID` でフィルタ可能にする
- **アラート**: DLQ 深度、エラーレート、レイテンシに対してアラートポリシーを設定
