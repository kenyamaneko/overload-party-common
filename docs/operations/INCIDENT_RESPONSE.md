# 障害対応の初動手順

Slack の `#overload-party-alerts` への発報、またはユーザーからの報告を受けてから、切り分けと応急対応までを行う手順。

## 状況の特定

1. 発報の表題の `[dev]` / `[stg]` / `[prod]` から環境を特定する
2. dev / stg は毎日 JST 2:00 のノード停止後、Pod が `Pending`、ArgoCD の Health が `Degraded` になる。これは停止運用による平常状態なので、稼働時間帯の発報と prod の発報だけを対応対象にする
3. 影響範囲を確認する

```
curl -sS https://<対象環境のドメイン>/health
kubectl -n overload-party-<env> get pods
kubectl -n argocd get applications
```

## ログの確認

1. 対象環境の project の Logs Explorer を開き、ログの参照範囲を `gke-logs` バケットへ切り替える
2. 対象サービスと時間帯で絞り込む

```
resource.type="k8s_container"
resource.labels.container_name="<service>"
severity>=ERROR
```

3. newsfeed は Cloud Run Jobs で動くため、Cloud Run のジョブ実行履歴とログを確認する

## 切り分けと応急対応

1. 直近のリリースと突き合わせる。発生時刻の直前に対象サービスの反映 (dev は overlay の書き換え commit、stg / prod は昇格 commit と sync) があればリリース起因を疑い、[ROLLBACK.md](ROLLBACK.md) で切り戻す
2. リリース起因でなければ依存先を切り分ける: Cloud SQL (接続エラー・接続数・CPU)、Pub/Sub、外部サービス。Cloud SQL の負荷は Cloud Monitoring のメトリクスで確認する
3. 詳細ログが必要なら、対象サービスの `LOG_LEVEL` を一時的に `DEBUG` へ変更して Pod を作り直す。調査が終わったら戻す
4. クラッシュや応答なしが単発なら、Pod の作り直しで回復を試みる

```
kubectl -n overload-party-<env> rollout restart deployment <service>
```

## 収束の確認と記録

1. `/health` の 200、Pod の `Running`、発報の収束 (Cloud Monitoring のインシデントが自動で閉じる) を確認する
2. 経緯・原因・再発防止を `docs/postmortem/` に「日付_トピック.md」で記録する
