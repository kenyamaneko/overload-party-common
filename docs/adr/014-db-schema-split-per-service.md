# ADR-014: DB スキーマのサービス単位分割

## ステータス

Proposed (2026-04-10)

## 結論

アプリ側のサービス分割（ADR-011）を DB レイヤーでも強制するため、DB インスタンスは 1 つのまま維持したうえで、**PostgreSQL スキーマをサービス単位に分割する**。各サービスは自分が所有するスキーマのみに直接アクセスでき、他サービスのデータが必要な場合は所有サービスの REST API 経由で取得する。テーブルの所有が DB 権限レベルで強制されて仕様と実装の乖離が起きにくくなり、将来 DB インスタンスをサービス単位に分ける場合も変更は接続先とデータ移行だけで済む。インスタンス数は 1 のままなので固定費は据え置ける。

## 背景・課題

現在、Overload Party の全サービス（gateway / battle / 将来分割予定の account / shop / scenario / card 等）は、単一の PostgreSQL インスタンス上の単一スキーマ（`public`）を共有している。IAM 認証で各サービスアカウントにユーザーが払い出されてはいるが、`db/grant_iam.sql` の通り、いずれのユーザーも `public` スキーマ全テーブルに対して `SELECT, INSERT, UPDATE, DELETE` を持つ横並びの権限になっている。

この構成には次の問題がある。

- **責務の混在**: テーブルの所有サービスが DDL・ドキュメント上は整理されていても、DB レイヤーにはそれを強制する仕組みがない。任意のサービスが任意のテーブルを書き換えられてしまい、「誰がそのテーブルを壊しうるか」がコードを読まないと分からない
- **クロスサービスアクセスの野放し**: 本来であれば他サービスのドメインデータは所有サービスの API 経由で取得すべきだが、現状はどのサービスからでも直接 JOIN / SELECT が書けてしまう。`card_definitions` のように複数サービス（gateway と battle）が直接参照しているケースもあり、所有者が曖昧になっている
- **将来の物理分割が困難**: マイクロサービス化が進むにつれ、いずれ DB インスタンス自体もサービス単位に分けたくなる可能性がある。現状のように「誰でも他ドメインのテーブルを触っている」コードベースのままでは、物理分割の際にクエリを洗い出して書き換える大規模な改修が必要になってしまう
- **ADR-011 との歩調**: ADR-011 で Gateway を account / matchmaking / shop / scenario / card 等に分割することを決めた。リポジトリ境界をネットワークレベルで引き上げる以上、DB レイヤーの境界もそれに合わせて引き直さないと、アプリ側の分割が DB を通じて骨抜きになる

## 詳細

### 基本方針

- **1 インスタンス維持**: Cloud SQL インスタンスを複数立てるコスト（固定費・運用・バックアップ）を避けるため、物理的には単一インスタンスを継続する
- **スキーマ分離**: サービスごとに PostgreSQL スキーマを切る。スキーマ名は ADR-011 のサービス名と揃える
- **専用 DB ユーザー**: 各サービスには専用の DB ユーザー（IAM サービスアカウント）を払い出し、自スキーマにのみ `USAGE` と `SELECT/INSERT/UPDATE/DELETE` を付与する。他スキーマには一切権限を付与しない
- **書き込みは所有サービスのみ**: これまでのルール（テーブルは所有サービスのみが書く）を継続し、今回の分割で権限レベルにも強制する
- **クロスサービス read も API 経由**: 「別ドメインのデータが読みたい」という要求は、所有サービスが提供する REST API 経由で解決する。直接のクロススキーマ SELECT は権限上も設計上も許容しない
- **マッチメイキング例外**: ADR-010 / ADR-012 の通り、マッチメイキングキューは Upstash Redis に載っており、RDB にテーブルを持たない。そのため matchmaking 用のスキーマは原則作成しない（将来永続化したい項目が出てきた時点で改めて検討する）

### スキーマ配置案

ADR-011 のリポジトリ分割に揃えて、次のスキーマ構成を想定する。スキーマ名は暫定で、実装段階で最終調整する余地を残す。

| スキーマ | 所有サービス | 主な対象テーブル（現行 public からの移動） |
|---|---|---|
| `account` | account | `players`, `player_daily_battle`, `player_factions`, `user_settings` |
| `card` | card | `card_definitions`, `factions`, `player_cards`, `decks`, `deck_cards`, `cosmetic_items`, `player_items` |
| `shop` | shop | `products`, `subscriptions`, `one_time_purchases` |
| `scenario` | scenario | `scenario_episodes`, `episode_required_factions`, `player_story_progress` |
| `battle` | battle | `games`, `game_npcs`, `game_decks`, `game_players`, `game_states`, `game_actions`, `game_events`, `game_config` |
| `newsfeed` | newsfeed | `news_articles` |
| （なし） | matchmaking | キューは Redis のため DB スキーマなし |

上記はあくまで現行 `db/schema_postgres.sql` のテーブル一覧を ADR-011 の責務分担にマッピングしたものであり、いくつか検討が必要な論点がある。

