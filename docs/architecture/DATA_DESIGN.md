# Overload Party - データ設計 (Data Architecture)

> **完全なスキーマ定義:** `db/schema_postgres.sql` を参照。以下は各テーブルの設計意図とカラム仕様の概要。

## ID 設計方針

`player_id` をはじめとするユーザー関連の主キーには UUID（`gen_random_uuid()`）を採用している。連番 ID ではなく UUID を使う理由は、通信を傍受された場合に ID の値からゲーム数やユーザー数を推測されることを防ぐため。

---

## スキーマ分割方針 (Service-owned Schemas)

Overload Party の RDB は **1 つの PostgreSQL インスタンスの上で、サービスごとに PostgreSQL スキーマを分離配置する** 構成を採る。物理インスタンスを分けずに論理境界だけを引く狙いは、Cloud SQL インスタンスを増やすコスト（固定費・運用・バックアップ）を避けつつ、将来的に物理 DB 分割へ進む際にアプリコードの書き換えが不要な状態を今から作っておくことにある。

基本ルールは次のとおり。

- 各サービスには専用の DB ユーザー（IAM サービスアカウント）が払い出され、**自分のスキーマに対してのみ** `USAGE` と CRUD 権限を持つ。他サービスのスキーマには一切の権限（`USAGE` すら）を持たない
- **書き込みは所有サービスのみ** が行う。このルールは DB 権限レベルで強制される
- **クロスサービスの read は所有サービスの REST API 経由** で行う。別ドメインのテーブルを直接 `SELECT` / `JOIN` することは権限上も設計上も許容しない
- スキーマ名は所有サービス名（account / card / shop / scenario / battle / newsfeed など）と揃える

### データストア配置

サービス別スキーマ以外に、特定サービスが使うデータストアが存在する。以下が Overload Party の全データ配置。

| ストア | 用途 | 利用サービス |
|---|---|---|
| PostgreSQL (Cloud SQL) | サービス別スキーマによる永続化（本ドキュメントの対象） | 各サービス |
| Upstash Redis (Sorted Set) | マッチメイキングキューの永続化。`matchmaking:queue` に `ZADD`/`ZPOPMIN` で FIFO 管理 | matchmaking |
| Google Cloud Pub/Sub (Exactly-Once Delivery) | マッチ成立イベントの非同期通知チャネル（matchmaking → gateway）。トピック `matchmaking-events` / サブスクリプション `matchmaking-events-gateway` | matchmaking (publisher), gateway (subscriber) |
| Google Cloud Pub/Sub (At-Least-Once Delivery) | shop → account のサブスクリプション状態伝搬（Outbox + Pub/Sub パターン）。トピック `subscription-events` / サブスクリプション `subscription-events-account` | shop (publisher via outbox), account (subscriber) |
| Google Cloud Pub/Sub (At-Least-Once Delivery) | カード定義キャッシュの invalidation 通知（ペイロードは invalidation signal のみ）。トピック `card-definitions-updated` | card (publisher), battle (subscriber) |

matchmaking サービスはキュー状態を Upstash Redis、マッチ成立通知を Cloud Pub/Sub に載せているため、**RDB 上に専用スキーマを持たない**。将来永続化したい項目が出てきた時点で改めて検討する。

shop → account の整合性は Transactional Outbox パターンで担保されている。shop サービスはサブスクリプション購入・更新・失効などの処理時に、`subscriptions` テーブルと `subscription_outbox` テーブルを**同一トランザクション**で書き込み、別プロセスの publisher loop が `subscription_outbox` の未送信行を読み取って `subscription-events` トピックへ publish する。account 側は `subscription-events-account` サブスクリプションでメッセージを受信し、`players.is_premium` / `premium_expires_at` を natural idempotency（同じ状態への再適用は no-op）を用いて更新する。Pub/Sub の at-least-once 配信による重複配送や順序逆転に対しても integrity を保つ設計であり、詳細は [internal/shop.md](internal/shop.md) および [internal/account.md](internal/account.md) を参照。

### スキーマ所有権マップ

各テーブルのスキーマ配置は以下のとおり (ADR-014 に従い実装済み)。

| スキーマ | 所有サービス | 主な対象テーブル |
|---|---|---|
| `shared` | （なし: マイグレーション管理） | `game_config` |
| `account` | account | `players`, `player_daily_battle`, `player_factions`, `user_settings` |
| `card` | card | `card_definitions`, `player_cards`, `decks`, `deck_cards` |
| `shop` | shop | `products`, `subscriptions`, `one_time_purchases`, `cosmetic_items`, `player_items` |
| `scenario` | scenario | `scenario_episodes`, `episode_required_factions`, `player_story_progress` |
| `battle` | battle | `games`, `game_npcs`, `game_decks`, `game_players`, `game_states`, `game_actions`, `game_events` |
| `newsfeed` | newsfeed | `news_articles` |
| （なし） | matchmaking | キューは Upstash Redis、通知は Cloud Pub/Sub のため RDB スキーマなし |

