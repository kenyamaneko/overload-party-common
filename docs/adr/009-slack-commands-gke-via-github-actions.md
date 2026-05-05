# ADR-009: Slack コマンド /gke-up, /gke-down の実行方式に GitHub Actions を採用

## ステータス

Accepted (2026-03-19)

## コンテキスト

GKE 環境の起動・停止を Slack コマンドから実行したい。
処理内容は PSC 作成、Pod スケール、Ingress 適用、Cloudflare DNS 更新と多岐にわたり、
`gcloud` CLI と `kubectl` を使うのが最もシンプルな実装になる。

Slack コマンドの受け口は Cloud Run 上の FastAPI サービス（slack-commands）にあるが、
コンテナ内に gcloud SDK + kubectl を入れると **イメージサイズが 500MB 以上増加** し、
起動時間・メモリ消費・ビルド時間すべてに悪影響を及ぼす。

Python の Google Cloud クライアントライブラリや kubernetes ライブラリで代替も可能だが、
対象 API が多い（GKE, Compute, Cloudflare）ため依存が重くなる点は同様。

## 決定

Slack コマンド → GitHub Actions workflow_dispatch → gcloud/kubectl の構成を採用する。

```
Slack → Cloudflare Worker (即時応答)
         ↓ Bearer token 認証
       Cloud Run (FastAPI)
         ↓ GitHub API (workflow_dispatch)
       GitHub Actions
         ↓ gcloud / kubectl
       GKE, Cloudflare, etc.
         ↓ Slack webhook
       完了通知
```

- Cloudflare Worker が Slack の 3 秒タイムアウトを吸収し、Cloud Run のコールドスタートの影響を回避する
- Cloud Run 側は GitHub API を叩くだけなので軽量なまま維持できる
- GitHub Actions には gcloud / kubectl が標準で用意されている
- 既存の startup.yaml, env-up.sh, env-down.sh の処理を統合する

## 補足

Cloud SQL の起動・停止（/db-start, /db-stop）は対象 API が Cloud SQL Admin API のみのため、
Cloud Run から REST API を直接呼ぶ方式で実装済み。対象 API が少ない場合はこちらが適切。
