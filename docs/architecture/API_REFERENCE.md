# Overload Party - REST API リファレンス

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
   - [Scenario](#36-scenarioストーリー)
   - [Shop](#37-shop)
   - [Webhook](#38-webhook)
4. [Dev API（開発専用）](#4-dev-api開発専用)
5. [エンドポイント一覧](#5-エンドポイント一覧)

WebSocket API リファレンスは [WS_REFERENCE.md](WS_REFERENCE.md) を参照。

---

## 1. 概要

### ベース URL

| 環境 | URL |
|------|-----|
| ローカル | `http://localhost:9001/api/v1/` |
| dev | `https://overloadparty-dev.keyandnotes.com/api/v1/` |
| stg | `https://overloadparty-stg.keyandnotes.com/api/v1/` |
| prod | `https://overloadparty.keyandnotes.com/api/v1/` |

### ヘルスチェック

```
GET /health
```

詳細は [GET /health](#get-health) を参照。

---

## 2. 認証

### 本番環境

- `Authorization: Bearer {Firebase ID Token}` ヘッダー

ミドルウェアが Firebase Token を検証し、`firebase_uid` をコンテキストに設定。
`PlayerResolve` ミドルウェアが `firebase_uid` → `player_id`（UUID）に解決し、コンテキストにセットする。
認証エンドポイント（`/auth/register`, `/auth/login`）は `PlayerResolve` を経由しない（プレイヤー未作成の場合があるため）。

### ローカル開発

- `Authorization: Bearer dev-token-{uid}` ヘッダー
- トークンが空の場合、`uid = "dev-anonymous"` として扱う
- 未登録の uid は **自動でプレイヤーが作成**される

---

## 3. REST API

### 3.0 Public（認証不要）

スプラッシュ画面やバージョンチェックで使用。認証不要。

#### GET `/health`

ヘルスチェック。

**レスポンス (200):**

```jsonc
{
  "status": "string" // サーバーステータス（`ok`）,
  "mode": "string" // 動作モード（`local` / `dev` / `stg` / `prod`）
}
```

---

#### GET `/version`

アプリバージョン確認。

**レスポンス (200):**

<!-- BEGIN GENERATED: VersionResponse -->
```jsonc
{
  "minimumVersion": "string" // 最低要求バージョン,
  "latestVersion": "string" // 最新バージョン,
  "forceUpdate": false // `true` の場合、クライアントはストアへ誘導する,
  "storeUrl": "string" // ストア URL
}
```
<!-- END GENERATED: VersionResponse -->

---

#### GET `/announcements`

お知らせ一覧取得。

**レスポンス (200):** `[Announcement]`

<!-- BEGIN GENERATED: Announcement -->
```jsonc
{
  "id": "string" // お知らせID,
  "title": "string" // タイトル,
  "body": "string" // 本文,
  "type": "string" // 種別（`info` / `warning` / `maintenance`）,
  "published_at": "2006-01-02T15:04:05Z" // 公開日時,
  "expires_at": null // 有効期限
}
```
<!-- END GENERATED: Announcement -->

---

#### GET `/daily`

デイリー Tips 取得。

**レスポンス (200):**

<!-- BEGIN GENERATED: DailyTip -->
```jsonc
{
  "id": "string" // TipID,
  "text": "string" // Tip テキスト
}
```
<!-- END GENERATED: DailyTip -->

---

#### GET `/cloud-news`

クラウドニュース一覧取得。ホーム画面のニュースセクション用。

**クエリパラメータ:**

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `limit` | int | 20 | 取得件数（1-100） |
| `offset` | int | 0 | オフセット |

**レスポンス (200):** `[NewsArticle]`

<!-- BEGIN GENERATED: NewsArticle -->
```jsonc
{
  "article_id": "string" // 記事 ULID,
  "source": "string" // ソース（`aws` / `google-cloud` / `azure` / `oci` / `other`）,
  "title": "string" // 記事タイトル,
  "summary": null // AI 要約（未完了の場合 null）,
  "tags": [] // タグ配列,
  "published_at": null // 記事の公開日時,
  "fetched_at": "2006-01-02T15:04:05Z" // 取得日時
}
```
<!-- END GENERATED: NewsArticle -->

---

以下のエンドポイントは認証が必要（Webhook を除く）。

### 3.1 Auth

#### POST `/auth/register`

新規プレイヤー登録。スターターアイテム（スタンプ 1〜7）とデフォルトユーザー設定（language: `ja`）が作成される。

**リクエスト:**

<!-- BEGIN GENERATED: RegisterRequest -->
```jsonc
{
  "username": "string" // ユーザー名（1〜50文字）
}
```
<!-- END GENERATED: RegisterRequest -->

**レスポンス (201):**

<!-- BEGIN GENERATED: PlayerResponse -->
```jsonc
{
  "player_id": "string" // プレイヤーID（UUID）,
  "firebase_uid": "string" // Firebase UID,
  "username": "string" // ユーザー名,
  "level": 0 // プレイヤーレベル,
  "exp": 0 // 累計経験値,
  "is_premium": false // プレミアム会員か,
  "equipped_icon_no": null // 装備中のアイコン番号,
  "selected_faction": null // 選択済みファクション,
  "premium_expires_at": null // プレミアム有効期限,
  "created_at": "2006-01-02T15:04:05Z" // 登録日時,
  "updated_at": "2006-01-02T15:04:05Z" // 最終更新日時,
  "level_exp_current": 0 // 現在レベル内の経験値,
  "level_exp_required": 0 // 次レベルまでの必要経験値
}
```
<!-- END GENERATED: PlayerResponse -->

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

<!-- BEGIN GENERATED: UserSettings -->
```jsonc
{
  "player_id": "string" // プレイヤーID,
  "language": "string" // 言語（`ja` / `en`）,
  "bgm_volume": 0 // BGM 音量（0-100）,
  "se_volume": 0 // SE 音量（0-100）,
  "push_enabled": false // プッシュ通知の有効/無効,
  "updated_at": "2006-01-02T15:04:05Z" // 最終更新日時
}
```
<!-- END GENERATED: UserSettings -->

---

#### PUT `/player/settings`

ユーザー設定更新。

**リクエスト:**

<!-- BEGIN GENERATED: UpdateSettingsRequest -->
```jsonc
{
  "language": "string" // 言語（`ja` / `en`）,
  "bgm_volume": 0 // BGM 音量（0-100）,
  "se_volume": 0 // SE 音量（0-100）,
  "push_enabled": false // プッシュ通知の有効/無効
}
```
<!-- END GENERATED: UpdateSettingsRequest -->

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

<!-- BEGIN GENERATED: PlayerNameRequest -->
```jsonc
{
  "name": "string" // 新しいプレイヤー名
}
```
<!-- END GENERATED: PlayerNameRequest -->

**レスポンス (200):** Player オブジェクト

**エラー:**
- `400` リクエスト不正（`name` フィールド欠落）
- `500` サーバーエラー

---

#### GET `/player/battle-limit`

デイリーバトル回数の確認。

**レスポンス (200):**

<!-- BEGIN GENERATED: BattleLimitResponse -->
```jsonc
{
  "daily_battle_count": 0 // 本日のバトル回数,
  "daily_battle_limit": 0 // デイリーバトル上限（`-1` で無制限 = プレミアム会員）,
  "can_battle": false // バトル可能か
}
```
<!-- END GENERATED: BattleLimitResponse -->

`daily_battle_limit` が `-1` の場合は無制限（プレミアム会員）。

---

#### GET `/player/cards`

所持カード一覧取得。カード定義を含む enriched レスポンスを返す。

**レスポンス (200):** `[PlayerCardWithDef]`

<!-- BEGIN GENERATED: PlayerCardWithDef -->
```jsonc
{
  "card_id": "string" // カードID,
  "art_no": 0 // アート番号,
  "count": 0 // 所持枚数,
  "card_name": "string" // カード名,
  "resource_label": "string" // リソースラベル（AWS/Azure/GCP/Oracle のサービス名）,
  "faction": "string" // ファクション（`SHE` / `Tenki` / `Sugar` / `Tuners` / `Neutral`）,
  "card_type": "string" // カード種別,
  "deploy_turns": 0 // デプロイターン数（0=即時）,
  "resizable": false // 手動スケール可能か,
  "elastic": false // 自動スケール対応か,
  "stats": {} // スタッツ（ComputeStats または DataStats）,
  "effect_text": null // エフェクト説明テキスト,
  "restriction": "string" // 制限（`unlimited` / `semi_limited` / `limited` / `forbidden`）
}
```
<!-- END GENERATED: PlayerCardWithDef -->

---

### 3.3 Deck

#### GET `/player/decks`

デッキ一覧取得。

**レスポンス (200):** `[Deck]`

<!-- BEGIN GENERATED: Deck -->
```jsonc
{
  "deck_id": 0 // デッキID（自動採番）,
  "deck_name": "string" // デッキ名,
  "is_valid": false // バトル使用可能か（都度算出: 30枚 + 全カード所持 + 制限枚数以内）,
  "playmat_no": null // プレイマット番号（null: デフォルト）,
  "sleeve_no": null // スリーブ番号（null: デフォルト）,
  "deck_cards": [] // デッキのカード構成（`card_id`, `art_no`, `count`）
}
```
<!-- END GENERATED: Deck -->

> **Note:** `is_valid` は DB に保存せず、リクエストごとにサーバーが算出する。所持カードの変動や制限改定を即座に反映するため。


---

#### GET `/player/decks/{deckId}`

デッキ詳細取得。

**レスポンス (200):**

<!-- BEGIN GENERATED: DeckDetailResponse -->
```jsonc
{
  "deck": "Deck" // デッキ本体,
  "cards": [] // デッキ内のカード一覧
}
```
<!-- END GENERATED: DeckDetailResponse -->

---

#### POST `/player/decks`

デッキ作成。

**リクエスト:**

<!-- BEGIN GENERATED: DeckCreateRequest -->
```jsonc
{
  "deck_name": "string" // デッキ名,
  "cards": [] // デッキのカード構成,
  "playmat_no": null // プレイマット番号,
  "sleeve_no": null // スリーブ番号
}
```
<!-- END GENERATED: DeckCreateRequest -->

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

**レスポンス (200):** `[CardDefinition]`

CardDefinition の詳細は PlayerCardWithDef と同構造（+ `effects`, `passive_effects`, `platform_effects`, `attachment_effects`, `is_active`, `created_at`, `updated_at`）。

---

### 3.5 NPC Battle

#### GET `/npc/models`

NPC モデル一覧取得。Gateway が Battle Server の内部 API にプロキシする。

**レスポンス (200):** `{ "models": [NpcModel] }`

<!-- BEGIN GENERATED: NpcModel -->
```jsonc
{
  "model": "string" // NPC モデル ID。`npc_battle_start` で使用する,
  "faction": "string" // ファクション名,
  "difficulty": "string" // 難易度（`easy` / `hard`）,
  "display_name": "string" // NPC の表示名
}
```
<!-- END GENERATED: NpcModel -->

**内部 API:** Gateway → Battle `GET http://battle:9002/api/v1/npc/models`

---

NPC 対戦の開始は WebSocket で行う。詳細は [WS_REFERENCE.md の npc_battle_start](WS_REFERENCE.md#npc_battle_start--npc-対戦開始) を参照。

---

### 3.6 Scenario（ストーリー）

#### GET `/scenarios`

シナリオエピソード一覧取得。各エピソードのアンロック状態・完了状態を含む。

**クエリパラメータ:**

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `lang` | string | `ja` | タイトル言語（`ja` / `en`） |

**レスポンス (200):** `{ "episodes": [EpisodeWithStatus] }`

<!-- BEGIN GENERATED: EpisodeWithStatus -->
```jsonc
{
  "episode_id": "string" // エピソードID,
  "faction": null // ファクション名,
  "episode_number": 0 // エピソード番号,
  "title": "string" // エピソードタイトル,
  "thumbnail_url": null // サムネイル画像 URL,
  "is_unlocked": false // アンロック済みか,
  "is_completed": false // クリア済みか,
  "lock_reasons": [] // 未達のアンロック条件（アンロック済みの場合は空配列）
}
```
<!-- END GENERATED: EpisodeWithStatus -->

**`lock_reasons`:** 未達のアンロック条件を全て返す配列。アンロック済みの場合は空配列。

<!-- BEGIN GENERATED: LockReason -->
```jsonc
{
  "type": "string" // 条件種別（`level` / `faction` / `episode`）,
  "required": null // 必要値（種別により型が異なる）,
  "current": null // 現在値（`level` の場合のみ）
}
```
<!-- END GENERATED: LockReason -->

`lock_reasons` の例:

```json
[{ "type": "level", "required": 6, "current": 2 }]
[{ "type": "faction", "required": "SHE" }]
[{ "type": "episode", "required": "she_ep5" }, { "type": "episode", "required": "tenki_ep5" }]
```

---

#### GET `/scenarios/{episodeId}/script`

エピソードのスクリプト（`.ks` 形式）を取得。アンロック済みのエピソードのみ取得可能。

**クエリパラメータ:**

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `lang` | string | `ja` | スクリプト言語（`ja` / `en`、未対応言語は `ja` にフォールバック） |

**レスポンス (200):**

<!-- BEGIN GENERATED: ScenarioScriptResponse -->
```jsonc
{
  "episode_id": "string" // エピソードID,
  "script": "string" // スクリプト（`.ks` 形式）
}
```
<!-- END GENERATED: ScenarioScriptResponse -->

**エラー:** `404` エピソードが存在しない / `403` ロック中

---

#### POST `/scenarios/{episodeId}/complete`

エピソードの完了を記録。冪等（同じエピソードを複数回完了してもエラーにならない）。

**リクエスト:** なし

**レスポンス (200):**

<!-- BEGIN GENERATED: ScenarioCompleteResponse -->
```jsonc
{
  "message": "string" // 結果メッセージ,
  "episode_id": "string" // エピソードID
}
```
<!-- END GENERATED: ScenarioCompleteResponse -->

**エラー:** `404` エピソードが存在しない / `403` ロック中

---

### 3.7 Shop

> **注:** 旧番号 3.6。ストーリーセクション追加に伴い 3.7 に繰り下げ。

#### POST `/player/select-faction`

ファクション選択。対応する初期カードセットが付与される。

**リクエスト:**

<!-- BEGIN GENERATED: SelectFactionRequest -->
```jsonc
{
  "faction": "string" // ファクション（`SHE` / `Tenki` / `Sugar` / `Tuners`）
}
```
<!-- END GENERATED: SelectFactionRequest -->

**レスポンス (200):**

<!-- BEGIN GENERATED: SelectFactionResponse -->
```jsonc
{
  "message": "string" // 結果メッセージ,
  "faction": "string" // 選択されたファクション,
  "cards_granted": 0 // 付与されたカード枚数
}
```
<!-- END GENERATED: SelectFactionResponse -->

**エラー:** `400` 不正なファクション / `409` 選択済み

---

#### GET `/shop/products`

商品一覧取得。プレイヤーIDは認証トークンから自動解決される。

**レスポンス (200):** `{ "products": [ProductResponse] }`

<!-- BEGIN GENERATED: ProductResponse -->
```jsonc
{
  "product_id": "string" // 商品ID,
  "name": "string" // 商品名,
  "type": "string" // 商品種別（`faction_set` / `cosmetic` / `subscription`）,
  "price": 0 // 価格（円）,
  "content": {} // 商品内容（種別により構造が異なる）,
  "description": null // 商品説明,
  "image_url": null // 商品画像 URL,
  "is_active": false // 販売中か,
  "is_owned": false // 購入済みか
}
```
<!-- END GENERATED: ProductResponse -->

---

#### POST `/shop/purchase`

商品購入。

**リクエスト:**

<!-- BEGIN GENERATED: PurchaseRequest -->
```jsonc
{
  "product_id": "string" // 商品ID,
  "platform": "string" // プラットフォーム（`ios` / `android`）,
  "purchase_token": "string" // 購入トークン
}
```
<!-- END GENERATED: PurchaseRequest -->

**レスポンス (200):**

<!-- BEGIN GENERATED: PurchaseResponse -->
```jsonc
{
  "message": "string" // 結果メッセージ,
  "product_id": "string" // 購入した商品ID
}
```
<!-- END GENERATED: PurchaseResponse -->

---

#### POST `/shop/subscribe`

サブスクリプション登録。

**リクエスト:**

```jsonc
{
  "product_id": "string" // 商品ID,
  "platform": "string" // プラットフォーム（`ios` / `android`）,
  "purchase_token": "string" // 購入トークン
}
```

**レスポンス (200):**

<!-- BEGIN GENERATED: SubscribeResponse -->
```jsonc
{
  "message": "string" // 結果メッセージ,
  "expires_at": "2006-01-02T15:04:05Z" // サブスクリプション有効期限
}
```
<!-- END GENERATED: SubscribeResponse -->

---

### 3.8 Webhook（認証不要）

#### POST `/shop/webhook/apple`

Apple In-App Purchase のサーバー通知。

**リクエスト:**

```jsonc
{
  "signedPayload": "string" // Apple JWS トークン
}
```

---

#### POST `/shop/webhook/google`

Google Play Billing のサーバー通知。

**リクエスト:**

```jsonc
{
  "message": "string" // Base64 エンコードされた通知データを含む JSON オブジェクト
}
```

---

## 4. Dev API（開発専用）

`/api/dev/` 以下のエンドポイントは認証不要。ローカルモードのみ。

| メソッド | パス | 用途 |
|----------|------|------|
| POST | `/api/dev/games` | テストゲーム作成（`player1Id`, `player2Id`, `deck1`, `deck2`, `firstPlayer`） |
| POST | `/api/dev/games/{gameId}/select` | 初期配置選択 |
| POST | `/api/dev/games/{gameId}/action` | アクション実行 |
| GET | `/api/dev/games/{gameId}/state` | 状態取得 |
| GET | `/api/dev/cards` | カード一覧 |

---

## 5. エンドポイント一覧

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
| **NPC** | GET | `/npc/models` | 要 | 要 | NPC モデル一覧 |
| **Scenario** | GET | `/scenarios` | 要 | 要 | エピソード一覧 |
| | GET | `/scenarios/{episodeId}/script` | 要 | 要 | スクリプト取得 |
| | POST | `/scenarios/{episodeId}/complete` | 要 | 要 | エピソード完了 |
| **Shop** | POST | `/player/select-faction` | 要 | 要 | ファクション選択 |
| | GET | `/shop/products` | 要 | 要 | 商品一覧 |
| | POST | `/shop/purchase` | 要 | 要 | 商品購入 |
| | POST | `/shop/subscribe` | 要 | 要 | サブスク登録 |
| **Webhook** | POST | `/shop/webhook/apple` | 不要 | 不要 | Apple 通知 |
| | POST | `/shop/webhook/google` | 不要 | 不要 | Google 通知 |
