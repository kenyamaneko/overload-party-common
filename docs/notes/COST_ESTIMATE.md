# 本番環境コスト見積もり

リージョン: asia-northeast1 (Tokyo) / 24/7 常時稼働 / 2026-03 時点

---

## サマリ

| カテゴリ | 月額 (USD) |
|----------|-----------|
| GKE Autopilot | $47.68 |
| Cloud SQL | ~$28 |
| ネットワーク | ~$19 |
| その他 | ~$3 |
| **合計** | **~$98/月** |

---

## GKE Autopilot

東京リージョン Pod 単価:

| リソース | 単価 |
|----------|------|
| vCPU | $0.0571/vCPU-hour |
| Memory | $0.0063215/GB-hour |
| Ephemeral Storage | $0.0000704/GB-hour |

Pod ごとの内訳（730 時間/月で計算）:

| Pod | CPU Req | Mem Req | CPU/月 | Mem/月 | 小計 |
|-----|---------|---------|--------|--------|------|
| gateway | 250m | 512Mi | $10.42 | $2.31 | $12.73 |
| gateway cloud-sql-proxy | 100m | 128Mi | $4.17 | $0.58 | $4.75 |
| battle | 500m | 1Gi | $20.84 | $4.61 | $25.45 |
| battle cloud-sql-proxy | 100m | 128Mi | $4.17 | $0.58 | $4.75 |
| **合計** | **950m** | **1.75Gi** | | | **$47.68** |

クラスタ管理費: $0.10/hour ($73/月) → **無料枠 $74.40/月でカバー (実質 $0)**

> 無料枠は 1 Autopilot クラスタ分の管理費を billing account ごとに提供。
> Pod のコンピュート料金は無料枠の対象外。

---

## Cloud SQL

インスタンス: db-g1-small (shared-core, 1.7 GiB RAM) / Enterprise Edition / PostgreSQL 16

| 項目 | スペック | 月額 |
|------|---------|------|
| インスタンス (24/7) | db-g1-small | ~$25 |
| SSD ストレージ | 10 GB | ~$2.20 |
| 自動バックアップ | ~10 GB | ~$1.00 |
| **合計** | | **~$28** |

> db-g1-small は shared-core のため CUD (Committed Use Discount) の対象外。
> 将来 db-custom 以上にスケールアップした場合は CUD で最大 52% 割引が可能。

---

## ネットワーク

| 項目 | 単価 | 月額 |
|------|------|------|
| Forwarding rules (Ingress LB + PSC) | 最初の 5 個まで $0.025/h 合計 | $18.25 |
| 静的外部 IP (Ingress 用) | 使用中は無料 | $0 |
| LB データ処理 | $0.008–$0.012/GB | ~$1 |
| **合計** | | **~$19** |

> Forwarding rule は同一プロジェクト内の最初の 5 個が $0.025/h **合計** で課金。
> 1 個でも 5 個でも同額のため、Ingress + PSC の 2 個で追加コストなし。

---

## その他

| 項目 | 月額 |
|------|------|
| Cloud Monitoring (SYSTEM + DEPLOYMENT + POD) | $0 (システムメトリクスは無料) |
| Cloud Logging (~1 GB/月) | $0 (50 GB/月まで無料) |
| Cloud Run — newsfeed job (12 回/日 × 30 日, 最大 30 分/回) | ~$2 |
| Cloud Run — db-migrate job (月数回, 5 分以内) | ~$0 |
| Cloud Scheduler (2 jobs) | $0 (無料枠: 3 jobs/月) |
| Artifact Registry (~2 GB, 10 images 保持) | ~$0.20 |
| GCS — assets bucket | ~$0.10 |
| GCS — newsfeed bucket (90 日で自動削除) | ~$0.10 |
| Cloud DNS (1 zone) | $0.20 |
| **合計** | **~$3** |

> Monitoring: CADVISOR, KUBELET, HPA, DCGM 等の有料パッケージは無効化済み。
> SYSTEM_COMPONENTS + DEPLOYMENT + POD のみ有効（CPU/メモリ使用量、Pod 状態、レプリカ数を監視可能）。

---

## コスト削減オプション

| 施策 | 削減額 | 備考 |
|------|--------|------|
| env-up/down 運用 (Pod + LB + PSC を使用時のみ起動) | 最大 -$65 | 初期・トラフィックが少ない時期向け |
| Cloud SQL 夜間停止 (Scheduler で自動 stop/start) | ~-$10 | アクセスがない時間帯を停止 |
| Spot Pod (gateway のみ) | ~-$8 | battle は WebSocket 長時間接続のため不向き |
| db-custom へ移行 + CUD 1 年 | 最大 -52% | トラフィック増加後に検討 |

### env-up/down 運用時の月額目安

1 日 4 時間 × 月 20 日 = 80 時間/月 の場合:

| カテゴリ | 月額 |
|----------|------|
| GKE Pod (80h) | ~$5.22 |
| ネットワーク (80h) | ~$2 |
| Cloud SQL (80h + 夜間停止) | ~$8 |
| クラスタ管理費 | $0 (無料枠) |
| その他 | ~$3 |
| **合計** | **~$18/月** |

---

## 料金ソース

- GKE Autopilot 東京リージョン単価: https://g-gen.co.jp/useful/google-service/23688/
- GKE pricing: https://cloud.google.com/kubernetes-engine/pricing
- Cloud SQL pricing: https://cloud.google.com/sql/pricing
- Cloud Load Balancing pricing: https://cloud.google.com/load-balancing/pricing
- VPC pricing (forwarding rules, static IP): https://cloud.google.com/vpc/pricing
- Cloud Monitoring pricing: https://cloud.google.com/stackdriver/pricing
- Cloud Run pricing: https://cloud.google.com/run/pricing

> 最終更新: 2026-03-14
