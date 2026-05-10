# ADR-038: CI 実行時間・実行回数を削減して GitHub Actions 課金を抑える

- Status: Accepted
- Date: 2026-05-10
- Deciders: kenyamaneko
- Supersedes: 本 ADR の初版 (Blacksmith 集約案、commit `692b287` / PR #61)

## Context

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

## Decision

サードパーティ runner には移行せず、**GitHub-hosted ubuntu-latest を維持したまま、CI の実行時間と実行回数を構造的に削減する**。具体策は以下 3 点を全リポで標準化する。

### 1. paths-ignore で不要トリガーを削減する

PR トリガーの CI workflow には `paths-ignore` を設定し、ドキュメント・設定のみの変更で CI が走らないようにする。共通の除外パターン:

```yaml
on:
  pull_request:
    branches: [main]
    paths-ignore:
      - '**/*.md'
      - 'docs/**'
      - '.vscode/**'
      - '.gitignore'
      - 'LICENSE'
```

リポ固有のパス (例: `presets/`, `rules/`, `.claude/docs/`) は各リポで追加する。

### 2. timeout-minutes を全 job に必須化する

job 種別ごとの上限を以下で標準化する:

| job 種別 | timeout-minutes |
|---|---|
| lint / format | 10 |
| unit test | 20 |
| integration test (Firestore emulator / Testcontainers) | 30 |
| build / docker build | 30 |
| image-scan (trivy) | 20 |
| deploy (docker push / gcloud / kubectl) | 20 |
| publish (tag push / npm publish) | 15 |
| terraform plan / apply | 30 (既設) |

**根拠**: 各 job 種別の現状実行時間 (5〜15 分) に対して、ハング検知の余裕を残しつつデフォルト 360 分の課金事故を防ぐ上限値。実測との乖離が出た job は個別に調整する。

### 3. concurrency cancel-in-progress を全 CI workflow に設定する

PR トリガーの CI には以下を設定し、同一 PR 内の古い workflow を自動キャンセルする:

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

deploy / publish 系で既に `cancel-in-progress: false` を設定しているもの (中断を避ける必要があるもの) はそのまま維持する。

### 4. 補助的にキャッシュ最適化と job 並列化を進める

主要 CI で以下のキャッシュが効いていないものは個別 PR で改善する。本 ADR では「やる」だけ宣言し、実装計画は各リポの issue で扱う。

- Go module (`actions/setup-go` の `cache: true` 利用)
- npm / pnpm (`actions/setup-node` の `cache:` 利用)
- NuGet (`actions/setup-dotnet` の cache)
- Docker layer (`docker/build-push-action` の `cache-from` / `cache-to`)
- Firestore emulator image / Testcontainers postgres image の事前 pull

job 並列化は、現状 lint → test → build を直列で動かしている workflow があれば、依存関係が無いものは別 job に分離する。

## 検討した代替案

### A. Blacksmith に集約 (本 ADR 初版)

GitHub organization 必須。個人アカウントから org への移管は WIF / npm scope / Go module path 書き換えを伴い、純粋な runner 入れ替えコストを大きく超える。不採用。

### B. Ubicloud に集約

個人アカウント可。ただし利用可能リージョンが EU のみで、`asia-northeast1` Artifact Registry への push レイテンシが各 deploy で 30〜60 秒余分にかかる可能性。さらに 2026/5/1 以降は新規顧客は premium プランのみで、月額削減幅が小さい。本 ADR の「実行時間削減」と組み合わせれば検討余地はあるが、本 ADR では runner は据え置く。

### C. Cloud Run Jobs を使った自作 ephemeral runner

Docker daemon / service container 互換性を埋めるリファクタコストが大きい。本 ADR 初版の代替案 B として詳細を検討済。本 ADR では不採用。

### D. GitHub Team プラン (3,000 min/月)

無料枠が 1,000 min 増えるが超過単価は同じで、CI 速度は変わらない。最適化しないままプラン引き上げするのは構造的問題を放置するだけになるため、まず本 ADR の最適化を実施する。

## Consequences

### Positive

- **全リポで設定変更のみで完結**: コード / アーキテクチャに手を入れない
- **新たなベンダロックインなし**: GitHub-hosted runner を維持
- **課金事故防止**: timeout-minutes 必須化により、ハング 1 件あたりの最大被害が job 種別の timeout 上限に制限される
- **2026 年価格改定の恩恵を素直に受け取れる**: 1/1 の 39% 値下げが超過分にそのまま効く
- **不要 CI の抑制**: ドキュメント修正で CI が走らなくなり、作業者の待ち時間も短縮される

### Negative

- **15 リポで workflow 編集 PR が必要**: 1 リポあたり 1〜3 workflow を編集
- **paths-ignore のメンテ負荷**: 新しいファイル種別を追加した際に「CI を走らせるべきか」を判断する手間が出る
- **concurrency 設定で UX が変わる**: PR 中の連続 push で古い CI が自動キャンセルされる (中断レビューには良いが、長時間 CI を待っていた人には驚き)
- **timeout が短いことによる偽陽性**: 通常より時間がかかったテストが timeout で落ちる可能性。実測ベースで調整する

### 緩和策

- 適用ルールを `rules/principles.md` に 1 行追記し、値の根拠は本 ADR を参照させる。新規 workflow / 新規リポでも初期から適用される
- timeout が頻繁に当たる job は個別に上限引き上げ。3 回以上当たるなら根本対処 (テスト分割 / cache / 並列化)

## 移行計画

### Phase 1: 適用ルールの追記

- `rules/principles.md` に `[base] CI方針` セクションを新設し、本 ADR の Decision で定めた施策 (paths-ignore / timeout-minutes / concurrency) を運用ルールとして箇条書きで追記する
- 値の根拠は本 ADR の Decision セクションを SSoT として参照する (短命なテンプレファイルは作らない)
- 適用方針: PR トリガーの CI workflow と、push (main / develop / release) トリガーの deploy workflow が対象

### Phase 2: 全 workflow を一括改修

全リポの全 workflow を対象に施策を一括適用する。リポ単位で 1 issue を起票し、PR は workflow ごとまたは一括のいずれかリポ側で判断する。

workflow 種別ごとの適用方針:

- **PR トリガー (ci / validate)**: paths-ignore + timeout-minutes + concurrency `cancel-in-progress: true` + 各ステップに `name`
- **push トリガー (deploy)**: timeout-minutes + concurrency `cancel-in-progress: false` (中断不可) + 各ステップに `name`
- **publish / release-tag / workflow_dispatch のみ**: timeout-minutes + 各ステップに `name` (concurrency は既設のものは維持)
- **schedule (ops の定期実行)**: timeout-minutes + concurrency (重複実行防止) + 各ステップに `name`

paths-ignore は PR トリガーのみ意味があるため、push paths trigger / schedule では適用しない。

## Out of scope

- サードパーティ runner (Blacksmith / Ubicloud / Cloud Run Jobs 自作) の採用 — 本 ADR で却下
- 個別 workflow の構造リファクタ (Firestore emulator 起動の高速化、Testcontainers 戦略変更など) — 必要と判断されたら別 ADR
- GitHub プラン引き上げ — 本 ADR の最適化後に必要なら検討
- 個人アカウント → organization 移管 — 本 ADR とは独立した検討事項

## 関連

- 本 ADR の初版 (Blacksmith 集約案): commit `692b287` / PR #61
- 各リポの適用 issue は本 ADR マージ後に起票
