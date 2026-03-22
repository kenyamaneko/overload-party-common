# Overload Party - データ設計 (Data Architecture)

> **完全なスキーマ定義:** `db/schema_postgres.sql` を参照。以下は各テーブルの設計意図とカラム仕様の概要。

---

## 目次

1. [ゲーム管理](#1-ゲーム管理-game-management)
2. [ゲーム状態管理](#2-ゲーム状態管理-game-state-management)
3. [ゲームイベント管理](#3-ゲームイベント管理-game-event-management)
4. [対戦履歴管理](#4-対戦履歴管理-match-history)
5. [プレイヤー管理](#5-プレイヤー管理-player-management)
6. [カード定義マスター](#6-カード定義マスター-card-definitions)
7. [カード・デッキ管理](#7-カードデッキ管理-card--deck-management)
8. [ショップ・設定管理](#8-ショップ設定管理-shop--settings)
9. [コスメティクス管理](#9-コスメティクス管理-cosmetics)
10. [陣営所持管理](#10-陣営所持管理-player-factions)
11. [ストーリー管理](#11-ストーリー管理-story-scenarios)

---

## 1. ゲーム管理 (Game Management)

ゲームのライフサイクルを管理する基盤テーブル。

### 1.1 PostgreSQL スキーマ (games)

**Games** (ゲームマスター)
- **Primary Key:** `game_id`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | VARCHAR(26) | No | ULID |
| `player1_id` | UUID | No | プレイヤー1 ID |
| `player2_id` | UUID | No | プレイヤー2 ID |
| `player1_deck_snapshot` | JSONB | No | 使用デッキのスナップショット（カードIDリスト） |
| `player2_deck_snapshot` | JSONB | No | 使用デッキのスナップショット（カードIDリスト） |
| `status` | VARCHAR(20) | No | `'waiting'`, `'playing'`, `'finished'` |
| `winner_id` | UUID | Yes | 勝者 ID |
| `created_at` | TIMESTAMPTZ | No | 作成日時 (DEFAULT now()) |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 (DEFAULT now()) |
| `finished_at` | TIMESTAMPTZ | Yes | 終了日時 |

### 1.2 JSONスキーマ (Deck Snapshot)

`Games` テーブルの `player1_deck_snapshot`, `player2_deck_snapshot` カラムに格納されるデッキ情報。

| フィールド | 型 | 説明 |
|---|---|---|
| `deckId` | string | 元になったデッキID |
| `cards` | Array[int64] | デッキに含まれる card_no のリスト（順序はシャッフル前） |

### 1.3 関連インデックス

- `GamesByStatus`: `Games(status, created_at DESC)`

---

## 2. ゲーム状態管理 (Game State Management)

対戦中のリアルタイムな状態を管理する構造。

### 2.1 PostgreSQL スキーマ (game_states)

**GameStates** (ゲーム状態・頻繁に更新)
- **Primary Key:** `game_id`
- **Foreign Key:** `game_id REFERENCES games(game_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | VARCHAR(26) | No | 親テーブル参照 |
| `version` | BIGINT | No | 楽観的ロック用バージョン |
| `current_turn` | BIGINT | No | 現在ターン数 |
| `current_phase` | VARCHAR(20) | No | `'draw'`, `'main'`, `'battle'`, `'end'` |
| `active_player` | BIGINT | No | 現在のターンプレイヤー (1 or 2) |
| `player1_budget` | BIGINT | No | Player 1 Budget |
| `player1_insight_pool` | BIGINT | No | Player 1 Insight Pool |
| `player1_field` | JSONB | No | Player 1 フィールド上のカード |
| `player1_hand` | JSONB | No | Player 1 手札 |
| `player1_repository` | JSONB | No | Player 1 リポジトリ（山札） |
| `player1_trash` | JSONB | No | Player 1 トラッシュ |
| `player1_time_bank` | BIGINT | No | Player 1 残り時間 |
| `player2_...` | ... | No | Player 2 各種ステータス（構成は Player 1 と同じ。`player2_insight_pool` 等） |
| `chain_stack` | JSONB | Yes | 現在積まれているチェーンスタック |
| `current_action_timer`| BIGINT | Yes | アクションタイマー |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 (DEFAULT now()) |

> **フェーズについて:** ゲームフェーズは `draw`, `main`, `battle`, `end` の4つ。Yield（Insight）生成は End フェーズ中に処理される。

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
| `rank` | string | `"small"` / `"medium"` / `"large"` |
| `instanceFamily` | string等 | `"M"` / `"C"` / `"R"` / null |
| `currentAV` | int | 現在耐久値 |
| `maxAV` | int | AV最大値 |
| `currentTP` | int? | 現在TP（DB系およびオブジェクトストレージは null） |
| `maxTP` | int? | TP最大値（DB系およびオブジェクトストレージは null。Elastic カードは `nil`＝上限なし） |
| `currentYield` | int? | 現在Yield量（コンピュート系リソースは null） |
| `maxYield` | int? | Yield最大値（コンピュート系リソースは null。Elastic カードは `nil`＝上限なし） |
| `damage` | int | 蓄積ダメージ量 |
| `attachments` | array | アタッチメントリスト（instanceId + cardId） |
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
| `faceDown` | bool | 裏向きか否か |

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

## 3. ゲームイベント管理 (Game Event Management)

リプレイや監査のためのログデータ。

### 3.1 PostgreSQL スキーマ (game_events)

**GameEvents** (イベントログ・リプレイ用)
- **Primary Key:** `game_id`, `sequence_number`
- **Foreign Key:** `game_id REFERENCES games(game_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | VARCHAR(26) | No | 親テーブル参照 |
| `sequence_number` | BIGINT | No | イベント連番 |
| `event_type` | VARCHAR(50) | No | イベント種別 |
| `player_id` | UUID | Yes | 行動プレイヤー |
| `event_data` | JSONB | No | イベント詳細データ（攻撃対象、使用カードID、ダメージ量など） |
| `created_at` | TIMESTAMPTZ | No | 発生日時 (DEFAULT now()) |

**イベントデータの例:**
- `attack`: `{ "sourceId": "...", "targetId": "...", "damage": 500 }`
- `deploy`: `{ "cardId": "...", "position": 0, "cost": 300 }`

---

## 4. 対戦履歴管理 (Match History)

ユーザーの対戦結果の記録。

> **レーティング制は廃止。** 教育系カードゲームとしてデッキ構築と学習を楽しむことを重視し、勝敗ランキングは設けない。

### 4.1 PostgreSQL スキーマ (matches)

**Matches** (対戦履歴)
- **Primary Key:** `match_id`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `match_id` | BIGINT (IDENTITY) | No | 自動採番 |
| `game_id` | VARCHAR(26) | No | 対応する `Games` レコード ID（`Games.player1_id/player2_id` を参照） |
| `created_at` | TIMESTAMPTZ | No | マッチ成立日時 |

> **注:** プレイヤーIDは `Games` テーブルの `player1_id` / `player2_id` を正とする。`Matches` からプレイヤーを特定する場合は `game_id` を通じて `Games` テーブルを参照する。

### 4.2 関連インデックス

- `MatchesByGameId`: `Matches(game_id)`

---

## 5. プレイヤー管理 (Player Management)

ユーザーアカウントと基本情報。

### 5.1 PostgreSQL スキーマ (players & player_daily_battle)

**Players** (プレイヤーマスター)
- **Primary Key:** `player_id`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | UUID |
| `firebase_uid` | VARCHAR(128)| No | Firebase Auth UID (Unique) |
| `username` | VARCHAR(50) | No | 表示名 |
| `level` | BIGINT | No | レベル (Default: 1) |
| `exp` | BIGINT | No | 経験値 (Default: 0) |

| `is_premium` | BOOLEAN | No | 課金ステータス (Default: false) |
| `equipped_icon_no` | BIGINT | Yes | 装備中アイコン番号（`CosmeticItems` 参照。NULL: デフォルト） |
| `selected_faction` | VARCHAR(20) | Yes | 選択済みファクション |
| `premium_expires_at` | TIMESTAMPTZ | Yes | サブスク有効期限 |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |

**player_daily_battle** (デイリーバトル管理)
- **Primary Key:** `player_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `daily_battle_count` | BIGINT | No | 本日のバトル回数 |
| `last_reset_date` | DATE | No | 最終リセット日 |

### 5.2 関連インデックス

- `PlayersByFirebaseUID`: `Players(firebase_uid)` (UNIQUE)

---

## 6. カード定義マスター (Card Definitions)

カードのステータス・効果テキスト・コスト等の定義データ。`CARDS.md` の内容をDB上で管理する。

### 6.1 PostgreSQL スキーマ (card_definitions)

**CardDefinitions** (カード定義マスター)
- **Primary Key:** `card_no`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `card_no` | BIGINT | No | カード番号（`CARDS.md` の `#` に対応） |
| `card_name` | VARCHAR(100) | No | カード名 |
| `faction` | VARCHAR(20) | No | 陣営 (`SHE`, `Tenki`, `Sugar`, `Tuners`, `Neutral`) |
| `card_type` | VARCHAR(30) | No | カードタイプ (`Compute`, `Container`, `Orchestrator`, `Serverless`, `AI_ML`, `Database`, `ObjectStorage`, `CacheDB`, `Platform`, `Attachment`, `Strategy`, `Incident`, `Reactive`) |
| `resizable` | BOOLEAN | No | Resizable 属性 (Default: false) |
| `elastic` | BOOLEAN | No | Elastic 属性 (Default: false) |
| `elastic_increment` | BIGINT | Yes | Elastic トリガーごとの TP/Yield 増加量。Elastic カードのみ設定（非 Elastic は `null` または `0`） |
| `stats` | JSONB | No | ステータス定義 |
| `effect_text` | VARCHAR(500) | Yes | 効果テキスト（表示用） |
| `effects` | JSONB | Yes | 効果定義（複数効果を JSON 配列で保持） |
| `restriction` | VARCHAR(20) | No | 制限区分 (`unlimited`, `semi_limited`, `limited`, `forbidden`) |
| `is_active` | BOOLEAN | No | 有効フラグ（メンテ・バランス調整用） |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |

### 6.2 JSONスキーマ (stats)

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

> **Elastic メカニクス（オートスケーリング）:**
> Elastic カードは ElasticBonus が累積的に蓄積され、TP/Yield が増加する。上限キャップは無く、代わりに対数的な逓減が適用される。
>
> | ゾーン | トリガー | 増加対象 |
> |--------|----------|----------|
> | フロントエンド | 攻撃を受けた時 | スループット (TP) + `elastic_increment` |
> | バックエンド Compute | 収益化（Monetize）に使用された時 | スループット (TP) + `elastic_increment` |
> | バックエンド DB | 各エンドフェイズ | Yield + `elastic_increment` |
>
> - ElasticBonus は**累積**される（トリガーごとに `elastic_increment` ずつ線形加算。上限なし）
> - **ln 逓減:** 実効値は `effectiveElasticBonus = free_tier × ln(1 + ElasticBonus / free_tier)` で計算される。蓄積が進むほど伸びが鈍化する
> - ElasticBonus = 0 の状態が初期値（フリーティア相当、MC = 0）
> - **MC 計算式（Elastic）:** `MC = max(0, intrinsicStat - free_tier) × cost_per_request / 100`
>   - `intrinsicStat = base × rank_multiplier × family_multiplier + effectiveElasticBonus`（外部バフを除く固有ステータス）
>   - `free_tier` はランクで変動しない固定値
>   - Serverless（`cost_per_request=0`）は常に MC=0
> - Elastic カードは MaxTP / MaxYield を持たない（ResourceInstance 上は `nil`）

**その他のカードタイプ（Platform, Attachment, Strategy, Incident, Reactive）:**

stats フィールドなし（Platform の場合、`deploy_turns` はトップレベルで管理）。

> `deploy_turns` は stats 内ではなく、カード定義のトップレベルフィールドとして管理する。カードタイプごとのデフォルト値は RULEBOOK.md を参照。

### 6.3 関連インデックス

- `CardsByFaction`: `CardDefinitions(faction, card_type)`
- `CardsByType`: `CardDefinitions(card_type)`

### 6.4 サーバー側のカード参照設計

| 用途 | 参照方法 |
|------|----------|
| ゲーム中の効果計算 | サーバー起動時に `CardDefinitions` を全件メモリにキャッシュ。`card_no` → 定義データの `map` で O(1) 参照 |
| デッキ構築画面 | REST API `GET /api/v1/cards` で全カード定義を返却。クライアントはローカルキャッシュ |
| カードバランス更新 | Admin Dashboard からカード定義を更新後、キャッシュリフレッシュを実行 |

**キャッシュリフレッシュ方式:**

| タイミング | 方式 | 説明 |
|-----------|------|------|
| Pod 起動時 | 全件ロード | Cloud SQL から `card_definitions` を全件取得し `sync.Map` にキャッシュ |
| 定期更新 | ポーリング | 各 Pod が **5分間隔**で `CardDefinitions` の `updated_at` を確認し、更新があれば差分リフレッシュ |
| 管理者操作時 | ポーリングで反映 | Admin API でカード定義を更新すると、次回ポーリング（最大5分）で各 Pod がキャッシュをリフレッシュ |

```
[Admin Dashboard / API]
     │
     │ POST/PUT /admin/cards
     ▼
[api-server Pod]
     │
     └── Cloud SQL に書き込み → 定期ポーリングで各 Pod がキャッシュ更新
```

> **設計判断:** カード定義の更新頻度は低い（月数回程度）ため、5分間隔ポーリングで十分。最大5分の遅延は許容範囲。

### 6.5 ゲーム定数 (constants.json — initial_values)

`data/constants.json` の `initial_values` セクションで管理されるゲーム全体の初期値・定数。サーバー（Go）とクライアント（TypeScript）の両方に自動生成される。

| キー | 型 | 値 | 説明 |
|------|-----|-----|------|
| `budget` | int | 5000 | 初期 Budget |
| `insight_pool` | int | 0 | 初期 Insight Pool |
| `hand_size` | int | 5 | 初期手札枚数 |
| `hand_limit` | int | 6 | 手札上限 |
| `time_bank` | int | 480 | タイムバンク（秒） |
| `deck_size` | int | 30 | デッキ枚数 |
| `max_attachments` | int | 2 | リソースあたりの最大アタッチメント数 |
| `slots_per_zone` | int | 3 | ゾーンあたりのスロット数 |

---

## 7. カード・デッキ管理 (Card & Deck Management)

所持カードとデッキ構築。

### 7.1 PostgreSQL スキーマ (player_cards, decks, deck_cards)

**PlayerCards** (所持カード)
- **Primary Key:** `(player_id, card_no, illustration_variant)`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `card_no` | BIGINT | No | `CARDS.md` のカード番号 |
| `illustration_variant`| BIGINT | No | イラスト違いID (Default: 0) |
| `count` | INT | No | 所持枚数 (Default: 1) |

**Decks** (デッキ定義)
- **Primary Key:** `player_id`, `deck_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `deck_id` | BIGINT (IDENTITY) | No | デッキID（自動採番） |
| `deck_name` | VARCHAR(50) | No | デッキ名 |
| `is_valid` | BOOLEAN | No | 有効デッキフラグ (30枚ルール適合) |
| `playmat_no` | BIGINT | Yes | プレイマット番号（`CosmeticItems` 参照。NULL: デフォルト） |
| `sleeve_no` | BIGINT | Yes | スリーブ番号（`CosmeticItems` 参照。NULL: デフォルト） |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |

**DeckCards** (デッキ内カード)
- **Primary Key:** `(player_id, deck_id, card_no, illustration_variant)`
- **Foreign Key:** `(player_id, deck_id) REFERENCES decks(player_id, deck_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | ルート親参照 |
| `deck_id` | BIGINT | No | 親テーブル参照 |
| `card_no` | BIGINT | No | カード番号 |
| `illustration_variant`| BIGINT | No | イラスト違いID (Default: 0) |
| `count` | INT | No | 枚数 (Default: 1) |

### 7.2 関連インデックス

- `PlayerCardsByCardNo`: `PlayerCards(player_id, card_no)`
- `DecksByPlayer`: `Decks(player_id, updated_at DESC)`

---

## 8. ショップ・設定管理 (Shop & Settings)

アプリ内課金とユーザー設定。

### 8.1 PostgreSQL スキーマ (products, subscriptions, etc.)

**Products** (商品マスター)
- **Primary Key:** `product_id`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `product_id` | VARCHAR(50) | No | 商品ID (e.g. `theme_aws`) |
| `name` | VARCHAR(100) | No | 商品名 |
| `type` | VARCHAR(20) | No | `card_pack` / `subscription` |
| `price` | BIGINT | No | 価格 (JPY) |
| `content` | JSONB | No | 商品内容 (カードIDリスト等) |
| `is_active` | BOOLEAN | No | 販売中フラグ |

**Subscriptions** (サブスクリプション管理)
- **Primary Key:** `player_id`, `subscription_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `subscription_id` | BIGINT (IDENTITY) | No | 自動採番 |
| `product_id` | VARCHAR(50) | No | 商品ID（`premium_monthly` 等） |
| `platform` | VARCHAR(10) | No | `apple` / `google` |
| `purchase_token` | VARCHAR(256) | No | Apple: `originalTransactionId` / Google: `purchaseToken`（UNIQUE） |
| `status` | VARCHAR(20) | No | `active` / `grace_period` / `expired` / `refunded` |
| `current_period_start` | TIMESTAMPTZ | No | 現在の課金期間開始日時 |
| `current_period_end` | TIMESTAMPTZ | No | 現在の課金期間終了日時 |
| `created_at` | TIMESTAMPTZ | No | 初回購入日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |

**OneTimePurchases** (買い切り購入履歴)
- **Primary Key:** `player_id`, `purchase_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `purchase_id` | UUID | No | UUID |
| `product_id` | VARCHAR(50) | No | 商品ID（`faction_sws` 等） |
| `platform` | VARCHAR(10) | No | `apple` / `google` |
| `purchase_token` | VARCHAR(256) | No | Apple: `transactionId` / Google: `purchaseToken`（UNIQUE） |
| `purchased_at` | TIMESTAMPTZ | No | 購入日時 |

**UserSettings** (ユーザー設定)
- **Primary Key:** `player_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | ユーザーID |
| `language` | VARCHAR(10) | No | 言語設定 (Default: `ja`) |
| `bgm_volume` | BIGINT | No | BGM音量 (0-100) |
| `se_volume` | BIGINT | No | SE音量 (0-100) |
| `push_enabled` | BOOLEAN | No | 通知許可 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |

---

## 9. コスメティクス管理 (Cosmetics)

装飾アイテム（プレイマット・スリーブ等）の定義・所持・装備。

### 9.1 PostgreSQL スキーマ (cosmetic_items, player_items)

**CosmeticItems** (装飾アイテムマスター)
- **Primary Key:** `item_type`, `item_no`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `item_type` | VARCHAR(20) | No | アイテム種別（`playmat` / `sleeve` / `icon` / `stamp`） |
| `item_no` | BIGINT | No | アイテム番号（種別内で一意） |
| `item_name` | VARCHAR(100) | No | アイテム名 |
| `description` | VARCHAR(500) | Yes | 説明文 |
| `is_purchasable` | BOOLEAN | No | 購入可能フラグ |
| `is_active` | BOOLEAN | No | 有効フラグ |

**PlayerItems** (プレイヤーの装飾アイテム所持)
- **Primary Key:** `player_id`, `item_type`, `item_no`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `item_type` | VARCHAR(20) | No | アイテム種別 |
| `item_no` | BIGINT | No | アイテム番号 |
| `acquired_at` | TIMESTAMPTZ | No | 獲得日時 |

### 9.2 装備状態の管理

装備中のアイテムは使用時に即座に参照できるよう、所持テーブルではなく **Players / Decks テーブルに直接保持** する。

| アイテム種別 | 装備先テーブル | カラム |
|-------------|-------------|--------|
| アイコン | `Players` | `equipped_icon_no` |
| プレイマット | `Decks` | `playmat_no` |
| スリーブ | `Decks` | `sleeve_no` |

> 対戦開始時にデッキ情報と合わせて取得できるため、追加クエリ不要。

---

## 10. 陣営所持管理 (Player Factions)

プレイヤーが所持している陣営カードセットの中間テーブル。初期選択やショップ購入で取得する。

### 10.1 PostgreSQL スキーマ (player_factions)

**PlayerFactions** (陣営所持)
- **Primary Key:** `(player_id, faction)`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`
- **CHECK:** `faction IN ('SHE', 'Tenki', 'Sugar', 'Tuners')`
- **CHECK:** `source IN ('initial_selection', 'shop_purchase')`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `faction` | VARCHAR(20) | No | 陣営名 (`SHE`, `Tenki`, `Sugar`, `Tuners`) |
| `source` | VARCHAR(20) | No | 取得経路 (`initial_selection`, `shop_purchase`) |
| `acquired_at` | TIMESTAMPTZ | No | 取得日時 (DEFAULT now()) |

> `Players.selected_faction` は初回選択のみを保持するが、`player_factions` はショップ購入を含む全所持陣営を管理する。ストーリーのアンロック条件判定はこのテーブルを参照する。

---

## 11. ストーリー管理 (Story Scenarios)

各陣営のストーリーエピソード定義と、プレイヤーの進行状況。

### 11.1 PostgreSQL スキーマ (scenario_episodes, player_story_progress)

**ScenarioEpisodes** (エピソード定義マスター)
- **Primary Key:** `episode_id`
- **CHECK:** `category IN ('main', 'side', 'event')`
- **CHECK:** `faction IS NULL OR faction IN ('SHE', 'Tenki', 'Sugar', 'Tuners')`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `episode_id` | VARCHAR(50) | No | エピソードID（例: `she_ep1`, `final`） |
| `category` | VARCHAR(20) | No | エピソード種別（DEFAULT `'main'`）。`main`: メインストーリー, `side`: サイドストーリー, `event`: イベントストーリー |
| `faction` | VARCHAR(20) | Yes | 所属陣営（`NULL` = グランドエンディング等の全陣営共通エピソード） |
| `episode_number` | BIGINT | No | 陣営内の章番号 |
| `title_ja` | VARCHAR(200) | No | 日本語タイトル |
| `title_en` | VARCHAR(200) | No | 英語タイトル |
| `required_level` | BIGINT | No | アンロックに必要なプレイヤーレベル (DEFAULT 1) |
| `required_factions` | TEXT[] | No | アンロックに必要な陣営所持（DEFAULT '{}'） |
| `required_episodes` | TEXT[] | No | アンロックに必要な完了済みエピソード（DEFAULT '{}'） |
| `script_path` | VARCHAR(500) | No | スクリプトパステンプレート（`{lang}` を言語コードに置換） |
| `thumbnail_path` | VARCHAR(500) | Yes | サムネイル画像パス |
| `sort_order` | BIGINT | No | 表示順 |
| `is_active` | BOOLEAN | No | 公開フラグ (DEFAULT true) |
| `created_at` | TIMESTAMPTZ | No | 作成日時 (DEFAULT now()) |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 (DEFAULT now()) |

**PlayerStoryProgress** (プレイヤーの進行状況)
- **Primary Key:** `(player_id, episode_id)`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`
- **Foreign Key:** `episode_id REFERENCES scenario_episodes(episode_id) ON DELETE RESTRICT`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `episode_id` | VARCHAR(50) | No | 完了したエピソードID |
| `completed_at` | TIMESTAMPTZ | No | 完了日時 (DEFAULT now()) |

> 完了記録は冪等（`ON CONFLICT DO NOTHING`）。同じエピソードを再読了してもレコードは増えない。

### 11.2 アンロック条件の判定

アンロック条件は以下の優先順で判定される。最初に不足が見つかった時点で `lock_reason` を返す:

1. **レベル**: `players.level >= scenario_episodes.required_level`
2. **陣営所持**: `player_factions` に `required_factions` のすべてが存在
3. **前提エピソード**: `player_story_progress` に `required_episodes` のすべてが存在

### 11.3 エピソード構成

| ラウンド | レベル帯 | エピソード数 | 内容 |
|----------|---------|-------------|------|
| Round 1 | Lv 2〜5 | 4 | 各陣営 第1章 |
| Round 2 | Lv 6〜9 | 4 | 各陣営 第2章 |
| Round 3 | Lv 10〜13 | 4 | 各陣営 第3章 |
| Round 4 | Lv 14〜17 | 4 | 各陣営 第4章 |
| Round 5 | Lv 18〜21 | 4 | 各陣営 第5章 |
| Final | Lv 22 | 1 | グランドエンディング（全陣営クリア必須） |

### 11.4 関連インデックス

- `ScenarioEpisodesBySort`: `scenario_episodes(sort_order)`
