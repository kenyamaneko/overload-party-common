# インフラ TODO

dev 環境の基盤は構築済み。今後のフェーズで必要になる項目。

---

## 短期 (クライアント結合前)

### Ingress / ドメイン / TLS
- [x] ドメイン: `keyandnotes.com` (お名前.com + Cloudflare DNS)
- [x] サブドメイン構成: `overloadparty-{dev,stg}.keyandnotes.com` / `overloadparty.keyandnotes.com` (prod)
- [x] TLS: Cloudflare SSL (Flexible) で TLS 終端 → GKE Ingress は HTTP
- [x] パスベースルーティング: `/api/*` → api-server, `/ws` → ws-server (Ingress component)
- [x] CORS 設定 (`ALLOWED_ORIGINS` 環境変数 + WebSocket Origin チェック)
- [x] dev 用グローバル静的 IP 予約 (`overload-party-dev-ip`: `34.149.76.35`)
- [x] `env-up.sh` / `env-down.sh` の bash 3.2 互換修正 (`declare -A` → `case`)
- [x] `env-up.sh` に静的 IP annotation 自動付与を追加
- [x] Cloudflare DNS A レコード作成 (`overloadparty-dev.keyandnotes.com` → `34.149.76.35`)
- [x] Cloudflare SSL モードを Flexible に設定
- [x] HTTPS 疎通確認 (`https://overloadparty-dev.keyandnotes.com/health` → 200 OK)

### Firebase Authentication
- [ ] Firebase プロジェクト作成 + Web/iOS/Android アプリ登録
- [x] サーバー側の Firebase Admin SDK 設定 (認証ミドルウェア) ※実装済み (`internal/middleware/auth.go`)
- [ ] クライアント側の Firebase SDK 統合

---

## 中期 (リリース前)

### Terraform リポジトリ分離
- [ ] `overload-party-infra` リポ作成 (Terraform: GCP プロジェクト, Cloud SQL, VPC, IAM, 静的 IP 等)
  - K8s マニフェスト (`overload-party-k8s`) とはライフサイクル・権限・CI が異なるため別リポ
  - 構成: `environments/{dev,stg,prod}/` + `modules/`

### stg / prod 環境
- [x] k8s overlay 作成 (`k8s/overlays/stg/`, `k8s/overlays/prod/`)
- [ ] Cloud SQL インスタンス作成 (stg / prod プロジェクト)
- [ ] Terraform environments 追加 (stg / prod)
- [ ] GitHub Secrets 追加 (stg / prod 用)
- [ ] deploy.yaml に承認ステップ追加 (prod)

### モニタリング / アラート（詳細: [MONITORING.md](MONITORING.md)）
- [ ] **Phase 1: 構造化ログ** — `log/slog` 導入 + JSON 出力 (Cloud Logging 自動連携)
- [ ] **Phase 2: Cloud SQL Insights** — Terraform `insights_config` 有効化
- [ ] **Phase 3: カスタムメトリクス** — `prometheus/client_golang` + PodMonitoring CRD (GKE Managed Prometheus)
- [ ] **Phase 4: ダッシュボード + アラート** — Cloud Monitoring (Pod restart, error spike, Cloud SQL 高負荷, WS 接続断)

### セキュリティ
- [ ] Cloud SQL: Public IP 廃止 + CI db-migrate を GKE Job に移行
  - 現状: Public IP 有効 + `authorized_networks` 未設定（全 IP 許可）
  - ただし IAM DB 認証のため SA トークンなしでは接続不可（リスク中程度）
  - 方針: リリース前に `ipv4_enabled = false` にして Public IP を廃止
  - CI からは GKE 内の K8s Job で psqldef を実行（Private IP 経由）
- [ ] GKE: NetworkPolicy でサービス間通信を制限
- [ ] Secret Manager でアプリシークレットを管理 (Apple/Google 課金キー等)
  - Firebase credentials は ADC + Workload Identity で管理済み（キーファイル不要）

---

## 長期 (スケール時)

### パフォーマンス
- [ ] HPA (Horizontal Pod Autoscaler) 設定
- [ ] Cloud SQL のスケールアップ (db-g1-small → db-custom)
- [ ] Read Replica 追加 (読み取り負荷分散)
- [ ] Cloud CDN (静的アセット)

### 運用改善
- [ ] Agones 統合 (ゲームサーバー管理)
- [ ] CD 自動化: server repo の main push → k8s repo の deploy 自動トリガー
- [ ] Canary deploy / Blue-Green deploy
- [ ] Cloud SQL のメンテナンスウィンドウ設定

### コスト最適化
- [ ] Spot Pod 検討 (API サーバーのみ)
- [ ] Cloud SQL committed use discount (prod)
- [ ] 環境ごとのリソースサイズ最適化

---

## 完了済み

- [x] GKE Autopilot クラスタ作成 (overload-party-shared)
- [x] Cloud SQL PostgreSQL 作成 (overload-party-dev)
- [x] Artifact Registry 作成
- [x] WIF + CI SA + Deploy SA 作成
- [x] Workload Identity (KSA → GSA) 設定
- [x] CI パイプライン (lint, test, build-and-push, db-migrate)
- [x] K8s マニフェスト (api + ws + Cloud SQL Proxy sidecar)
- [x] コスト削減自動化 (nightly-shutdown, startup)
- [x] 初回 GKE デプロイ成功
- [x] Ingress パスベースルーティング (`/api/*`, `/ws`, `/health`)
- [x] BackendConfig (WS 24h timeout + connection draining)
- [x] CORS ミドルウェア + WebSocket Origin チェック (`ALLOWED_ORIGINS`)
- [x] K8s ConfigMap に `allowed-origins` 追加 (stg/prod)
- [x] ドメイン・TLS 方針決定 (Cloudflare SSL Flexible)
- [x] dev 用グローバル静的 IP 予約 (`overload-party-dev-ip`)
- [x] env-up.sh / env-down.sh bash 3.2 互換修正 + 静的 IP 対応
- [x] k8s overlay stg / prod 作成 (Ingress component 含む)
- [x] dev 環境 Ingress デプロイ + 静的 IP での LB 動作確認 (`http://34.149.76.35/health` → 200 OK)
- [x] Firebase Admin SDK 認証ミドルウェア (`internal/middleware/auth.go`, REST + WS 両対応)