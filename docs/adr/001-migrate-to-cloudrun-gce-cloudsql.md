# ADR-001: GKE + Spanner → Cloud Run + GCE + Cloud SQL への移行

## ステータス

Accepted (2026-02-26)

## 結論

MVP フェーズのインフラコストを最小化するため、ハイブリッド構成を採用する。REST API は Cloud Run、WebSocket は GCE VM (Managed Instance Group)、DB は Cloud SQL PostgreSQL に移行する。インフラコストは ~$41-46/月 (70% 以上削減) となり、コード変更は DB 層 (Repository 実装追加) とサーバー分割 (cmd/api, cmd/ws) に閉じ、ゲームエンジン・サービス層・WebSocket Manager・マッチメイキングは変更しない。

## 背景・課題

Overload Party ゲームサーバーは初期段階では GKE + Spanner ($150+/月) のコストが過剰。
MVP フェーズではコストを最小化しつつ、将来のスケーラビリティへの道筋を残す構成が必要。

## 制約

- プレイヤーアクション毎の DB 書き込み (GameState の read-modify-write)
- WebSocket によるリアルタイム対戦通信
- ステートレス REST API (デッキ編集、ショップ等)
- PostgreSQL の JSONB で Spanner の JSON 列を再現可能

## 詳細

### REST API → Cloud Run

- ステートレス HTTP エンドポイント
- オートスケール、アイドル時はゼロスケール ($0)
- デッキ管理、ショップ、NPC 戦、ゲームログ等

### WebSocket → GCE VM (Managed Instance Group)

- 単一 e2-small インスタンス (ターゲットサイズ: 1)
- Manager のインメモリ状態 (接続プール、ゲーム所属、切断タイマー) をそのまま活用
- マッチメイキングキューもインメモリ
- MIG のヘルスチェック + 自動修復で可用性確保
- 将来のスケール時: GCE → 複数インスタンス化する場合は Valkey を導入

### DB → Cloud SQL PostgreSQL

- UUID 主キー (Spanner の STRING(36) から移行)
- JSONB 列で GameState のフィールド/手札/リポジトリ等を格納
- SELECT FOR UPDATE による行ロック (Spanner の ReadWriteTransaction 相当)
- Repository パターンにより DB 実装の差し替えを吸収する

### デプロイ時の注意点

- **`/healthz` は GFE 予約パス**: Cloud Run や App Engine では、Google Front End (ロードバランサー層) が `/healthz` をインターセプトし、コンテナに到達せず Google の 404 を返す。ヘルスチェックには `/health` を使用すること
- **Cloud Run v2 の `PORT` 環境変数**: 予約語のため明示設定不可。`containerPort` の値から自動設定される
- **Cloud SQL の `edition`**: `db-g1-small` 等の小型インスタンスでは `edition = "ENTERPRISE"` を明示指定 (デフォルトの ENTERPRISE_PLUS ではエラー)
- **Direct VPC Egress**: VPC Access Connector より追加コスト不要。Cloud Run の `network_interfaces` で設定
- **GCE MIG はリージョナル + `ANY` 分散ポリシー**: ゾーン単位のリソース枯渇 (`ZONE_RESOURCE_POOL_EXHAUSTED`) を回避するため、ゾーナル MIG ではなくリージョナル MIG を使用。`distribution_policy_target_shape = "ANY"` でリソースが確保できるゾーンに自動配置。MIG の自動修復がリトライを行う

## 不採用案

### Cloud Run のみ (WebSocket + Cloud Pub/Sub)

却下理由:

- Cloud Run のエフェメラルインスタンスと WebSocket の相性が悪い
- 複数インスタンス間の fan-out に per-instance subscription が必要
- subscription のライフサイクル管理が複雑 (orphan 問題)
- コスト面では有利だが、設計の複雑さが MVP に不釣り合い

### Cloud Run + Memorystore for Valkey

却下理由:

- Valkey は Pub/Sub + 状態管理を 1 つのサービスで解決できる
- しかし ~$35/月の追加コストが初期段階には過剰
- WS を単一 GCE にすれば Valkey 自体が不要

### PostgreSQL LISTEN/NOTIFY

却下理由:

- Cloud Run のエフェメラル特性と非互換
- LISTEN 接続はインスタンスの常時起動が前提
- Cloud Run のゼロスケールの利点と矛盾
