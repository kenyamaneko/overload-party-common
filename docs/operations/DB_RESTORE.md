# Cloud SQL の復旧手順

誤操作・データ破損・インスタンス障害から各環境の Cloud SQL を復旧する手順。日次自動バックアップと時点復旧 (PITR) を前提にする。

## 前提

- dev / stg のインスタンスが夜間停止中の場合は、infra リポの `cloudsql-activation` workflow (`action=up`) で起動してから作業する
- インスタンス名は次で確認する

```
gcloud sql instances list --project overload-party-<env>
```

## 復旧方針の決定

1. 失われた・壊れたデータと、その発生時刻を特定する (アプリのエラーログ、直近の db-migrate 実行履歴)
2. 復旧方式を選ぶ
   - **時点復旧**：破損直前の時刻へ戻したいとき。指定時刻の状態を持つ複製インスタンスを新規に作る
   - **バックアップ復元**：日次バックアップの時点まで戻ればよいとき。既存インスタンスへ上書き復元する

## 書き込みの停止

1. 対象環境のアプリからの書き込みを止める。応急操作として全 Deployment を 0 に縮退する (ArgoCD 上は OutOfSync になるが、復旧後の sync で元に戻る)

```
kubectl -n overload-party-<env> scale deployment --all --replicas=0
```

2. db-migrate が実行中でないことを確認する (ops リポの Actions 実行履歴)

## 時点復旧

1. 指定時刻の複製インスタンスを作る

```
gcloud sql instances clone <instance> <instance>-restore \
  --point-in-time <RFC 3339 形式の時刻> --project overload-party-<env>
```

2. 複製インスタンスのデータを「データの確認」の方法で確認する
3. 接続先を複製インスタンスへ切り替える。Cloud SQL Auth Proxy の接続先インスタンスは k8s リポで管理しているため、該当設定を新インスタンスへ変更する PR を作りマージして sync する
4. Terraform (infra リポ) の定義と実体がずれた状態になるため、収束後にどちらかへ寄せる: 元インスタンスへデータを戻して複製インスタンスを削除するか、Terraform の定義を新インスタンスへ合わせる

## バックアップ復元

1. 復元に使うバックアップを選ぶ

```
gcloud sql backups list --instance <instance> --project overload-party-<env>
```

2. 既存インスタンスへ上書き復元する

```
gcloud sql backups restore <backup-id> --restore-instance=<instance> --project overload-party-<env>
```

## データの確認

1. Cloud SQL Auth Proxy を経由して psql で接続し (IAM 認証)、主要テーブルの件数と直近レコードを確認する
2. スキーマが期待状態と一致することを db-migrate の `dry_run=true` 実行で確認する (差分が出なければ一致)

## サービスの再開

1. ArgoCD で対象環境の Application を sync し、縮退した replicas を元に戻す
2. `/health` の 200 と主要動線 (e2e または手動) を確認する
3. 経緯・原因・再発防止を `docs/postmortem/` に記録する
