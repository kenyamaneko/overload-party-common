# ADR-018: ArgoCD による GitOps 化と nodepool 単位の nightly shutdown

**Status:** Proposed
**Date:** 2026-04-14

---

## 背景

Overload Party の k8s マニフェストは `overload-party-k8s` リポジトリに Kustomize 構成（base / components / overlays）で集約されており、現状は同リポの GitHub Actions `deploy.yaml` を**手動トリガー**して `kustomize build | kubectl apply` で各環境に反映している。image tag は全環境共通で `:latest` 固定、環境間の差分は overlay の replicas と Workload Identity annotation のみ。

この運用には以下の課題がある。

- **Git と実クラスタの乖離が検知できない**: 手動 apply の失敗や apply 漏れ、手で `kubectl edit` した差分が可視化されない
- **deploy 履歴が追えない**: 「いつ・誰が・どの image を本番に当てたか」が Actions の run log に散在し、rollback 対象の特定が難しい
- **環境ごとの deploy gate がない**: `:latest` を全環境で参照しているため、dev に当てたい変更が直ちに prod にも影響しうる構造で、prod 向けの承認フローを挟む余地がない
- **サービス単位の切り戻しができない**: 7 サービスを一括で apply する形になっており、特定サービスだけ前 tag に戻すオペレーションは手作業

併せて ADR-013 で決めた Standard モードへの移行に伴い、dev/stg の夜間コスト削減方式も変更する必要がある。Autopilot 時代の「Pod を `replicas: 0` にする」方式は Pod 課金を止める目的で機能していたが、Standard では VM 単位課金のため Pod を 0 にしても料金は下がらず、**ノードプール自体を 0 ノードにする**のが本質的な停止方式になる。

この 2 つ（GitOps 化とノード停止方式の切り替え）は、Pod スケールと ArgoCD の desired state が衝突する問題を共通の論点として持つため、同一 ADR で決定する。

## 決定

以下を採用する。

1. **ArgoCD を導入し、k8s マニフェストは GitOps で同期する**
2. **image tag の更新は ArgoCD Image Updater が行う**（サービスリポ CI は k8s リポに一切書き込まない）
3. **ArgoCD の sync は全環境で manual**（Image Updater が manifest を更新した後、人が UI から sync を実行）
4. **Application 粒度は service × env = 21 Application**
5. **ArgoCD / Image Updater は prod nodepool に同居**させる
6. **Ingress / backendConfig / Service annotation は prod のみ ArgoCD 管理**、dev/stg は既存の `env-lifecycle` が管理し続ける
7. **PSC forwarding rule は現状維持**（`env-lifecycle` が dev/stg の up/down で作成・削除）
8. **nightly shutdown は Pod scale 0 方式から dev/stg 共有 nodepool を 0 ノードに resize する方式へ切り替える**

### image tag 運用

各サービスの GitHub Actions は現状 `:latest` と `:<commit-sha>` の両方を Artifact Registry (`asia-northeast1-docker.pkg.dev/keyandnotes-platform/overload-party/<service>`) に push している。manifest 側を **commit sha (40 桁 hex) 追従**に切り替え、`:latest` の参照をやめる。

Image Updater は Artifact Registry を polling し、新しい sha tag を検出すると k8s リポに commit する。sync は人が ArgoCD UI で起動する。

```
argocd-image-updater.argoproj.io/image-list: <svc>=asia-northeast1-docker.pkg.dev/keyandnotes-platform/overload-party/<svc>
argocd-image-updater.argoproj.io/<svc>.update-strategy: newest-build
argocd-image-updater.argoproj.io/<svc>.allow-tags: regex:^[a-f0-9]{40}$
argocd-image-updater.argoproj.io/write-back-method: git
```

### Application 構成

env ごとに 1 Application（計 3 個）でも overlay 構造には合致するが、**単一サービスの切り戻しをクラスタ操作なしに UI から実行できる**ことを重視し、service × env = 21 Application とする。`ApplicationSet` で CRD 化しておけば、サービス追加時の Application 生成は自動化できる。

### 管理責務の分担（Ingress / PSC / DNS / IP）

| リソース | dev / stg | prod |
|---|---|---|
| Deployment / Service / ConfigMap / ServiceAccount | ArgoCD | ArgoCD |
| Ingress / backendConfig / Service annotation | env-lifecycle (kubectl apply/delete) | ArgoCD |
| PSC forwarding rule | env-lifecycle (gcloud, up/down 時に作成・削除) | env-lifecycle で初回作成後、削除せず維持 |
| Reserved global IP | env-lifecycle（down で削除） | 常時保持（削除しない） |
| Cloudflare DNS | env-lifecycle（down で 127.0.0.1 に切り替え） | 常時有効 |

Kustomize 構成上は、`k8s/components/ingress` を **prod overlay にだけ組み込む**ことで上記を自然に実現できる。dev/stg overlay は Ingress component を含まないため、そもそも ArgoCD の sync 対象外となり `ignoreDifferences` のような回避設定は不要。

### nightly shutdown の方式変更

