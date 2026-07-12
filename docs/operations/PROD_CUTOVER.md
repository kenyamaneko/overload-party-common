# 本稼働切替手順

prod 環境を利用者へ公開する切替の手順。上から順に実行する。

## 前提条件

以下がすべて完了していることを確認してから着手する。

- エラーログ発報と基本アラート (Pod 異常再起動 / 5xx 率 / Cloud SQL 負荷 / 死活監視) が導入され、`#overload-party-alerts` への到達を確認済み
- Cloud SQL prod の時点復旧 (PITR) とバックアップ保持世代が明示設定済み
- Cloud SQL の Public IP が廃止され、db-migrate が Private 経路で dev に適用できることを確認済み
- NetworkPolicy によるサービス間通信の制限が prod まで適用済み
- db-migrate が prod へ実行できること (workflow の environment 選択肢と prod 用の設定)
- client のストア配布の前提 (ストア登録・署名・Firebase 本番アプリ・prod 向けビルド構成) が整備済み

## インフラの起動

1. prod ノードプールを起動する。infra リポの ops state で prod の `node_count` を 1 へ変更する PR を作り、マージ後に `terraform.yaml` の apply (ops の path) を実行する
2. Cloud SQL prod が稼働中であることを確認する

```
gcloud sql instances describe <instance> --project overload-party-prod \
  --format='value(state,settings.activationPolicy)'
```

## データの投入

1. スキーマを適用する。db-migrate を `environment=prod` / `dry_run=true` で実行して差分を確認し、問題なければ本実行する
2. Firestore の game_config を投入する (ops リポ)

```
python3 firestore-seed/seed_game_config.py --project overload-party-prod --fetch
```

3. shop の課金資格情報の prod 値が Secret Manager に投入済みであることを確認する

```
gcloud secrets versions list shop-apple-private-key --project overload-party-prod
```

## アプリの反映

1. 全 9 サービスを stg 検証済みバージョンで prod へ反映する ([SERVICE_RELEASE.md](SERVICE_RELEASE.md) の「prod への反映」をサービスごとに実行する)
2. `prod-ingress` の Application を sync し、Ingress と LB が作られることを確認する

## 公開経路の確認

1. 予約 IP の値を確認する

```
gcloud compute addresses list --global --project overload-party-prod
```

2. Cloudflare で prod 用サブドメインの A レコードを予約 IP へ向ける (Proxied モード。SSL は既存環境と同じ Flexible)
3. `https://<prod ドメイン>/health` が 200 を返すことを確認する

## 最終確認

1. prod の namespace でテスト Pod から ERROR ログを 1 件出し、`#overload-party-alerts` に届くことを確認する
2. client の検証配布ビルド (prod 接続) で、実機からログイン〜主要動線を確認する
3. 夜間停止と cost-monitor の対象が dev / stg のみで、prod が含まれないことを確認する
4. 切替後の 1 週間は、アラートの発報傾向とコスト通知を毎日確認する