**補足**: Transactional Outbox パターンで使う `subscription_outbox` テーブル (shop → account) は設計上 `shop` スキーマに配置する予定だが、shop サービス実装時 (ADR-015 Phase 6) に schema_postgres.sql へ追加する。現時点では未定義。

#### `shared` スキーマの位置付け

特定サービスに属さず、全サービスが SELECT だけする master / config データの置き場として `shared` スキーマを用意する。

- 所有サービスは存在しない。write 権限は **マイグレーション管理ユーザー**（`db/schema_postgres.sql` に対する DDL 適用、および `db/seed/` 以下のシードデータ投入を行う専用アカウント）にのみ付与する
- 各サービスユーザーには `USAGE + SELECT` のみを与え、`INSERT/UPDATE/DELETE` は付与しない
- runtime update を想定しない read-only データの置き場であり、現時点の住人は `game_config` のみ
- 将来的に複数サービスが同一マスター（たとえば通貨レートやゲームバランス設定など）を参照するケースが出たときに追加する余地を残す

#### `factions` テーブルの廃止 (実施済み)

従来 DB に存在した陣営マスター (`factions` テーブル) は完全に廃止し、陣営は constants として code generation 経由で配布する方式に一本化済み。

- ID の定数は `packages/gamedata/constants/game_design/` に `FactionSHE` / `FactionTenki` / `FactionSugar` / `FactionTuners` / `FactionNeutral` および `SelectableFactions` リストとして code-generated されている
- 表示名（`short_name_ja` / `short_name_en` / `full_name_ja` / `full_name_en`）、`is_collectible`、`sort_order` といった metadata は `data/factions.yaml` を SSoT として `scripts/generate_constants.py` から Go / C# / TypeScript 定数および `FactionMetadata` 構造体に一括生成される
- `players.selected_faction`, `products.faction_id`, `player_factions.faction`, `scenario_episodes.faction`, `episode_required_factions.faction_id` などに張られていた `factions(faction_id)` への FK 制約は全て撤廃済み。代わりに各カラムは `VARCHAR(20)` + `CHECK (<col> IN ('SHE','Tenki','Sugar','Tuners','Neutral'))` で不正値を DB 層で拒否する
- クロススキーマ FK を避けることで、将来 Cloud SQL インスタンスをサービス単位に物理分割した際もスキーマ間の依存がなく、アプリ側のクエリ書き換えも不要

### 権限 (GRANT) の方針

IAM 認証の権限付与 SQL は [`db/grant_iam.sql`](../../db/grant_iam.sql) が SSoT。各サービスユーザーは自スキーマに対してのみ `GRANT USAGE ON SCHEMA <schema>` と必要な CRUD 権限（`SELECT, INSERT, UPDATE, DELETE`）を付与され、他スキーマには `USAGE` すら付与されない。

- Cloud SQL IAM 認証 (`--auto-iam-authn`) 自体は現行構成を維持する
- 各サービスが使う IAM サービスアカウント名は現行（`overload-party-<service>@<project>.iam`）を踏襲する
- DDL マイグレーション用には、全スキーマを対象にできる別の管理ユーザーを用意する
- 具体的な GRANT 文は [`db/grant_iam.sql`](../../db/grant_iam.sql) を参照。本ドキュメントでは SSoT 重複を避けるため SQL は転記しない

---

## 目次

