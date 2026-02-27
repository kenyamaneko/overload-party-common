# Overload Party - API リファレンス

**Version:** 1.0
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
   - [Game Log](#37-game-log)
   - [Webhook](#38-webhook)
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

以下のエンドポイントは認証が必要（Webhook を除く）。

### 3.1 Auth

#### POST `/auth/register`

新規プレイヤー登録。スターターアイテム（スタンプ 1〜7）が付与される。

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
  "wins": 0,
  "losses": 0,
  "is_premium": false,
  "selected_faction": null,
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
    "illustration_variant": 0,
    "count": 3,
    "card_name": "EC2 Instance",
    "faction": "SWS",
    "card_type": "resource",
    "scalability": "scalable",
    "stats": { "throughput": 3, "availability": 4, "maintenance_cost": 2, "deploy_cost": 3, "sla_penalty": 2 },
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
    "deck_id": 1,
    "deck_name": "My Deck",
    "is_valid": true,
    "playmat_no": 1,
    "sleeve_no": 2,
    "card_nos": [1, 1, 1, 2, 2, 3, 4, 4, 4],
    "created_at": "timestamp",
    "updated_at": "timestamp"
  }
]
```

`card_nos` は DeckCards を card_no × count で展開した配列。

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
      "illustration_variant": 0,
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
    { "card_no": 1, "illustration_variant": 0, "count": 3 },
    { "card_no": 2, "illustration_variant": 0, "count": 2 }
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
    "faction": "SWS|Aozora|Guruguru|Miracle|Neutral",
    "card_type": "resource|support|action",
    "scalability": "scalable|non_scalable|none",
    "stats": {},
    "effect_text": "string",
    "effects": [],
    "passive_effects": [],
    "platform_effects": [],
    "attachment_effects": [],
    "restriction": "unlimited|semi_limited|limited",
    "is_active": true
  }
]
```

---

### 3.5 NPC Battle

#### POST `/npc/battle/start`

NPC 対戦開始。即座にゲームが作成される（マッチメイキング不要）。

**リクエスト:**
```json
{
  "deckId": 1,
  "npcFaction": "SWS|Aozora|Guruguru|Miracle"
}
```

**レスポンス (200):**
```json
{
  "gameId": "ULID",
  "player1Id": "uuid",
  "player2Id": "npc_...",
  "status": "selecting"
}
```

---

#### POST `/npc/battle/{gameId}/select`

初期配置カードの選択。

**リクエスト:**
```json
{
  "frontendCardNo": 1,
  "backendCardNo": 2
}
```

**レスポンス (200):** ゲーム状態オブジェクト

---

#### POST `/npc/battle/{gameId}/action`

ゲームアクションの実行。NPC は自動応答する。

**リクエスト:**
```json
{
  "actionType": "play_card|attack|scale_up|distribute_dv|end_phase|discard_hand|activate_effect",
  "data": { /* アクション固有のデータ */ }
}
```

**アクション別データ:**

| actionType | data |
|---|---|
| `play_card` | `{ "cardInstanceId": "i0001", "position": { "zone": "frontend\|backend\|support", "index": 0-2 }, "targetInstanceId": "i0002?" }` |
| `attack` | `{ "attackerInstanceId": "i0001", "targetInstanceId": "i0002" }` |
| `scale_up` | `{ "componentInstanceId": "i0001", "targetRank": "medium\|large", "instanceFamily": "string?" }` |
| `distribute_dv` | `{ "distributions": [{ "componentInstanceId": "i0001", "amount": 10 }] }` |
| `end_phase` | `{}` |
| `discard_hand` | `{ "cardInstanceIds": ["i0001"] }` |
| `activate_effect` | `{ "instanceId": "i0001", "targetInstanceId": "i0002?" }` |

**レスポンス (200):** ゲーム状態オブジェクト

---

#### GET `/npc/battle/{gameId}/state`

現在のゲーム状態を取得（情報秘匿適用済み）。

**レスポンス (200):** ゲーム状態オブジェクト

---

### 3.6 Shop

#### POST `/player/select-faction`

ファクション選択。対応する初期カードセットが付与される。

