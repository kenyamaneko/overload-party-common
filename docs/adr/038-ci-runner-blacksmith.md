# ADR-038: CI runner を Blacksmith に集約する

- Status: Accepted
- Date: 2026-05-10
- Deciders: kenyamaneko

## Context

全 15 リポの GitHub Actions workflow (計 44 本) はすべて `runs-on: ubuntu-latest` で動いており、GitHub-hosted runner の月間無料枠 (2,000 min) を大幅に超過している。実消費は約 6,000〜7,000 min/月で、超過分の課金が継続的に発生している。

主な消費源:

- 各サービスリポの `ci.yaml` (Go / .NET / Python の lint + test + docker build + image-scan): 1 回 10〜15 分 × PR 件数
- `deploy.yaml` 系の docker build & push (Artifact Registry): 1 回 5〜10 分
- 定期実行 (`ops/cost-monitor` 1日3回, `ops/drift-monitor` / `ops/nightly-shutdown` 各 1日1回)

加えて、ローカルでの開発体感に対して GitHub-hosted runner の I/O / cache / 並列度がボトルネックになっており、PR フィードバック時間そのものを短縮したい要求がある。

### 構造的な制約

44 workflow のうち以下の構造を持つものが多く、runner を入れ替える際の互換性が意思決定を支配する:

- **Docker daemon を要する**: 12 workflow (各サービスの `ci.yaml` の `image-scan` / `build-and-push` ジョブ、`deploy.yaml` の docker build)
- **Service container / Testcontainers を要する**: matchmaking (Redis), newsfeed (Valkey), scenario / shop / card / account (Postgres + Firestore emulator)
- **GitHub OIDC + Workload Identity Federation**: 13 workflow が `google-github-actions/auth@v2` 経由で Google Cloud に認証
- **Cross-repo workflow_dispatch (同期待機)**: `ops/nightly-shutdown` → `k8s/env-lifecycle` → platform 側、最大 20 分待機

これらのいずれかが新 runner で動かないと、各リポで個別の対応コストが発生する。

## Decision

CI runner を **Blacksmith** に集約する。各 workflow の `runs-on:` ラベルを GitHub-hosted から Blacksmith のラベルに置き換える。

### 1. Blacksmith を採用する

- ホスト型のマネージド GitHub Actions 互換 runner
- `runs-on:` ラベル変更のみで導入できる (workflow の他の構造に手を入れない)
- Docker daemon / service container / GitHub OIDC token / `actions/cache` 互換
- 同等スペックでの実行速度が GitHub-hosted より速く、`actions/cache` に加えて独自のキャッシュ層が効く

### 2. 標準ラベルは 4 vCPU を採用する

GitHub-hosted ubuntu-latest と同等以上のスペック (4 vCPU / 16 GiB) を全 workflow の標準とする。重い CI (docker build を含むもの) で時間を要するものについては、個別に 8 vCPU ラベルへ昇格させて良い。

### 3. 切り戻し可能性を残す

`runs-on:` を直値で書き、移行検証中に問題が出た workflow は個別に `ubuntu-latest` へ戻せる構造を維持する。全リポ移行完了までは Blacksmith と GitHub-hosted の混在を許容する。

## 検討した代替案

### A. GitHub Actions 上位プランへの移行

Team プラン (3,000 min/月込み) でも超過は継続し、超過単価 ($0.008/min) は変わらない。CI 実行速度は改善しない。コスト改善余地が小さく、速度改善ゼロのため不採用。

### B. Cloud Run Jobs を使った自作 ephemeral runner

GitHub の `workflow_job` webhook を Cloud Run Service で受け、`gcloud run jobs execute` で 1 job 1 container の使い捨て runner を起動する構成。

純粋な秒課金は Blacksmith より安いが、以下の構造的不一致が大きい:

