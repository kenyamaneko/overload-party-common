# 環境の立ち上げ手順

overload-party の環境 (dev / stg / prod) でサービスが動く状態を作るときの手順。`terraform apply` だけでは各サービスは起動しない。apply が作らないものがあり、それぞれ別の操作で入れる必要がある。

## terraform が作らないもの

| 対象 | terraform が作るもの | 別途入れるもの | 欠けると起動しないサービス |
|---|---|---|---|
| Secret Manager | シークレットの入れ物と `secretAccessor` | 値のバージョン | gateway / support / shop |
| Cloud Firestore | データベースと読み取り権限 | `game_config` コレクションの値 | account / card / shop / scenario / gateway / battle |
| Cloud SQL | インスタンスとデータベース | 起動状態 (`activation_policy`)・`postgres` のパスワード・スキーマ | データベースを使う全サービス |
| Upstash Redis | シークレットの入れ物 (upstash の state) | gateway は接続 URL、matchmaking は endpoint と password | gateway / matchmaking |

Cloud Run サービスは revision が ready になるまで作成完了とみなされないため、これらが欠けているとコンテナが起動できず `terraform apply` そのものが失敗する。「apply が通らない」と「値が入っていない」は同じ原因であることが多い。

## 実行者に要る権限

手順の大半は GitHub Actions が持つ権限で回るが、手作業の部分は実行者自身の権限で動く。対象プロジェクトに対して次が要る。

- `roles/secretmanager.secretVersionAdder` (シークレットの値の投入)
- `roles/cloudsql.admin` (インスタンスの起動停止とパスワード設定)
- `roles/run.developer` (ジョブの実行、サービスの再起動)
- Firestore の書き込み
- state バケット `keyandnotes-tf-state` の読み取り (`terraform output` を手元で打つため)

prod は `gh-db-migrator` サービスアカウントの対象外なので、prod のマイグレーションは実行者自身の権限で走る。

## 手順

apply は overload-party-infra の `terraform.yaml` を `workflow_dispatch` で実行する。`path` に対象の state root を選ぶ。Upstash の資格情報はこの workflow にしか無いため、手元では apply できない。

```
gh workflow run terraform.yaml --repo kenyamaneko/overload-party-infra \
  -f path=google-cloud/env/<env>
```

### 1. terraform apply

`path=google-cloud/env/<env>` で実行する。この時点では Cloud Run サービスの作成が失敗してよい。ネットワーク・データベース・シークレットの入れ物・サービスアカウントが揃うことが目的。

### 2. シークレットに値を投入する

terraform は値を投入しない。state と CI のログに平文が残ることを避けるため、値の投入は手作業になっている。

| シークレット | 消費サービス |
|---|---|
| `internal-auth-private-key` | gateway (署名するのは gateway だけで、下流は公開鍵で検証する) |
| `support-slack-bot-token` / `support-sendgrid-api-key` | support |
| `shop-apple-bundle-id` / `shop-apple-issuer-id` / `shop-apple-key-id` / `shop-apple-private-key` / `shop-google-package-name` | shop |
| `migration-db-password` | db-migrate ジョブ (投入は手順 5) |
| `gateway-upstash-redis-url` | gateway |
| `matchmaking-upstash-redis-endpoint` / `matchmaking-upstash-redis-password` | matchmaking |

```
gcloud secrets versions add <secret-id> --project <project-id> --data-file=<path>
```

shop の 5 つは App Store Connect と Google Play の資格情報が要る。取得手順は overload-party-shop の `docs/operations/IAP_SECRETS.md` にある。

Upstash の値は upstash 側の state が持っている。先に overload-party-infra の `terraform.yaml` を `path=upstash/env/<env>` で実行してから、その output を投入する。`terraform output` を手元で打つには state バケットへの読み取り権限と `terraform init` が要る。

