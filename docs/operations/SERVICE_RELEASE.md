# サービスリポのリリースタグを打つ手順

サービスリポの `vX.Y.Z` タグを発行し、stg への反映を起動するときの手順。上げ幅 (patch / minor / major) の判断基準は共通ルール (keyandnotes-rules の principles「バージョニング」) に従う。

## 手順

1. `common/scripts/create-release-tag.sh` を対象サービスリポのルート (main の最新コミットをチェックアウトした状態) で実行する

   ```
   /path/to/overload-party-common/scripts/create-release-tag.sh <major|minor|patch>
   ```

2. スクリプトが直近の `vX.Y.Z` タグを指定した桁だけ上げ、チェックアウト中のコミットにタグを打ってプッシュする。タグが無ければ `v0.1.0` から始まる
3. プッシュされたタグが対象リポの `deploy.yaml` (`push: tags: v*.*.*`) を起動し、stg への反映が始まる

## 前提

- タグは自身の git 認証情報でプッシュする。GitHub Actions の `GITHUB_TOKEN` で打ったタグは workflow を起動しないため、CI 経由の自動発行にはしていない
- `vX.Y.Z` 以外の形式のタグ (pre-release タグ等) が直近にあると、スクリプトはエラーで止まる。誤った版を打つよりは止める方を採っている。運用に pre-release タグを混ぜる場合は採番の設計を見直す