- **`card_definitions` の所有者変更**: 現在は gateway（デッキバリデーション）と battle（対戦中のカード効果解決）の双方が直接参照している共有テーブルだが、本 ADR では **card スキーマの所有物** とする。battle を含む他サービスはカードマスターデータを card サービスの REST API 経由で取得する
- **battle の高頻度参照とキャッシュ**: battle は対戦中に大量のカードデータを参照するため、毎回 card サービスに API コールする構成はレイテンシ・負荷の両面で現実的ではない。battle 側でカードマスターデータをインメモリキャッシュする前提で運用する。カードマスターは更新頻度が低く、バージョン付きで配布されている（`card_data_version` を `games` に記録済み）ため、キャッシュ戦略は比較的単純に組める。これは本方針に伴うコストとして受け入れる
- **`game_config`, `cosmetic_items` 等の横断マスタ**: 所属サービスがまだ曖昧なテーブルもある。現時点では上表の通り仮置きとし、**テーブル単位の最終的な割り当ては次のステップ（移行計画の PR）で詳細設計する**。本 ADR ではスキーマ分割の方針と責務分担ルールを確定させることにスコープを限定する

### 権限設計

#### スキーマレベル GRANT

各サービスユーザーに対して、自スキーマに対してのみ権限を付与する。現状 `db/grant_iam.sql` が `public` スキーマに対して一括付与している構造を、スキーマ単位の GRANT に分割する。

```sql
-- 例: battle サービスユーザー
GRANT USAGE ON SCHEMA battle TO "overload-party-battle@<project>.iam";
GRANT SELECT, INSERT, UPDATE, DELETE
  ON ALL TABLES IN SCHEMA battle
  TO "overload-party-battle@<project>.iam";
ALTER DEFAULT PRIVILEGES IN SCHEMA battle
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES
  TO "overload-party-battle@<project>.iam";
-- 他スキーマへの GRANT は一切行わない
```

他スキーマについては `USAGE` すら付与しない。これにより、アプリ側で誤って他サービスのテーブル名を書いたクエリを実行しても DB レイヤーで拒否される。

#### IAM 認証との関係

Cloud SQL IAM 認証（`--auto-iam-authn`）自体は現行構成を維持する。`db/grant_iam.sql` は本 ADR の採用後、「スキーマごとに分割した GRANT 文を、対応する IAM ユーザーに付与する」形にリファクタする。各サービスが使う IAM サービスアカウント名自体は現行（`overload-party-<service>@<project>.iam`）を踏襲する。

#### `search_path`

各サービスの接続文字列または接続時の `SET search_path` で、自スキーマを先頭に設定する。DDL マイグレーション（ops リポジトリ、psqldef）では全スキーマを対象にできる別の管理ユーザーを用意する。

### トレードオフ

- **クロスサービス read のオーバーヘッド**: 「他ドメインのデータが読みたい」というケースは、従来の JOIN から API 呼び出しに置き換わる。レイテンシ増・失敗モード増・クライアントキャッシュの必要性が発生する
- **battle のカードマスターデータ参照**: 特に battle は対戦中に `card_definitions` を高頻度で参照するため、毎回 card サービスへ問い合わせる構成は非現実的。battle 側でカードマスターをインメモリキャッシュする必要がある。カードマスターは更新頻度が低くバージョン管理されているため、キャッシュ戦略自体は単純に組めるが、新たな実装責任として明示的にコストを受け入れる
- **マイグレーション運用の複雑化**: スキーマが増えるぶん、psqldef による差分適用・権限付与スクリプトの管理対象が増える。ops リポジトリ側でスキーマ一覧を明示的に扱うようにする
- **移行コスト**: 既存 `public` スキーマからサービス別スキーマへのテーブル移設は一度きりの大きな作業になる。テーブル単位の割り当て（特に横断マスタ）は次ステップの移行計画 PR で詳細設計する

## 不採用案

### 物理 DB 分離を即座に実施

各サービスに Cloud SQL インスタンスを立てる、あるいは同一インスタンスでも DB（`CREATE DATABASE`）レベルで分離する案。

- メリット: 分離度が最も高い。将来のスケールアウト・障害分離に対して最も強い
- 却下理由: インスタンス数に比例してコスト（最小インスタンスでも固定費が発生する）と運用負荷（バックアップ・監視・証明書・マイグレーション）が大きく増える。現時点のトラフィック・チーム規模では過剰投資。スキーマ分割で論理的な境界を引いておけば、将来インスタンス分離に進むときの差分は接続先変更＋データ移行だけで済み、アプリコードの書き換えはほぼ不要にできる

### 現状維持（単一スキーマ共有を継続）

`public` スキーマに全テーブルを置き続け、責務分担はドキュメントとコードレビューで守る案。

- メリット: 追加作業がゼロ
- 却下理由: マイクロサービス化（ADR-002 に続く ADR-011）の趣旨に反する。DB レイヤーに境界がないかぎり、クロスサービスの直接参照はいつでも発生しうる。現状すでに `card_definitions` が複数サービスから直接参照されており、放置するほど結びつきが増える

### アプリレベルの ORM 制約のみで制御

DB は単一スキーマのまま、アプリ側の ORM / リポジトリ層で「他ドメインのテーブルを触らない」ことを強制する案。