`overload-party-ops` の `nightly-shutdown/shutdown.sh` が dev/stg の Pod を `kubectl scale --replicas=0` で止めている処理を、**dev/stg が共有している nodepool 自体を 0 ノードに resize** する処理に置き換える。

```sh
gcloud container clusters resize keyandnotes-main \
  --node-pool=keyandnotes-main-dev \
  --num-nodes=0 \
  --region=asia-northeast1
```

`env-lifecycle.yaml` の up 側も対応して変更する。`Scale pods up` ステップを削除し、代わりに nodepool を 1 ノードに resize した後、`kubectl wait --for=condition=Available deployment` で Pod Ready を待つ。

PSC / Ingress / DNS / Reserved IP の扱いは従来通り（nodepool を 0 にしても LB や Reserved IP は課金されるため、既存の停止処理は維持する必要がある）。

### ArgoCD の配置

ArgoCD と Image Updater は prod nodepool に同居させる。専用の system nodepool は新設しない。

- prod は 24h 稼働するため ArgoCD の可用性要件に合致する
- 追加 nodepool の常時稼働コストを発生させない
- `nodeSelector` で prod pool に固定、`podAntiAffinity` で app Pod と同居を回避
- resource requests: ArgoCD 本体（controller / repo-server / redis / server）と Image Updater を合わせて **0.5 vCPU / 1 GiB** 程度を見込む
- ArgoCD 自身は ArgoCD Application として self-manage せず、初回のみ Helm / Terraform で導入する（chicken-and-egg 回避）

## 検討した代替案

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

## 結果

### 得られるもの

- **Git と実クラスタの一致が自動検知される**: 手動 apply 漏れや drift が ArgoCD UI で可視化される
- **deploy 履歴と rollback 経路の明確化**: どの Application にどの image が当たっているかが UI で確認でき、過去の commit に戻すだけで rollback が完結する
- **全環境で人間の sync gate**: prod だけでなく dev/stg も含めて、反映タイミングを人が制御できる
- **サービス単位の独立 deploy / rollback**: 21 Application 構成により、gateway の不具合だけを前 tag に戻すといった操作が他サービスに影響せず実行できる
- **リポジトリ間の疎結合維持**: サービスリポは k8s リポを知らないまま image を push するだけ、k8s リポは Image Updater 経由で image を受け取るだけ、という片方向依存が保たれる
- **nightly shutdown の VM 課金停止**: Standard モードで nodepool 0 ノード方式にすることで、夜間の VM 課金が実際に止まる

### トレードオフ

- **Image Updater の debug 容易性が低い**: registry polling の filter 設定や反映遅延の原因追跡が CI push 方式より難しい。採用理由（疎結合）とのトレードオフとして許容する
- **dev/stg の Application が夜間 Degraded**: nodepool 0 ノード時は Pod が Pending になり ArgoCD 上 Degraded 表示になる。通知除外ルールで対応する
- **全環境 manual sync の運用負荷**: dev へのフィードバックループが「CI 完了 → Image Updater 検知 → ArgoCD UI で sync」の 3 ステップになる。短いが手動操作は増える
- **Application 21 個の管理**: ApplicationSet で生成するため初期セットアップは軽いが、サービス追加のたびに ApplicationSet テンプレートのレビューが必要
- **ArgoCD を prod pool に同居させるリスク**: prod pool のリソース逼迫が ArgoCD 自体に影響する可能性がある。podAntiAffinity と resource requests/limits の設定で緩和するが、将来 prod トラフィックが増えた段階で専用 pool への分離を再検討する

### 実装スコープ

本 ADR で決まったのは設計方針のみ。具体的な実装作業は以下に分担する。引き継ぎ: [handoff/argocd-introduction-infra-ops.md](../handoff/argocd-introduction-infra-ops.md)

- `keyandnotes-platform`: ArgoCD Image Updater 用の GSA / Secret Manager 枠、GKE `secret_manager_config` addon 有効化（ArgoCD はクラスタレベルのサービスのため platform が所有）
- `overload-party-infra`: prod 環境の Cloud SQL / PSC / Reserved IP / DNS / Workload Identity 紐付け
- `overload-party-ops`: `nightly-shutdown/shutdown.sh` の nodepool 方式への書き換え
- `overload-party-k8s`: Kustomize manifest の sha tag 対応、ArgoCD / Image Updater のインストール、ApplicationSet 作成、SecretProviderClass 定義、`env-lifecycle.yaml` の修正

### 認証情報の扱い

- **git write-back**: GitHub Fine-grained PAT を使う（Contents Read & Write 権限を `overload-party-k8s` リポのみに付与、有効期限 1 年）。個人開発スコープのため GitHub App は採用しない
- **PAT の保管**: Secret Manager にマスターを置き、GKE の Secret Manager CSI Driver 経由で k8s Secret に同期する。SecretProviderClass の定義は k8s リポ側（namespace スコープのリソースは ArgoCD 管理対象と同じ責務）
- **Artifact Registry 読み取り**: Workload Identity（Image Updater Pod の KSA ↔ GSA）