1. [ゲーム管理](#1-ゲーム管理-game-management)
2. [ゲーム状態管理](#2-ゲーム状態管理-game-state-management)
3. [ゲームイベント・アクション管理](#3-ゲームイベントアクション管理-game-event--action-management)
4. [プレイヤー管理](#4-プレイヤー管理-player-management)
5. [カード定義マスター](#5-カード定義マスター-card-definitions)
6. [カード・デッキ管理](#6-カードデッキ管理-card--deck-management)
7. [ショップ・設定管理](#7-ショップ設定管理-shop--settings)
8. [コスメティクス管理](#8-コスメティクス管理-cosmetics)
9. [陣営所持管理](#9-陣営所持管理-player-factions)
10. [ストーリー管理](#10-ストーリー管理-story-scenarios)

---

## 1. ゲーム管理 (Game Management)

ゲームのライフサイクルを管理する基盤テーブル。

### 1.1 PostgreSQL スキーマ (games)

**Games** (ゲームマスター)
- **Primary Key:** `game_id`

<!-- BEGIN GENERATED: games -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | VARCHAR(26) | No | ULID |
| `status` | VARCHAR(20) | No | 'waiting' / 'playing' / 'finished' |
| `first_player` | SMALLINT | No | 先攻プレイヤー番号 (1 or 2) |
| `winning_player_num` | SMALLINT | Yes | NULL=進行中, 0=引分, 1=P1勝, 2=P2勝 |
| `win_reason` | TEXT | Yes | 'budget_zero', 'turn_timeout' 等 |
| `engine_version` | TEXT | No | バトルエンジンバージョン（ゲーム作成時に記録） |
| `card_data_version` | TEXT | No | カードデータバージョン（ゲーム作成時に記録） |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |
| `finished_at` | TIMESTAMPTZ | Yes | 終了日時 |
<!-- END GENERATED: games -->

### 1.2 PostgreSQL スキーマ (game_npcs)

**GameNpcs** (NPC 設定、NPC 戦のみ。PvP では行なし。Battle が書き込む)
- **Primary Key:** `game_id`, `player_num`
- **Foreign Key:** `game_id REFERENCES games(game_id)`

<!-- BEGIN GENERATED: game_npcs -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | VARCHAR(26) | No | 親テーブル参照 |
| `player_num` | SMALLINT | No | NPC が座っているスロット番号 (1 or 2) |
| `npc_model` | VARCHAR | No | NPC モデル名 |
<!-- END GENERATED: game_npcs -->

### 1.3 PostgreSQL スキーマ (game_decks)

**GameDecks** (デッキスナップショット、常に 2 行。Battle が書き込む)
- **Primary Key:** `game_id`, `player_num`
- **Foreign Key:** `game_id REFERENCES games(game_id)`

<!-- BEGIN GENERATED: game_decks -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | VARCHAR(26) | No | 親テーブル参照 |
| `player_num` | SMALLINT | No | 1 or 2 |
| `deck_snapshot` | JSONB | No | デッキスナップショット |
<!-- END GENERATED: game_decks -->

### 1.4 PostgreSQL スキーマ (game_players)

**GamePlayers** (プレイヤー ID マッピング、人間スロットのみ。Gateway が書き込む)
- **Primary Key:** `game_id`, `player_num`
- **Foreign Key:** `game_id REFERENCES games(game_id)`
- **Index:** `idx_game_players_player_id` ON `game_players(player_id)`

<!-- BEGIN GENERATED: game_players -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | VARCHAR(26) | No | 親テーブル参照 |
| `player_num` | SMALLINT | No | 人間が座っているスロット番号 (1 or 2) |
| `player_id` | UUID | No | プレイヤー ID (cross-schema reference to account.players; app-level integrity, not enforced by FK) |
| `exp_awarded` | BOOLEAN | No | 経験値付与済みフラグ（二重付与防止） |
<!-- END GENERATED: game_players -->

### 1.5 JSONスキーマ (Deck Snapshot)

`game_decks` テーブルの `deck_snapshot` カラムに格納されるデッキ情報。

| フィールド | 型 | 説明 |
|---|---|---|
| `deckId` | string | 元になったデッキID |
| `cards` | Array[object] | デッキに含まれるカードのリスト（`cardId` を持つオブジェクト配列、順序はシャッフル前） |

### 1.6 関連インデックス

- `GamesByStatus`: `Games(status, created_at DESC)`

### 1.7 書き込み責務

| テーブル | 書き込み責務 | 内容 |
|---------|------------|------|
| `games` | Battle | セッション（状態・結果・先攻・バージョン） |
| `game_npcs` | Battle | NPC 設定（NPC 戦のみ） |
| `game_decks` | Battle | デッキスナップショット（常に 2 行） |
| `game_players` | Gateway | プレイヤー ID マッピング（人間スロットのみ） |

---

## 2. ゲーム状態管理 (Game State Management)

対戦中のリアルタイムな状態を管理する構造。

### 2.1 PostgreSQL スキーマ (game_states)

**GameStates** (ゲーム状態・頻繁に更新)
- **Primary Key:** `game_id`
- **Foreign Key:** `game_id REFERENCES games(game_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: game_states -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | VARCHAR(26) | No | 親テーブル参照 |
| `initial_state` | JSONB | No | ゲーム開始時の初期状態スナップショット（作成後は上書きされない） |
| `version` | BIGINT | No | 楽観的ロック用バージョン |
| `current_turn` | BIGINT | No | 現在ターン数 |
| `current_phase` | VARCHAR(20) | No | 'draw' / 'main' / 'battle' / 'end' |
| `active_player` | BIGINT | No | 現在のターンプレイヤー (1 or 2) |
| `player1_budget` | BIGINT | No | Player 1 Budget |
| `player1_insight_pool` | BIGINT | No | Player 1 Insight Pool |
| `player1_field` | JSONB | No | Player 1 フィールド上のカード |
| `player1_hand` | JSONB | No | Player 1 手札 |
| `player1_repository` | JSONB | No | Player 1 リポジトリ（山札） |
| `player1_trash` | JSONB | No | Player 1 トラッシュ |
| `player1_time_bank` | BIGINT | No | Player 1 残り時間 |
| `player2_budget` | BIGINT | No | Player 2 Budget |
| `player2_insight_pool` | BIGINT | No | Player 2 Insight Pool |
| `player2_field` | JSONB | No | Player 2 フィールド上のカード |
| `player2_hand` | JSONB | No | Player 2 手札 |
| `player2_repository` | JSONB | No | Player 2 リポジトリ（山札） |
| `player2_trash` | JSONB | No | Player 2 トラッシュ |
| `player2_time_bank` | BIGINT | No | Player 2 残り時間 |
| `chain_stack` | JSONB | Yes | 現在積まれているチェーンスタック |
| `current_action_timer` | BIGINT | Yes | アクションタイマー |
| `next_instance_seq` | BIGINT | No | インスタンスID発番用シーケンス |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |
<!-- END GENERATED: game_states -->

### 2.2 JSONスキーマ (State Details)

`GameStates` テーブルの JSON カラムに格納される詳細データ構造。

**フィールド状態 (`GameStates.player1_field / player2_field`)**

**フィールド全体レイアウト:** (JSON Root)

| フィールド | 型 | 説明 |
|---|---|---|
| `frontend` | Array[3] | フロントエンドエリアのリソーススロット。固定長3。空きは `null`。<br>要素型: **Resource Object** |
| `backend` | Array[3] | バックエンドエリアのリソーススロット。固定長3。空きは `null`。<br>要素型: **Resource Object** |
| `support` | Array[3] | サポートゾーンのスロット。固定長3。空きは `null`。<br>要素型: **Support Object** |

**フロントエンド・バックエンドリソースのフィールド (Resource Object):**

| フィールド | 型 | 説明 |
|--------|-----|------|
| `instanceId` | string | フィールド上のインスタンス固有ID |
| `cardId` | string | カード定義ID |
| `artNo` | int | アート番号 |
| `faceDown` | bool | 裏向きか否か |
| `rank` | string | `"small"` / `"medium"` / `"large"` |
| `instanceFamily` | string等 | `"M"` / `"C"` / `"R"` / null |
| `currentAV` | int | 現在耐久値 |
| `maxAV` | int | AV最大値 |
| `currentTP` | int? | 現在TP（DB系およびオブジェクトストレージは null） |
| `maxTP` | int? | TP最大値（DB系およびオブジェクトストレージは null。Elastic カードは `nil`＝上限なし） |
| `currentYield` | int? | 現在Yield量（コンピュート系リソースは null） |
| `maxYield` | int? | Yield最大値（コンピュート系リソースは null。Elastic カードは `nil`＝上限なし） |
| `damage` | int | 蓄積ダメージ量 |
| `temporaryEffects` | array | 一時効果リスト |
| `monetizedAmount` | int | このターンに収益化済みのTP量（ターン終了時リセット） |
| `hasAttacked` | bool | そのターン攻撃済みか |

**一時効果のオブジェクト構造 (`temporaryEffects` 配列内):**

| フィールド | 型 | 説明 |
|---|---|---|
| `effectType` | string | 効果種別 (`buff_tp`, `mod_av`, `disable_atk` 等) |
| `value` | int | 変動値（加減算） |
| `duration` | string | 持続期間 (`this_turn`, `until_next_turn_end`, `until_next_own_turn_end`) |
| `sourceId` | string | 発生源のカード/インスタンスID |

**サポートゾーンカードのフィールド (Support Object):**

| フィールド | 型 | 説明 |
|--------|-----|------|
| `instanceId` | string | インスタンス固有ID |
| `cardId` | string | カード定義ID |
| `artNo` | int | アート番号 |
| `faceDown` | bool | 裏向きか否か |
| `targetInstanceId` | string? | アタッチメントの場合、対象リソースの instanceId。プラットフォーム・リアクティブは `null` |

**チェーンスタック (`GameStates.chain_stack`)**

| フィールド | 型 | 説明 |
|--------|-----|------|
| `chainLevel` | int | チェーンの深さ（1から始まる） |
| `actionType` | string | `"attack"` / `"component_effect"` / `"reactive"` |
| `sourcePlayerId` | string | 発動プレイヤーID |
| `sourceInstanceId` | string | 発動リソースのinstanceId |
| `targetInstanceId` | string | 対象となるリソースのinstanceId |
| `targetChainLevel` | int | 対象チェーンのレベル |
| `effectData` | object | 発動する効果のパラメータ（変動値、対象種別など） |
| `resolved` | bool | 解決済みか否か |

---

## 3. ゲームイベント・アクション管理 (Game Event & Action Management)

リプレイや監査のためのログデータ。

### 3.1 PostgreSQL スキーマ (game_events)

**GameEvents** (イベントログ・リプレイ用)
- **Primary Key:** `game_id`, `sequence_number`
- **Foreign Key:** `game_id REFERENCES games(game_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: game_events -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | VARCHAR(26) | No | 親テーブル参照 |
| `sequence_number` | BIGINT | No | イベント連番 |
| `event_type` | VARCHAR(50) | No | イベント種別 |
| `player_num` | SMALLINT | Yes | NULL=system event, 1 or 2=プレイヤーイベント |
| `event_data` | JSONB | No | イベント詳細データ |
| `created_at` | TIMESTAMPTZ | No | 発生日時 |
<!-- END GENERATED: game_events -->

**イベントデータの例:**
- `attack`: `{ "sourceId": "...", "targetId": "...", "damage": 500 }`
- `deploy`: `{ "cardId": "...", "position": 0, "cost": 300 }`

### 3.2 PostgreSQL スキーマ (game_actions)

**GameActions** (プレイヤーアクション入力ログ・追記専用)
- **Primary Key:** `game_id`, `seq`
- **Foreign Key:** `game_id REFERENCES games(game_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: game_actions -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | VARCHAR(26) | No | 親テーブル参照 |
| `seq` | INT | No | アクション連番 |
| `player_num` | SMALLINT | No | アクション実行プレイヤー番号 (1 or 2) |
| `action_type` | TEXT | No | アクション種別（play_card, attack, scale_up 等） |
| `action_data` | JSONB | No | アクションの入力データ |
| `created_at` | TIMESTAMPTZ | No | 記録日時 |
<!-- END GENERATED: game_actions -->

> **設計意図:** `game_events` がサーバー側で生成されるイベントログであるのに対し、`game_actions` はプレイヤーの入力をそのまま記録する追記専用テーブル。`initial_state` + `game_actions` を順に再生することでゲームを再現できる。

---

## 4. プレイヤー管理 (Player Management)

ユーザーアカウントと基本情報。

### 4.1 PostgreSQL スキーマ (players & player_daily_battle)

**Players** (プレイヤーマスター)
- **Primary Key:** `player_id`

<!-- BEGIN GENERATED: players -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | UUID |
| `firebase_uid` | VARCHAR(128) | No | Firebase Auth UID (Unique) |
| `username` | VARCHAR(50) | No | 表示名 |
| `level` | BIGINT | No | レベル (Default: 1) |
| `exp` | BIGINT | No | 経験値 (Default: 0) |
| `is_premium` | BOOLEAN | No | 課金ステータス |
| `equipped_icon_no` | BIGINT | Yes | 装備中アイコン番号（NULL: デフォルト） |
| `selected_faction` | VARCHAR(20) | Yes | 選択済みファクション |
| `premium_expires_at` | TIMESTAMPTZ | Yes | サブスク有効期限 |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |
<!-- END GENERATED: players -->

**player_daily_battle** (デイリーバトル管理)
- **Primary Key:** `player_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: player_daily_battle -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `daily_battle_count` | BIGINT | No | 本日のバトル回数 |
| `last_reset_date` | DATE | No | 最終リセット日 |
<!-- END GENERATED: player_daily_battle -->

### 4.2 関連インデックス

- `PlayersByFirebaseUID`: `Players(firebase_uid)` (UNIQUE)

---

## 5. カード定義マスター (Card Definitions)

カードのステータス・効果テキスト・コスト等の定義データ。`CARDS.md` の内容をDB上で管理する。

> **所有サービス:** `card_definitions` は **`card` スキーマに配置され、card サービスが所有する**。battle / account / shop など他サービスからの参照は、card サービスの REST API 経由で行う（直接の DB 参照はしない）。battle は対戦中に高頻度でカードマスターを参照するため、**battle 側でカードマスターのインメモリキャッシュを保持する** 前提で運用する。

**キャッシュ戦略の概要:**

- battle Pod 起動時に card サービスの内部 REST API `GET /internal/v1/cards` で全カード定義を取得し、in-memory キャッシュに保持する
- 更新通知は Google Cloud Pub/Sub のトピック `card-definitions-updated` に invalidation signal として publish される（at-least-once で十分、ペイロードは invalidation のみで差分は含まない）
- battle Pod ごとに別々の subscription を割り当てる broadcast 構成を採る（各 Pod が独立したキャッシュを持つため、全 Pod に配送する必要がある）
- カードマスターにはバージョン番号があり、`games.card_data_version` に記録することでゲーム状態との整合を検証する
- Pub/Sub トピック設計やキャッシュ更新戦略の全体像は [ARCHITECTURE.md §5.3 カード定義キャッシュの更新通知](ARCHITECTURE.md#53-カード定義キャッシュの更新通知) を参照
- 内部 REST API の契約（エンドポイント、レスポンス形状、呼び出し側の責務）は [internal/card.md](internal/card.md) を参照（本ドキュメントでは SSoT 重複を避けるため概要のみ）

### 5.1 PostgreSQL スキーマ (card_definitions)

**CardDefinitions** (カード定義マスター)
- **Primary Key:** `card_id`

<!-- BEGIN GENERATED: card_definitions -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `card_id` | VARCHAR(10) | No | カード識別子（例: SH-0001） |
| `card_name` | VARCHAR(100) | No | カード名 |
| `resource_label` | VARCHAR(30) | No | リソースラベル |
| `faction` | VARCHAR(20) | No | 陣営（SHE / Tenki / Sugar / Tuners / Neutral） |
| `card_type` | VARCHAR(30) | No | カードタイプ（Resource / Support） |
| `resizable` | BOOLEAN | No | Resizable 属性 |
| `elastic` | BOOLEAN | No | Elastic 属性 |
| `stats` | JSONB | No | ステータス定義 |
| `effect_text` | VARCHAR(500) | Yes | 効果テキスト（表示用） |
| `effects` | JSONB | Yes | 効果定義（JSON 配列） |
| `restriction` | VARCHAR(20) | No | 制限区分（unlimited / semi_limited / limited / forbidden） |
| `is_active` | BOOLEAN | No | 有効フラグ |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |
<!-- END GENERATED: card_definitions -->

### 5.2 JSONスキーマ (stats)

**コンピュート系リソースの場合:**

| フィールド | 型 | 説明 |
|---|---|---|
| `throughput` | int | スループット（base値） |
| `availability` | int | 可用性 |
| `maintenance_cost` | int | 維持コスト（毎ターン終了時に徴収）。Resizable は MC×ランク乗数で固定。Elastic の MC 計算式は下記参照 |
| `free_tier` | int? | Elastic MC 閾値 + ln スケールパラメータ（Elastic以外は `null`）。ランクで変動しない固定値 |
| `cost_per_request` | int? | Elastic MC レート ÷100（Elastic以外は `null`）。Serverless は `0`（常に MC=0） |
| `sla_penalty` | int | SLAペナルティ |

**DB系リソースおよびオブジェクトストレージの場合:**

| フィールド | 型 | 説明 |
|---|---|---|
| `yield` | int | Yield生成量（base値） |
| `availability` | int | 可用性 |
| `maintenance_cost` | int | 維持コスト（毎ターン終了時に徴収）。Resizable は MC×ランク乗数で固定。Elastic の MC 計算式は下記参照 |
| `free_tier` | int? | Elastic MC 閾値 + ln スケールパラメータ（Elastic以外は `null`）。ランクで変動しない固定値 |
| `cost_per_request` | int? | Elastic MC レート ÷100（Elastic以外は `null`）。Serverless は `0`（常に MC=0） |
| `sla_penalty` | int | SLAペナルティ |

> Elastic メカニクス（蓄積・逓減・MC 計算式）の詳細は RULEBOOK.md を参照。

**その他のカードタイプ（Platform, Attachment, Strategy, Incident, Reactive）:**

stats フィールドなし（Platform の場合、`deploy_turns` はトップレベルで管理）。

> `deploy_turns` は stats 内ではなく、カード定義のトップレベルフィールドとして管理する。カードタイプごとのデフォルト値は RULEBOOK.md を参照。

### 5.3 関連インデックス

- `CardsByFaction`: `CardDefinitions(faction, card_type)`
- `CardsByType`: `CardDefinitions(card_type)`

---

## 6. カード・デッキ管理 (Card & Deck Management)

所持カードとデッキ構築。

### 6.1 PostgreSQL スキーマ (player_cards, decks, deck_cards)

**PlayerCards** (所持カード)
- **Primary Key:** `(player_id, card_id, art_no)`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: player_cards -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK) |
| `card_id` | VARCHAR(10) | No | カード識別子 |
| `art_no` | BIGINT | No | アート番号 (Default: 0) |
| `count` | INT | No | 所持枚数 (Default: 1) |
<!-- END GENERATED: player_cards -->

**Decks** (デッキ定義)
- **Primary Key:** `player_id`, `deck_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: decks -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK) |
| `deck_id` | BIGINT (IDENTITY) | No | デッキID（自動採番） |
| `deck_name` | VARCHAR(50) | No | デッキ名 |
| `playmat_no` | BIGINT | Yes | プレイマット番号（NULL: デフォルト） |
| `sleeve_no` | BIGINT | Yes | スリーブ番号（NULL: デフォルト） |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |
<!-- END GENERATED: decks -->

> **Note:** `is_valid` は DB に保存せず、API レスポンス時にサービス層が都度算出する（所持カード・制限改定に追従するため）。

**DeckCards** (デッキ内カード)
- **Primary Key:** `(player_id, deck_id, card_id, art_no)`
- **Foreign Key:** `(player_id, deck_id) REFERENCES decks(player_id, deck_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: deck_cards -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | ルート親参照 |
| `deck_id` | BIGINT | No | 親テーブル参照 |
| `card_id` | VARCHAR(10) | No | カード識別子 |
| `art_no` | BIGINT | No | アート番号 (Default: 0) |
| `count` | INT | No | 枚数 (Default: 1) |
<!-- END GENERATED: deck_cards -->

### 6.2 関連インデックス

- `PlayerCardsByCardId`: `PlayerCards(player_id, card_id)`
- `DecksByPlayer`: `Decks(player_id, updated_at DESC)`

---

## 7. ショップ・設定管理 (Shop & Settings)

アプリ内課金とユーザー設定。

### 7.1 PostgreSQL スキーマ (products, subscriptions, etc.)

**Products** (商品マスター)
- **Primary Key:** `product_id`

<!-- BEGIN GENERATED: products -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `product_id` | VARCHAR(50) | No | 商品ID |
| `name` | VARCHAR(100) | No | 商品名 |
| `type` | VARCHAR(20) | No | 商品タイプ (faction_set / cosmetic / subscription) |
| `price` | BIGINT | No | 価格 (JPY) |
| `content` | JSONB | No | 商品内容 |
| `faction_id` | VARCHAR(20) | Yes | 陣営（faction_set 商品のみ、それ以外は NULL） |
| `requires_product_id` | VARCHAR(50) | Yes | 購入前提の商品ID（拡張セット用、NULL: なし） |
| `description` | VARCHAR(500) | Yes | 商品説明 |
| `image_url` | VARCHAR(200) | Yes | 画像URL |
| `is_active` | BOOLEAN | No | 販売中フラグ |
<!-- END GENERATED: products -->

**Subscriptions** (サブスクリプション管理)
- **Primary Key:** `player_id`, `subscription_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: subscriptions -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK) |
| `subscription_id` | BIGINT (IDENTITY) | No | 自動採番 |
| `product_id` | VARCHAR(50) | No | 商品ID |
| `platform` | VARCHAR(10) | No | apple / google |
| `purchase_token` | VARCHAR(256) | No | 購入トークン（Apple: originalTransactionId / Google: purchaseToken） |
| `status` | VARCHAR(20) | No | active / grace_period / expired / refunded |
| `current_period_start` | TIMESTAMPTZ | No | 課金期間開始日時 |
| `current_period_end` | TIMESTAMPTZ | No | 課金期間終了日時 |
| `created_at` | TIMESTAMPTZ | No | 初回購入日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |
<!-- END GENERATED: subscriptions -->

**OneTimePurchases** (買い切り購入履歴)
- **Primary Key:** `player_id`, `purchase_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: one_time_purchases -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK) |
| `purchase_id` | BIGINT (IDENTITY) | No | 自動採番 |
| `product_id` | VARCHAR(50) | No | 商品ID |
| `platform` | VARCHAR(10) | No | apple / google |
| `purchase_token` | VARCHAR(256) | No | 購入トークン（Apple: originalTransactionId / Google: purchaseToken） |
| `purchased_at` | TIMESTAMPTZ | No | 購入日時 |
<!-- END GENERATED: one_time_purchases -->

**UserSettings** (ユーザー設定)
- **Primary Key:** `player_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: user_settings -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | ユーザーID |
| `language` | VARCHAR(10) | No | 言語設定 |
| `bgm_volume` | BIGINT | No | BGM音量 (0-100) |
| `se_volume` | BIGINT | No | SE音量 (0-100) |
| `push_enabled` | BOOLEAN | No | 通知許可 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |
<!-- END GENERATED: user_settings -->

---

## 8. コスメティクス管理 (Cosmetics)

装飾アイテム（プレイマット・スリーブ等）の定義・所持・装備。

### 8.1 PostgreSQL スキーマ (cosmetic_items, player_items)

**CosmeticItems** (装飾アイテムマスター)
- **Primary Key:** `item_type`, `item_no`

<!-- BEGIN GENERATED: cosmetic_items -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `item_type` | VARCHAR(20) | No | アイテム種別（playmat / sleeve / icon / stamp） |
| `item_no` | BIGINT | No | アイテム番号 |
| `item_name` | VARCHAR(100) | No | アイテム名 |
| `description` | VARCHAR(500) | Yes | 説明文 |
| `is_purchasable` | BOOLEAN | No | 購入可能フラグ |
| `is_active` | BOOLEAN | No | 有効フラグ |
<!-- END GENERATED: cosmetic_items -->

**PlayerItems** (プレイヤーの装飾アイテム所持)
- **Primary Key:** `player_id`, `item_type`, `item_no`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

<!-- BEGIN GENERATED: player_items -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK) |
| `item_type` | VARCHAR(20) | No | アイテム種別 |
| `item_no` | BIGINT | No | アイテム番号 |
| `acquired_at` | TIMESTAMPTZ | No | 獲得日時 |
<!-- END GENERATED: player_items -->

### 8.2 装備状態の管理

装備中のアイテムは使用時に即座に参照できるよう、所持テーブルではなく **Players / Decks テーブルに直接保持** する。

| アイテム種別 | 装備先テーブル | カラム |
|-------------|-------------|--------|
| アイコン | `Players` | `equipped_icon_no` |
| プレイマット | `Decks` | `playmat_no` |
| スリーブ | `Decks` | `sleeve_no` |

> 対戦開始時にデッキ情報と合わせて取得できるため、追加クエリ不要。

---

## 9. 陣営所持管理 (Player Factions)

プレイヤーが所持している陣営カードセットの中間テーブル。初期選択やショップ購入で取得する。

### 9.1 PostgreSQL スキーマ (player_factions)

**PlayerFactions** (陣営所持)
- **Primary Key:** `(player_id, faction)`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`
- **CHECK:** `faction IN ('SHE', 'Tenki', 'Sugar', 'Tuners')`
- **CHECK:** `source IN ('initial_selection', 'shop_purchase')`

<!-- BEGIN GENERATED: player_factions -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `faction` | VARCHAR(20) | No | 陣営名 (SHE / Tenki / Sugar / Tuners / Neutral) |
| `source` | VARCHAR(20) | No | 取得経路 (initial_selection / shop_purchase) |
| `acquired_at` | TIMESTAMPTZ | No | 取得日時 |
<!-- END GENERATED: player_factions -->

> `Players.selected_faction` は初回選択のみを保持するが、`player_factions` はショップ購入を含む全所持陣営を管理する。ストーリーのアンロック条件判定はこのテーブルを参照する。

---

## 10. ストーリー管理 (Story Scenarios)

各陣営のストーリーエピソード定義と、プレイヤーの進行状況。

### 10.1 PostgreSQL スキーマ (scenario_episodes, player_story_progress)

**ScenarioEpisodes** (エピソード定義マスター)
- **Primary Key:** `episode_id`
- **CHECK:** `category IN ('main', 'side', 'event')`
- **CHECK:** `faction IS NULL OR faction IN ('SHE', 'Tenki', 'Sugar', 'Tuners')`

<!-- BEGIN GENERATED: scenario_episodes -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `episode_id` | VARCHAR(50) | No | エピソードID（例: she_ep1, final） |
| `category` | VARCHAR(20) | No | エピソード種別 (main / side / event) |
| `faction` | VARCHAR(20) | Yes | 所属陣営（NULL: 全陣営共通） |
| `episode_number` | BIGINT | No | 陣営内の章番号 |
| `title_ja` | VARCHAR(200) | No | 日本語タイトル |
| `title_en` | VARCHAR(200) | No | 英語タイトル |
| `required_level` | BIGINT | No | アンロックに必要なレベル (Default: 1) |
| `required_episodes` | TEXT[] | No | アンロックに必要な完了済みエピソード |
| `script_path` | VARCHAR(500) | No | スクリプトパステンプレート（{lang} を言語コードに置換） |
| `thumbnail_path` | VARCHAR(500) | Yes | サムネイル画像パス |
| `sort_order` | BIGINT | No | 表示順 |
| `is_active` | BOOLEAN | No | 公開フラグ (Default: true) |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |
<!-- END GENERATED: scenario_episodes -->

**PlayerStoryProgress** (プレイヤーの進行状況)
- **Primary Key:** `(player_id, episode_id)`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`
- **Foreign Key:** `episode_id REFERENCES scenario_episodes(episode_id) ON DELETE RESTRICT`

<!-- BEGIN GENERATED: player_story_progress -->
| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK) |
| `episode_id` | VARCHAR(50) | No | 完了したエピソードID |
| `completed_at` | TIMESTAMPTZ | No | 完了日時 |
<!-- END GENERATED: player_story_progress -->

> 完了記録は冪等（`ON CONFLICT DO NOTHING`）。同じエピソードを再読了してもレコードは増えない。

### 10.2 関連インデックス

- `ScenarioEpisodesBySort`: `scenario_episodes(sort_order)`
