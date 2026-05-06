# ADR-033: cross-repo CI/automation 認証を個人 PAT から GitHub App に統一

- Status: Accepted
- Date: 2026-05-05
- Deciders: kenyamaneko
- Related: [overload-party-common#34](https://github.com/kenyamaneko/overload-party-common/issues/34) (Common Read App), [overload-party-common#35](https://github.com/kenyamaneko/overload-party-common/issues/35) (CLAUDE_SYNC App), [overload-party-ops#18](https://github.com/kenyamaneko/overload-party-ops/issues/18) (Ops Automation App), [overload-party-k8s#16](https://github.com/kenyamaneko/overload-party-k8s/issues/16) (ArgoCD Image Updater App)

## Context

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
| 8 | `ARGOCD_IMAGE_UPDATE` | k8s クラスタ内 ArgoCD Image Updater Pod (GCP Secret Manager `argocd-image-updater-github-pat` 経由、`overload-party-k8s` への git write-back) | Contents:Write |
| 9 | `SERVICES_GO_MODULES_FETCH` | `overload-party-e2e/docker/docker-compose.yml` で BuildKit secret として開発者ローカル使用 | Contents:Read |
| 10 | `BATTLE_GO_MODULES_FETCH` | 同上 (e2e ローカル)。`overload-party-account/.github/scripts/deploy/build-image.sh` には死コード残骸あり | Contents:Read |
| 11 | `COMMON_CI_DISPATCH` | grep ヒットなし (Last used 5 週間前)。死蔵候補 | — |
| 12 | `SLACK_COMMANDS` | `overload-party-ops/slack-commands/` Cloud Run service (GCP Secret Manager `github-pat-slack-commands` 経由、ユーザの Slack コマンドから workflow_dispatch / repository_dispatch / Issue 操作を発火) | Actions:Write + Contents:Read (用途により Issues:Write も) |

### PAT 運用の構造的問題

1. **個人帰属の認証情報を組織活動に使っている**: PAT は発行者個人の権限で動作する。発行者が組織を抜けた瞬間に CI / automation が全停止し、監査ログも個人名義で組織活動として追跡できない
2. **scope と本数のトレードオフが避けられない**: scope を絞ると複数 PAT に分裂 (#9, #10 の e2e ローカル用や `gateway` で過去使われていた 3 PAT 構成のように)、scope を広げると漏洩時の被害が大きくなる
3. **secret rotation が完全手動**: PAT の期限切れに気付くのは「ある日 CI / image 更新 / Slack コマンドが落ちた」タイミング。GitHub には計画的 rotate の仕組みがない
4. **書き込み権限を持つ PAT が長期生存**: #6, #7, #8 は Contents:Write / Actions:Write / Pull-requests:Write を持ち、漏洩時の blast radius が Read-only PAT より大きいまま長期生存している
5. **`insteadOf` スコープと PAT scope のミスマッチで構造的に落ちる**: PAT scope を狭く設定すると新規依存追加で毎回事故る (実際に [overload-party-card#6](https://github.com/kenyamaneko/overload-party-card/pull/6) で発生済み)
6. **死蔵 PAT の温存**: #11 のように grep で 0 件、利用元不明のまま長期残置されている PAT が存在する

GitHub 公式ドキュメントは数年前から PAT を automation / CI 用途に推奨しなくなっており、`GitHub App + 短命 token` への移行を案内している。本 ADR で組織横断の方針を確定する。

## Decision

**12 種の PAT を全廃し、用途別に 4 つの GitHub App に統合する**。各 App は最小権限の原則に従い、permission と installation 範囲を分ける。

### App 構成

| App 名 | permissions | installation 範囲 | カバー PAT | 主な consumer |
|---|---|---|---|---|
| **Common Read App** (`overload-party-cross-repo-deps`) | `Contents: Read` | overload-party-* リポ全部 (個人の無関係リポは除外) | #4 DB_MIGRATE / #5 COMMON_GO_MODULES_FETCH / #9 SERVICES_GO_MODULES_FETCH / #10 BATTLE_GO_MODULES_FETCH | 6 サービスリポの CI、ops の db-migrate、e2e ローカル開発者 |
| **Ops Automation App** (`overload-party-ops-automation`) | `Actions: Write` + `Issues: Write` + `Contents: Read` | overload-party-* + keyandnotes-platform (PLATFORM_DISPATCH 用) | #1 INFRA_DRIFT_MONITOR / #2 INFRA_DISPATCH / #3 K8S_DISPATCH / #7 PLATFORM_DISPATCH / #12 SLACK_COMMANDS | ops workflow 群、k8s/env-lifecycle、slack-commands Cloud Run |
| **Claude Sync App** (`overload-party-claude-sync`) | `Contents: Write` + `Pull-requests: Write` | overload-party-* リポ全部 (実 sync 対象は consumers.yaml で制御、将来 consumers が増えた際に再インストール不要にする) | #6 CLAUDE_SYNC | common/claude-presets-sync workflow |
| **Image Updater App** (`overload-party-image-updater`) | `Contents: Write` | overload-party-k8s のみ | #8 ARGOCD_IMAGE_UPDATE | k8s クラスタ内 ArgoCD Image Updater Pod |

#### App 分割の判断根拠

- **Read と Write を混ぜない**: Common Read App は overload-party-* 全リポ Read で済むので広く配っても影響が低い。Write は用途別に分割
- **ArgoCD と CLAUDE_SYNC を同じ Write App に相乗りさせない**: ArgoCD は k8s リポ 1 つの Contents:Write で済むのに対し、CLAUDE_SYNC は複数リポへの Contents:Write + Pull-requests:Write が必要。混ぜるとどちらかが過剰権限になり、漏洩時の blast radius が拡大する
- **Ops Automation を 1 App にまとめる**: workflow_dispatch / Issue 起票 / 他リポ schema fetch (Read) は Ops の自動化系として一体運用されており、separate しても運用コストが増えるだけ。Read を含めても Read-only の Common Read App と permission レイヤーは分かれている

### 死蔵 PAT の扱い

- `COMMON_CI_DISPATCH` (#11) は GitHub audit log で最終使用元を確認した上で revoke する。App 化対象外
- audit log で trace できなかった場合 (Free plan は 90 日制限) は revoke した上で 1 週間 monitoring する。問題が発生したら App 化対象に追加して再発行する

### App private key の rotation ポリシー

App private key は **明示 revoke しない限り無期限** で使える。本 ADR では:

- **定期 rotate を行わない**: PAT で問題になっていた「期限切れに気付くのが事故時」という構造的問題を、期限を排除することで解消する
- **漏洩疑い・key 保有者離脱時のみ revoke + 新 key 発行 → org secret を更新**: GitHub App は同じ App に対して複数の private key を同時発行・段階的差し替えが可能なため、ダウンタイムなしで rotation できる
- 期限管理を運用から完全に切り離すことを目的とする

### 認証フロー

#### GitHub Actions workflow から使う場合 (#1〜#7)

```yaml
- uses: actions/create-github-app-token@v1
  id: app-token
  with:
    app-id: ${{ vars.<APP_NAME>_APP_ID }}
    private-key: ${{ secrets.<APP_NAME>_APP_PRIVATE_KEY }}
    owner: kenyamaneko
- run: |
    # 例: workflow_dispatch
    gh workflow run ... --token ${{ steps.app-token.outputs.token }}
```

App ID は **organization variable**、private key は **organization secret** に登録する (App ID は単独では認証情報にならず、private key と組み合わせて初めて token が発行できるため variable で公開しても問題ない)。新リポ作成時に repo-level secret/variable を個別に貼る運用を必要としないため、設定漏れが構造的に発生しない。

#### Common Read App は reusable workflow 経由に統一する

Common Read App の利用は `overload-party-common/.github/workflows/setup-go-private-modules.yaml` (reusable workflow) 経由に統一する。各サービスリポの ci.yaml は以下のように呼び出すだけ:

```yaml
jobs:
  setup-auth:
    uses: kenyamaneko/overload-party-common/.github/workflows/setup-go-private-modules.yaml@main
    secrets: inherit
```

`actions/create-github-app-token` 呼び出し + `git config insteadOf` のセットアップを 1 箇所に集約し、行儀を組織横断で揃える。Reusable は **auth 専用**で、Go install / cache 等のセットアップはリポごとに事情が違うため呼び出し側に残す。

#### GitHub Actions の外で動くサービスから使う場合 (#8 ArgoCD Image Updater, #12 slack-commands Cloud Run)

PAT を渡す代わりに **App private key (PEM) を Secret Manager に投入** し、サービス側で:

1. App ID + Installation ID + private key で JWT を署名
2. JWT を `POST /app/installations/{id}/access_tokens` に投げて installation access token (1h expire) を取得
3. 取得した token で GitHub API を呼び出す (Bearer auth)
4. token は **1 リクエスト内で都度取得 or short TTL キャッシュ** で運用

ArgoCD Image Updater は GitHub App authentication を公式サポートしているため設定変更で完結。slack-commands Cloud Run service は実装変更が必要。

### e2e ローカル開発の認証

`overload-party-e2e/docker/docker-compose.yml` で開発者がローカルで使う `secrets/SERVICES_GO_MODULES_FETCH` / `secrets/BATTLE_GO_MODULES_FETCH` ファイルは、PAT を直書きする運用から **App private key で都度生成する短命 installation token を書き出す CLI スクリプト** に置き換える。e2e の README に手順を整備する。

## Consequences

### Positive

- **個人帰属からの脱却**: PAT 発行者個人が組織を抜けても automation が止まらない。監査ログが App 名義になり組織活動として追跡可能
- **token の長期存続を解消**: App token は 1 時間 expire。漏洩時の窓が PAT (数か月〜数年) から 1 時間に短縮
- **token 数の削減**: 12 PAT → 4 App に集約。Secret 管理 (各リポ secret + GCP Secret Manager) のメンテナンス対象が劇的に減る
- **書き込み App の影響範囲を最小化**: Image Updater App は overload-party-k8s のみインストール、Claude Sync App は sync 対象リポのみインストールで、漏洩時の被害を構造的に限定
- **insteadOf スコープと scope ミスマッチ問題の構造的解消**: App scope は overload-party-* 全リポ Read なので新規依存追加で落ちなくなる
- **死蔵 PAT の発見・除去**: #11 の死蔵 PAT が棚卸しで判明。本 ADR の作業中に revoke する
- **API rate limit の改善**: App installation token は per-installation で 15,000 req/hr (PAT は per-user で 5,000 req/hr)。複数 workflow が並行する場合や workflow 数が増えた際に PAT で頻発しがちな rate limit に当たる懸念が下がる
- **重複コードの集約**: 6 サービスリポに散在する auth セットアップ (~30+ 行) が reusable workflow 1 箇所に集約され、新リポ追加時は workflow を call するか否かの二択になる

### Negative

- **GitHub Actions の外で動くサービスは実装変更が必要**: slack-commands Cloud Run の GitHub API 呼び出しを App private key + installation token に書き換える工数が発生する (Go なら [`github.com/bradleyfalzon/ghinstallation/v2`](https://github.com/bradleyfalzon/ghinstallation) が標準的、`http.RoundTripper` 経由で installation token を透過注入できるため HTTP client 差し替えが最小で済む)。ArgoCD は設定変更のみで済むが、Secret Manager への PEM 投入と Image Updater Pod の roll が必要
- **e2e ローカル開発者の運用変更**: PAT を直書きしていた `secrets/*` ファイルを CLI スクリプト経由で再生成する手順に変わる。各開発者が一度 App private key (or 払い出された short token) を環境に設定する必要がある
- **App 数が増える**: 4 App それぞれに ID / Installation ID / private key を管理する必要がある。ただし PAT 12 種を管理する現状より総量は少ない

### 緩和策

- App 移行を Phase 分けして進める:
  - Phase 1: Common Read App (#4, #5) — 影響リポ多いが Read-only で安全。ops#18 / common#34 で並行進行
  - Phase 2: Ops Automation App の workflow 系 (#1, #2, #3, #7) — workflow 書き換えのみ
  - Phase 3: Image Updater App (#8) と Claude Sync App (#6) — Write 系で慎重に
  - Phase 4: Ops Automation App の Cloud Run 系 (#12) — slack-commands の実装変更を要するため最後
  - Phase 5: e2e ローカル (#9, #10) と死蔵 (#11) のクリーンアップ
- 各 Phase で旧 PAT を **すぐ revoke せず一定期間並走** させ、App 移行後の workflow が安定して green であることを確認してから revoke する

## 関連 issue

- [overload-party-common#34](https://github.com/kenyamaneko/overload-party-common/issues/34) — Common Read App migration
- [overload-party-common#35](https://github.com/kenyamaneko/overload-party-common/issues/35) — Claude Sync App migration
- [overload-party-ops#18](https://github.com/kenyamaneko/overload-party-ops/issues/18) — Ops Automation App migration
- [overload-party-k8s#16](https://github.com/kenyamaneko/overload-party-k8s/issues/16) — Image Updater App migration
