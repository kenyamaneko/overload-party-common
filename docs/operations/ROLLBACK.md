# 切り戻し手順

リリース後に不具合が判明したサービスを、直前のバージョンへ戻す手順。反映状態の SSoT は k8s リポの git なので、切り戻しも git の変更として行う。Application はサービス × 環境ごとに独立しているため、対象サービスだけを戻せる。

## stg / prod を戻す

1. k8s リポで、対象サービスの昇格 commit (`promote(<service>): ...`) を revert する PR を作りマージする。stg / prod の overlay の `newTag` が直前のバージョンへ戻る
2. stg は自動 sync で戻る。prod は ArgoCD で `prod-<service>` を手動 sync する
3. Application が `Synced` / `Healthy` に戻り、`/health` が 200 であることを確認する

## dev を戻す

サービスリポで原因 commit を revert する PR を `main` にマージする。以降は通常のリリースと同じ流れ (イメージ push → dev overlay の書き換え → 自動 sync) で戻る。

## DB スキーマも戻す場合

- スキーマは宣言的に管理されているため、巻き戻しも「望ましい状態の再宣言」として行う。サービスリポの `db/schema.sql` を revert し、db-migrate を対象環境に再実行する
- 列や表の削除を伴う巻き戻しは、db-migrate の安全チェックが破壊的変更として停止させる。`dry_run=true` で差分を確認し、失われるデータがないと判断できた場合のみ本実行する
- アプリだけを戻す場合は、リリースが加算的なスキーマ変更だったこと (旧アプリが現行スキーマで動くこと) を確認してから戻す

## 検証

- 対象サービスの動線を e2e (`TARGET_ENV=<env> pnpm test:api`) または手動で確認する
- Slack の `#overload-party-alerts` の発報が収束したことを確認する
