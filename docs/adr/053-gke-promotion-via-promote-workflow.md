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

## 不採用案

### サービスリポのタグ push を起点にする

人が `git tag vX.Y.Z` を push し、サービスリポの workflow が再タグと overlay 更新を行う案。gitops-sync.md の文言には忠実だが、dev 未反映のコミットへタグを打つ事故を構造的に防げず (promote 案は dev の `newTag` から sha を取るため防げる)、パッケージ publish のタグ手動打ち禁止の流儀とも割れるため不採用。

### Image Updater の semver 戦略で stg / prod を追従させる

stg / prod の allow-tags を `vX.Y.Z` 形式、update-strategy を semver にし、昇格をイメージ再タグ 1 操作にする案。変更は最小だが、反映する版の決定が Image Updater の「最大バージョン選択」に固定されるためロールバックが roll-forward しかできず、昇格操作の記録も残らないため不採用。
