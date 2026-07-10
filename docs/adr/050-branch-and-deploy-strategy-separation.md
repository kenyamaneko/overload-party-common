# ADR-050: ブランチ戦略とデプロイ戦略の分離

## ステータス

Proposed (2026-07-09)

## 結論

ルールを「ブランチ戦略」と「デプロイ戦略」の2軸に分離し、ブランチ運用ルールの重複を解消してデプロイ方式をリポ単位で選べるようにする。

- **ブランチ戦略は GitHub Flow の一本に統一する。** `main` + 短命 feature branch のみで運用し、環境を分岐で表現する運用 (develop / release / 環境ブランチ) は採用しない。デプロイ方式の違いは、別のブランチ戦略名としては表現しない。
- **デプロイ戦略はパターンごとに1ファイルに分け、リポ単位で選択する。** 「merge / タグ / 手動 sync でどの環境へ反映するか」はブランチ戦略から切り離し、`keyandnotes-rules/rules/deploy/<戦略>.md` として独立させる。リポがどのパターンを採るかは `repos.yaml` の `deploy` フィールドで解決する (`lang` / `flow` と同じ索引方式)。

サービス系の反映モデル (dev = merge で自動 sync / stg = タグで自動 sync / prod = 手動 sync) は、デプロイ戦略 `gitops-sync` として定義する。これは既存の GKE サービスの反映挙動であり、本 ADR はその分類を定めるもので挙動そのものは変えない。

## 背景・課題

ブランチ運用 (main + feature) と環境反映 (merge/タグ/手動 sync による dev→stg→prod 昇格) を一体のブランチ戦略として扱うと、次の歪みが生じる。

- ブランチ構成は GitHub Flow と同一なのに、反映方式の違いだけで別のブランチ戦略名 (gitflow / githubflow / release-flow) が並立し、ブランチ運用のルールが各ファイルで重複する。
- サービスの実態はデプロイ方式で分かれる (GKE サービスは ArgoCD sync、Cloud Function/Job は手動 dispatch、common はパッケージ publish、IaC は手動 apply)。これはブランチ戦略ではなくデプロイ戦略の差だが、ブランチ戦略の分類に押し込まれていた。

反映方式はブランチ構成と独立の軸であり、分離した方がリポごとの選択と参照が素直になる。

## 制約

- ソロ運用であり、複数人レビューや保護ブランチによる合意形成を前提にした運用は要求されない。
- GKE サービスは ArgoCD の Application と Kustomize overlay で環境差分と反映を管理する構成が確立している (ADR-018)。デプロイ戦略の分離はこの構成と両立する必要がある。
- ブランチ運用中・デプロイパイプライン整備前のリポが存在する。既存の反映挙動を壊さずに移行できることが条件になる。

## 詳細

### ブランチ戦略

`keyandnotes-rules/rules/flow/github-flow.md` の一本に統一する。旧 `gitflow.md` / `gitlabflow.md` / `release-flow.md` は廃止する。`repos.yaml` の `flow` は `github-flow | none` の2値になる (`none` は main 直 push を許容するリポ)。

### デプロイ戦略

`keyandnotes-rules/rules/deploy/` にパターンごとのファイルを置く。

| 戦略 | 環境 | トリガー → 反映 |
| --- | --- | --- |
| `merge-dev-tag-prod` | dev / prod | merge → dev 自動 / タグ → prod 自動 |
| `gitops-sync` | dev / stg / prod | merge → dev sync / タグ → stg sync / 手動 → prod sync |
| `manual-pipeline` | 任意 | 各環境ともパイプライン手動実行 |
| `store-release` | 検証配布 / ストア | ビルド → 検証配布 / 審査通過 → 本番配布 |
| `artifact-publish` | レジストリ | タグ push → publish |
| `merge-prod` | prod のみ | main マージ → prod (ゲートなし) |

### 索引と参照

`repos.yaml` に `deploy` フィールドを追加し、`rules/deploy/<deploy>.md` に 1:1 対応させる。`CLAUDE.md` のルール適用手順に「`deploy` を引き、対応する `rules/deploy/<deploy>.md` を Read する」ステップを追加する。デプロイ整備前のリポは `deploy: none` とし、整備時に値を確定する。

### 現行リポの割り当て

ADR-041 (CI/Deploy トリガー分離) と本リポ README の publish 構成から、実態が確定しているものを割り当てる。

- GKE サービス (shop / gateway / account / card / matchmaking / scenario / news / support / battle) → `gitops-sync`
- Cloud Function / Cloud Run Job (analytics / newsfeed) → `manual-pipeline`
- common (パッケージ publish) → `artifact-publish`
- infra (Terraform) → `manual-pipeline`
- client (モバイルアプリ) → `store-release`
- ops (運用ツール) → `merge-prod`
- k8s (ArgoCD の参照元でデプロイ主体でない) / assets / web / e2e → `none`

## 不採用案

### ブランチ戦略とデプロイ戦略を一体で扱う

- メリット: 追加の整理が不要。
- デメリット: ブランチ構成が同一なのに反映方式の違いで別戦略名が並立し、ブランチ運用ルールの重複が残る。
- 不採用理由: 本 ADR が解消しようとしている重複と、実態 (デプロイ方式の差) との不一致がそのまま残るため。

### デプロイ戦略を1ファイルのカタログに集約する

- メリット: パターン一覧を1箇所で見渡せる。
- デメリット: 各サービスリポからデプロイ戦略をファイル単位で参照する運用に合わない。1リポが不要なパターンまで読み込む。
- 不採用理由: `lang` / `flow` と同じくファイル単位で参照・解決する方式に揃えるため。