**リクエスト:**
```json
{
  "faction": "SWS|Aozora|Guruguru|Miracle"
}
```

**レスポンス (200):**
```json
{
  "message": "faction selected",
  "faction": "SWS",
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

### 3.7 Game Log

#### GET `/games/{gameId}/log`

構造化ゲームログ取得。

**レスポンス (200):**
```json
{
  "game_id": "ULID",
  "events": [
    {
      "game_id": "ULID",
      "sequence_number": 1,
      "event_type": "string",
      "player_id": "uuid",
      "event_data": {},
      "created_at": "timestamp"
    }
  ]
}
```

---

#### GET `/games/{gameId}/log/text`

テキスト形式のゲームログ取得。

**レスポンス (200):** `Content-Type: text/plain`

---

### 3.8 Webhook（認証不要）

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

#### `select_starters` — 初期配置カード選択

```json
{
  "type": "select_starters",
  "data": {
    "game_id": "ULID",
    "frontend_card_no": 1,
    "backend_card_no": 2
  }
}
```

**応答:** `game_state`（両プレイヤーに送信）/ `error` (code: `select_error`)

---

#### `game_action` — ゲームアクション実行

```json
{
  "type": "game_action",
  "data": {
    "game_id": "ULID",
    "action_type": "play_card|attack|scale_up|...",
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
    "currentPhase": "selecting|draw|dv_gen|main|battle|end",
    "activePlayer": 1,
    "isMyTurn": true,
    "my": {
      "playerNum": 1,
      "budget": 5,
      "dvPool": 0,
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
      "dvPool": 0,
      "field": {},
      "handCount": 3,
      "repoCount": 20,
      "trashCount": 0
    }
  }
}
```

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

再接続時にサーバーが最新のゲーム状態を送信する。`game_state` と同じ構造だがメッセージタイプで区別できる。

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
| **Auth** | POST | `/auth/register` | 要 | 不要 | プレイヤー登録 |
| | POST | `/auth/login` | 要 | 不要 | ログイン |
| **Player** | GET | `/player` | 要 | 要 | プロフィール取得 |
| | PUT | `/player/name` | 要 | 要 | プレイヤー名変更 |
| | GET | `/player/battle-limit` | 要 | 要 | バトル制限確認 |
| | GET | `/player/cards` | 要 | 要 | 所持カード一覧 |
| **Deck** | GET | `/player/decks` | 要 | 要 | デッキ一覧 |
| | GET | `/player/decks/{deckId}` | 要 | 要 | デッキ詳細 |
| | POST | `/player/decks` | 要 | 要 | デッキ作成 |
| | PUT | `/player/decks/{deckId}` | 要 | 要 | デッキ更新 |
| | DELETE | `/player/decks/{deckId}` | 要 | 要 | デッキ削除 |
| **Card** | GET | `/cards` | 要 | 要 | 全カード定義 |
| **NPC** | POST | `/npc/battle/start` | 要 | 要 | NPC 対戦開始 |
| | POST | `/npc/battle/{gameId}/select` | 要 | 要 | 初期配置選択 |
| | POST | `/npc/battle/{gameId}/action` | 要 | 要 | アクション実行 |
| | GET | `/npc/battle/{gameId}/state` | 要 | 要 | 状態取得 |
| **Shop** | POST | `/player/select-faction` | 要 | 要 | ファクション選択 |
| | GET | `/shop/products` | 要 | 要 | 商品一覧 |
| | POST | `/shop/purchase` | 要 | 要 | 商品購入 |
| | POST | `/shop/subscribe` | 要 | 要 | サブスク登録 |
| **Log** | GET | `/games/{gameId}/log` | 要 | 要 | ゲームログ (JSON) |
| | GET | `/games/{gameId}/log/text` | 要 | 要 | ゲームログ (テキスト) |
| **Webhook** | POST | `/shop/webhook/apple` | 不要 | 不要 | Apple 通知 |
| | POST | `/shop/webhook/google` | 不要 | 不要 | Google 通知 |
| **WS** | GET | `/ws?token={token}` | 接続時 | 接続時 | WebSocket 接続 |
