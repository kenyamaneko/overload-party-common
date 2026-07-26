# ADR-045: GKE 所有境界の再定義（ノードプールをアプリ所有に移管し、ブランド側に cross-project IAM 付与を集約する）

## ステータス

Superseded by [ADR-056](056-retire-gke-gitops-return-to-cloudrun.md)

GKE ノードプールの所有境界の決定は、GKE の廃止により失効した。現行の実行基盤と cross-project の権限構成は ADR-056 を参照のこと。

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

## 不採用案

- **アプリ SA にブランドプロジェクトの IAM admin を渡す**: 「nodepool 移管せず、cost-monitor 用 viewer だけブランド側で付与」案。摩擦の根本原因 (所有と意思決定の不一致) は解消しない。
- **cost-monitor をブランド側に移管**: ブランド配下の全アプリを横断監視するツールに昇格させる案。本 ADR 時点でブランド配下のアプリ数が 1 のため過剰投資。
- **k8s/env-lifecycle.yaml もアプリ側に集約**: env-lifecycle は k8s クラスタリソース全般の env レベル orchestration を担うため、k8s repo に残置するのが「executor は所有 repo」原則に整合する。
