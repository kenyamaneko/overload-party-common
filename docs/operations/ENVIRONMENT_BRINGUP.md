# 環境の立ち上げ手順

overload-party の環境 (dev / stg / prod) でサービスが動く状態を作るときの手順。`terraform apply` だけでは各サービスは起動しない。apply が作らないものがあり、それぞれ別の操作で入れる必要がある。

## terraform が作らないもの

| 対象 | terraform が作るもの | 別途入れるもの | 欠けると起動しないサービス |
|---|---|---|---|
| Secret Manager | シークレットの入れ物と `secretAccessor` | 値のバージョン | gateway / support / shop |
| Cloud Firestore | データベースと読み取り権限 | `game_config` コレクションの値 | account / card / shop / scenario / gateway / battle |
| Cloud SQL | インスタンスとデータベース | 起動状態 (`activation_policy`)・`postgres` のパスワード・スキーマ | データベースを使う全サービス |
| Upstash Redis | シークレットの入れ物 (upstash の state) | 接続 URL の値 | gateway / matchmaking |

Cloud Run サービスは revision が ready になるまで作成完了とみなされないため、これらが欠けているとコンテナが起動できず `terraform apply` そのものが失敗する。「apply が通らない」と「値が入っていない」は同じ原因であることが多い。

## 手順

### 1. terraform apply

`providers/google-cloud/env/<env>/` で apply する。この時点では Cloud Run サービスの作成が失敗してよい。ネットワーク・データベース・シークレットの入れ物・サービスアカウントが揃うことが目的。

### 2. シークレットに値を投入する

terraform は値を投入しない。state と CI のログに平文が残ることを避けるため、値の投入は手作業になっている。

| シークレット | 消費サービス |
|---|---|
| `internal-auth-private-key` | gateway (署名するのは gateway だけで、下流は公開鍵で検証する) |
| `support-slack-bot-token` / `support-sendgrid-api-key` | support |
| `shop-apple-bundle-id` / `shop-apple-issuer-id` / `shop-apple-key-id` / `shop-apple-private-key` / `shop-google-package-name` | shop |

```
gcloud secrets versions add <secret-id> --project <project-id> --data-file=<path>
```

shop の 5 つは App Store Connect と Google Play の資格情報が要る。取得手順は overload-party-shop の `docs/operations/IAP_SECRETS.md` にある。

Upstash の接続 URL は upstash 側の state が値を持っている。先に `providers/upstash/env/<env>` を apply してから、その output を投入する。

```
terraform -chdir=providers/upstash/env/<env> output -raw gateway_redis_url \
  | gcloud secrets versions add gateway-upstash-redis-url --project <project-id> --data-file=-
```

投入済みかは版の数で確かめる。

```
gcloud secrets versions list <secret-id> --project <project-id>
```

### 3. game_config を投入する

Firestore の `game_config` コレクションに初期値の 7 キーを入れる。SSoT は本リポの `data/game_config_defaults.yaml` で、`overload-party-ops/firestore-seed/seed_game_config.py` が取得して投入する runner になっている。

```
cd overload-party-ops/firestore-seed
python3 seed_game_config.py \
    --project <project-id> \
    --source ../../overload-party-common/data/game_config_defaults.yaml
```

既存のドキュメントはスキップされるので、繰り返し実行してよい。値を入れ替えるときだけ `--overwrite` を付ける。

投入済みかは件数で確かめる。7 件揃っていればよい。

```
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://firestore.googleapis.com/v1/projects/<project-id>/databases/(default)/documents/game_config"
```

### 4. Cloud SQL を起動する

夜間の自動停止でインスタンスが `STOPPED` になっていることがある。朝の自動起動は設けていないため、使うときは人が起動する。

overload-party-infra の `cloudsql-activation.yaml` を `workflow_dispatch` で実行し、`action` に `up` を指定する。対象に選べるのは dev と stg だけ。

状態は次で確かめる。`RUNNABLE` かつ `ALWAYS` なら起動している。

```
gcloud sql instances describe overload-party-db --project <project-id> \
  --format="value(state,settings.activationPolicy)"
```

`activation_policy` は terraform の `ignore_changes` に入っていて、起動と停止は運用側が所有する。terraform で状態を戻そうとしないこと。コスト保護が効かなくなる。

### 5. postgres のパスワードを揃える

マイグレーションは組み込みの `postgres` ユーザーで接続し、パスワードを `migration-db-password` から読む。terraform は `root_password` を `ignore_changes` に入れており、インスタンス側とシークレットのどちらも作らないため、両者が食い違っていることがある。

