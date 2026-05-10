---
name: implementing-from-issue
description: GitHub Issue を起点に feature ブランチを切って実装・PR 作成まで行う手順 (GitHub Flow 版)。ユーザーが「Issue xx をやって」「この Issue を対応」と依頼したときに使う。
---

# Issue を元に実装する (GitHub Flow)

GitHub Issue を起点に、`main` から feature ブランチを切り、テストファーストで実装し、`main` への PR を作成するまでの手順。

## 手順

1. Issue の内容を確認する
   - 背景・受け入れ基準・関連リンクを読み、何が「完了」かを把握する
   - 方針に迷いがあれば**着手前に**ユーザーに相談する(実装後の手戻りを避ける)
2. `main` から feature ブランチを切る
   - 命名: `feature/{issue番号}-{概要}` (例: `feature/42-add-foo`)
   - 最新の `main` を取得してから切る: `git fetch origin && git switch -c feature/{n}-{summary} origin/main`
3. 必要に応じてドキュメントを更新する
   - 仕様変更: `docs/FEATURE_SPEC.md` / `docs/API_REFERENCE.md` 等
   - 設計レベルの意図: `docs/ARCHITECTURE.md`
   - インフラ変更で環境への反映順序が変わる場合: `docs/CI_AND_RELEASE.md`
   - データモデル・型定義の SSoT を変更した場合は、各リポの CLAUDE.md / README に従って生成スクリプトを再実行する
4. テストファーストで実装する
   - 受け入れ基準を Given/When/Then に落としてテストを書いてから実装する
   - インフラ系リポ (Terraform / k8s 等) でユニットテストが書けない場合は、plan / dry-run / kubeconform 等の検証コマンドを必ず通す
   - テスト方針・設計思想・コーディング方針は [CLAUDE.md](../../CLAUDE.md) に従う
5. コミット・プッシュする
   - コミットメッセージ形式: `{type}: {要約}` (Conventional Commits)
   - type: `feat` / `fix` / `refactor` / `docs` / `chore` / `test` / `perf` / `ci` のいずれか
   - **コミット前にユーザーの承認を得る**: 変更内容(`git diff` の要点)とコミットメッセージ案をユーザーに提示し、修正内容が妥当か・メッセージが適切かを確認してから `git commit` を実行する
   - `git push -u origin feature/{n}-{summary}`
6. `main` への PR を作成する
   - タイトルは 70 文字以内。本文は「Summary」「Test plan」を含める
   - Issue 番号を本文に記載する (例: `Closes #42`)
   - インフラ系で plan / diff の出力がある場合は、PR 本文に貼り付けてレビュアーが確認できるようにする
7. ユーザーに PR URL を通知する

## 確認事項

着手前に以下が不明なら**推測せず質問する**:

- Issue の受け入れ基準が読み取れない / 複数解釈できる
- 影響範囲が想定より広い(他サービス・DB スキーマ・公開 API・本番インフラに及ぶ)
- ドキュメント更新の要否が判断できない
- 環境への反映順序やロールバック手順が不明
