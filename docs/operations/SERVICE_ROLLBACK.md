# サービスの切り戻し手順

Cloud Run に載っているサービスを前の版へ戻すときの手順。反映するイメージは digest で固定されるので、リリースタグ・commit sha・digest・リビジョンが一対一で対応する。

以下のコマンドは全て `--region asia-northeast1` を前提にする。`<image>` は `asia-northeast1-docker.pkg.dev/keyandnotes-platform/overload-party/<service>` を指す。

## 環境ごとの戻し方

| 環境 | 反映の起点 | 戻す手段 |
|---|---|---|
| dev | main への push | リビジョンへトラフィックを戻す |
| stg | `vX.Y.Z` タグの push | リビジョンへトラフィックを戻す |
| prod | `deploy.yaml` の `workflow_dispatch` (`version` にタグを渡す) | 前のタグを渡して再実行する、またはリビジョンへトラフィックを戻す |

stg は「タグを push すると反映される」形なので、過去の版を選んで反映し直す入口が無い。リリースタグの発行 workflow は必ず新しい版を採番するため、stg を戻すときはリビジョンで戻す。

## 1. 今動いている成果物を調べる

トラフィックを受けているリビジョンを見る。

```
gcloud run services describe <service> --project <project-id> --region asia-northeast1 \
  --format="value(status.traffic)"
```

```
{'latestRevision': True, 'percent': 100, 'revisionName': 'card-00001-2t4'}
```

そのリビジョンが載せているイメージは digest で記録されている。

```
gcloud run revisions describe <revision> --project <project-id> --region asia-northeast1 \
  --format="value(spec.containers[0].image)"
```

```
asia-northeast1-docker.pkg.dev/keyandnotes-platform/overload-party/card@sha256:5ef128d4a697...
```

サービスの `spec.template` 側は terraform が作ったときの `:latest` のような可変のタグが残っていることがあるので、動いている成果物はリビジョン側で確かめる。

digest からビルド元の commit sha を引く。

```
gcloud artifacts docker images list <image> --include-tags \
  --filter="version:<digest>" --format="value(tags)"
```

```
531bbcfd5d5a4068021fce2b50edf6794e444ae7,latest
```

sha 形式のタグがビルド元の commit である。サービスリポでその commit を含むリリースタグを引くと、動いている版がわかる。

```
git -C <service-repo> tag --points-at <commit-sha>
```

## 2. 戻す先のバージョンを決める

サービスリポのリリースタグから戻す先を選ぶ。

```
git -C <service-repo> tag -l 'v*.*.*' --sort=-v:refname | head
```

そのタグが指す commit と、対応するイメージが Artifact Registry に残っているかを確かめる。

```
git -C <service-repo> rev-list -n 1 <tag>

gcloud artifacts docker images describe <image>:<commit-sha> \
  --project keyandnotes-platform --format="value(image_summary.digest)"
```

ここで出る digest が、戻したときに載る成果物である。リポジトリの保持設定は新しい 10 版までなので、古い版はイメージが消えていることがある。`Image not found.` になる版へは戻せない。

## 3. 戻す

### prod をタグの再実行で戻す

サービスリポの `deploy.yaml` を `workflow_dispatch` で実行し、`version` に 2 で決めたタグを渡す。2 で確かめた digest がそのまま載る。

### リビジョンへトラフィックを戻す

戻したいリビジョンを選ぶ。イメージの digest を出すと、どの版かを 1 の対応で確かめられる。

```
gcloud run revisions list --service <service> --project <project-id> --region asia-northeast1 \
  --format="table(metadata.name,spec.containers[0].image)"
```

```
gcloud run services update-traffic <service> --project <project-id> --region asia-northeast1 \
  --to-revisions=<revision>=100
```

リビジョン名を指定してトラフィックを寄せると、その後のデプロイで新しいリビジョンができてもトラフィックは移らない。原因を直した版を反映する前に、トラフィックを最新へ戻す。

```
gcloud run services update-traffic <service> --project <project-id> --region asia-northeast1 \
  --to-latest
```

## 4. 戻ったことを確認する

1 と同じ 2 つのコマンドで、トラフィックを受けているリビジョンと、そのリビジョンの digest が戻す先のものになっていることを確かめる。digest が 2 で確かめた値と一致すれば、意図した成果物が載っている。

サービスが応答することも確かめる。

```
gcloud run services describe <service> --project <project-id> --region asia-northeast1 \
  --format="value(status.conditions)"
```

`Ready` が `True` にならないときは、コンテナが起動していない。切り分けは [ENVIRONMENT_BRINGUP.md](ENVIRONMENT_BRINGUP.md) の「起動しないときの切り分け」に従う。
