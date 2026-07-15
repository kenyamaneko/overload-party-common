# ADR-038: CI 実行時間・実行回数を削減して GitHub Actions 課金を抑える

## ステータス

Accepted (2026-05-10)。本 ADR の初版 (Blacksmith 集約案、commit `692b287` / PR #61) を置き換える。不採用案「Ubicloud に集約」は後に [ADR-040](040-ci-runner-migration-to-ubicloud.md) で再評価され採用に覆された

## 結論

無料枠を継続超過している GitHub Actions 課金を抑えるため、サードパーティ runner には移行せず、**GitHub-hosted ubuntu-latest を維持したまま、CI の実行時間と実行回数を構造的に削減する** (paths-ignore / timeout-minutes / concurrency の全リポ標準化 + キャッシュ最適化)。全リポで設定変更のみで完結してコード / アーキテクチャに手を入れず、新たなベンダロックインもない。timeout-minutes 必須化によりハング 1 件あたりの最大被害が job 種別の上限に制限され、ドキュメント修正で CI が走らなくなって作業者の待ち時間も短縮される。2026 年の runner 値下げの恩恵も超過分にそのまま効く。

## 背景・課題

全 15 リポの GitHub Actions workflow (計 40 本) はすべて `runs-on: ubuntu-latest` で動いており、月間消費は約 6,000〜7,000 min。GitHub-hosted runner の無料枠 (2,000 min) を継続的に超過し、超過課金が発生している。

### サードパーティ runner への移行は採算が合わない

当初 Blacksmith / Ubicloud などのサードパーティ runner への移行を検討したが、本 ADR では採用しない:

- **Blacksmith**: GitHub organization 必須。現状リポは個人アカウント (`kenyamaneko/*`) 配下にあり、org 移管は WIF プロバイダの attribute condition 書き換え (13 workflow) や Go module / npm パッケージの namespace 変更を伴うため、移行コストが純粋な runner 入れ替えに見合わない
- **Ubicloud**: 個人アカウント可だが利用可能リージョンが EU (Frankfurt / Helsinki) のみで、Artifact Registry `asia-northeast1` への docker push レイテンシが増える懸念がある。さらに 2026/5/1 から新規顧客は premium プラン (4 vCPU $0.0032/min) のみとなり、月額メリットは数〜十数ドル程度に縮小
- **Cloud Run Jobs 自作**: Docker daemon 不在 / service container 概念無しのため、12 workflow の docker build と Testcontainers 系テストを Kaniko / Cloud Build / Memorystore 等に切り出すリファクタが必要

### 2026 年の GitHub Actions 価格改定

判断時点で以下の改定が公表されている:

- **2026/1/1**: GitHub-hosted runner 単価が最大 39% 値下げ (超過課金単価そのものが下がる)
- **2026/3/1**: self-hosted runner も $0.002/min で課金開始 (サードパーティ runner 経由でも GitHub 側の課金が乗る可能性。実際の対象範囲は別途要確認)
- 無料枠 (2,000 min/月) は据え置き

この改定により、サードパーティ runner に移行して得られる金銭メリットがさらに縮小する一方、**実行時間 / 実行回数の削減はそのまま単価 × min 削減分の効果**として残る。投資対効果は後者が高い。

### 現状の構造的な無駄

調査により以下が判明している:

| 項目 | 現状 |
|---|---|
| paths filter 設定済み workflow | 11 / 40 |
| **paths filter 未設定の PR トリガー CI** | **10 / 40** |
| timeout-minutes 設定済み job | 4 / 131 (infra リポのみ) |
| **timeout-minutes 未設定 job** | **127 / 131** |
| concurrency 設定済み workflow | 9 / 40 (主に deploy / publish) |
| **concurrency 未設定の CI workflow** | **10 / 40** |

paths filter 未設定の CI workflow:

- `scenario/ci.yaml`, `shop/ci.yaml`, `client/ci.yml`, `analytics/ci.yaml`, `battle/ci.yaml`, `matchmaking/ci.yaml`, `card/ci.yaml`, `gateway/ci.yaml`, `account/ci.yaml`, `newsfeed/ci.yaml`, `newsfeed/validate.yaml`

これらは `docs/**` や `*.md` の修正だけでも 10〜30 分の CI を起動する。timeout-minutes 未設定の job は GitHub のデフォルト 360 分で走るため、ハング 1 件で半日分の minutes が消費される。concurrency 未設定の CI は force-push のたびに古い実行が完走するまで動き続ける。

## 不採用案

### Blacksmith に集約 (本 ADR 初版)

GitHub organization 必須。個人アカウントから org への移管は WIF / npm scope / Go module path 書き換えを伴い、純粋な runner 入れ替えコストを大きく超える。不採用。

### Ubicloud に集約

個人アカウント可。ただし利用可能リージョンが EU のみで、`asia-northeast1` Artifact Registry への push レイテンシが各 deploy で 30〜60 秒余分にかかる可能性。さらに 2026/5/1 以降は新規顧客は premium プランのみで、月額削減幅が小さい。本 ADR の「実行時間削減」と組み合わせれば検討余地はあるが、本 ADR では runner は据え置く (のちに [ADR-040](040-ci-runner-migration-to-ubicloud.md) で再評価し採用)。

### Cloud Run Jobs を使った自作 ephemeral runner

Docker daemon / service container 互換性を埋めるリファクタコストが大きい。本 ADR 初版の代替案として詳細を検討済。本 ADR では不採用。

### GitHub Team プラン (3,000 min/月)

無料枠が 1,000 min 増えるが超過単価は同じで、CI 速度は変わらない。最適化しないままプラン引き上げするのは構造的問題を放置するだけになるため、まず本 ADR の最適化を実施する。
