# ADR-028: E2E / クロスサービス統合テストの戦略

- 状態: Accepted
- 決定日: 2026-04-26
- 関連 ADR: ADR-011（リポジトリ分割）、ADR-012（matchmaking Pub/Sub）、ADR-015（パッケージ分割）、ADR-024（サービス内統合テスト）、ADR-027（gateway Pub/Sub fan-out 削除）

## コンテキスト

ADR-024 で各サービスは `integration` build tag による自リポジトリ内統合テスト、`cloud_integration` tag による stg 向けスモークを持つ。これらはサービス境界の正しさを担保するが、複数サービスを跨ぐ業務シナリオ（例: ショップ購入 → account へ伝播）や、gateway の WS 終端を通したマッチメイキング → battle のライフサイクルを検証できない。

サービス数は phase 1 で gateway / account / matchmaking / shop / scenario / card / battle の 7 つ。client UI は未完成、battle のロジックは不安定だがエンドポイントは整備済み。

## 決定事項

新規リポジトリ `overload-party-e2e` を作成し、以下の方針でクロスサービス統合 E2E を運用する。

### 1. 入口は gateway のみ
全テストは gateway の REST `/api/v1/*` または WS `/ws` を経由する。サービスを直接叩くテストは禁止。これらは各サービスリポジトリ内の integration test の責務に閉じる。

**根拠:** クライアントが踏むのと同じコードパス（Firebase 認証、PlayerResolve、WS 終端、Pub/Sub fan-out）を経由しない検証は、本番でしか出ないバグを取りこぼす。

### 2. 言語 / ランナー: TypeScript + Playwright Test
- API E2E と将来の UI E2E を同一ランナーで運用するため `@playwright/test` を採用。
- TypeScript strict mode 必須、`noUncheckedIndexedAccess` 有効。
- 将来 client が完成したら `tests/ui/` に Playwright ブラウザテストを追加する。phase 1 では構造のみ用意。

### 3. 型のソースは `@kenyamaneko/overload-party-api-gateway` 1 本
gateway の REST/WS 契約は `overload-party-gateway/packages/api-gateway-npm` が SSoT として TS 公開している。e2e リポジトリはこのパッケージのみを依存にする。各サービス内部のメッセージ型（shop の Pub/Sub event 型など）は import しない（gateway を介さないため不要）。

**根拠:** ADR-015 で「メッセージ型は送信側サービスが所有」と決めた結果、TS 用に統合された messaging パッケージは存在しない。e2e は gateway 越しの観測点のみ持てばよく、内部 event 型を二重定義する動機はない。

### 4. 検証は3層
1. **レスポンス検証**: HTTP ステータス・主要フィールド形状
2. **同期的副作用**: 別の gateway エンドポイントを叩いて状態を観測（例: 購入後に `/api/v1/shop/products` の `is_owned` を確認）
3. **非同期副作用**: gateway-observable な状態を eventual consistency で polling（例: 購入後に `/api/v1/player/cards` でカード付与を確認）

Pub/Sub への直接購読 fixture は採用しない。gateway を素通りするとテスト境界が崩れる。

### 5. 認証戦略: 環境ごとに切り替え
- **local**: gateway の dev mode を利用し `dev-token-{uid}` を発行（Firebase 不要）
- **stg**: Firebase Admin SDK で custom token を発行 → Firebase Auth REST `accounts:signInWithCustomToken` で ID token に交換
- **prod-smoke**: 認証なしの public REST のみ（`/health` 等）

stg では `overload-party-stg` Firebase project をテストにも流用する（専用 test project は持たない）。テストアカウントは `e2e-{timestamp}-{scope}-{rand}` プレフィックス UID で識別し、ログ/監視で本番ユーザーと区別できる。Firebase Auth コンソールでの事前アカウント作成は**不要** — custom token の uid に対して初回サインイン時に自動作成される。

#### 認証戦略: ADC + Service Account Impersonation（SA キー不発行）
Firebase Admin SDK の認証は **Application Default Credentials + サービスアカウントのインパーソネーション** で行う。SA の JSON キーは発行・配布・保管しない。

実装上のポイント: Admin SDK は `initializeApp({ projectId, serviceAccountId })` で初期化する。`serviceAccountId` を渡すことで、SDK は `createCustomToken` 呼び出し時に `iamcredentials.signBlob` を target SA に対して呼ぶ動作モードに入る。`gcloud config set auth/impersonate_service_account` は **gcloud CLI 専用**で Node.js の `google-auth-library` には効かないため、コードに明示する必要がある。

