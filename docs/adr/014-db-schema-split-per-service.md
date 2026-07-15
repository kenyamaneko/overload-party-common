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
