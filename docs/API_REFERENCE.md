# Overload Party - API リファレンス

**Last Updated:** 2026-02-27

---

## 目次

1. [概要](#1-概要)
2. [認証](#2-認証)
3. [REST API](#3-rest-api)
   - [Auth](#31-auth)
   - [Player](#32-player)
   - [Deck](#33-deck)
   - [Card](#34-card)
   - [NPC Battle](#35-npc-battle)
   - [Shop](#36-shop)
   - [Webhook](#37-webhook)
4. [WebSocket API](#4-websocket-api)
   - [接続](#41-接続)
   - [Client → Server メッセージ](#42-client--server-メッセージ)
   - [Server → Client メッセージ](#43-server--client-メッセージ)
5. [Dev API（開発専用）](#5-dev-api開発専用)
6. [エンドポイント一覧](#6-エンドポイント一覧)

---

## 1. 概要

### ベース URL

| 環境 | REST API | WebSocket |
|------|----------|-----------|
| ローカル | `http://localhost:9001/api/v1/` | `ws://localhost:9001/ws` |
| dev | `https://overloadparty-dev.keyandnotes.com/api/v1/` | `wss://overloadparty-dev.keyandnotes.com/ws` |
| stg | `https://overloadparty-stg.keyandnotes.com/api/v1/` | `wss://overloadparty-stg.keyandnotes.com/ws` |
| prod | `https://overloadparty.keyandnotes.com/api/v1/` | `wss://overloadparty.keyandnotes.com/ws` |

### ヘルスチェック

```
GET /health
```

**レスポンス:**
```json
{ "status": "ok", "mode": "local" }
```

---

## 2. 認証

### 本番環境

- REST API: `Authorization: Bearer {Firebase ID Token}` ヘッダー
- WebSocket: `GET /ws?token={Firebase ID Token}` クエリパラメータ

ミドルウェアが Firebase Token を検証し、`firebase_uid` をコンテキストに設定。
`PlayerResolve` ミドルウェアが `firebase_uid` → `player_id`（UUID）に解決し、コンテキストにセットする。
認証エンドポイント（`/auth/register`, `/auth/login`）は `PlayerResolve` を経由しない（プレイヤー未作成の場合があるため）。
WS ハンドラは接続時に `FindByFirebaseUID` で PlayerID（UUID）に解決する。

### ローカル開発

- REST API: `Authorization: Bearer dev-token-{uid}` ヘッダー
- WebSocket: `GET /ws?token=dev-token-{uid}` クエリパラメータ（空でも可）
- トークンが空の場合、`uid = "dev-anonymous"` として扱う
- 未登録の uid は **自動でプレイヤーが作成**される

---

## 3. REST API

### 3.0 Public（認証不要）

スプラッシュ画面やバージョンチェックで使用。認証不要。

#### GET `/health`

ヘルスチェック。

**レスポンス (200):**
```json
{ "status": "ok" }
```

---

#### GET `/version`

アプリバージョン確認。

**レスポンス (200):**
```json
{
  "minimumVersion": "1.0.0",
  "latestVersion": "1.2.0",
  "forceUpdate": false,
  "storeUrl": "https://..."
}
```

`forceUpdate` が `true` の場合、クライアントはストアへ誘導する。

---

#### GET `/announcements`

お知らせ一覧取得。

**レスポンス (200):**
```json
[
  {
    "id": "string",
    "title": "string",
    "body": "string",
    "type": "info|event|maintenance",
    "createdAt": "timestamp"
  }
]
```

---

#### GET `/daily`

デイリー Tips 取得。

**レスポンス (200):**
```json
{
  "id": "string",
  "text": "string"
}
```

---

#### GET `/cloud-news`

クラウドニュース一覧取得。ホーム画面のニュースセクション用。

**クエリパラメータ:**

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `limit` | int | 20 | 取得件数（1-100） |
| `offset` | int | 0 | オフセット |

**レスポンス (200):**
```json
[
  {
    "article_id": "string (ULID)",
    "source": "aws|gcp|azure|oci",
    "title": "string",
    "summary": "string (nullable)",
    "tags": ["aws", "storage"],
    "published_at": "timestamp (nullable)",
    "fetched_at": "timestamp"
  }
]
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `article_id` | string | 記事 ULID |
| `source` | string | ソース。`aws` / `gcp` / `azure` / `oci` のいずれか |
| `title` | string | 記事タイトル |
| `summary` | string? | AI 要約（未完了の場合 null） |
| `tags` | string[] | タグ配列 |
| `published_at` | timestamp? | 記事の公開日時 |
| `fetched_at` | timestamp | 取得日時 |

---

以下のエンドポイントは認証が必要（Webhook を除く）。

### 3.1 Auth

#### POST `/auth/register`

新規プレイヤー登録。スターターアイテム（スタンプ 1〜7）とデフォルトユーザー設定（language: `ja`）が作成される。

**リクエスト:**
```json
{
  "username": "string (1〜50文字)"
}
```

**レスポンス (201):**
```json
{
  "player_id": "uuid",
  "firebase_uid": "string",
  "username": "string",
  "level": 1,
  "exp": 0,
  "is_premium": false,
  "selected_faction": null,
  "equipped_icon_no": null,
  "premium_expires_at": null,
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

**エラー:** `409` 登録済み

---

#### POST `/auth/login`

既存プレイヤーのログイン。

**リクエスト:** なし（トークンから uid を取得）

**レスポンス (200):** Player オブジェクト（register と同じ構造）

**エラー:** `404` プレイヤーが見つからない

---

### 3.2 Player

#### GET `/player/settings`

ユーザー設定取得。未作成の場合はデフォルト値を返す。

**レスポンス (200):**
```json
{
  "player_id": "uuid",
  "language": "ja",
  "bgm_volume": 50,
  "se_volume": 50,
  "push_enabled": true,
  "updated_at": "timestamp"
}
```

---

#### PUT `/player/settings`

ユーザー設定更新。

**リクエスト:**
```json
{
  "language": "ja|en",
  "bgm_volume": 50,
  "se_volume": 50,
  "push_enabled": true
}
```

**レスポンス (200):** UserSettings オブジェクト

---

#### GET `/player`

認証済みプレイヤーの情報取得。プレイヤーIDはミドルウェアが認証トークンから解決する。

**レスポンス (200):** Player オブジェクト

**エラー:** `404` プレイヤーが見つからない

---

#### PUT `/player/name`

プレイヤー名変更。

**リクエスト:**
```json
{
  "name": "string"
}
```

**レスポンス (200):** Player オブジェクト

---

#### GET `/player/battle-limit`

デイリーバトル回数の確認。

**レスポンス (200):**
```json
{
  "daily_battle_count": 3,
  "daily_battle_limit": 10,
  "can_battle": true
}
```

`daily_battle_limit` が `-1` の場合は無制限（プレミアム会員）。

---

#### GET `/player/cards`

所持カード一覧取得。カード定義を含む enriched レスポンスを返す。

**レスポンス (200):**
```json
[
  {
    "card_no": 1,
    "art_no": 0,
    "count": 3,
    "card_name": "EC2 Instance",
    "faction": "SHE",
    "card_type": "resource",
    "resizable": true,
    "elastic": false,
    "stats": { "throughput": 3, "availability": 4, "maintenance_cost": 2, "sla_penalty": 2 },
    "effect_text": "デプロイ時: スループット+1",
    "restriction": "unlimited"
  }
]
```

---

### 3.3 Deck

#### GET `/player/decks`

デッキ一覧取得。

**レスポンス (200):**
```json
[
  {
    "player_id": "uuid",
    "playmat_no": 1,
    "sleeve_no": 2,
    "deck_cards": [
      {"card_no": 1, "art_no": 0, "count": 3},
      {"card_no": 2, "art_no": 1, "count": 2}
    ],
    "created_at": "timestamp",
    "updated_at": "timestamp"
  }
]
```

`deck_cards` はデッキのカード構成（`card_no`, `art_no`, `count`）の配列。


---

#### GET `/player/decks/{deckId}`

デッキ詳細取得。

**レスポンス (200):**
```json
{
  "deck": { /* Deck オブジェクト */ },
  "cards": [
    {
      "player_id": "uuid",
      "deck_id": 1,
      "card_no": 1,
      "art_no": 0,
      "count": 3
    }
  ]
}
```

---

#### POST `/player/decks`

デッキ作成。

**リクエスト:**
```json
{
  "deck_name": "string",
  "cards": [
    { "card_no": 1, "art_no": 0, "count": 3 },
    { "card_no": 2, "art_no": 0, "count": 2 }
  ],
  "playmat_no": 1,
  "sleeve_no": 2
}
```

**レスポンス (201):** Deck オブジェクト

**エラー:** `400` バリデーションエラー（枚数不正、未所持カード、制限超過）

---

#### PUT `/player/decks/{deckId}`

デッキ更新。リクエスト/レスポンスは POST と同じ。

---

#### DELETE `/player/decks/{deckId}`

デッキ削除。

**レスポンス:** `204 No Content`

---

### 3.4 Card

#### GET `/cards`

全カード定義取得。

**レスポンス (200):**
```json
[
  {
    "card_no": 1,
    "card_name": "string",
    "faction": "SHE|Tenki|Sugar|Tuners|Neutral",
    "card_type": "resource|support|action",
    "resizable": true,
    "elastic": false,
    "stats": {},
    "effect_text": "string",
    "effects": [],
    "passive_effects": [],
    "platform_effects": [],
    "attachment_effects": [],
    "restriction": "unlimited|semi_limited|limited|forbidden",
    "is_active": true
  }
]
```

---

### 3.5 NPC Battle (WebSocket)

NPC バトルは WebSocket 経由で処理される。REST エンドポイントは存在しない。

#### `npc_battle_start` (Client → Server)

NPC 対戦開始。即座にゲームが作成される（マッチメイキング不要）。

**ペイロード:**
```json
{
  "type": "npc_battle_start",
  "deckId": 1,
  "npcFaction": "SHE|Tenki|Sugar|Tuners"
}
```

**レスポンス:** `npc_battle_created` (Server → Client)
```json
{
  "type": "npc_battle_created",
  "gameId": "ULID",
  "player1Id": "uuid",
  "player2Id": "npc_..."
}
```

エラー時は `error` メッセージが返る。

ゲーム開始後は PvP と同じ `game_action` メッセージでアクションを送信する。NPC は自動応答する。ゲーム状態は `game_enter` → `game_state` メッセージで取得可能。

---

### 3.6 Shop

#### POST `/player/select-faction`

ファクション選択。対応する初期カードセットが付与される。

**リクエスト:**
```json
{
  "faction": "SHE|Tenki|Sugar|Tuners"
}
```

**レスポンス (200):**
```json
{
  "message": "faction selected",
  "faction": "SHE",
  "cards_granted": 59
}
```

**エラー:** `400` 不正なファクション / `409` 選択済み

---

#### GET `/shop/products`

商品一覧取得。プレイヤーIDは認証トークンから自動解決される。

**レスポンス (200):**
```json
{
  "products": [
    {
      "product_id": "uuid",
      "name": "string",
      "type": "faction_set|cosmetic|subscription",
      "price": 999,
      "content": {},
      "is_active": true,
      "is_owned": false
    }
  ]
}
```

---

#### POST `/shop/purchase`

商品購入。

**リクエスト:**
```json
{
  "product_id": "uuid",
  "platform": "ios|android",
  "purchase_token": "string"
}
```

**レスポンス (200):**
```json
{
  "message": "purchase completed",
  "product_id": "uuid"
}
```

---

#### POST `/shop/subscribe`

サブスクリプション登録。

**リクエスト:**
```json
{
  "product_id": "uuid",
  "platform": "ios|android",
  "purchase_token": "string"
}
```

**レスポンス (200):**
```json
{
  "message": "subscription activated",
  "expires_at": "timestamp"
}
```

---

### 3.7 Webhook（認証不要）

#### POST `/shop/webhook/apple`

Apple In-App Purchase のサーバー通知。

**リクエスト:**
```json
{
  "signedPayload": "JWS_TOKEN"
}
```

---

#### POST `/shop/webhook/google`

Google Play Billing のサーバー通知。

**リクエスト:**
```json
{
  "message": {
    "data": "base64_encoded_json"
  }
}
```

---

## 4. WebSocket API

### 4.1 接続

```
GET /ws?token={token}
```

- 本番: Firebase ID Token
- ローカル: `dev-token-{uid}` または空
- サーバーが FirebaseUID → PlayerID (UUID) に解決
- ローカルでは未登録 uid に対してプレイヤーを自動作成

接続後、サーバーは 15 秒間隔で WebSocket Ping を送信。クライアントは Pong を返す必要がある（ブラウザは自動応答）。

### メッセージフォーマット

```json
{
  "type": "message_type",
  "data": { /* ペイロード */ }
}
```

---

### 4.2 Client → Server メッセージ

#### `matchmaking_start` — PvP マッチメイキング開始

```json
{
  "type": "matchmaking_start",
  "data": { "deck_id": 1 }
}
```

**応答:** `matchmaking_started` / `error` (code: `matchmaking_error`)

冪等: 既にマッチメイキング中の場合はデッキを更新して成功。

---

#### `matchmaking_cancel` — マッチメイキングをキャンセル

```json
{ "type": "matchmaking_cancel" }
```

**応答:** `matchmaking_cancelled`

---

#### `game_enter` — ゲームルームに参加

```json
{
  "type": "game_enter",
  "data": { "game_id": "ULID", "deck_id": 1 }
}
```

**応答:** `game_entered` → `game_state`（両プレイヤーに送信）

---

#### `game_action` — ゲームアクション実行

```json
{
  "type": "game_action",
  "data": {
    "game_id": "ULID",
    "action_type": "play_card|attack|scale_up|distribute_yield|...",
    "data": { /* アクション固有データ（NPC Battle セクション参照） */ }
  }
}
```

**応答:** `game_state`（両プレイヤーに送信）
**エラー:** `action_rejected`
**ゲーム終了時:** `game_over`（両プレイヤーに送信）

---

#### `use_stamp` — スタンプ送信（演出のみ）

```json
{
  "type": "use_stamp",
  "data": { "game_id": "ULID", "stamp_no": 1 }
}
```

**応答:** `stamp_used`（両プレイヤーにブロードキャスト）

---

#### `ping` — 生存確認

```json
{ "type": "ping" }
```

**応答:** `pong`

---

### 4.3 Server → Client メッセージ

#### `matchmaking_started`
```json
{ "type": "matchmaking_started" }
```

#### `matchmaking_cancelled`
```json
{ "type": "matchmaking_cancelled" }
```

#### `match_found` — マッチ成立
```json
{
  "type": "match_found",
  "data": {
    "game_id": "ULID",
    "player1_id": "uuid",
    "player2_id": "uuid"
  }
}
```

#### `game_entered`
```json
{
  "type": "game_entered",
  "data": { "game_id": "ULID" }
}
```

#### `game_state` — ゲーム状態（情報秘匿適用済み）
```json
{
  "type": "game_state",
  "data": {
    "gameId": "ULID",
    "currentTurn": 1,
    "currentPhase": "selecting|draw|yield|main|battle|end",
    "activePlayer": 1,
    "isMyTurn": true,
    "my": {
      "playerNum": 1,
      "budget": 5,
      "insightPool": 0,
      "field": {
        "frontend": [null, null, null],
        "backend": [null, null, null],
        "support": [null, null, null]
      },
      "hand": [
        { "instanceId": "i0001", "cardId": 1 }
      ],
      "repoCount": 20,
      "trashCount": 0
    },
    "opponent": {
      "playerNum": 2,
      "budget": 5,
      "insightPool": 0,
      "field": {},
      "handCount": 3,
      "repoCount": 20,
      "trashCount": 0
    },
    "my": {
      "playerNum": 1,
      "budget": 5,
      "insightPool": 0,
      "field": {
        "frontend": [null, null, null],
        "backend": [null, null, null],
        "support": [null, null, null]
      },
      "hand": [
        { "instanceId": "i0001", "cardId": 1 }
      ],
      "repoCount": 20,
      "trashCount": 0,
      "available_actions": [
        { "type": "play_card", "hand_instance_id": "i0001", "card_id": 1, "valid_zones": ["frontend_0", "frontend_1", "frontend_2", "backend_0", "backend_1", "backend_2"] }
      ]
    },
    "opponent": { ... }
  }
}
```

##### `available_actions` — 実行可能アクション一覧（カード操作のみ）

`my` の配下に含まれる。サーバーが毎回の状態更新時にフェーズごとの有効アクションを計算し、クライアントはこれを元に操作可能なカードのハイライトやUI制御を行う（クライアント側にゲームロジックの重複を持たせない設計）。

カードに紐付かないゲームフロー制御（フェーズ終了、手札破棄）は `turn_controls` メッセージで別途通知される。

- **`playing` 状態**: アクティブプレイヤーのみに送信される。対戦相手の `game_state` にはこのフィールドは含まれない。
- **`finished` 状態**: 省略される。

| type | 追加フィールド | 説明 |
|------|--------------|------|
| `play_card` | `hand_instance_id`, `card_id`, `valid_zones?`, `valid_targets?` | 手札からカードをデプロイ。デプロイターン 0 なら即表向き、1以上なら裏向き配置。`valid_zones` はゾーン+スロット (例: `"frontend_0"`)。Attachment の場合は `valid_targets` にリソース ID |
| `attack` | `source_instance_id`, `valid_targets` | フロントの表向き Compute で攻撃。相手フロントに表向きリソースあり→フロントのみ対象 |
| `scale_up` | `source_instance_id`, `target_rank`, `needs_family` | リソースをスケールアップ（無料）。`needs_family=true` なら S→M でファミリー選択が必要 |
| `migrate` | `source_instance_id`, `target_instance_id` | 新リソース(source)から旧リソース(target)へマイグレーション開始。新.deploy_turns >= 旧.deploy_turns が必要 |
| `distribute_yield` | `source_instance_id`, `remaining_capacity` | バックエンド Compute に Insight を配分。`remaining_capacity` は残りスループット |
| `activate_effect` | `source_instance_id`, `effect_target_type`, `valid_targets?` | アクティブ効果を発動。`effect_target_type`: `"none"`, `"choice"`, `"all_opp"`, `"self"` |

#### `turn_controls` — ゲームフロー制御

カードに紐付かないゲームフロー制御を通知する。`game_state` とは別メッセージとして、状態更新のたびにアクティブプレイヤーにのみ送信される。

```json
{
  "type": "turn_controls",
  "data": {
    "can_end_phase": true,
    "discard_required": 0
  }
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `can_end_phase` | boolean | 現在のフェーズを終了できるか（main / battle フェーズで `true`） |
| `discard_required` | int | 手札破棄が必要な枚数（end フェーズで手札 > 6 枚の場合のみ > 0） |

---

#### `game_over` — ゲーム終了
```json
{
  "type": "game_over",
  "data": {
    "game_id": "ULID",
    "winner_num": 1,
    "win_reason": "ko|deck_out|disconnect"
  }
}
```

#### `action_rejected` — アクション拒否
```json
{
  "type": "action_rejected",
  "data": {
    "game_id": "ULID",
    "action_type": "string",
    "reason": "error message"
  }
}
```

#### `stamp_used` — スタンプ受信
```json
{
  "type": "stamp_used",
  "data": {
    "game_id": "ULID",
    "player_id": "uuid",
    "stamp_no": 1
  }
}
```

#### `error` — エラー
```json
{
  "type": "error",
  "data": {
    "error_code": "invalid_message|invalid_data|matchmaking_error|select_error",
    "message": "エラー詳細",
    "retryable": true
  }
}
```

#### `game_state_restore` — 再接続時のゲーム状態復元
```json
{
  "type": "game_state_restore",
  "data": { /* game_state と同じ構造 */ }
}
```

再接続時にサーバーが最新のゲーム状態を送信する。`game_state` と同じ構造だがメッセージタイプで区別できる。再接続時は `turn_controls` も併せて送信される。

---

#### `action_performed` — 対戦相手のアクション通知

対戦相手（NPC または PvP 相手）が実行した個別アクションを通知する。クライアントはこのメッセージをキューに積み、順番にアニメーション再生する。

```json
{
  "type": "action_performed",
  "data": {
    "action_type": "play_card",
    "action_data": {
      "cardInstanceId": "uuid",
      "position": { "zone": "frontend", "index": 0 }
    },
    "state": { /* game_state と同じ構造 (per-player info-hidden) */ }
  }
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `action_type` | string | 実行されたアクション種別 (`play_card`, `attack`, `scale_up`, `activate_effect`, `distribute_yield`, `end_phase`, `discard_hand`, `battle_start`, `turn_start`) |

| `action_data` | object | アクションの詳細データ（アクション種別により構造が異なる） |
| `state` | ClientGameState | アクション実行後のゲーム状態（情報隠蔽適用済み） |

**送信タイミング:**
- **NPC ターン**: `runNPCTurnIfNeeded` 内の各アクション実行後
- **PvP**: 相手プレイヤーのアクション実行後（自分のアクションには送信されない）
- **battle_start**: selecting 完了後、最初の `game_state` より前に送信
- **turn_start**: 各ターン開始時、draw フェーズの `game_state` より前に送信

**クライアント処理フロー:**
1. `action_performed` 受信 → アニメーションキューに追加
2. キューを順番に処理（各アクションにディレイを設けて再生）
3. 最後の `game_state` を ground truth として適用

##### `battle_start` — バトル開始バナー

selecting フェーズ完了後、最初の game_state より前に送信される。各プレイヤーに自分視点の情報が届く。

```json
{
  "type": "action_performed",
  "data": {
    "action_type": "battle_start",
    "action_data": {
      "my_name": "Ken",
      "my_level": 24,
      "opponent_name": "Smile Horizon Express",
      "opponent_level": 50,
      "match_type": "npc"
    },
    "state": { /* ClientGameState */ }
  }
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `my_name` | string | 自分の表示名 |
| `my_level` | int | 自分のレベル |
| `opponent_name` | string | 対戦相手の表示名（NPC の場合は陣営日本語名） |
| `opponent_level` | int | 対戦相手のレベル（NPC は固定 50） |
| `match_type` | string | `"npc"` or `"pvp"` |

NPC 表示名:
| Faction ID | 表示名 |
|------------|--------|
| SHE | Smile Horizon Express |
| Tenki | 天気使い |
| Sugar | しゅがーらぼ |
| Tuners | 調律部 |

##### `turn_start` — ターン開始バナー

各ターン開始時に送信される。draw フェーズの `game_state` より前に届く。

```json
{
  "type": "action_performed",
  "data": {
    "action_type": "turn_start",
    "action_data": {
      "turn": 1,
      "is_my_turn": true
    },
    "state": { /* ClientGameState */ }
  }
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `turn` | int | ターン番号 |
| `is_my_turn` | bool | このプレイヤーのターンかどうか |

**送信順序:**

```
[selecting 完了]
  → action_performed (battle_start)
  → action_performed (turn_start, turn=1)
  → game_state
  → turn_controls

[ターン切り替わり時]
  → action_performed (turn_start, turn=N)
  → game_state
  → turn_controls
```

---

#### `pong`
```json
{ "type": "pong" }
```

---

## 5. Dev API（開発専用）

`/api/dev/` 以下のエンドポイントは認証不要。ローカルモードのみ。

#### POST `/api/dev/games` — テストゲーム作成
```json
// リクエスト
{
  "player1Id": "uuid",
  "player2Id": "uuid",
  "deck1": "npc_deck_name",
  "deck2": "npc_deck_name",
  "firstPlayer": 1
}
// レスポンス
{ "gameId": "ULID" }
```

#### POST `/api/dev/games/{gameId}/select` — 初期配置選択
#### POST `/api/dev/games/{gameId}/action` — アクション実行
#### GET `/api/dev/games/{gameId}/state` — 状態取得
#### GET `/api/dev/cards` — カード一覧

---

## 6. エンドポイント一覧

| カテゴリ | メソッド | パス | 認証 | PlayerResolve | 用途 |
|----------|----------|------|------|---------------|------|
| **Public** | GET | `/health` | 不要 | 不要 | ヘルスチェック |
| | GET | `/version` | 不要 | 不要 | バージョン確認 |
| | GET | `/announcements` | 不要 | 不要 | お知らせ一覧 |
| | GET | `/daily` | 不要 | 不要 | デイリー Tips |
| | GET | `/cloud-news` | 不要 | 不要 | クラウドニュース一覧 |
| **Auth** | POST | `/auth/register` | 要 | 不要 | プレイヤー登録 |
| | POST | `/auth/login` | 要 | 不要 | ログイン |
| **Player** | GET | `/player/settings` | 要 | 要 | ユーザー設定取得 |
| | PUT | `/player/settings` | 要 | 要 | ユーザー設定更新 |
| | GET | `/player` | 要 | 要 | プロフィール取得 |
| | PUT | `/player/name` | 要 | 要 | プレイヤー名変更 |
| | GET | `/player/battle-limit` | 要 | 要 | バトル制限確認 |
| | GET | `/player/cards` | 要 | 要 | 所持カード一覧 |
| **Deck** | GET | `/player/decks` | 要 | 要 | デッキ一覧 |
| | GET | `/player/decks/{deckId}` | 要 | 要 | デッキ詳細 |
| | POST | `/player/decks` | 要 | 要 | デッキ作成 |
| | PUT | `/player/decks/{deckId}` | 要 | 要 | デッキ更新 |
| | DELETE | `/player/decks/{deckId}` | 要 | 要 | デッキ削除 |
| **Card** | GET | `/cards` | 要 | 要 | 全カード定義 |
| **Game Log** | GET | `/games/{gameId}/log` | 要 | 要 | ゲームログ取得 |
| | GET | `/games/{gameId}/log/text` | 要 | 要 | ゲームログ（テキスト） |
| **Spectate** | GET | `/spectate/games` | 要 | 要 | 観戦可能ゲーム一覧 |
| | WS | `spectate_join` | 要 | 要 | 観戦参加（WebSocket） |
| | WS | `spectate_leave` | - | - | 観戦離脱（WebSocket） |
| | WS | `spectate_stamp` | - | - | 観戦スタンプ送信（WebSocket） |
| **NPC** | WS | `npc_battle_start` | 要 | 要 | NPC 対戦開始（WebSocket） |
| | WS | `npc_battle_created` | - | - | NPC 対戦作成通知（Server→Client） |
| **Shop** | POST | `/player/select-faction` | 要 | 要 | ファクション選択 |
| | GET | `/shop/products` | 要 | 要 | 商品一覧 |
| | POST | `/shop/purchase` | 要 | 要 | 商品購入 |
| | POST | `/shop/subscribe` | 要 | 要 | サブスク登録 |
| **Webhook** | POST | `/shop/webhook/apple` | 不要 | 不要 | Apple 通知 |
| | POST | `/shop/webhook/google` | 不要 | 不要 | Google 通知 |
| **WS** | GET | `/ws?token={token}` | 接続時 | 接続時 | WebSocket 接続 |
