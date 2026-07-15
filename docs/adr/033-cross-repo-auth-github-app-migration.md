# ADR-033: cross-repo CI/automation 認証を個人 PAT から GitHub App に統一

## ステータス

Accepted (2026-05-05)

## 結論

個人帰属・長期生存・手動 rotation という PAT 運用の構造的問題を解消するため、**12 種の PAT を全廃し、用途別に 4 つの GitHub App に統合する**。各 App は最小権限の原則に従い、permission と installation 範囲を分ける。PAT 発行者個人が組織を抜けても automation が止まらず、監査ログが App 名義で追跡可能になる。token は 1 時間 expire となって漏洩時の窓が大幅に縮小し、Secret 管理対象は 12 PAT から 4 App に集約される。App scope は overload-party-* 全リポ Read なので insteadOf スコープのミスマッチで CI が落ちる問題も構造的に解消し、rate limit も per-installation 15,000 req/hr に改善する。6 サービスリポに散在していた auth セットアップ (~30+ 行) は composite action 1 箇所に集約される。

## 背景・課題

組織 (`@kenyamaneko`) 配下の全リポで CI / automation の cross-repo 認証に **個人 PAT** を使っている。全 PAT を棚卸ししたところ、有効な PAT が 12 種、用途と permissions がバラバラに広がっていた。

### 現状の PAT 一覧 (棚卸し結果)

| # | PAT | 実使用箇所 | 必要権限 |
|---|---|---|---|
| 1 | `INFRA_DRIFT_MONITOR` | `overload-party-ops/.github/workflows/drift-monitor.yaml` | Issues:Write + Contents:Read |
| 2 | `INFRA_DISPATCH` | `overload-party-ops/.github/workflows/nightly-shutdown.yaml` (overload-party-infra への workflow_dispatch) | Actions:Write |
| 3 | `K8S_DISPATCH` | `overload-party-ops/.github/workflows/nightly-shutdown.yaml` (overload-party-k8s への workflow_dispatch) | Actions:Write |
| 4 | `DB_MIGRATE` | `overload-party-ops/.github/workflows/db-migrate.yaml` (各サービスリポの schema fetch) | Contents:Read |
| 5 | `COMMON_GO_MODULES_FETCH` | 6 サービスリポ (card / shop / account / scenario / gateway / matchmaking) の CI で `insteadOf` 経由 Go module fetch | Contents:Read |
| 6 | `CLAUDE_SYNC` | `overload-party-common/.github/workflows/claude-presets-sync.yaml` (各リポへ `.claude/` 同期 PR/commit) | Contents:Write + Pull-requests:Write |
| 7 | `PLATFORM_DISPATCH` | `overload-party-k8s/.github/workflows/env-lifecycle.yaml` (keyandnotes-platform への workflow_dispatch) | Actions:Write |
| 8 | `ARGOCD_IMAGE_UPDATE` | k8s クラスタ内 ArgoCD Image Updater Pod (Secret Manager `argocd-image-updater-github-pat` 経由、`overload-party-k8s` への git write-back) | Contents:Write |
| 9 | `SERVICES_GO_MODULES_FETCH` | `overload-party-e2e/docker/docker-compose.yml` で BuildKit secret として開発者ローカル使用 | Contents:Read |
| 10 | `BATTLE_GO_MODULES_FETCH` | 同上 (e2e ローカル)。`overload-party-account/.github/scripts/deploy/build-image.sh` には死コード残骸あり | Contents:Read |
| 11 | `COMMON_CI_DISPATCH` | grep ヒットなし (Last used 5 週間前)。死蔵候補 | — |
| 12 | `SLACK_COMMANDS` | (廃止済) `overload-party-ops/slack-commands/` Cloud Run service が使用していたが、2026-05-06 に Slack コマンド機能自体を廃止 (代替: GitHub Actions UI の workflow_dispatch)。本 ADR の App 化対象外、PAT 単体 revoke で完了 | — |

### PAT 運用の構造的問題

1. **個人帰属の認証情報を組織活動に使っている**: PAT は発行者個人の権限で動作する。発行者が組織を抜けた瞬間に CI / automation が全停止し、監査ログも個人名義で組織活動として追跡できない
2. **scope と本数のトレードオフが避けられない**: scope を絞ると複数 PAT に分裂 (#9, #10 の e2e ローカル用や `gateway` で過去使われていた 3 PAT 構成のように)、scope を広げると漏洩時の被害が大きくなる
3. **secret rotation が完全手動**: PAT の期限切れに気付くのは「ある日 CI / image 更新 / Slack コマンドが落ちた」タイミング。GitHub には計画的 rotate の仕組みがない
4. **書き込み権限を持つ PAT が長期生存**: #6, #7, #8 は Contents:Write / Actions:Write / Pull-requests:Write を持ち、漏洩時の blast radius が Read-only PAT より大きいまま長期生存している
5. **`insteadOf` スコープと PAT scope のミスマッチで構造的に落ちる**: PAT scope を狭く設定すると新規依存追加で毎回事故る (実際に [overload-party-card#6](https://github.com/kenyamaneko/overload-party-card/pull/6) で発生済み)
6. **死蔵 PAT の温存**: #11 のように grep で 0 件、利用元不明のまま長期残置されている PAT が存在する

GitHub 公式ドキュメントは数年前から PAT を automation / CI 用途に推奨しなくなっており、`GitHub App + 短命 token` への移行を案内している。本 ADR で組織横断の方針を確定する。
