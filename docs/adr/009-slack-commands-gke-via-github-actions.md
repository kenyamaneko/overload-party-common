# ADR-009: Slack コマンド /gke-up, /gke-down の実行方式に GitHub Actions を採用

## ステータス

Superseded by [ADR-061](061-retire-slack-commands-for-ops.md) (2026-05-06)。旧ステータス: Accepted (2026-03-19)

## 結論

Slack コマンド → GitHub Actions workflow_dispatch → gcloud/kubectl の構成を採用する。gcloud / kubectl が標準で用意されている GitHub Actions に実行を委ねることで、Cloud Run 側は GitHub API を叩くだけの軽量なコンテナのまま維持できる。

## 背景・課題

GKE 環境の起動・停止を Slack コマンドから実行したい。
処理内容は PSC 作成、Pod スケール、Ingress 適用、Cloudflare DNS 更新と多岐にわたり、
`gcloud` CLI と `kubectl` を使うのが最もシンプルな実装になる。

Slack コマンドの受け口は Cloud Run 上の FastAPI サービス（slack-commands）にあるが、
コンテナ内に gcloud SDK + kubectl を入れると **イメージサイズが 500MB 以上増加** し、
起動時間・メモリ消費・ビルド時間すべてに悪影響を及ぼす。

Python の Google Cloud クライアントライブラリや kubernetes ライブラリで代替も可能だが、
対象 API が多い（GKE, Compute, Cloudflare）ため依存が重くなる点は同様。