```
terraform -chdir=providers/upstash/env/<env> init -input=false
terraform -chdir=providers/upstash/env/<env> output -raw gateway_redis_url \
  | gcloud secrets versions add gateway-upstash-redis-url --project <project-id> --data-file=-
```

matchmaking が読む 2 本 (`matchmaking-upstash-redis-endpoint` / `matchmaking-upstash-redis-password`) は、`upstash/env/modules/matchmaking` に output が無いため同じ方法では取れない。Upstash のコンソールから取得して投入する。

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

prod は夜間停止の対象外で、workflow でも選べない。止まっていたら直接起動する。

```
gcloud sql instances patch overload-party-db --project <project-id> --activation-policy=ALWAYS
```

`activation_policy` は terraform の `ignore_changes` に入っていて、起動と停止は運用側が所有する。terraform で状態を戻そうとしないこと。コスト保護が効かなくなる。

### 5. postgres のパスワードを揃える

マイグレーションは組み込みの `postgres` ユーザーで接続し、パスワードを `migration-db-password` から読む。terraform は `root_password` を `ignore_changes` に入れており、インスタンス側とシークレットのどちらも作らないため、両者が食い違っていることがある。

食い違っているとマイグレーションがこう落ちる。

```
pq: password authentication failed for user "postgres" (28P01)
ERROR: psqldef failed — aborting before grant_iam.sql to avoid applying grants to a partially-migrated schema.
```

**新規環境ではシークレットにバージョンが 1 本も無い。**値を作って、シークレットとインスタンスの両方に入れる。

```
openssl rand -base64 24 | tr -d '\n' > /tmp/dbpw
gcloud secrets versions add migration-db-password --project <project-id> --data-file=/tmp/dbpw
gcloud sql users set-password postgres --instance=overload-party-db \
  --project <project-id> --password="$(cat /tmp/dbpw)"
rm -f /tmp/dbpw
```

既にバージョンがあり食い違っているだけなら、インスタンス側をシークレットに合わせる。

```
gcloud sql users set-password postgres --instance=overload-party-db \
  --project <project-id> \
  --password="$(gcloud secrets versions access latest --secret=migration-db-password --project <project-id>)"
```

これでも `28P01` が消えないときは、シークレットの値に末尾改行が入っている可能性がある。ジョブはシークレットの中身をそのまま使うが、`$( )` は末尾改行を落とすため、インスタンス側だけ改行なしになる。上の「値を作る」手順でシークレットを作り直す。

`--prompt-for-password` にパイプで渡してはいけない。gcloud は `/dev/tty` を先に開くため、端末があるとパイプした値は捨てられ、手で打った値が設定される。gcloud にパスワードを標準入力から取る経路は無いので、`--password` で渡す。値がプロセス一覧に見える点は許容する。

パスワードを揃えたら、次の手順のマイグレーションが通ることで確かめる。

### 6. データベースのスキーマとマスターデータを適用する

インスタンスが起動していても、スキーマが無ければテーブルを読むサービスは起動できない。terraform が作るのは空のデータベースまで。

**`db-migrate` ジョブを直接実行してはいけない。**スキーマとマスターデータは `fetch-schemas.py` が各サービスリポから取得してイメージにビルド時に焼き込む。ジョブを再実行しても、イメージに入っている時点の SQL を流し直すだけで、各リポの最新は反映されない。

overload-party-ops の `db-migrate.yaml` を `workflow_dispatch` で実行する。イメージの再ビルドからジョブの更新、実行までを通す。

```
gh workflow run db-migrate.yaml --repo kenyamaneko/overload-party-ops \
  -f environment=<dev|stg> -f dry_run=false -f bootstrap_baseline=true
```

`bootstrap_baseline` は初回だけ `true` にする。適用済みの記録が無い環境で付けないと `EXIT_NO_BASELINE` で中断し、逆に記録がある環境で付けても中断する。2 回目以降は外す。

この workflow の `environment` は dev と stg しか選べない。prod のジョブは terraform が設定した `db-migrate:latest` を指しており、Cloud Run はこのタグを実行のたびに解決する。**dev か stg を先に回して `:latest` を押し出してから**、prod のジョブを直接実行する。

