# Overload Party - API リファレンス

**Version:** 1.0
**Last Updated:** 2026-02-26

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
WS ハンドラは `FindByFirebaseUID` で PlayerID（UUID）に解決する。

### ローカル開発

- REST API: `Authorization: Bearer dev-token-{uid}` ヘッダー
- WebSocket: `GET /ws?token=dev-token-{uid}` クエリパラメータ（空でも可）
- トークンが空の場合、`uid = "dev-anonymous"` として扱う
- 未登録の uid は **自動でプレイヤーが作成**される

---

## 3. REST API

全エンドポイントに認証が必要（Webhook を除く）。

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

#### GET `/players/{id}`

プレイヤー情報取得。

**レスポンス (200):** Player オブジェクト

**エラー:** `404` プレイヤーが見つからない

---

#### GET `/players/{id}/battle-limit`

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

#### GET `/players/{id}/cards`

所持カード一覧取得。`(card_no, illustration_variant)` ごとに count で管理。

**レスポンス (200):**
```json
[
  {
    "player_id": "uuid",
    "card_no": 1,
    "illustration_variant": 0,
    "count": 3
  }
]
```

---

### 3.3 Deck

#### GET `/players/{id}/decks`

デッキ一覧取得。

**レスポンス (200):**
```json
[
  {
    "player_id": "uuid",
    "deck_id": "uuid",
    "deck_name": "My Deck",
    "is_valid": true,
    "playmat_no": 1,
    "sleeve_no": 2,
    "created_at": "timestamp",
    "updated_at": "timestamp"
  }
]
```

---

#### GET `/players/{id}/decks/{deckId}`

デッキ詳細取得。

**レスポンス (200):**
```json
{
  "deck": { /* Deck オブジェクト */ },
  "cards": [
    {
      "player_id": "uuid",
      "deck_id": "uuid",
      "card_no": 1,
      "illustration_variant": 0,
      "count": 3
    }
  ]
}
```

---

#### POST `/players/{id}/decks`

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

#### PUT `/players/{id}/decks/{deckId}`

デッキ更新。リクエスト/レスポンスは POST と同じ。

---

