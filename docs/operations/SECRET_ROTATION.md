# シークレットのローテーション手順

運用中の資格情報を、漏えい時や定期更新で差し替える手順。保管場所ごとに差し替えの操作と反映のさせ方が異なる。どの保管場所でも「新しい資格情報を追加 → 動作確認 → 旧資格情報を失効」の順で行い、失効を先にしない。

## Secret Manager (keyandnotes-platform): ArgoCD Image Updater の GitHub App 資格情報

対象: `argocd-image-updater-github-app-id` / `argocd-image-updater-github-app-installation-id` / `argocd-image-updater-github-app-private-key`

1. GitHub App (overload-party-image-updater) の設定で private key を新規生成する
2. 新しい値を Secret Manager に追加する

```
gcloud secrets versions add argocd-image-updater-github-app-private-key \
  --project keyandnotes-platform --data-file=<pem ファイル>
```

3. CSI driver は新しい version を自動では反映しないため、Pod を作り直す

```
kubectl -n argocd rollout restart deployment argocd-image-updater
```

4. k8s リポへの書き戻し commit が成功していることをログで確認してから、GitHub 側で旧 key を削除する

```
kubectl -n argocd logs -l app.kubernetes.io/name=argocd-image-updater -f
```

## Secret Manager (overload-party 各環境): shop の課金 API 資格情報

対象: `shop-apple-key-id` / `shop-apple-issuer-id` / `shop-apple-bundle-id` / `shop-apple-private-key` / `shop-google-package-name`

1. App Store Connect で API キーを再発行し、新しい値を `gcloud secrets versions add` で対象環境の project に追加する
2. shop の Pod を作り直して新しい値を読み込ませる

```
kubectl -n overload-party-<env> rollout restart deployment shop
```

3. 購入 → 反映の動線を確認してから、旧キーを失効させる

## GitHub Actions の secrets

対象はリポジトリごとに列挙して確認する。

```
gh secret list --repo kenyamaneko/<repo>
```

主な secrets と差し替え方法:

| secret | 発行元 | 差し替え後の確認 |
|---|---|---|
| `CROSS_REPO_DEPS_APP_PRIVATE_KEY` | GitHub App (Cross-Repo Deps) の private key 再生成 | db-migrate の `dry_run=true` 実行が成功する |
| `OPS_AUTOMATION_APP_PRIVATE_KEY` | GitHub App (Ops Automation) の private key 再生成 | 昇格 workflow の実行が成功する |
| `CLOUDFLARE_DNS_API_TOKEN` / `CLOUDFLARE_CDN_API_TOKEN` | Cloudflare ダッシュボードで再発行 | infra の terraform plan が成功する |
| `UPSTASH_API_KEY` | Upstash コンソールで再発行 | infra の terraform plan が成功する |
| `SLACK_WEBHOOK_URL` | Slack App の Incoming Webhook を再発行 | 定時ジョブの通知が Slack に届く |
| `COMMON_PKG_FETCH` | GitHub の personal access token を再発行 | パッケージ取得を伴う CI が成功する |

1. 発行元で新しい資格情報を作る
2. 同じ資格情報を参照する全リポジトリの secret を `gh secret set <name> --repo kenyamaneko/<repo>` で更新する
3. 表の「差し替え後の確認」を確かめてから、発行元で旧資格情報を失効させる

## Cloud SQL の postgres ユーザーのパスワード

アプリと db-migrate は IAM 認証で接続しており postgres ユーザーのパスワードを使う経路がないため、差し替えは単独で完結する。

```
gcloud sql users set-password postgres --instance=<instance> \
  --project overload-party-<env> --prompt-for-password
```
