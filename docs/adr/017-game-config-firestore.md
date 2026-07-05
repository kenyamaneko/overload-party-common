# ADR-017: shared.game_config の Cloud Firestore 移管

## ステータス

Accepted (2026-04-13)

## 結論

サービス分割後に解決不能になった `shared` スキーマの配布問題を解消するため、`shared.game_config` を **Cloud Firestore** に移管し、PostgreSQL の `shared.game_config` テーブルおよび `shared` スキーマは廃止する。NoSQL 化によりスキーマ定義の配布問題が原理的に消え、各サービスは Firestore クライアントでキーを読むだけになる（サービス追加時の追従コストがほぼゼロ）。運営チューニングは Google Cloud コンソールから即時反映可能になり、PostgreSQL マイグレーション経由の更新フローから解放される。将来のサービス横断共有状態の置き場としても拡張できる。

## 背景・課題

`shared.game_config` はゲーム運営中に調整が必要な動的な設定値（バトル上限数、経験値、タイムバンク等）を管理するストアとして設計された。当初は PostgreSQL の `shared` スキーマとして実装していたが、ADR-011 / ADR-014 によりリポジトリ・スキーマがサービス単位に完全分割された結果、以下の問題が顕在化した：

- 各サービスのリポジトリが分割されているため、`shared` スキーマの定義 SQL をどのサービスにどう配布するかが原理的に解決できない
- テスト時（ADR-016 の Testcontainers 戦略）に common リポのスキーマ定義を各サービスから参照する仕組みを作るコストが高い
- 設定値はサービス横断で参照されるため、特定のサービスの DB に属するべきデータでもない

`shared.game_config` は KV 構造（`key TEXT PRIMARY KEY, value TEXT`）であり、リレーショナルである必要はない。

## 制約

- スキーマ定義の配布／同期が運用負荷にならないこと
- Go / C# / Python の各言語から同等に扱えること（Testcontainers の方針と整合）
- ローカル開発と CI で本物に近い動作が再現できること
- サービス横断の共有状態を将来追加する際の置き場として拡張できること

## 詳細

- コレクション設計：コレクション `game_config`、ドキュメント ID = key、フィールド `value`（型は値ごとの実型: number / string / bool）
- 各サービスは公式 Firestore クライアントから読み取る
  - Go: `cloud.google.com/go/firestore`
  - C#: `Google.Cloud.Firestore`
  - Python: `google-cloud-firestore`
- 書き込み（運営チューニング）は Google Cloud コンソール / Firestore admin SDK 経由で行う

### Firestore モード

- **Native モード**を採用する（Datastore モードではない）。リアルタイム更新・サブコレクション・SDK 機能が揃っており、将来のサービス横断共有状態の置き場としても拡張余地が大きい
- dev / stg / prod の各 Google Cloud プロジェクトで Firestore Native モードを有効化する（現時点で未有効化）
- ロケーション: `asia-northeast1`（Tokyo single-region）

### 読み取り失敗時の挙動

- キー不在は **fail-fast**（CLAUDE.md 方針準拠）。リポジトリは `port.ErrNotFound` を返し、サービス層は即座にエラーを伝播する
- 旧 PostgreSQL 実装は第 3 引数 `fallback` を取っていたが、本移行で interface を `GetInt64(ctx, key) (int64, error)` に変更し fallback を削除する

### パイロット戦略

- **account をパイロット**とする。理由: 現時点で game_config を runtime で読み取っている唯一のサービス（`PlayerService` の daily battle limit / exp formula coefficient / exp_win|loss|draw）。shop は構造体定義のみで dead code のため検証にならない
- account dev デプロイで問題無いことを確認してから、shop / battle / card / scenario / gateway に順次展開

### `shared.update_updated_at()` の扱い

