# インフラ TODO

dev 環境の基盤は構築済み。今後のフェーズで必要になる項目。

---

## 短期 (クライアント結合前)

### Ingress / ドメイン / TLS
- [ ] ドメイン取得・DNS 設定
- [ ] GKE Ingress に TLS 証明書を設定 (Google-managed certificate)
- [ ] パスベースルーティング: `/api/*` → api-server, `/ws` → ws-server
- [ ] CORS 設定 (`ALLOWED_ORIGINS` 環境変数)

### Firebase Authentication
- [ ] Firebase プロジェクト作成 + Web/iOS/Android アプリ登録
- [ ] サーバー側の Firebase Admin SDK 設定 (認証ミドルウェア)
- [ ] クライアント側の Firebase SDK 統合

---

## 中期 (リリース前)

### stg / prod 環境
- [ ] k8s overlay 作成 (`k8s/overlays/stg/`, `k8s/overlays/prod/`)
- [ ] Cloud SQL インスタンス作成 (stg / prod プロジェクト)
- [ ] Terraform environments 追加 (stg / prod)
- [ ] GitHub Secrets 追加 (stg / prod 用)
- [ ] deploy.yaml に承認ステップ追加 (prod)

### モニタリング / アラート
- [ ] Cloud Monitoring ダッシュボード (CPU, Memory, HTTP latency, error rate)
- [ ] アラートポリシー (Pod restart, error spike, Cloud SQL 高負荷)
- [ ] 構造化ログ (Cloud Logging / JSON 形式)
- [ ] Cloud SQL Insights 有効化

### セキュリティ
- [ ] Cloud SQL: Authorized Networks を CI の IP に限定 (現在は全 IP 許可)
- [ ] GKE: NetworkPolicy でサービス間通信を制限
- [ ] Secret Manager でアプリシークレットを管理 (Firebase credentials 等)

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