- メリット: DB 構成変更が不要
- 却下理由: 強制力が弱い。異なるリポジトリ・異なる言語（Go / C#）にまたがってコード規約だけで境界を守り続けるのは現実的ではなく、レビュー漏れや運用スクリプトからの直クエリで簡単に穴が空く。ADR-011 の却下理由と同じく「境界の強制をアプリ層に任せると守られない」という学びを踏襲する

## Amendment: 2026-04-11 スキーマ配置の最終確定

本 ADR 本体の「スキーマ配置案」には `game_config` / `cosmetic_items` / `factions` 等の横断マスタに関する placeholder を残していたが、その後の対話で**最終確定**した内容を以下に記録する。本体の配置案を読む際は、本 Amendment を上書き指示として扱うこと。

### `shared` スキーマの新設

特定サービスに属さず、全サービスが SELECT のみ行う master / config データの置き場として **`shared` スキーマ** を新設する。

- **所有サービスなし**（マイグレーション管理ユーザーのみが write 権限を持つ）
- 各サービスユーザーには自スキーマの権限に加えて **`shared` への `USAGE + SELECT` のみ** を付与する
- runtime update を想定しない read-only データの置き場であり、現時点の住人は `game_config` のみ
- 将来的に複数サービスが同一マスター（通貨レート・ゲームバランス設定など）を参照するケースが出たら追加する余地を残す

### `factions` テーブルの廃止

従来 DB に存在した陣営マスター (`factions` テーブル) は**完全に廃止**する。

- 陣営 ID の定数（`FactionSHE` / `FactionTenki` / `FactionSugar` / `FactionTuners` / `FactionNeutral`）は既に `packages/gamedata/constants/` に code-generated されている
- 表示名 (`short_name_ja` / `short_name_en` / `full_name_ja` / `full_name_en`) や `is_collectible` / `sort_order` などの metadata は、新設する `data/factions.yaml` を SSoT として `scripts/generate_constants.py` から Go / C# / TypeScript 定数および i18n リソースに一括生成する構成へ移行する
- これまで `players.selected_faction`, `products.faction_id`, `player_factions.faction`, `scenario_episodes.faction`, `episode_required_factions.faction_id` などに張られていた `factions(faction_id)` への FK 制約は**全て撤廃**する。代わりに各カラムは `VARCHAR(20) + CHECK (... IN ('SHE','Tenki','Sugar','Tuners','Neutral'))` として不正値を DB 層で拒否する
- クロススキーマ FK を避けることで、将来 Cloud SQL インスタンスをサービス単位に物理分割した際もスキーマ間の依存がなくなり、アプリ側のクエリ書き換えも不要になる
- 実装フェーズ（`data/factions.yaml` 新設、`generate_constants.py` 拡張、`schema_postgres.sql` からの `factions` テーブル削除と関連 FK の撤廃、`grant_iam.sql` 更新）は本 ADR の採用後に別ステップで進める

### スキーマ配置の最終確定版

本 ADR 本体 §スキーマ配置案の表は以下で**置き換える**。

| スキーマ | 所有サービス | 主な対象テーブル |
|---|---|---|
| `shared` | （なし: マイグレーション管理） | `game_config` |
| `account` | account | `players`, `player_daily_battle`, `player_factions`, `user_settings` |
| `card` | card | `card_definitions`, `player_cards`, `decks`, `deck_cards` |
| `shop` | shop | `products`, `subscriptions`, `one_time_purchases`, `cosmetic_items`, `player_items` |
| `scenario` | scenario | `scenario_episodes`, `episode_required_factions`, `player_story_progress` |
| `battle` | battle | `games`, `game_npcs`, `game_decks`, `game_players`, `game_states`, `game_actions`, `game_events` |
| `newsfeed` | newsfeed | `news_articles` |
| （なし） | matchmaking | キューは Upstash Redis、通知は Cloud Pub/Sub のため RDB スキーマを持たない |

主な変更点:

- **`shared` 行を追加**: `game_config` を `battle` スキーマから `shared` スキーマへ移動。シードデータとして投入され、runtime update を想定していないため
- **`cosmetic_items` / `player_items` を `card` → `shop` に移動**: コスメアイテムの購入・所持管理は shop の責務であり、`products` / `subscriptions` / `one_time_purchases` と同じスキーマに揃えるほうが自然
- **`factions` テーブルを `card` から削除**: 上述のとおり廃止
- **`game_config` を `battle` から削除**: `shared` スキーマへ移動

### 関連する設計更新

本 Amendment の確定に伴い、以下のドキュメントは既に更新済みである。

- [docs/architecture/ARCHITECTURE.md §スキーマ分割とオーナーシップ](../architecture/ARCHITECTURE.md)
- [docs/architecture/DATA_DESIGN.md スキーマ所有権マップ](../architecture/DATA_DESIGN.md)

本 ADR 本体（「スキーマ配置案」節と「`game_config`, `cosmetic_items` 等の横断マスタ」に関する注記）は歴史的経緯として残しているが、**現行の方針は本 Amendment が SSoT** となる。
