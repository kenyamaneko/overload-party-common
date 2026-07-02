# ADR-048: Dev/Stg 環境の Cluster Autoscaler によるノードスケールダウン（棄却）

## ステータス

Rejected (2026-07-02)

## コンテキスト

Dev/Stg 環境では、未使用時にノードと LB を落としてコストを抑える目的で、これまで独自スクリプトを運用してきた。ADR-013 で Standard モードへ移行して以降、コスト削減の本質的なレバーは Pod ではなく VM (ノード) 単位にあり、ADR-018 でその停止方式を「dev/stg の nodepool を 0 ノードへ resize し、併せて LB / PSC / DNS / Reserved IP を teardown する」形で定めていた。

このスクリプト群のメンテナンスコストと複雑さを下げるため、ノードスケールダウンを GKE Cluster Autoscaler へ寄せ、LB は常時起動を許容する案を検討した。

## 当初の決定案

- **Dev/Stg**: 全ノードプールで `min_node_count = 0` を設定し、Cluster Autoscaler による自動スケールダウンを導入する。ノードプール設定変更は Terraform で反映する
- **Prod/Ops**: 対象外。現状維持とする
- **スケールダウン判定時間**: デフォルト (10 分) のまま変更しない
- **LB (Ingress / Service type LoadBalancer)**: 落とさず常時起動を許容し、コスト増より運用のシンプルさを優先する
- **Pod (Deployment / StatefulSet) のレプリカを 0 にする仕組み**: 別途用意し、本 ADR のスコープ外とする
- **Dev の起動**: CI 経由で Pod を 0→N に戻すトリガーとする
- **深夜の強制停止**: 行わない。既存の Slack 通知スクリプトで、ノードが起動したままの状態を検知・通知する

## 棄却理由

本案は、掲げた 2 つの便益 (コスト削減・運用簡素化) をいずれも達成できないため棄却する。

### 1. Ingress 常時起動のコストを許容できない

- LB (Ingress の GCE L7 LB) は dev/stg で各 1 本、`~$0.025/hr × 2 ≈ $36.5/mo` かかる。DNS (Cloudflare) は無料、外部 IP は ephemeral で軽微だが、LB 本体のコストが残る。
- この LB は **node / Pod を 0 にしても落ちない唯一のリソース**であり、autoscaler で node が 0 の深夜も課金され続ける。コスト面でこれを常時起動で許容することはできず、dev/stg の Ingress は落としたい。
- Ingress を落とすなら LB / DNS の teardown スクリプトが結局残る。「独自スクリプトを全廃してシンプルにする」という本案の主目的が、その時点で崩れる。

### 2. Cluster Autoscaler 導入単体の便益が薄い

- ノード停止方式を「直接 resize」→「autoscaler + Pod scale-0」に替えても、消えるのは `gcloud container clusters resize` の 1 行のみ。
- 代わりに **Pod を 0 にする仕組み (別途実装)** と、**ArgoCD の desired state との衝突対応**が増える。後者は ADR-018 が node-resize を選んだ理由そのもの (Deployment spec を変えないため ArgoCD と衝突しない) であり、autoscaler 方式はその衝突を呼び戻す。
- 宣言的・自動 right-sizing という便益はあるが、運用簡素化を目的とする本案の文脈ではこのスワップを正当化できない。

## 結論

コスト削減 (Ingress) も運用簡素化 (autoscaler) も達成できないため、本案は採用しない。dev/stg のコスト削減は ADR-018 の node-resize + LB / DNS teardown スクリプト方式を継続する。ノードスケールダウンの autoscaler 化は、Pod scale-0 の仕組みが別の理由で導入される時点で改めて再検討する。