開発者は一度だけ:
```
gcloud auth application-default login
```
ADC は developer の user account のままで OK。Admin SDK 側のコードが `serviceAccountId` で impersonation 対象を指定する。developer の user account に `roles/iam.serviceAccountTokenCreator` が付与されていれば `signBlob` が成功する。

#### シークレット管理: GCP Secret Manager
custom token を ID token に交換するための Firebase Web API key だけは Secret Manager に保管する。

| シークレット名 | 内容 |
|---|---|
| `e2e-firebase-test-api-key` | Firebase Web API key（`signInWithCustomToken` REST 呼び出し用） |

開発者は `source scripts/load-secrets.sh {dev|stg}` で `gcloud secrets versions access` 経由で取得する。

サービスアカウント `e2e-test-runner`、Secret Manager のシークレット枠、IAM 設定（開発者への `roles/iam.serviceAccountTokenCreator` と `roles/secretmanager.secretAccessor`）は **`overload-party-infra` リポの Terraform で管理**。e2e リポは consume するだけ。

**根拠:** SA キーは漏洩リスクが永続的(失効するまで使える)・ローテーションが手間。ADC + impersonation なら鍵そのものが存在せず、IAM の付与/剥奪だけでアクセス制御できる。Web API key はシークレットとはいえ Firebase クライアントが普通に使う公開可能性のあるキーなので、漏洩リスクの絶対値が低い。

### 6. ローカル実行環境: e2e 所有の docker-compose
`overload-party-e2e/docker/docker-compose.yml` で 7 サービス + Postgres + Pub/Sub emulator + Firestore emulator + Redis を起動する。各サービスのイメージは sibling リポジトリの `Dockerfile` を `build:` で指定。Go private modules 取得用の PAT は `secrets/` に配置（`.gitignore` 済み）。

**根拠:** infra リポジトリは本番デプロイ向けの k8s overlay を持つ。テスト目的の compose をそこに混ぜると責務が混線する。

### 7. テストデータ
- 全テストデータは gateway の REST/WS 経由で作成（DB 直書きは最終手段）
- UID/デッキ名等は `e2e-{timestamp}-{scope}-{rand}` プレフィックスで一意化
- 既存 ADR-024 の seed API パターンは個別サービスの責務として使い分けるが、e2e からは触らない

### 8. 実行モデル: 自動 CI なし、手動実行のみ

dev / stg はコスト削減のため普段停止している。テスト実行の前に環境を起こす必要があり、これは人間のオペレーション。したがって **自動 CI（cron / push trigger）は採用しない**。

- ローカル: `pnpm compose:up && pnpm test:api`（local target、エミュレータ）
- dev: `source scripts/load-secrets.sh dev && pnpm test:api`
- stg: `source scripts/load-secrets.sh stg && pnpm test:api`

GitHub Actions ワークフローは置かない。将来手動 dispatch が必要になった時点で `workflow_dispatch` ジョブを足す。

## 結果

- ✅ クロスサービス業務シナリオを必要時に検証できる
- ✅ クライアント完成前から battle 含む WS ライフサイクルを capture できる
- ✅ 型安全。手書き request/response 型を持たない
- ✅ 自動 CI が無いため dev/stg の停止運用と整合する
- ⚠️ dev/stg を共有環境として使うため、テストデータが残留する。プレフィックス + 手動/定期 cleanup は follow up

## 代替案

- **自動 cron による夜間 stg 実行**: 却下。dev/stg 停止運用と矛盾する。
- **直接 Pub/Sub を購読する subscriber fixture**: 却下。gateway を介さないと「客が見える状態」を検証していない。
- **`overload-party-infra` に compose を置く**: 却下。infra は本番向けの責務に閉じ、テスト用 compose は e2e で完結させる。
- **Go で書く（各サービスと同じ言語）**: 却下。UI E2E（Playwright）と同じランナーで継続するため TS。
- **各サービスの内部 event 型を再公開する**: 却下。gateway 観測点で十分。ADR-015 の方針も維持。

## Phase 2 スコープ

- `tests/ui/` に Playwright ブラウザテスト（client が安定したら）
- 残留テストデータの cleanup 運用
- 必要になれば手動 dispatch CI ジョブを追加