食い違っているとマイグレーションがこう落ちる。

```
pq: password authentication failed for user "postgres" (28P01)
ERROR: psqldef failed — aborting before grant_iam.sql
```

インスタンス側をシークレットの値に合わせる。パスワードが argv に載らないよう標準入力から渡す。

```
gcloud secrets versions access latest --secret=migration-db-password --project <project-id> \
  | gcloud sql users set-password postgres --instance=overload-party-db \
      --project <project-id> --prompt-for-password
```

### 6. データベースのスキーマとマスターデータを適用する

インスタンスが起動していても、スキーマが無ければテーブルを読むサービスは起動できない。terraform が作るのは空のデータベースまで。

**`db-migrate` ジョブを直接実行してはいけない。**スキーマと seed は `fetch-schemas.py` が各サービスリポから取得してイメージにビルド時に焼き込む。ジョブを再実行しても、イメージに入っている時点の SQL を流し直すだけで、各リポの最新は反映されない。

overload-party-ops の `db-migrate.yaml` を `workflow_dispatch` で実行する。イメージの再ビルドからジョブの更新、実行までを通す。

```
gh workflow run db-migrate.yaml --repo kenyamaneko/overload-party-ops \
  -f environment=<dev|stg> -f dry_run=false
```

スキーマが適用されていないと card がこう落ちる。

```
card fatal
error="load card cache: query cards: ERROR: relation \"card.card_definitions\" does not exist (SQLSTATE 42P01)"
```

card が起動しないと、起動時に card を呼ぶ battle も作成できない。

### 7. card を再起動する

card はカードのマスターデータを起動時に一度だけデータベースから読み、メモリに保持する。再読み込みの経路は無い。seed を流しても、動いているリビジョンは古いデータを配り続ける。

同じイメージを指定し直して新しいリビジョンを作る。

```
gcloud run services update card --project <project-id> --region asia-northeast1 \
  --image asia-northeast1-docker.pkg.dev/keyandnotes-platform/overload-party/card:latest
```

反映されていないと battle がこう落ちる。カード定義に battle が知らない効果名が含まれている状態。

```
System.InvalidOperationException: Unknown custom effect: <effect-name>
```

### 8. terraform apply をやり直す

2 から 7 が揃った状態で apply すると、Cloud Run サービスが ready になり作成が完了する。

新規環境では初回の apply が battle の作成で失敗する。`iam_grants` は付与先をサービス名の文字列で指定していて参照を持たないため `depends_on` で全サービスの作成完了を待つが、battle は起動時に card を呼ぶので card への `run.invoker` を要求する。この循環は terraform では解けない。

回避するには、battle の作成が失敗した時点で呼び出し先の付与を手で作り、apply をやり直す。

```
gcloud run services add-iam-policy-binding card --project <project-id> --region asia-northeast1 \
  --member="serviceAccount:overload-party-battle@<project-id>.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

gateway は `module.battle.uri` を受け取るため、battle が作成されるまで作成されない。同じ apply の中で gateway への付与が gateway 自身より先に走ることもあり、その場合は `Resource 'gateway' ... does not exist` で失敗する。もう一度 apply すれば通る。

### 9. イメージをデプロイする

CI はイメージの差し替えだけを行い、サービスを作らない。存在しないサービスに対してデプロイすると失敗する。必ず 8 を先に通す。

## 起動しないときの切り分け

```
gcloud run services describe <service> --project <project-id> --region asia-northeast1 \
  --format="value(status.conditions)"
```

`HealthCheckContainerError` ならコンテナが起動に失敗している。原因はアプリのログに出る。

```
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="<service>"' \
  --project <project-id> --limit 20 --format=json
```

`--format=json` で読むこと。`--format="value(textPayload)"` だと構造化ログの `jsonPayload.error` が落ちて原因が消える。

サービス間の呼び出しが 403 を返し、内容が Google の HTML エラーページなら、Cloud Run の呼び出し IAM で弾かれている。呼び出し元のサービスアカウントに呼び出し先の `roles/run.invoker` があるか、呼び出し元が呼び出し先の URL を audience とする ID トークンを付けているかを確かめる。

matchmaking が `redis ping: ERR Your database has been temporarily rate-limited` で落ちるときは Upstash 側の制限で、この手順では解消しない。Upstash のコンソールで対象データベースの状態を確認する。
