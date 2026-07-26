# 本番環境コスト見積もり

リージョン: asia-northeast1 (Tokyo) / 2026-07 時点

ADR-056 と ADR-058 で決めた Cloud Run 構成 (gateway を含む全サービスが未使用時にゼロへスケールする) を前提とする。

## 前提

計算資源の課金は稼働時間に比例する。

- **gateway の接続時間**: 月 120 時間 (1 日あたり 4 時間)。WebSocket 接続は実行中のリクエストとして扱われ、接続が 1 本でもある間は課金が続く
- **gateway のサービス設定**: 1 vCPU / 512 MiB。実際の値は Cloud Run 化 (overload-party-infra#51) で決める。この行の金額は CPU 割り当てにほぼ比例する
- **battle の処理時間**: 月 12 時間 (接続時間の 1 割)。対戦アクションを受けている間だけ課金される
- **他 7 サービスの処理時間**: 合計で月 20 時間
- **無料枠**: 差し引かない。Cloud Run の無料枠 (月 180,000 vCPU 秒・360,000 GiB 秒・200 万リクエスト) が東京リージョンに適用されるかを確認していないため、適用されない側に倒している

## サマリ

| カテゴリ | 月額 (USD) |
|----------|-----------|
| Cloud SQL | ~$28 |
| Cloud Run (gateway) | ~$11 |
| Cloud Run (battle + 7 サービス) | ~$1.5 |
| ネットワーク | ~$0.2 |
| その他 | ~$3 |
| **合計** | **~$43/月** |

GKE 構成での見積もり (2026-03 時点で ~$98/月) のおよそ 45%。差額の大半は、クラスタの Pod 課金 ($47.68) と Ingress のロードバランサ ($18.25) が無くなったことによる。

---

## Cloud Run

asia-northeast1 は Tier 1 リージョン。リクエスト課金 (CPU をリクエスト処理中のみ割り当てる方式) の単価:

| リソース | 秒単価 | 時間単価 |
|----------|--------|---------|
| vCPU | $0.000024/vCPU 秒 | $0.0864/vCPU 時 |
| メモリ | $0.0000025/GiB 秒 | $0.009/GiB 時 |
| リクエスト | $0.40/100 万件 | |

### gateway

最小インスタンス数 0 / 最大インスタンス数 1。1 vCPU + 512 MiB の時間単価は $0.0909/時。同時接続数ではなく、誰かが繋いでいる時間の合計が金額を決める。

| 接続がある時間 | 月額 |
|---------------|------|
| 40 時間 | $3.64 |
| **120 時間 (基準)** | **$10.91** |
| 400 時間 | $36.36 |
| 730 時間 (24/7) | $66.36 |

### battle と 7 サービス

| サービス | 割り当て | 時間単価 | 想定処理時間 | 月額 |
|----------|---------|---------|-------------|------|
| battle | 1 vCPU / 1 GiB | $0.0954 | 12 時間 | $1.14 |
| account・card・shop・scenario・matchmaking・news・support | 各 0.2 vCPU / 256 MiB | $0.0195 | 合計 20 時間 | $0.39 |
| **合計** | | | | **~$1.5** |

最大インスタンス数 3 は Cloud SQL のコネクション数を守るための上限で、平常時に 3 つ動く想定ではない。

リクエスト数は月 10 万件程度で、$0.40/100 万件では $0.1 に満たない。

---

## Cloud SQL

インスタンス: db-g1-small (shared-core, 1.7 GiB RAM) / Enterprise Edition / PostgreSQL 16

| 項目 | スペック | 月額 |
|------|---------|------|
| インスタンス (24/7) | db-g1-small | ~$25 |
| SSD ストレージ | 10 GB | ~$2.20 |
| 自動バックアップ | ~10 GB | ~$1.00 |
| **合計** | | **~$28** |

常時課金される唯一の費目であり、構成変更後の最大の費目でもある。

> db-g1-small は shared-core のため CUD (Committed Use Discount) の対象外。
> 将来 db-custom 以上にスケールアップした場合は CUD で最大 52% 割引が可能。

---

## ネットワーク

| 項目 | 単価 | 月額 |
|------|------|------|
| Cloud Run の外向きデータ転送 (~1 GB/月) | ~$0.12–0.15/GB | ~$0.2 |
| **合計** | | **~$0.2** |

外部からの入口は Cloudflare から gateway の Cloud Run サービスへの直結になり、ロードバランサも予約 IP も持たない。

---

## その他

| 項目 | 月額 |
|------|------|
| Cloud Run — newsfeed job (12 回/日 × 30 日, 最大 30 分/回) | ~$2 |
| Cloud Run — db-migrate job (月数回, 5 分以内) | ~$0 |
| Cloud Scheduler (2 jobs) | $0 (無料枠: 3 jobs/月) |
| Secret Manager (内部認証鍵 + support 通知シークレット) | ~$0.2 |
| Artifact Registry (~2 GB, 10 images 保持) | ~$0.20 |
| GCS — assets bucket | ~$0.10 |
| GCS — newsfeed bucket (90 日で自動削除) | ~$0.10 |
| Cloud DNS (1 zone) | $0.20 |
| Cloud Monitoring | $0 (システムメトリクスは無料) |
| Cloud Logging (~1 GB/月) | $0 (50 GB/月まで無料) |
| **合計** | **~$3** |

---

## dev / stg 環境

環境の起動停止で操作する対象は Cloud SQL だけになる。Cloud SQL を停止しておけば、動作確認をした時間分の Cloud Run 料金 (数ドル未満) とその他の固定費だけが残る。

---

## コスト削減の余地

| 施策 | 削減額 | 備考 |
|------|--------|------|
| Cloud SQL の夜間停止 (Scheduler で自動 stop/start) | ~-$10 | アクセスがない時間帯を停止 |
| gateway の CPU 割り当てを下げる | gateway 分に比例 | 同時接続数が少ないうちは 1 vCPU を使い切らない |
| db-custom へ移行 + CUD 1 年 | 最大 -52% | トラフィック増加後に検討 |

---

## 料金ソース

- Cloud Run pricing: https://cloud.google.com/run/pricing
- Cloud SQL pricing: https://cloud.google.com/sql/pricing
- Network pricing (外向きデータ転送): https://cloud.google.com/vpc/network-pricing
- Secret Manager pricing: https://cloud.google.com/secret-manager/pricing
- Cloud Monitoring pricing: https://cloud.google.com/stackdriver/pricing

> 最終更新: 2026-07-25