```
gcloud run jobs execute db-migrate --project <project-id> --region asia-northeast1 --wait
```

prod のこの経路は workflow が行う破壊的変更チェックと baseline の記録を通らない。スキーマに破壊的な差分があっても止まらないため、dev と stg で同じ差分を先に通しておく。

スキーマが適用されていないと card がこう落ちる。

```
card fatal
error="load card cache: query cards: ERROR: relation \"card.card_definitions\" does not exist (SQLSTATE 42P01)"
```

card が起動しないと、起動時に card を呼ぶ battle も作成できない。

### 7. card と battle を再起動する

card はカードのマスターデータを起動時に一度だけデータベースから読み、メモリに保持する。battle も起動時に card から同じデータを取ってメモリに載せる。どちらも再読み込みの経路が無いため、マスターデータを流しても動いているリビジョンは古いデータを持ち続ける。card を直してから battle を直す順で再起動する。

**この手順は対象のサービスが既に存在する環境でのみ実行する。**`gcloud run services update` は対象が無いとサービスを作ってしまい、環境変数が 1 つも設定されていないサービスが terraform の管理外に生まれる。そうなると terraform は自分の state に無いサービスを作ろうとして `Error 409: Resource 'card' already exists` で止まり、以降 apply が通らなくなる。新規環境ではまだ存在しないので、この手順は飛ばして次に進む。

先に存在を確かめる。

```
gcloud run services describe card --project <project-id> --region asia-northeast1 \
  --format="value(metadata.name)"
```

存在する場合だけ、**今動いているイメージをそのまま指定し直して**新しいリビジョンを作る。battle にも同じことをする。

```
gcloud run services update card --project <project-id> --region asia-northeast1 \
  --image "$(gcloud run services describe card --project <project-id> --region asia-northeast1 \
      --format='value(spec.template.spec.containers[0].image)')"
```

`:latest` を書いてはいけない。CI は stg で確かめた物と同じ物が prod に載るようダイジェストを固定してデプロイするため、タグを指定し直すと検証済みの版から別のビルドへ黙って載せ替わる。

新しいリビジョンが配信しているかで確かめる。

```
gcloud run revisions list --service card --project <project-id> --region asia-northeast1 \
  --format="table(metadata.name,metadata.creationTimestamp,status.conditions[0].status)"
```

反映されていないと battle がこう落ちる。カード定義に battle が知らない効果名が含まれている状態。

```
System.InvalidOperationException: Unknown custom effect: <effect-name>
```

### 8. terraform apply をやり直す

2 から 7 が揃った状態で apply すると、Cloud Run サービスが ready になり作成が完了する。

新規環境では初回の apply が battle の作成で失敗する。`iam_grants` に渡す `internal_calls` は全ての呼び出し先の `module.<svc>.service_name` を参照する 1 つの map で、これを `for_each` に使うため、**付与 1 本ごとに全サービスの作成完了を待つ**。一方 battle は起動時に card を呼ぶので、作成が完了するには先に card への `run.invoker` が要る。この循環は terraform では解けない。

回避するには、battle の作成が失敗した時点で呼び出し先の付与を手で作り、apply をやり直す。

```
gcloud run services add-iam-policy-binding card --project <project-id> --region asia-northeast1 \
  --member="serviceAccount:overload-party-battle@<project-id>.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

gateway は他の 8 サービス全ての URI を受け取るため、**1 つでも作成できないと gateway も作成されない**。同じ apply の中で gateway への付与が gateway 自身より先に走ることもあり、その場合は `Resource 'gateway' ... does not exist` で失敗する。もう一度 apply すれば通る。

シークレットが揃っていないサービスがあると、そのサービスと gateway の 2 つが作成できない。prod は shop の課金検証シークレットが未投入のため、この状態になっている (overload-party-shop#129)。

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
