# ADR-045: GKE 所有境界の再定義（ノードプールをアプリ所有に移管し、ブランド側に cross-project IAM 付与を集約する）

## ステータス

Proposed (2026-05-20)

本 ADR は keyandnotes-platform リポの「ノードプールスケーリング戦略とGKEの所有権」 (`keyandnotes-platform/docs/ARCHITECTURE.md` から参照) を supersede する。

## 結論

「運用上の決定者と Terraform 上の所有定義が一致しない」摩擦を根本解決するため、GKE の所有境界を再定義する。env nodepool (`keyandnotes-main-{dev,stg,prod}`) と Ingress LB の論理所有をアプリ (overload-party) に移管し、アプリ側 SA へのブランドプロジェクト権限付与はブランド側 Terraform に集約して一覧・監査可能にする。env nodepool の変更がアプリ PR で完結するようになり、cost-monitor の silent skip はブランド側の viewer 権限付与で解消され、nodepool resize の executor は「executor は対象リソースの所有 repo に置く」原則どおり overload-party-infra に移る。

## 背景・課題

`keyandnotes-main` GKE クラスタはブランドプロジェクト keyandnotes-platform に作られており、env nodepool (`keyandnotes-main-{dev,stg,prod}`) も同 cluster module 内で一体管理されている。一方、これらの env nodepool で稼働する Pod、生成される Ingress L7 LB、nightly shutdown / scale-up のトリガはいずれも overload-party 側 (アプリ) の責務である。

つまり「運用上の決定者と Terraform 上の所有定義が一致しない」状態で、これが複数の摩擦を生んでいた:

- **cost-monitor の権限不足** ([ops#15](https://github.com/kenyamaneko/overload-party-ops/issues/15)): overload-party-ops の cost-monitor SA が `keyandnotes-platform` プロジェクト上で `roles/container.viewer` を持たず、GKE 関連チェックが silent skip される。「アプリの監視ツールがブランド側クラスタを読む」という非対称な構造をどこで吸収するかが未決
- **nodepool 変更がブランドリポを経由する**: env nodepool の machine_type / labels / taints 変更や追加削除のようなアプリに閉じた意思決定が、ブランドリポの PR を要する
- **dispatch chain が所有境界を越えている**: ops → k8s → platform の連鎖 dispatch は「アプリの lifecycle をブランドに頼む」構造で、所有越境を「Why コメント」で許容している
- **境界が暗黙**: 「クラスタはブランド、その上のものはアプリ」が明文化されておらず、Ingress LB の物理リソース (= ブランドプロジェクトに作られる) の所有も曖昧

「ノードプールスケーリング戦略とGKEの所有権」では「GKE 所有権は keyandnotes-platform」として nodepool resize をブランド側で実行する判断を採っていたが、上記の摩擦は所有自体を見直すことで根本解決できる。

## 詳細

### 境界の再定義

論理所有 = 「変更の意思決定者・PR の所属リポ」を指す。物理所在 = 「実際に Google Cloud リソースが作られるプロジェクト」を指す。

| 資源 | 論理所有 | 物理所在 |
|---|---|---|
| GKE Cluster `keyandnotes-main` | ブランド | keyandnotes-platform |
| `keyandnotes-main-platform` nodepool (ArgoCD 等のブランド共有 add-on 用) | ブランド | keyandnotes-platform |
| `keyandnotes-main-{dev,stg,prod}` env nodepool | **アプリ** | keyandnotes-platform (GCE VM) |
| Ingress object (`overload-party` namespace 単位) | アプリ | (k8s 内部) |
| Ingress LB (GCE L7 LB / forwarding rule / NEG、k8s が auto-create) | **アプリ** | keyandnotes-platform |
| Cloud SQL / Static IP / PSC | アプリ | overload-party-{dev,stg} |
| ArgoCD (ブランド横断の GitOps) | ブランド | keyandnotes-platform (`platform` pool に scheduling) |
| Workload Identity Pool / WIF providers | ブランド | keyandnotes-platform |
| VPC / subnet / DNS / 共通証明書 | ブランド | keyandnotes-platform |

env nodepool と Ingress LB は **k8s manifest または Terraform 宣言がアプリ側にあり、それがブランドプロジェクトに物理リソースを生やす** ハイブリッド構造。これを「ブランドクラスタの上でアプリが手を伸ばす範囲」として、ブランド側で必要な権限を明示的に付与して扱う。

### cross-project IAM 付与をブランド側に集約

アプリ側 SA がブランドプロジェクトのリソースを操作するための IAM 付与は、ブランド側 Terraform で明示的に declare する。「誰に何を許すか」のポリシーをブランドリポ内で一覧・監査可能な形に保つのが目的。

| 付与名 | 付与先 SA (アプリ側) | role | 用途 |
|---|---|---|---|
| nodepool 管理権限 | アプリ側の Terraform deployer SA | `roles/container.clusterAdmin` | env nodepool の CRUD |
| cluster 読み取り権限 | cost-monitor 用 SA (`github-ci@overload-party-ops...`) | `roles/container.viewer` | nodepool / Ingress の kubectl get |

アプリ側は「ブランドが付与してくれた前提で動く」だけで、付与の追加 / 撤回はブランド側 PR が必要。

### 原則: executor は対象リソースの所有 repo に置く

「処理 (executor) は対象リソースを所有する repo に置く」原則を継続採用する。本境界変更に伴い、nodepool resize の executor はブランドリポからアプリ側 (= overload-party-infra) に移管する。

### dispatch chain の変更

末尾の executor (`node-pool-scale.yaml`) の所在のみが移管対象で、cron trigger と env orchestrator は据置 (矢印は workflow_dispatch の呼び出し方向):

```
変更前:  ops/nightly-shutdown → k8s/env-lifecycle → platform/node-pool-scale
変更後:  ops/nightly-shutdown → k8s/env-lifecycle → infra/node-pool-scale
                                                    ↑ ここのみ移管
```

`platform/node-pool-scale.yaml` は削除する。

### prod nodepool の扱い

prod 用 env nodepool (`keyandnotes-main-prod`) もアプリ所有とし、overload-party-infra で管理する。常時 1 ノードで scale 対象外という現運用は変更しない (Terraform で固定、`node-pool-scale.yaml` の対象は dev/stg のみ)。

### Terraform state 境界

- **ブランド tfstate**: cluster、`platform` nodepool、Workload Identity Pool、cross-project IAM 付与定義、cluster networking
- **アプリ tfstate** (overload-party-infra): env nodepool (dev/stg/prod)、Cloud SQL、Static IP、PSC、node-pool-scaler の SA

アプリ側はブランドクラスタを `data "google_container_cluster"` で参照する。依存方向はアプリ → ブランドのみ。

### なぜこの設計か

| 観点 | 評価 |
|---|---|
| 所有と意思決定の一致 | env nodepool の machine_type / count / labels の変更はアプリの意思決定。所有をアプリ側に置くことで、アプリ PR で完結する |
| cross-project IAM の集約 | ブランド → アプリの IAM 付与はブランド側 Terraform に集約。誰に何を許すかがブランドのガバナンス対象として一覧可能 |
| dispatch chain の一貫性 | 「executor は対象リソースの所有 repo」原則は既に確立済み (cf. node-pool-scale.yaml / env-lifecycle.yaml の Why コメント)。境界変更に伴って機械的に追従する |
| ブランドの責務範囲 | コード量は減るが、cluster / 共有 add-on / WIF / IAM 付与ポリシー / 共通ネットワーク土台と、責任の重い土台部分がブランドに残る |
| 境界の検証可能性 | 「クラスタはブランド、nodepool はアプリ、Ingress LB は論理アプリ」を Terraform state 境界として物理的に表現できる |

### 連動する変更

| repo | 変更 |
|---|---|
| keyandnotes-platform | cluster module から dev/stg/prod の env nodepool を削除 (platform pool は残す) / cross-project IAM 付与 module の新設 / `modules/node-pool-scaler/` 削除 / `.github/workflows/node-pool-scale.yaml` 削除 / `docs/ARCHITECTURE.md` を新所有境界に合わせて更新 |
| overload-party-infra | `providers/google-cloud/ops/modules/gke-nodepools/` 新設 (dev/stg/prod) / `modules/node-pool-scaler/` 新設 / `.github/workflows/node-pool-scale.yaml` 新設 (executor 移管) |
| overload-party-k8s | `.github/workflows/env-lifecycle.yaml` の dispatch 先を `keyandnotes-platform` → `overload-party-infra` に更新 / README の「ArgoCD 同居」記述を `platform` pool 分離の実態に追従 |
| overload-party-ops | (変更なし) cost-monitor は本 ADR の cluster 読み取り権限付与で silent skip が解消される。コード変更は不要 |

## 不採用案

- **アプリ SA にブランドプロジェクトの IAM admin を渡す**: 「nodepool 移管せず、cost-monitor 用 viewer だけブランド側で付与」案。摩擦の根本原因 (所有と意思決定の不一致) は解消しない。
- **cost-monitor をブランド側に移管**: ブランド配下の全アプリを横断監視するツールに昇格させる案。本 ADR 時点でブランド配下のアプリ数が 1 のため過剰投資。
- **k8s/env-lifecycle.yaml もアプリ側に集約**: env-lifecycle は k8s クラスタリソース全般の env レベル orchestration を担うため、k8s repo に残置するのが「executor は所有 repo」原則に整合する。