`shared.update_updated_at()` トリガー関数は、現在 account / card / shop / scenario など複数サービスのテーブルが `BEFORE UPDATE` トリガーから参照している。`shared` スキーマ削除に際し、本関数は **各サービスのスキーマ内に再定義**する（例: `account.update_updated_at()`, `card.update_updated_at()` …）。各サービスの `db/schema.sql` 冒頭で関数を宣言し、トリガー側の参照名も置き換える。全サービスがスキーマ自前定義に切り替わるまで common の `db/schema_postgres.sql` を残し、最後の 1 サービスが完了した時点で common 側のファイルを削除して ops/db-migrate dependency order からも `shared` を除外する。

### IAM / 環境分離

- プロジェクト単位で Firestore を分離（dev / stg / prod）
- 各サービスのワークロード ID に `roles/datastore.user`（Firestore Native モードでも本ロールを使用）を付与
- 書き込みは運営オペレーター + ops サービスアカウントのみに限定

### ローカル開発

- `gcloud emulators firestore start --host-port=localhost:9041` でエミュレーターを起動
- `FIRESTORE_EMULATOR_HOST=localhost:9041` を環境変数で渡すと、Go / C# / Python のいずれの公式クライアントも自動的にエミュレーターに接続する。production コードに分岐は書かない（fail-fast 原則）
- Python スクリプト（`scripts/` 配下）からも同じエミュレーターに繋がるため、constants codegen 系のスクリプトも本番／ローカルでコードを変えずに済む

### テスト

- ADR-016 の Testcontainers と整合させるため、Firestore エミュレーターも CI で起動する
- テスト間のリセットはエミュレーターの REST API（`DELETE http://${FIRESTORE_EMULATOR_HOST}/emulator/v1/projects/<project>/databases/(default)/documentData`）で実施
- Firestore エミュレーター本体は Java で実装されているため、**CI runner に Java 21 以上のセットアップが必要**（GitHub Actions 標準の `actions/setup-java@v3` を利用）
  - エミュレーターを動かすランタイムとして Java が必要なだけで、Java コードを書く必要は無い
- Testcontainers のように「テストコードがコンテナを自動起動する」モデルではなく、ジョブ前段で `gcloud emulators firestore start` を立てておく構成

```yaml
# GitHub Actions ステップ例
- uses: actions/setup-java@v3
  with:
    java-version: '21'
- name: Start Firestore emulator
  run: gcloud emulators firestore start --host-port=localhost:9041 &
- name: Wait for emulator
  run: until curl -sf http://localhost:9041; do sleep 0.2; done
```

ポート 9041 を採用（8080 は他用途と衝突しやすいため回避）。ローカル/CI で他サービスと衝突しないよう全サービスで同一ポートを使う。

### トレードオフ

- 新規インフラ（Firestore）が増える。dev / stg / prod の 3 プロジェクトに有効化が必要
- CI runner に Java 21+ のセットアップステップが追加で必要（Java コード自体は不要）
- PostgreSQL（Cloud SQL）と Firestore の 2 つのデータストアを運用することになる
- Firestore は強整合性こそあるが、SQL 的な集計／JOIN は不可。`game_config` は KV のため問題にならないが、将来追加するデータの種類は注意が必要
- エミュレーターは Testcontainers のような「テストコードからの自動起動」モデルではないため、ジョブ前段での起動／待機ステップが必要
- interface 引数を変える破壊的変更（`GetInt64(ctx, key, fallback)` → `GetInt64(ctx, key)`）はサービス内部の呼び出し全てを修正する必要がある。1 サービス内で完結するので各サービス独立に進められる

## 不採用案

### common の SQL 定義を各リポジトリにコピーして持つ

却下。スキーマ変更のたびに全リポジトリ同期が必要になり、ADR-014 で排除した「サービスを跨いだ DDL 同期負荷」が再発する。

### GCS の JSON ファイルで管理する

却下。読み取りパフォーマンスが不透明で、サービス側にパース／キャッシュ層を持たせる必要がある。動的更新時のキャッシュ無効化も自前で組む必要がある。
