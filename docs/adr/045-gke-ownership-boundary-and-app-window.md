# ADR-045: GKE 所有境界の再定義 — cluster=brand / nodepool=app と brand→app の IAM window

## ステータス

Proposed (2026-05-20)

本 ADR は keyandnotes-platform リポの「ノードプールスケーリング戦略とGKEの所有権」 (`keyandnotes-platform/docs/ARCHITECTURE.md:15` から参照) を supersede する。

## コンテキスト

`keyandnotes-main` GKE クラスタは brand プロジェクト keyandnotes-platform に作られており、env nodepool (`keyandnotes-main-{dev,stg,prod}`) も同 cluster module 内で一体管理されている。一方、これらの env nodepool で稼働する Pod、生成される Ingress L7 LB、nightly shutdown / scale-up のトリガはいずれも overload-party 側 (app) の責務である。

この実態と所有の食い違いは複数の摩擦を生んでいた:

- **cost-monitor の権限不足** ([ops#15](https://github.com/kenyamaneko/overload-party-ops/issues/15)): overload-party-ops の cost-monitor SA が `keyandnotes-platform` プロジェクト上で `roles/container.viewer` を持たず、GKE 関連チェックが silent skip される。「app の監視ツールが brand cluster を読む」という非対称な構造をどこで吸収するかが未決
- **nodepool 変更が brand リポを経由する**: env nodepool の machine_type / labels / taints 変更や追加削除のような app に閉じた意思決定が、brand リポの PR を要する
- **dispatch chain が所有境界を越えている**: ops → k8s → platform の連鎖 dispatch は「app の lifecycle を brand に頼む」構造で、所有越境を「Why コメント」で許容している
- **境界が暗黙**: 「cluster は brand、その上のものは app」が明文化されておらず、Ingress LB の GCP 物理リソース (= brand project に作られる) の所有も曖昧

「ノードプールスケーリング戦略とGKEの所有権」では「GKE 所有権は keyandnotes-platform」として nodepool resize を brand 側で実行する判断を採っていたが、上記の摩擦は所有自体を見直すことで根本解決できる。

## 決定

### 境界の再定義

| 資源 | 論理所有 | GCP 物理所在 |
|---|---|---|
| GKE Cluster `keyandnotes-main` | brand | keyandnotes-platform |
| `keyandnotes-main-platform` nodepool (ArgoCD 等の brand-shared add-on 用) | brand | keyandnotes-platform |
| `keyandnotes-main-{dev,stg,prod}` env nodepool | **app** | keyandnotes-platform (GCE VM) |
| Ingress object (`overload-party` namespace 単位) | app | (k8s 内部) |
| Ingress LB (GCE L7 LB / forwarding rule / NEG、k8s が auto-create) | **app** (論理) | keyandnotes-platform |
| Cloud SQL / Static IP / PSC | app | overload-party-{dev,stg} |
| ArgoCD (brand 横断の GitOps) | brand | keyandnotes-platform (`platform` pool に scheduling) |
| Workload Identity Pool / WIF providers | brand | keyandnotes-platform |
| VPC / subnet / DNS / 共通証明書 | brand | keyandnotes-platform |

env nodepool と Ingress LB は **k8s manifest または Terraform 宣言が app 側にあり、それが brand project に物理 GCP リソースを生やす** ハイブリッド構造。これを「brand cluster の上で app が手を伸ばす範囲」として、brand が許可する window として一括で扱う。

### IAM window を brand 側に集約

brand 側 Terraform で「app に開ける window」を明示する。

| window | 付与先 SA (app) | role | 用途 |
|---|---|---|---|
| W1 | app の Terraform deployer SA | `roles/container.clusterAdmin` (or scoped equivalent) | env nodepool の CRUD |
| W2 | cost-monitor 用 SA (`github-ci@overload-party-ops...`) | `roles/container.viewer` | nodepool / Ingress の kubectl get |

「誰に何を許すか」のポリシーは brand リポ内で監査可能な形にし、app は「brand が開けてくれた前提で動く」だけにする。

### 原則: executor は対象リソースの所有 repo に置く

「処理 (executor) は対象リソースを所有する repo に置く」 原則を継続採用する。本境界変更に伴い、nodepool resize の executor は brand リポから app 側 (= overload-party-infra) に移管する。

### dispatch chain の変更

末尾の executor (`node-pool-scale.yaml`) の所在のみが移管対象で、cron trigger と env orchestrator は据置:

```
変更前:  ops/nightly-shutdown → k8s/env-lifecycle → platform/node-pool-scale
変更後:  ops/nightly-shutdown → k8s/env-lifecycle → infra/node-pool-scale
                                                    ↑ ここのみ移管
```

`platform/node-pool-scale.yaml` は削除する。

### prod nodepool の扱い

prod 用 env nodepool (`keyandnotes-main-prod`) も app 所有とし、overload-party-infra で管理する。常時 1 ノードで scale 対象外という現運用は変更しない (Terraform で固定、`node-pool-scale.yaml` の対象は dev/stg のみ)。

### Terraform state 境界

- **brand tfstate**: cluster、`platform` nodepool、Workload Identity Pool、app-window grant (W1/W2)、cluster networking
- **app tfstate** (overload-party-infra): env nodepool (dev/stg/prod)、Cloud SQL、Static IP、PSC、node-pool-scaler の SA

app 側は brand cluster を `data "google_container_cluster"` で参照する。依存方向は app → brand のみ。

### なぜこの設計か

| 観点 | 評価 |
|---|---|
| 所有と意思決定の一致 | env nodepool の machine_type / count / labels の変更は app の意思決定。所有を app 側に置くことで、app PR で完結する |
| IAM 越境の集約 | brand → app の cross-project IAM は brand 側 Terraform に集約。誰に何を許すかが brand のガバナンス対象として一覧可能 |
| dispatch chain の一貫性 | 「executor は対象リソースの所有 repo」原則は既に確立済み (cf. node-pool-scale.yaml / env-lifecycle.yaml の Why コメント)。境界変更に伴って機械的に追従する |
| brand の責務範囲 | コード量は減るが、cluster / 共有 add-on / WIF / IAM window policy / 共通ネットワーク土台と、責任の重い土台部分が brand に残る |
| 境界の検証可能性 | 「cluster=brand、nodepool=app、Ingress LB は論理 app」を Terraform state 境界として物理的に表現できる |

### 不採用案

- **app SA に brand プロジェクトの IAM admin を渡す**: 「nodepool 移管せず、cost-monitor 用 viewer だけ brand 側で grant」案。摩擦の根本原因 (所有と意思決定の不一致) は解消しない。
- **cost-monitor を brand 側に移管**: brand 共通の cross-app 監視ツールに昇格させる案。本 ADR の app 数が現状 1 のため過剰投資。
- **k8s/env-lifecycle.yaml も app 側に集約**: env-lifecycle は k8s クラスタリソース全般の env レベル orchestration を担うため、k8s repo に残置するのが「executor は所有 repo」原則に整合する。

## 連動する変更

| repo | 変更 |
|---|---|
| keyandnotes-platform | cluster module から dev/stg/prod の env nodepool を削除 (platform pool は残す) / `modules/app-window/` 新設 (W1/W2 grant) / `modules/node-pool-scaler/` 削除 / `.github/workflows/node-pool-scale.yaml` 削除 / `docs/ARCHITECTURE.md` を新所有境界に合わせて更新 |
| overload-party-infra | `providers/google-cloud/ops/modules/gke-nodepools/` 新設 (dev/stg/prod) / `modules/node-pool-scaler/` 新設 / `.github/workflows/node-pool-scale.yaml` 新設 (executor 移管) |
| overload-party-k8s | `.github/workflows/env-lifecycle.yaml` の dispatch 先を `keyandnotes-platform` → `overload-party-infra` に更新 / README の「ArgoCD 同居」記述を `platform` pool 分離の実態に追従 |
| overload-party-ops | (変更なし) cost-monitor は本 ADR の W2 grant 適用で silent skip が解消される。コード変更は不要 |

## 検証

- Phase B/C 適用後、cost-monitor workflow を手動 dispatch して GKE 関連チェックが silent skip されないことを Slack ログで確認
- nightly-shutdown → env-lifecycle → node-pool-scale の dispatch chain が新形 (executor=infra) で動作することを dev / stg で確認
- `kubectl get nodes -l cloud.google.com/gke-nodepool=keyandnotes-main-{env}` の応答が各 env で取得できる

本番稼働前のため Phase B apply で env nodepool が一時的に destroy されることを許容、Phase C apply で再生成して復活させる。
