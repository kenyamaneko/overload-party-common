# ADR-056: GKE + GitOps を廃し Cloud Run + GCE + Cloud SQL 構成へ戻す

## ステータス

Accepted (2026-07-24)

この ADR は [ADR-001](001-migrate-to-cloudrun-gce-cloudsql.md) を置き換え、[ADR-013](013-gke-autopilot-to-standard.md)・[ADR-018](018-argocd-gitops-and-nodepool-based-shutdown.md)・[ADR-045](045-gke-ownership-boundary-and-cross-project-iam.md)・[ADR-051](051-ingress-always-on.md)・[ADR-053](053-gke-promotion-via-promote-workflow.md) を廃止する。ADR-001 が定めた「REST は Cloud Run、WebSocket は GCE、DB は Cloud SQL」という振り分けへ戻し、その後に重ねた GKE 構成を巻き戻す。

## 結論

バックエンドの実行基盤を GKE から次の構成へ戻す。

- WebSocket を担う gateway は GCE の Managed Instance Group で常時起動し、単一インスタンスの自己修復で可用性を確保する
- battle と他のステートレスな REST サービスは Cloud Run で実行し、未使用時はゼロへスケールさせる
- DB は各環境の Cloud SQL PostgreSQL を継続する
- クラスタと GitOps ツール (ArgoCD / Flux) は廃止する

これにより、未使用時にゼロへスケールできない要素が gateway 一つに限定される。クラスタ維持のための運用 (ノード停止、GitOps ツールの常駐、公開ロードバランサ) が不要になり、未使用環境のコストは実質ゼロに近づく。本番の月額コストは GKE 構成のおよそ半分に下がる。

## 背景・課題

ADR-001 は MVP のコスト最小化のため Cloud Run + GCE + Cloud SQL を採用した。その後 WebSocket のステートフル性を根拠に GKE へ移し (この移行自体は ADR 化されていない)、GKE 上で ADR-013 が Standard 化を、ADR-018 が GitOps とノードプール単位の夜間停止を重ねてきた。

この構成には、未使用時のコスト最小化と GitOps の宣言的運用が両立しないという緊張がある。コスト削減のためノードを 0 にすると、Pod の望ましい状態 (稼働) と実態 (停止) が乖離し、GitOps ツールが恒常的に不整合を報告する。ノード回収を Cluster Autoscaler へ寄せようとすると、ロードバランサの常時課金、Pod をゼロにする別機構、常駐コンポーネントの追加が連鎖し、クラスタを軽くするはずの GitOps 移行の意義が崩れる (ADR-048 で棄却済み)。

構成を精査した結果、クラスタ上で真にステートフルかつ常時起動を要するのは、WebSocket 接続とゲーム進行のインメモリ状態を持つ gateway だけと判明した。battle はステートフルに見えるが、ゲーム盤面をアクションごとにトランザクションで DB へ永続化しており、プロセスとしてはステートレスである。他サービスも状態を DB や外部キューへ外部化している。したがってクラスタ全体を維持する根拠は、gateway 相当の単一 VM に置き換えられる。

## 不採用案

### GKE + GitOps を継続する

未使用時のノード停止と GitOps の宣言的状態が両立せず、Cluster Autoscaler 化はロードバランサの常時課金と Pod ゼロ機構を呼び戻す。クラスタ維持の運用コストに見合う便益がゲーム一本の規模では得られないため採用しない。

### gateway も Cloud Run で常時起動する

WebSocket サーバはゼロへスケールできず、Cloud Run では常時一インスタンスに固定する必要がある。この場合サーバレスの割増料金が同等スペックの VM のおよそ二倍かかり、さらに WebSocket リクエストに接続時間の上限が課されて定期的な再接続を強いる。ゼロスケールの利点が得られない用途で割増を払う形になるため採用しない。

### gateway を Cloudflare Workers (Durable Objects) で実装する

Durable Objects は WebSocket とゲーム単位の状態管理に適し、ゼロスケールとゲーム単位の自動シャーディングを備える。しかし gateway は DB・イベント基盤・複数サービスへの同期呼び出しと密に結合しており、移すには全面的な言語書き換えと、それらすべてのクロスクラウド化、運用基盤の二重化、専有基盤へのロックインを伴う。運用面の縮小という目的に反するため現時点では採用しない。
