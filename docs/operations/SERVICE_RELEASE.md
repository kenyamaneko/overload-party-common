# サービスのリリース手順

GKE 上の 9 サービス (gateway / battle / card / matchmaking / account / shop / scenario / news / support) を dev → stg → prod へ反映する手順。反映モデルは dev が `main` マージで自動反映、stg が昇格の実行で自動反映、prod が同一バージョンの手動 sync。

## 前提

- kubectl の接続先を設定済みであること

```
gcloud container clusters get-credentials keyandnotes-main --zone asia-northeast1-a --project keyandnotes-platform
```

- ArgoCD の UI への接続はポート転送で行う

```
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

- DB スキーマの変更を含むリリースは、旧バージョンのアプリが新スキーマの上でも動く形 (加算的な変更) にし、スキーマを先に適用してからアプリを反映する。適用の仕組みは ops リポの `db-migrate/README.md` を参照する

## dev への反映

1. サービスリポの PR を `main` にマージする。CI がイメージを Artifact Registry へ push し、ArgoCD Image Updater が k8s リポの dev overlay の `newTag` をマージ commit の sha へ書き換え、dev の Application が自動 sync する
2. dev のノードが停止中 (毎日 JST 2:00 に自動停止) の場合は、k8s リポの `env-lifecycle` workflow を `action=up` / `environment=dev` で実行して起動する
3. 反映されたことを確認する。`Synced` / `Healthy` であること

```
kubectl -n argocd get application dev-<service>
```

4. e2e で動作を確認する (実行方法は e2e リポの README)

```
TARGET_ENV=dev pnpm test:api
```

## stg への昇格

1. スキーマ変更を含む場合は、db-migrate を stg に適用する (ops リポの Actions → `CD: DB Migration` → `environment=stg`)
2. ops リポの Actions → `CD: Promote to stg/prod` を、対象の `service` と `bump` (バージョンの上げ幅) を指定して実行する。上げ幅の判断は共通ルール (keyandnotes-rules の principles「バージョニング」) に従う
3. workflow が dev で稼働中のビルドへ `vX.Y.Z` を発行し、stg / prod の overlay を同一バージョンに固定する。stg は自動 sync で反映される
4. stg で確認する

```
kubectl -n argocd get application stg-<service>
TARGET_ENV=stg pnpm test:api
```

## prod への反映

1. スキーマ変更を含む場合は、db-migrate を prod に適用する (`environment=prod`。`dry_run=true` で差分を確認してから本実行する)
2. ArgoCD で `prod-<service>` の差分を確認する。反映されるバージョンが stg で検証した `vX.Y.Z` と同一であること
3. `prod-<service>` を手動 sync する
4. 反映後を確認する: Application が `Synced` / `Healthy`、公開エンドポイントの `/health` が 200、Slack の `#overload-party-alerts` に発報がないこと

## 切り戻し

[ROLLBACK.md](ROLLBACK.md) に従う。
