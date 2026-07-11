# ADR-053: GKE サービスの環境昇格を promote workflow とバージョン固定 overlay で実装する

## ステータス

Accepted (2026-07-11)

## 結論

gitops-sync (ADR-050) が定義する昇格モデル (dev = 自動反映 / stg = バージョン起点で自動反映 / prod = 同一 digest を手動反映) を、次の 3 点で実装する。

- **dev**: Image Updater の追従対象を dev のみに絞り、dev の Application を automated sync にする。main マージから人手なしで dev に反映される
- **昇格**: ops リポに **promote workflow** (`workflow_dispatch`、inputs: service / bump) を新設する。dev で稼働中の sha イメージに `vX.Y.Z` タグを追加し (再ビルドなし、同一 digest)、サービスリポへ git tag を発行し、k8s リポの stg / prod overlay の `newTag` を `vX.Y.Z` に commit する
- **stg / prod**: stg の Application は automated sync にし、promote の commit で自動反映する。prod は手動 sync のままとし、人が sync した時点で stg と同一 digest が反映される

これにより、prod へ出る内容が「sync した瞬間の最新 main ビルド」から「stg で検証した digest」に固定される。昇格の記録は k8s リポの commit とサービスリポの git tag に残り、ロールバックは k8s リポの revert で行える。

## 背景・課題

現状の反映経路は、Image Updater が最新 sha ビルドを dev / stg / prod 全環境の kustomization に write-back し、人が ArgoCD で sync した環境にだけ反映される (全 Application manual sync)。この構成には次の問題がある。

- stg / prod に「どのビルドを出すか」を固定する場所がなく、sync した瞬間の最新 main ビルドが出る。stg 検証中に main が進むと、prod の sync で検証していないビルドが出る
- バージョン番号が存在せず、どの環境に何が出ているかは sha の突き合わせでしか確認できない
- ロールバック手段が「過去の sha を kustomization に手書きして sync」しかない

ADR-050 はこの反映モデルを gitops-sync として分類したが、バージョン起点の stg 反映と同一 digest 昇格は実装されていない (common#201)。

## 詳細

### 変更しないもの

- 各サービスリポの deploy.yaml (main push → `:<sha>` / `:latest` を push)
- prod の Application の manual sync

### ApplicationSet (overload-party-k8s)

- Image Updater の annotation (image-list / update-strategy / allow-tags / write-back) を dev の Application にのみ付与する (goTemplate の env 分岐)
- dev / stg の syncPolicy を automated にする。prune は付けず、リソース削除を伴う変更は従来どおり手動 sync で prune する
- stg / prod の kustomization `newTag` は promote workflow だけが書き換える。「Image Updater が上書きする」旨のコメントを実態に合わせて更新する

### promote workflow (overload-party-ops)

`workflow_dispatch` (inputs: service = 9 サービスの choice / bump = patch・minor・major) で次を行う。

1. k8s リポの dev overlay の `newTag` から昇格対象の sha を解決する (dev で稼働中のビルドだけが昇格できる)
2. サービスリポの既存 `vX.Y.Z` タグから次バージョンを採番する
3. `gcloud artifacts docker tags add` で対象 sha イメージに `vX.Y.Z` タグを追加する (同一 digest)
4. サービスリポの対象コミットへ git tag `vX.Y.Z` を発行する
5. k8s リポの stg / prod overlay の `newTag` を `vX.Y.Z` に commit する。stg は automated sync で反映され、prod は人の sync 待ちになる

認証は既存の運用系 workflow と同型にする (GitHub App token で k8s / サービスリポへ write、WIF で Artifact Registry)。

### ロールバック

k8s リポで promote の commit を revert する (stg は自動で戻り、prod は手動 sync で戻す)。または旧 digest を対象に promote し直す。

### ルール文書との差分

rules/deploy/gitops-sync.md は「SemVer タグを人が手動で打つ」「タグ push → stg 自動 sync」と記述しており、本 ADR ではタグの発行主体が promote workflow になる。パッケージ publish で確立した「タグの手動打ちを禁止し workflow を唯一の発行元にする」流儀に合わせたもので、rules 側の文言更新は keyandnotes-rules へ提案する (rules は人間運用のため)。

## 不採用案

### サービスリポのタグ push を起点にする

人が `git tag vX.Y.Z` を push し、サービスリポの workflow が再タグと overlay 更新を行う案。gitops-sync.md の文言には忠実だが、dev 未反映のコミットへタグを打つ事故を構造的に防げず (promote 案は dev の `newTag` から sha を取るため防げる)、パッケージ publish のタグ手動打ち禁止の流儀とも割れるため不採用。

### Image Updater の semver 戦略で stg / prod を追従させる

stg / prod の allow-tags を `vX.Y.Z` 形式、update-strategy を semver にし、昇格をイメージ再タグ 1 操作にする案。変更は最小だが、反映する版の決定が Image Updater の「最大バージョン選択」に固定されるためロールバックが roll-forward しかできず、昇格操作の記録も残らないため不採用。
