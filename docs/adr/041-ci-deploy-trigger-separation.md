# ADR-041: CI と Deploy のトリガー責務分離

## ステータス

Accepted (2026-05-12)

## 結論

post-merge の CI 重複と暗黙的な自動本番反映を解消するため、CI (品質ゲート) と Deploy (artifact 出力 / 環境反映) の責務を分離する。

- **ci.yaml**: `on: pull_request` のみ。lint / test / codegen / image-scan 等
- **deploy.yaml (GKE サービス)**: `on: push: branches: [main]` で resolve-env + image build & push のみ (ArgoCD 連携前提)
- **deploy.yaml (Cloud Function / Cloud Run Job)**: `on: workflow_dispatch` のみ、`needs:` で lint/test green を待つ

post-merge の lint/test 再実行がゼロになって Ubicloud 起動回数が減り、9 GKE サービスで deploy 体制が統一される。analytics / newsfeed の本番反映は人の判断を経由するようになり、k8s リポから死んだ workflow が消えて意図が明確になる。

## 背景・課題

ADR-038 (CI 時間削減) と ADR-040 (Ubicloud 移行) で CI 課金は抑制したが、運用上の歪みが残っている:

1. **post-merge CI 重複**: gateway / card / matchmaking / battle で ci.yaml に build-and-push が混在し、PR で通った lint/test/codegen が main push 時にも `needs:` 依存で再実行される
2. **死んだ workflow**: overload-party-k8s の deploy.yaml (kubectl apply) と terraform.yaml (対象 path 不在) は ArgoCD 導入前の遺産。README で「撤去予定」と明記されている
3. **自動 deploy の暗黙的本番反映**: analytics (Cloud Function) / newsfeed (Cloud Run Job) は main push で gcloud deploy が自動実行され、リリース判断が CI 側に固定されている
4. **image push workflow 不在**: 9 GKE サービス中 news / support のみ image push 系 workflow が無い

なお、ArgoCD の sync policy は manual。Service リポ image push → Image Updater がマニフェスト書き換え → 人が ArgoCD UI で sync する流れなので、CI 段階での品質ゲート漏れは production 反映の前段で必ず人が判断する。

## 詳細

リポ別適用:

| 区分 | 対象 | 変更 |
|---|---|---|
| A. 死んだ workflow 削除 | overload-party-k8s | deploy.yaml + terraform.yaml を削除 |
| B. post-merge CI 重複削減 | gateway / card / matchmaking / battle | ci.yaml から build-and-push を deploy.yaml (push:main) に切り出し |
| C. デプロイの手動ボタン化 | analytics / newsfeed | deploy を workflow_dispatch に変更、`needs:` で lint/test 待ち |
| D. deploy.yaml 新設 | news / support | shop/account/scenario と同形の deploy.yaml を追加 |

### トレードオフ

- workflow ファイル数が増える (各リポで ci + deploy)
- analytics / newsfeed の運用が自動 → 手動 dispatch に変わるため周知が必要
