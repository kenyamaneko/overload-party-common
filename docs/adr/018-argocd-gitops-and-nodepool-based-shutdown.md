# ADR-018: ArgoCD による GitOps 化と nodepool 単位の nightly shutdown

## ステータス

Proposed (2026-04-14)

## 結論

手動 apply 運用の drift 不可視・履歴不明・切り戻し困難を解消するため、以下を採用する。

1. **ArgoCD を導入し、k8s マニフェストは GitOps で同期する**
2. **image tag の更新は ArgoCD Image Updater が行う**（サービスリポ CI は k8s リポに一切書き込まない）
3. **ArgoCD の sync は全環境で manual**（Image Updater が manifest を更新した後、人が UI から sync を実行）
4. **Application 粒度は service × env = 21 Application**
5. **ArgoCD / Image Updater は prod nodepool に同居**させる
6. **Ingress / backendConfig / Service annotation は prod のみ ArgoCD 管理**、dev/stg は既存の `env-lifecycle` が管理し続ける
7. **PSC forwarding rule は現状維持**（`env-lifecycle` が dev/stg の up/down で作成・削除）
8. **nightly shutdown は Pod scale 0 方式から dev/stg 共有 nodepool を 0 ノードに resize する方式へ切り替える**

Git と実クラスタの drift が ArgoCD UI で自動検知され、deploy 履歴と rollback 経路が明確になる。反映タイミングは全環境で人が制御でき、21 Application 構成によりサービス単位の独立 deploy / rollback が可能になる。サービスリポは image を push するだけという片方向依存が保たれ、nightly shutdown は VM 課金が実際に止まる方式になる。

## 背景・課題

Overload Party の k8s マニフェストは `overload-party-k8s` リポジトリに Kustomize 構成（base / components / overlays）で集約されており、現状は同リポの GitHub Actions `deploy.yaml` を**手動トリガー**して `kustomize build | kubectl apply` で各環境に反映している。image tag は全環境共通で `:latest` 固定、環境間の差分は overlay の replicas と Workload Identity annotation のみ。

この運用には以下の課題がある。

- **Git と実クラスタの乖離が検知できない**: 手動 apply の失敗や apply 漏れ、手で `kubectl edit` した差分が可視化されない
- **deploy 履歴が追えない**: 「いつ・誰が・どの image を本番に当てたか」が Actions の run log に散在し、rollback 対象の特定が難しい
- **環境ごとの deploy gate がない**: `:latest` を全環境で参照しているため、dev に当てたい変更が直ちに prod にも影響しうる構造で、prod 向けの承認フローを挟む余地がない
- **サービス単位の切り戻しができない**: 7 サービスを一括で apply する形になっており、特定サービスだけ前 tag に戻すオペレーションは手作業

併せて ADR-013 で決めた Standard モードへの移行に伴い、dev/stg の夜間コスト削減方式も変更する必要がある。Autopilot 時代の「Pod を `replicas: 0` にする」方式は Pod 課金を止める目的で機能していたが、Standard では VM 単位課金のため Pod を 0 にしても料金は下がらず、**ノードプール自体を 0 ノードにする**のが本質的な停止方式になる。

この 2 つ（GitOps 化とノード停止方式の切り替え）は、Pod スケールと ArgoCD の desired state が衝突する問題を共通の論点として持つため、同一 ADR で決定する。

## 不採用案

### CI push 方式（サービスリポ CI が k8s リポに commit）

セットアップ量は Image Updater と同等で、deploy 履歴が Git log に明示的に残る利点がある。しかし **サービスリポの CI が infra リポに書き込む**構造になり、リポジトリ分割（ADR-011）で意図した責務境界が崩れる。権限面でも各サービスリポの CI token が k8s リポへの write 権限を持つ必要があり、blast radius が 7 倍に増える。今回は **リポジトリ間の疎結合を最優先**するため採用しない。Image Updater の debug 容易性の低さ（registry polling の filter 設定、sync タイミングが見えづらい）はトレードオフとして許容する。

### CI が PR を開く方式

CI が k8s リポに PR を作成し、dev は auto-merge、stg/prod は手動 approve、という運用分けが可能。責務分離と prod gate の両立では理想的に近いが、**サービスリポ CI が k8s リポのディレクトリ構造を知り PR を作る**という依存関係は残り、疎結合の観点では CI push と同質の結合が残る。今回はその依存自体を排除したいため採用しない。

### env ごとに 1 Application（計 3 個）

Kustomize overlay と 1:1 対応でシンプル。ただし**単一サービスの切り戻し**が Application 単位でできず、k8s リポ側で該当サービスの image tag を手で書き戻す必要がある。ADR-011 でサービスを分割した利点（障害局所化・独立デプロイ）を運用面で享受しにくくなるため採用しない。

### ArgoCD sync を dev/stg は自動、prod だけ manual にする

dev/stg のフィードバックループが速くなる利点がある。ただし「深夜に nodepool が 0 ノードになっている間に Image Updater が commit し、翌朝 nodepool 復旧と同時に dev に未確認の image が自動 sync される」といった、意図していないタイミングでの反映が起こりうる。全環境で人間が sync を明示的に発火させることで、**反映タイミングと内容の両方**を人が決められるようにする。

### 別途 system nodepool を作って ArgoCD を配置する

クラスタ運用の独立性（app pool の障害や 0 スケールに引きずられない）という利点があるが、常時 1 ノード分の VM 課金が追加発生する。prod pool は 24h 稼働するため ArgoCD の稼働要件と一致し、nodepool を追加する動機が乏しい。

### Pod scale 0 方式を継続する

`kubectl scale --replicas=0` は実装が単純だが、Standard モードでは **Pod を 0 にしても VM 課金は止まらない**ため夜間コスト削減の目的を果たせない。また ArgoCD の desired state と衝突し、`ignoreDifferences` や Application `suspend` のような回避が必要になる。nodepool 0 ノード方式なら Deployment の spec は変化しないため ArgoCD と衝突せず（Pod は Pending のまま、Application は Degraded 扱い）、コスト削減も VM 単位で確実に効く。