- Cloud Run コンテナに Docker daemon が無いため、12 workflow の docker build を Kaniko / Cloud Build / Buildah rootless のいずれかに切り出すリファクタが全リポで必要
- service container 概念が無いため、Testcontainers / Redis / Postgres の起動戦略を Memorystore / Cloud SQL に置き換えるか、テスト戦略の見直しが必要
- webhook → Job 起動 / JIT runner token 発行 / runner image の継続保守 (各種ツール追従、CVE 対応) を自前で持つ必要がある

`$/min` 差で稼げる金額に対して、初期構築 + 継続保守の人月コストが上回ると判断。

### C. その他のサードパーティ runner (Ubicloud / Depot / RunsOn など)

Blacksmith と同カテゴリ。docker build 特化や AWS spot ベースなど特性差はあるが、本意思決定の段階では Blacksmith を採用し、PoC 結果に応じて再評価する余地は残す。

## Consequences

### Positive

- **コスト圧縮**: GitHub-hosted の超過課金 (約 $32〜40/月) が、Blacksmith 4 vCPU で約 $6〜10/月に縮小する見込み
- **CI 速度改善**: 同等スペックでの実行時間が短縮され、PR フィードバックループが速くなる
- **互換性温存**: docker build / service container / WIF / `actions/cache` のいずれも既存設計のまま動くため、44 workflow 側の構造変更が不要
- **意思決定後の追加 ADR が要らない**: `nightly-shutdown` の同期待機なども現状維持で動く

### Negative

- **第三者が CI critical path に入る**: Blacksmith 側の障害で全リポの CI が停止する可能性がある
- **secret / source code が第三者ホスト上で実行される**: 本番デプロイ workflow も Blacksmith 上で動くため、データ取扱の契約条項を確認する必要がある
- **ラベル名がベンダ固有**: Blacksmith 撤退時には `runs-on:` の一括置換が再度必要になる

### 緩和策

- 移行は段階的に行い、各 Phase で deploy 系 workflow を最後に切り替える
- 障害時は `runs-on:` を `ubuntu-latest` に戻す手順を runbook 化する (本 ADR では runbook 自体は scope 外)
- Blacksmith の SOC2 等のコンプライアンス資料を契約時に確認する

## 移行計画

### Phase 1: PoC (副作用なし workflow)

- 対象: `overload-party-client/ci.yml` (npm のみ、deploy 無し)
- 確認: ラベル切り替えで通ること、`actions/cache` がそのまま動くこと、ログが GitHub UI で読めること

### Phase 2: docker build + service container 検証

- 対象: `overload-party-matchmaking/ci.yaml` (Redis service container + docker build + Go test の典型ケース)
- 確認: Docker daemon / service container / WIF / Artifact Registry push の egress レイテンシ

### Phase 3: 共通 Action / 多言語パイプライン検証

- 対象: `overload-party-common/publish.yaml` (Go / .NET / npm の matrix publish)
- 確認: matrix 並列度、複数言語のキャッシュ、Cloudsmith publish

### Phase 4: 全リポ展開

- 残る各リポの ci / deploy / publish workflow を順次切り替え
- 共通 Action (`kenyamaneko/overload-party-common/.github/actions/*`) 内部の `runs-on` も追従

### Phase 5: 定期実行系の切り替え

- `ops/cost-monitor` / `ops/drift-monitor` / `ops/nightly-shutdown` を最後に切り替え
- 失敗時の検知が遅れるため、Phase 1〜4 で十分な実績が出てから移す

## Out of scope

- Blacksmith 以外のサードパーティ runner との詳細ベンチマーク (Phase 1〜2 の PoC 結果次第で別途評価)
- Cloud Run Jobs / GKE ARC による自作 runner (代替案 B として却下済)
- runner 障害時の runbook (運用ドキュメントとして別途)
- `nightly-shutdown` の同期待機を Pub/Sub 化する設計見直し (本 ADR の範囲では現状維持)

## 関連

- 関連 issue は本 ADR マージ後に起票
