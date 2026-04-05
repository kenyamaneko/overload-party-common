# Overload Party - Battle Server 内部 API リファレンス

Gateway Server が Battle Server に対して呼び出す内部 HTTP API の仕様。**サーバー間の内部契約**であり、クライアントからは直接呼ばない。

パブリック REST API は [API_REFERENCE.md](API_REFERENCE.md)、WebSocket API は [WS_REFERENCE.md](WS_REFERENCE.md) を参照。

---

## 目次

1. [概要](#1-概要)
2. [共通レスポンス型](#2-共通レスポンス型)
3. [エンドポイント](#3-エンドポイント)
   - [Health](#31-health)
   - [NPC](#32-npc)
   - [Game 作成](#33-game-作成)
   - [Game アクション](#34-game-アクション)
   - [Game 状態取得](#35-game-状態取得)
   - [Game ログ（リプレイ）](#36-game-ログリプレイ)
4. [エンドポイント一覧](#4-エンドポイント一覧)
5. [契約の管理](#5-契約の管理)

---

## 1. 概要

### ベース URL

| 環境 | URL |
|------|-----|
| ローカル | `http://localhost:9002/api/v1/` |
| Kubernetes | `http://battle:9002/api/v1/` |

### 認証

Battle Server は認証を行わない。同一 Pod / 同一 Namespace 内の Gateway からの呼び出しのみを信頼する（ネットワーク層で保護）。

### シリアライズ規約

- **Content-Type:** `application/json`
- **Enum:** 文字列（snake_case）でシリアライズされる（例: `Rank.Small` → `"small"`）
- **エラー:** 非 200 系は `{"error": "message"}` 形式の JSON を返す

#### キー命名規約（3 層構造）

プロジェクト全体の JSON wire format は 3 層に分かれており、それぞれ異なる命名規約を採用している:

| レイヤ | 対象 | 命名 | SSoT |
|---|---|---|---|
| **A. Envelope** | REST/WS の封筒・リクエストボディ・レスポンスラッパー（`ActionResult`, `ActionEvent`, `GameCreatedResult`, `TurnControlsMessage` 等） | **snake_case** | `common/data/models.yaml` |
| **B. Payload** | `state` 配下の `ClientGameState` とその内部型（`PlayerView`, `Field` 等） | **camelCase** | `common/data/models.yaml` の `game_state_view` セクション |
| **C. Action data** | `data` 配下のアクション固有ペイロード（`PlayCardRequest` 等の中身） | **camelCase** | `common/data/event_schemas.yaml` |

各レイヤは別々の JSON シリアライズ設定で実現されている:
- **レイヤ A:** Battle 側は anonymous type のフィールド名を snake_case で直書き、または C# record に `[JsonPropertyName("snake_case")]` を付与。Gateway 側は Go struct の `json:"snake_case"` タグで送受信
- **レイヤ B:** Battle 側は C# PascalCase プロパティを定義し、ASP.NET Core Minimal API の Web defaults（`JsonNamingPolicy.CamelCase`）で自動変換（例: `GameID` → `"gameID"`）
- **レイヤ C:** Battle 側は `ActionDataDeserializer` で専用の `JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase }` を適用

### エラーレスポンス

| ステータス | 意味 | Battle 側の送出契機 |
|---|---|---|
| `200 OK` | 成功 | 正常処理 |
| `400 Bad Request` | ゲームルール違反 | `GameRuleException` をキャッチ（ゲーム未発見・不正な操作・ルール違反等） |
| `404 Not Found` | リソース未発見 | ゲームログ系で対象が存在しない場合 |
| `500 Internal Server Error` | 予期しないエラー | それ以外の例外 |

エラー本文:

```jsonc
{
  "error": "string" // エラーメッセージ（ログ出力・Gateway 側で透過表示される）
}
```

Gateway 側は `parseBattleError` で `error` フィールドを抽出し、ログ出力およびクライアント向けの `action_rejected` 等に変換する。

---

## 2. 共通レスポンス型

### ActionResult

アクション処理系のエンドポイント（`POST /games/{gameId}/actions`, `POST /games/{gameId}/advance-npc`）の共通レスポンス。

```jsonc
{
  "game_over": false,            // ゲーム終了フラグ
  "winner_num": 0,               // 勝者プレイヤー番号（1 or 2、未終了時は 0）
  "win_reason": "budget_zero",   // 終了理由（WinReasons enum の文字列、未終了時は空文字）
  "npc_pending": false,          // true の場合、Gateway は `/advance-npc` を呼んで次の NPC アクションを取得する
  "events": [ /* ActionEvent[] */ ]
}
```

`win_reason` の値は GameData パッケージの [`WinReasons`](../../packages/gamedata-dotnet/GameConstants_gen.cs) を参照。

### ActionEvent

アクション処理によって生成された 1 イベント。

```jsonc
{
  "sequence": 42,                // イベントシーケンス番号（game 単位で単調増加）
  "event_type": "play_card",     // EventTypes enum の文字列
  "player_id": "uuid-or-empty",  // 当該イベントを起こしたプレイヤーID（system event では空文字）
  "is_system": false,            // システム生成イベントかどうか（turn_start 等は true）
  "event_data": { /* ... */ },   // イベント固有ペイロード（event_type ごとに形状が異なる）
  "state": { /* ... */ } | null  // NPC アクションの場合のみ中間 state スナップショット
}
```

### state フィールドの埋まり方（重要）

`state` フィールドは JSON 上常にキーとして含まれるが、値は誰のアクションによって生成されたイベントかで変わる。Gateway 側のルーティングは `is_system` を一次キー、`player_id` を二次キーにして判定する:

| イベントの発生元 | `is_system` | `player_id` | `state` の値 | Gateway 側の処理 |
|---|---|---|---|---|
| **system event**（`turn_start`） | `true` | `""` | `null` | 全プレイヤーに送信、`state` は `GET /games/{gameId}/state/{playerId}` で都度フェッチ |
| **人間プレイヤーのアクション** | `false` | プレイヤー UUID | `null` | 相手プレイヤー視点で `state` を都度フェッチして送信 |
| **NPC のアクション** | `false` | `""`（NPC はプレイヤーID を持たない） | 中間 state スナップショット（人間プレイヤー視点） | そのまま中継（逐次アニメーションのため） |

NPC イベントと system event は共に `player_id == ""` となるため、`player_id` だけでは両者を区別できない。`is_system` フラグはこの曖昧さを解消するためのもの。

`event_type` の値は GameData パッケージの [`EventTypes`](../../packages/gamedata-dotnet/GameConstants_gen.cs) を参照。

`event_data` の詳細スキーマは `event_type` ごとに異なり、GameData パッケージの `EventDataMap` 型に対応する。

### GameCreatedResult

ゲーム作成系エンドポイントの共通レスポンス。

```jsonc
{
  "game_id": "uuid",
  "player1_id": "uuid",
  "player2_id": "uuid"  // NPC 対戦時は空文字
}
```

`POST /games/npc` のみ追加で `npc1_model` / `npc2_model` を返す。

---

## 3. エンドポイント

### 3.1 Health

#### GET `/health`

ヘルスチェック。`/api/v1` プレフィックスを含まない。

**レスポンス (200):**

```jsonc
{ "status": "ok" }
```

---

### 3.2 NPC

#### GET `/api/v1/npc/models`

利用可能な NPC モデル一覧。Gateway の `GET /api/v1/npc/models` はこれをプロキシする。

**レスポンス (200):**

```jsonc
{
  "models": [
    {
      "model": "blue_easy",       // NPC モデル ID
      "faction": "blue",          // ファクション名
      "difficulty": "easy",       // 難易度（model から faction を除いた接尾辞）
      "display_name": "BLUE EASY" // NPC の表示名
    }
  ]
}
```

---

### 3.3 Game 作成

#### POST `/api/v1/games/npc`

NPC 対戦を作成する。作成後、Battle 側で `RunAutoAdvance`（ドローフェーズ自動進行）まで実行される。

**リクエスト:**

```jsonc
{
  "player_id": "uuid",      // 人間プレイヤーID
  "deck_id": 123,           // デッキID（int64）
  "cards": [                // デッキスナップショット
    { "card_id": "card_001", "art_no": 1 }
  ],
  "npc_model": "blue_easy"  // NPC モデルID（/npc/models から取得）
}
```

**レスポンス (200):**

```jsonc
{
  "game_id": "uuid",
  "player1_id": "uuid",     // 人間プレイヤーID（リクエストの player_id）
  "player2_id": "",         // NPC 側は空文字
  "npc1_model": null,
  "npc2_model": "blue_easy"
}
```

**備考:**
- どちらのスロット（Player1 / Player2）が NPC になるかは設計上不定。現状の実装では Player2 固定だが、将来的に Player1 NPC や両方 NPC の実験用対戦もサポート予定。クライアント / Gateway 側は `npc1_model` / `npc2_model` を見てスロットを判別すること（片方だけ埋まる場合・両方埋まる場合がありうる）
- 先攻プレイヤー（1 or 2）は `Random.Shared.Next(2)` でランダム決定される（NPC スロット決定とは独立）

**エラー:**
- `400`: デッキが空 / NPC モデルID が未登録

---

#### POST `/api/v1/games/pvp`

PvP ゲームを作成する。マッチメイキング成立後に Gateway が呼び出す。

**リクエスト:**

```jsonc
{
  "player1_id": "uuid",
  "player1_deck_id": 123,
  "player1_cards": [ { "card_id": "card_001", "art_no": 1 } ],
  "player2_id": "uuid",
  "player2_deck_id": 456,
  "player2_cards": [ { "card_id": "card_002", "art_no": 1 } ]
}
```

**レスポンス (200):** `GameCreatedResult`（`player2_id` も埋まる）

**エラー:**
- `400`: デッキ不正等

---

### 3.4 Game アクション

#### POST `/api/v1/games/{gameId}/actions`

人間プレイヤーのアクションを処理する。アクション実行後、相手が NPC であれば引き続き NPC ループも実行され、その結果イベントが同じレスポンスに含まれる。

**パスパラメータ:**
- `gameId`: ゲームID

**リクエスト:**

```jsonc
{
  "player_id": "uuid",          // アクションを起こしたプレイヤーID
  "action_type": "play_card",   // ActionTypes enum の文字列
  "data": { /* ... */ }         // アクション固有ペイロード（レイヤ C: camelCase、action_type ごとに形状が異なる）
}
```

`ActionType` の値は GameData パッケージの [`ActionTypes`](../../packages/gamedata-dotnet/GameConstants_gen.cs) を参照。

**レスポンス (200):** `ActionResult`

- イベントは時系列順で並ぶ（human アクション由来 → NPC アクション由来）
- `state` フィールドの埋まり方は [state フィールドの埋まり方](#state-フィールドの埋まり方重要) を参照

**エラー:**
- `400`: ゲームルール違反（`GameRuleException` 由来）
- `500`: その他の予期しない例外

---

#### POST `/api/v1/games/{gameId}/advance-npc`

NPC ターンを進める。人間プレイヤーがゲームに `game_enter` した直後、NPC が先攻だった場合に呼び出される。NPC アクションイベントを WebSocket で逐次配信するため必要。

**パスパラメータ:**
- `gameId`: ゲームID

**リクエスト:**

```jsonc
{
  "player_id": "uuid"  // 人間プレイヤーID（state の視点決定に使う）
}
```

**レスポンス (200):** `ActionResult`

- NPC ターンが不要な場合は `events: []` を返す
- 含まれるイベントはすべて NPC 由来なので、各 `state` が埋まる

**備考:** アクティブプレイヤーが人間の場合は何もせず空のイベント配列を返す。

---

### 3.5 Game 状態取得

#### GET `/api/v1/games/{gameId}/state/{playerId}`

指定プレイヤー視点の `ClientGameState` を返す。非公開情報（相手の手札内容等）はマスクされる。

**パスパラメータ:**
- `gameId`: ゲームID
- `playerId`: 視点となるプレイヤーID

**レスポンス (200):** `ClientGameState`（GameData パッケージで定義）

Gateway 側では `json.RawMessage` として受け取り、変換せずクライアントにパススルーする。

**エラー:**
- `400`: `playerId` がゲームに含まれない等
- `404`: ゲームが存在しない（`null` が返るケースもある）

---

#### GET `/api/v1/games/{gameId}/controls/{playerId}`

指定プレイヤーのターン制御情報を返す。自分のターンでない場合は `null`。

**パスパラメータ:**
- `gameId`: ゲームID
- `playerId`: 視点となるプレイヤーID

**レスポンス (200):** `TurnControlsMessage` または `null`

```jsonc
{
  "can_end_phase": true,
  "discard_required": 0
}
```

`null` が返った場合、Gateway 側は nil として扱い、WS メッセージを送信しない。

---

### 3.6 Game ログ（リプレイ）

#### GET `/api/v1/games/{gameId}/log`

ゲームログ（リプレイ）を JSON で返す。

**パスパラメータ:**
- `gameId`: ゲームID

**レスポンス (200):** `application/json`（GameLog オブジェクト）

**エラー:**
- `404`: ゲームが存在しない

---

#### GET `/api/v1/games/{gameId}/log/text`

ゲームログをテキスト形式で返す（人間可読）。

**レスポンス (200):** `text/plain`

**エラー:**
- `404`: ゲームが存在しない

---

## 4. エンドポイント一覧

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/health` | ヘルスチェック |
| GET | `/api/v1/npc/models` | NPC モデル一覧 |
| POST | `/api/v1/games/npc` | NPC ゲーム作成 |
| POST | `/api/v1/games/pvp` | PvP ゲーム作成 |
| POST | `/api/v1/games/{gameId}/actions` | アクション実行 |
| POST | `/api/v1/games/{gameId}/advance-npc` | NPC ターン実行 |
| GET | `/api/v1/games/{gameId}/state/{playerId}` | プレイヤー視点の状態取得 |
| GET | `/api/v1/games/{gameId}/controls/{playerId}` | ターン制御情報取得 |
| GET | `/api/v1/games/{gameId}/log` | ゲームログ（JSON） |
| GET | `/api/v1/games/{gameId}/log/text` | ゲームログ（テキスト） |

ローカルモード限定:

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/api/dev/cards` | カード一覧（デバッグ用） |

---

## 5. 契約の管理

この API の契約は **`common/data/models.yaml` から Go / C# / TS へ codegen** する方式で一元管理されている（レイヤ A の envelope、レイヤ B の payload、共通 enum 定数まで全て）。

### codegen が担保している領域

| カテゴリ | 型 / 定数 | 生成先 |
|---|---|---|
| 列挙値 | `ActionTypes`, `EventTypes`, `WinReasons`, `Phases`, `EffectDurations` 等 | Go / C# / TS |
| レイヤ A: Envelope | `ActionResult`, `ActionEvent`, `GameCreatedResult`, `BattleDeckCard`, `NpcBattleRequest`, `PvpBattleRequest`, `GameActionRequest`, `NpcAdvanceRequest`, `TurnControlsMessage` | Go (`packages/api/model/battle_gateway_rpc_gen.go`) / C# (`packages/gamedata-dotnet/BattleGatewayRpc_gen.cs`) |
| レイヤ B: State Payload | `ClientGameState`, `PlayerView`, `OpponentView`, `FieldView` 等 | Go / C# |
| レイヤ B: Event Payload | `PlayCardEventData`, `TurnStartEventData`, ... + `EventDataMap` | Go / C# / TS |
| NPC 情報 | `NpcModel` | Go / C# / TS |

### 両側で手書きしている領域

| カテゴリ | 型 | 定義場所 | 理由 |
|---|---|---|---|
| レイヤ C: Action Data | `PlayCardRequest`, `AttackRequest`, `ScaleUpRequest` 等 | Battle の `ActionRequests.cs` のみ | Gateway は `json.RawMessage` で透過中継するため Go 側には不要。Battle は `ActionDataDeserializer` で camelCase ポリシーを明示適用 |
| エラー本文 | `{"error": "..."}` | 両側で手書き | 固定形式のシンプルな契約 |

### 変更する際の手順

**レイヤ A envelope / レイヤ B payload を変更する場合** — codegen 経由:
1. `common/data/models.yaml` を更新
2. `python3 scripts/generate_constants.py` を実行
3. common のパッケージバージョンを昇格して publish
4. Battle / Gateway / Client で新バージョンを取り込む

**レイヤ C action data を変更する場合** — Battle のみ:
1. Battle の `ActionRequests.cs` に新しいリクエスト型を追加、または既存型にフィールド追加
2. 対応する `ActionType` enum を `common/data/constants.yaml` に追加（必要なら）
3. クライアント側はこれに合わせて `data` フィールドの payload を構築する
4. 本ドキュメントのアクション種別例を更新