#### DELETE `/players/{id}/decks/{deckId}`

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
    "faction": "sws|aozora|guruguru|miracle|neutral",
    "card_type": "Compute|Support|Resource|Attachment",
    "scalability": "R|RE|",
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
  "deckId": "uuid",
  "npcFaction": "sws|aozora|guruguru|miracle"
}
```

**レスポンス (200):**
```json
{
  "gameId": "uuid",
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
| `play_card` | `{ "cardInstanceId": "uuid", "position": { "zone": "frontend\|backend\|support", "index": 0-2 }, "targetInstanceId": "uuid?" }` |
| `attack` | `{ "attackerInstanceId": "uuid", "targetInstanceId": "uuid" }` |
| `scale_up` | `{ "componentInstanceId": "uuid", "targetRank": "small\|medium\|large" }` |
| `distribute_dv` | `{ "distribution": [{ "targetInstanceId": "uuid", "amount": 10 }] }` |
| `end_phase` | `{}` |
| `discard_hand` | `{ "selectedCardInstanceIds": ["uuid"] }` |
| `activate_effect` | `{ "cardInstanceId": "uuid", "effectIndex": 0, "targetInstanceId": "uuid?" }` |

**レスポンス (200):** ゲーム状態オブジェクト

---

#### GET `/npc/battle/{gameId}/state`

現在のゲーム状態を取得（情報秘匿適用済み）。

**レスポンス (200):** ゲーム状態オブジェクト

---

### 3.6 Shop

#### POST `/players/{id}/select-faction`

ファクション選択。対応する初期カードセットが付与される。

**リクエスト:**
```json
{
  "faction": "sws|aozora|guruguru|miracle"
}
```

**レスポンス (200):**
```json
{
  "message": "faction selected",
  "faction": "sws",
  "cards_granted": 59
}
```

**エラー:** `400` 不正なファクション / `409` 選択済み

---

#### GET `/shop/products?player_id={playerId}`

商品一覧取得。

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

#### POST `/shop/purchase?player_id={playerId}`

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

#### POST `/shop/subscribe?player_id={playerId}`

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
  "game_id": "uuid",
  "events": [
    {
      "game_id": "uuid",
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
  "data": { "deck_id": "uuid" }
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
  "data": { "game_id": "uuid", "deck_id": "uuid" }
}
```

**応答:** `game_entered` → `game_state`（両プレイヤーに送信）

---

#### `select_starters` — 初期配置カード選択

```json
{
  "type": "select_starters",
  "data": {
    "game_id": "uuid",
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
    "game_id": "uuid",
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
  "data": { "game_id": "uuid", "stamp_no": 1 }
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
    "game_id": "uuid",
    "player1_id": "uuid",
    "player2_id": "uuid"
  }
}
```

#### `game_entered`
```json
{
  "type": "game_entered",
  "data": { "game_id": "uuid" }
}
```

#### `game_state` — ゲーム状態（情報秘匿適用済み）
```json
{
  "type": "game_state",
  "data": {
    "gameId": "uuid",
    "currentTurn": 1,
    "currentPhase": "selecting|draw|dv_gen|action|end",
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
        { "instanceId": "uuid", "cardId": 1, "cardNo": 1 }
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
    "game_id": "uuid",
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
    "game_id": "uuid",
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
    "game_id": "uuid",
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
{ "gameId": "uuid" }
```

#### POST `/api/dev/games/{gameId}/select` — 初期配置選択
#### POST `/api/dev/games/{gameId}/action` — アクション実行
#### GET `/api/dev/games/{gameId}/state` — 状態取得
#### GET `/api/dev/cards` — カード一覧

---

## 6. エンドポイント一覧

| カテゴリ | メソッド | パス | 認証 | 用途 |
|----------|----------|------|------|------|
| **Auth** | POST | `/auth/register` | 要 | プレイヤー登録 |
| | POST | `/auth/login` | 要 | ログイン |
| **Player** | GET | `/players/{id}` | 要 | プロフィール取得 |
| | GET | `/players/{id}/battle-limit` | 要 | バトル制限確認 |
| | GET | `/players/{id}/cards` | 要 | 所持カード一覧 |
| **Deck** | GET | `/players/{id}/decks` | 要 | デッキ一覧 |
| | GET | `/players/{id}/decks/{deckId}` | 要 | デッキ詳細 |
| | POST | `/players/{id}/decks` | 要 | デッキ作成 |
| | PUT | `/players/{id}/decks/{deckId}` | 要 | デッキ更新 |
| | DELETE | `/players/{id}/decks/{deckId}` | 要 | デッキ削除 |
| **Card** | GET | `/cards` | 要 | 全カード定義 |
| **NPC** | POST | `/npc/battle/start` | 要 | NPC 対戦開始 |
| | POST | `/npc/battle/{gameId}/select` | 要 | 初期配置選択 |
| | POST | `/npc/battle/{gameId}/action` | 要 | アクション実行 |
| | GET | `/npc/battle/{gameId}/state` | 要 | 状態取得 |
| **Shop** | POST | `/players/{id}/select-faction` | 要 | ファクション選択 |
| | GET | `/shop/products` | 要 | 商品一覧 |
| | POST | `/shop/purchase` | 要 | 商品購入 |
| | POST | `/shop/subscribe` | 要 | サブスク登録 |
| **Log** | GET | `/games/{gameId}/log` | 要 | ゲームログ (JSON) |
| | GET | `/games/{gameId}/log/text` | 要 | ゲームログ (テキスト) |
| **Webhook** | POST | `/shop/webhook/apple` | 不要 | Apple 通知 |
| | POST | `/shop/webhook/google` | 不要 | Google 通知 |
| **WS** | GET | `/ws?token={token}` | 接続時 | WebSocket 接続 |
