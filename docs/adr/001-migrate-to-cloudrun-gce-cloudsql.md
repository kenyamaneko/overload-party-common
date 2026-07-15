# ADR-001: GKE + Spanner → Cloud Run + GCE + Cloud SQL への移行

## ステータス

Accepted (2026-02-26)

## 結論

MVP フェーズのインフラコストを最小化するため、ハイブリッド構成を採用する。REST API は Cloud Run、WebSocket は GCE VM (Managed Instance Group)、DB は Cloud SQL PostgreSQL に移行する。インフラコストは ~$41-46/月 (70% 以上削減) となり、コード変更は DB 層 (Repository 実装追加) とサーバー分割 (cmd/api, cmd/ws) に閉じ、ゲームエンジン・サービス層・WebSocket Manager・マッチメイキングは変更しない。

## 背景・課題

Overload Party ゲームサーバーは初期段階では GKE + Spanner ($150+/月) のコストが過剰。
MVP フェーズではコストを最小化しつつ、将来のスケーラビリティへの道筋を残す構成が必要。
ワークロードはインメモリの接続・ゲーム状態に依存するリアルタイム WebSocket、ゼロスケールが効くステートレス REST、アクション毎の行ロック書き込みを要する DB という性質の異なる三種からなり、それぞれに適したサービスへ振り分ける必要があった。

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
