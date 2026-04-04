# 引き継ぎ: モデル型の共通パッケージ化

## 背景

`generate_constants.py` は constants / eventData / wsMessages / variantTypes の 4 種を TS 生成しているが、
REST API レスポンス・リクエストのモデル型（Deck, Player, CardDefinition 等）は **TS 生成されていない**。

クライアントが `src/types/` にローカル定義しており、サーバーとの手動同期で
フィールド名の不一致バグが発生している（`art_no` vs `illustration_variant`、`publishedAt` vs `createdAt`）。

また、ゲームステート型は C#（battle）・Go（gateway transform）・TS（client）の 3 箇所で独立に手書きされており、
フィールドの追加漏れ・削除漏れが常態化している。

---

## 根本原因

### 1. models.yaml が DB モデルを定義しており、API コントラクトではない

models.yaml の `Player` 型は DB カラムと 1:1 対応（`db` タグ付き）。
しかしクライアントが受け取る JSON は `playerResponse`（handler が `level_exp_current/required` を付加）であり、DB モデルとは異なる。

同様に `CardDefinition` は DB モデルだが、API レスポンスは `CardWithOwnership`（`is_owned` 付き）。
**models.yaml の型から TS を生成しても、クライアントが受け取る JSON と一致しない。**

### 2. Gateway がゲームステートの変換処理を挟んでいる（設計違反）

バトル関連のやり取りで Gateway はロジックを挟んではいけない。
しかし `game_state_transform.go` が以下の変換を行っている:

- フィールドリネーム: `myView` → `my`, `oppView` → `opponent`
- JSON キー変換: `gameID` → `gameId`, `instanceID` → `instanceId`
- フィールド除外: `deployingTurnsLeft`, `scaleChangedThisTurn`
- 型変換: `flexString` → `*string`（C# enum の int/string 両対応）
- AvailableAction: camelCase → snake_case

これにより:
- ゲームステート型の同期ポイントが **4 箇所**（C# 内部モデル、C# View、Go battle*/client*、TS）に膨張
- battle サーバーのフィールド追加が Gateway で伝搬漏れ（`targetInstanceID` 未伝搬等）
- Client が Gateway を飛ばして battle に直接追従するケースが発生

### 3. 4 箇所の独立手書きによる drift

ゲームステート型の現状:

| 箇所 | 定義場所 | 例 |
|---|---|---|
| C# 内部モデル | `OverloadParty.Battle.Models/Field.cs` | `DeployedResource`, `DeployedSupport` |
| C# View 型 | `OverloadParty.Battle.Service/GameStateView.cs` | `ClientGameState`, `PlayerView`, `HiddenDeployedSupport` |
| Go transform 型 | `gateway/handler/ws/game_state_transform.go` | `battle*` 入力 + `client*` 出力の 2 セット |
| TS 型 | `client/src/types/game.ts` | `ClientGameState`, `ResourceInstance` 等 |

battle が変更 → Go の `battle*` と `client*` と transform 関数を手動更新 → TS を手動更新。
いずれかのステップが漏れると drift する。

---

## 設計方針

### 1. models.yaml を API コントラクトとして再定義する

**DB モデルではなく、リポジトリ間のインターフェース（API レスポンス・リクエスト型）を定義する。**

- DB モデル（`db` タグ付き Player, PlayerDailyBattle, Game 等）→ 各リポジトリのローカル定義に戻す
- API レスポンス型（PlayerResponse, CardWithOwnership 等）→ models.yaml に新設
- ゲームステート型（ClientGameState, DeployedResource 等）→ models.yaml に client view として定��

### 2. Gateway ゲームステート変換を廃止する

`game_state_transform.go` を廃止し、battle サーバーの JSON を `json.RawMessage` でパススルーする。

変更前:
```
Battle C# → JSON → Gateway battle* unmarshal → transform → client* marshal → JSON → Client
```

変更後:
```
Battle C# → JSON → Gateway json.RawMessage パススルー → Client
```

C# の JSON 出力がそのままクライアントに届く。Gateway の同期ポイントが消える。

### 3. Client のゲームステート型を C# 出力に合わせる

C# ASP.NET のデフォルト `JsonNamingPolicy.CamelCase` がそのままクライアントに届くため、
Client TS を C# 出力に合わせて修正する。

| 現在の Client TS | C# 出力（変更なし） | 修正後 |
|---|---|---|
| `gameId` | `gameID` | `gameID` |
| `instanceId` | `instanceID` | `instanceID` |
| `cardId` | `cardID` | `cardID` |
| `sourceId` | `sourceID` | `sourceID` |
| `my` | `myView` | `myView` |
| `opponent` | `oppView` | `oppView` |
| `hand_instance_id` (AA) | `handInstanceID` | `handInstanceID` |
| `valid_zones` (AA) | `validZones` | `validZones` |
| `source_instance_id` (AA) | `sourceInstanceID` | `sourceInstanceID` |
| `available_actions` | `availableActions` | `availableActions` |

AA = AvailableAction フィールド

### 4. JSON 命名規則

| 領域 | JSON キー | 理由 |
|---|---|---|
| REST API | snake_case | Go origin（`json:"player_id"`）。変更なし |
| WS メッセージ | snake_case | Go origin。変更なし（既存生成済み） |
| ゲームステート | camelCase | C# ASP.NET origin。Gateway パススルー |
| enum 値 | snake_case | C# `JsonStringEnumConverter(SnakeCaseLower)` |

### 5. 生成ターゲット

| 領域 | Go | C# | TS |
|---|---|---|---|
| REST API 型 | ○ (gateway) | — | ○ (client) |
| WS メッセージ | ○ (gateway) | — | ○ (client) ← 既存 |
| ゲームステート型 | — | ○ (battle) | �� (client) |
| variant_types | — | ○ (battle) ← 既存 | ○ (client) ← 既存 |
| 定数 / enum | ○ | ○ | ○ ← 既存 |

---

## 対象モデル一覧

### A. REST レスポンス型（Go + TS 生成）

API コントラクトとして新設。handler/service 層の拡張フィールド込みで定義する。

| 型名 | 元の Go 定義 | 備考 |
|---|---|---|
| `PlayerResponse` | handler `playerResponse` (model.Player embed) | `level_exp_current`, `level_exp_required` を含む |
| `CardWithOwnership` | service `CardWithOwnership` | CardDefinition + `is_owned` |
| `PlayerCardWithDef` | model (models.yaml 既存) | API レスポンス型として再定義 |
| `Deck` | model (models.yaml 既存) | `deck_cards` 込み。`db` タグ除去 |
| `DeckCard` | model (models.yaml 既存) | `db` タグ除去 |
| `ProductResponse` | model.Product + `is_owned` | Product + service 層付加フィールド |
| `BattleLimitResponse` | service `BattleLimitResponse` | |
| `UserSettings` | model `UserSettings` | gateway ローカルから移動 |
| `EpisodeWithStatus` | model `EpisodeWithStatus` | gateway ローカルから移動 |
| `LockReason` | model `LockReason` | gateway ローカルから移動 |
| `NewsArticle` | model `NewsArticle` | gateway ローカルから移動 |
| `Announcement` | handler `Announcement` | gateway ローカルから移動 |
| `DailyTip` | handler `DailyTip` | gateway ローカルから移動 |
| `SpectateGameInfo` | ws `ActiveGameInfo` | gateway ローカルから移動 |

### B. REST リクエスト型（Go + TS 生成）

| 型名 | 元の Go 定義 | 備考 |
|---|---|---|
| `DeckCardEntry` | service `DeckCardEntry` | `card_id`, `art_no`, `count` |
| `DeckCreateRequest` | service `CreateDeckRequest` | |
| `DeckUpdateRequest` | service `UpdateDeckRequest` | |
| `UpdateSettingsRequest` | handler inline | |
| `PurchaseRequest` | handler inline | |

### C. ゲームステート型（C# + TS 生成、Gateway パススルー）

C# ASP.NET CamelCase 出力に合わせた JSON キーで定義する。
YAML → C# View 型 + TS interface を生成。Gateway は生成不要（パススルー）。

| 型名 | C# 元クラス | JSON キー例 | 備考 |
|---|---|---|---|
| `ClientGameState` | `ClientGameState` | `gameID`, `myView`, `oppView` | |
| `PlayerView` | `PlayerView` | `playerNum`, `availableActions` | |
| `OpponentView` | `OpponentView` | `playerNum`, `handCount` | |
| `Field` | `Field` | `frontend`, `backend`, `support` | Zone<T> = 固定長 nullable 配列 |
| `OpponentField` | `OpponentField` | 同上 | support が HiddenDeployedSupport |
| `DeployedResource` | `DeployedResource` | `instanceID`, `cardID`, `faceUp`, `currentAV` | C# は `faceUp`（後述） |
| `DeployedSupport` | `DeployedSupport` | `instanceID`, `targetInstanceID`, `faceUp` | |
| `HiddenDeployedSupport` | `HiddenDeployedSupport` | `instanceID`, `faceDown`, `peeked` | |
| `UndeployedCard` | `UndeployedCard` | `instanceID`, `cardID`, `artNo` | 手札・リポ・トラッシュ共通 |
| `TemporaryEffect` | `TemporaryEffect` | `effectType`, `value`, `duration`, `sourceID` | |
| `AvailableAction` | `AvailableAction` | `type`, `handInstanceID`, `validZones` | variant_types から移動検討 |
| `TurnControls` | `TurnControls` | `canEndPhase`, `discardRequired` | |

### D. variant_types 更新

`AvailableAction` のフィールド名を snake_case → camelCase に変更。
`type` の値（`play_card`, `attack` 等）は snake_case のまま（C# `JsonStringEnumConverter(SnakeCaseLower)` の出力）。

```yaml
# 変更前
- {name: hand_instance_id, type: string}
- {name: valid_zones, type: "string[]", optional: true}

# 変更後
- {name: handInstanceID, type: string}
- {name: validZones, type: "string[]", optional: true}
```

### E. models.yaml から削除する DB モデル

API コントラクトではないため、各リポジトリのローカル定義に戻す。

| 型名 | 現在の target | 移動先 |
|---|---|---|
| `Player`（db タグ付き） | both | gateway `internal/model/` |
| `PlayerDailyBattle` | both | gateway `internal/model/` |
| `PlayerCard` | both | gateway `internal/model/` |
| `Game` | battle | battle C# Models（既に手書き存在） |
| `GameState` | battle | battle C# Models（既に手書き存在） |
| `GameEvent` | battle | battle C# Models（既に手書き存在） |
| `GameConfig` | both | gateway/battle ローカル |

注: `CardDefinition`, `ComputeStats`, `DataStats`, passive_effect 系はカードデータの構造定義として残す（API レスポンスの一部でもある）。

### F. 生成対象外

| 型名 | 理由 |
|---|---|
| `HealthResponse` | gateway handler で `gin.H` インライン構築 |
| `VersionResponse` | 同上 |
| `SelectFactionResponse` | 同上 |
| `NpcModel` / `NpcModelsResponse` | battle サーバーが定義、gateway は `json.RawMessage` パススルー |

---

## 検出済み不一致（要修正）

### 1. `art_no` vs `illustration_variant`（影響大）

サーバー全体で `art_no` (int64)。クライアントは `illustration_variant` (number)。

**影響箇所:**
- `DeckCard` 型 → レスポンスの `art_no` がクライアントで無視される
- `DeckCardEntry` 型 → リクエストの `illustration_variant` がサーバーで無視され `art_no=0` になる
- `OwnedCard` 型 → レスポンスの `art_no` がクライアントで無視される

**現在の影響:** バリアント 0 以外のカードが正しく扱えない。
現時点ではバリアント 0 のみ存在するため表面化していないが、コスメティックバリアント実装時にバグる。

**対応:** クライアント側で `illustration_variant` → `art_no` にリネーム。

### 2. `Announcement` フィールド不一致

| フィールド | Go (JSON) | クライアント | 状況 |
|---|---|---|---|
| `publishedAt` | `"publishedAt"` | 無し | クライアントが `createdAt` として定義 |
| `expiresAt` | `"expiresAt"` | 無し | クライアント未定義 |
| `createdAt` | 無し | `"createdAt"` | サーバーに存在しない |
| `type` | `"info" \| "warning" \| "maintenance"` | `"info" \| "event" \| "maintenance"` | enum 値不一致 |

### 3. `CardDefinition` フィールド差分

クライアントに無いフィールド（サーバーには存在）:
- `deploy_turns`, `elastic_increment`, `free_tier`, `cost_per_request`
- `effects`, `passive_effects`, `platform_effects`, `attachment_effects`
- `created_at`, `updated_at`

クライアントにのみ存在するフィールド:
- `effect_id` — サーバー側に該当なし
- `deploy_turn`（`CardStats` 内）— サーバーは `deploy_turns` として `CardDefinition` 直下

### 4. ゲームステート型の未同期フィールド

#### `attachments` フィールド（C# で削除済み）

battle サーバーのコミット `3f89842` でアタッチメント方式が変更された:
- 旧: `DeployedResource.Attachments []AttachmentRef`
- 新: `DeployedSupport.TargetInstanceID string?`（サポート側が対象リソースを参照）

| 箇所 | 状態 |
|---|---|
| C# `DeployedResource` | `Attachments` **削除済み** |
| Go `clientResourceInstance` | `Attachments` **まだある** |
| TS `ResourceInstance` | `attachments` **なし**（追従済み） |
| models.yaml `ResourceInstance` | `Attachments` **まだある** |

#### `targetInstanceID`（C# で追加済み）

| 箇所 | 状態 |
|---|---|
| C# `DeployedSupport` | `TargetInstanceID` **あり** |
| Go `clientSupportInstance` | **なし** |
| TS `SupportInstance` | `targetInstanceId` **あり**（追従済み） |
| models.yaml `SupportInstance` | **なし** |

#### `faceUp` vs `faceDown`

C# `DeployedResource` は `FaceUp` (bool) を使用。
Gateway/Client は `FaceDown` (bool) を使用。意味が反転。
Gateway パススルー化後は C# の `faceUp` がクライアントに届くため、クライアント側を `faceUp` に統一する。

注: `HiddenDeployedSupport` は C# も `FaceDown` を使用（一致）。

#### `HiddenDeployedSupport.artNo`

C# `HiddenDeployedSupport` に `ArtNo` がない。Gateway/Client にはある。
対面相手の伏せサポートカードのアート表示に必要な場合は C# View に追加する。不要なら Client から削除する。

#### nullability の不一致

| フィールド | C# | Client TS | 影響 |
|---|---|---|---|
| `currentTP` | `long?` (nullable) | `number` (non-null) | デプロイ中リソースで null |
| `maxTP` | `long?` | `number` | 同上 |
| `currentYield` | `long?` | `number` | 同上 |
| `maxYield` | `long?` | `number` | 同上 |
| `rank` | `Rank?` | `Rank` | デプロイ中は null |
| `instanceFamily` | `InstanceFamily?` | `InstanceFamily` | デプロイ中は null |

C# は `JsonIgnoreCondition.WhenWritingNull` で null フィールドを省略するため、
TS 側は optional (`?`) として定義する必要がある。

---

## 実装フェーズ

### Phase 1: Gateway パススルー化 + Client ゲームステート型修正

**Gateway の transform 廃止が最優先。** 設計に反する変換を続けると drift が拡大する。

#### gateway

1. `game_state_transform.go` の `transformGameState()` を廃止
2. WS ハンドラで battle レスポンスの `state` を `json.RawMessage` のままクライアントに転送
3. `battle*` / `client*` struct を全削除
4. `flexString` ヘルパーを削除

#### battle

1. `HiddenDeployedSupport` に `ArtNo` が必要かを判断し、必要なら追加
2. `faceUp` / `faceDown` の命名を確認（DeployedResource は `FaceUp`、HiddenDeployedSupport は `FaceDown` — 意味的に正しいのでそのまま）

#### client

1. `src/types/game.ts` を C# 出力に合わせて修正:
   - `gameId` → `gameID`, `instanceId` → `instanceID`, `cardId` → `cardID`, `sourceId` → `sourceID`
   - `my` → `myView`, `opponent` → `oppView`
   - `available_actions` �� `availableActions`
   - `faceDown` → `faceUp`（`ResourceInstance` / `SupportInstance`）
   - AvailableAction フィールド: `hand_instance_id` → `handInstanceID` 等
   - nullable 対応: `currentTP` → `currentTP?` 等
2. 上記フィールド名の変更をコンポーネント・ストア全体に波及
3. `attachments` フィールドが使われていないことを確認し、型から削除（C# で既に削除済み）

### Phase 2: models.yaml 再定義 + REST API 型の TS 生成

#### common

1. models.yaml から DB モデル（Player with db tags, PlayerDailyBattle, Game, GameState, GameEvent, GameConfig）を削除
2. REST API レスポンス/リクエスト型をセクション A/B の通り追加
3. `generate_constants.py` に `generate_ts_models()` を追加
4. 出力先: `packages/gamedata-npm/src/models.ts`
5. `packages/gamedata-npm/src/index.ts` に `export * from './models'` を追加
6. Go 型生成を API コントラクト型に対応させる（db タグなし）

#### gateway

1. DB モデル（Player, PlayerDailyBattle, PlayerCard, GameConfig）を `internal/model/` にローカル定義
2. handler/service 層の API レスポンス型（`playerResponse`, `CardWithOwnership` 等）を生成型に切り替え
3. `gen.go` のエイリアスを更新

#### client

1. `src/types/card.ts` から `Deck`, `DeckCard`, `DeckCardEntry`, `OwnedCard`, `CardDefinition`, `CardStats` を削除 → パッケージ import
2. `src/types/api.ts` から `Player`, `BattleLimitResponse`, `AnnouncementItem`, `DailyTip`, `CloudNewsItem` を削除 → パッケージ import
3. `src/types/settings.ts` から `ServerSettings`, `UpdateSettingsRequest` を削除 → パッケージ import
4. `src/types/scenario.ts` から `EpisodeWithStatus`, `LockReason` を削除 → パッケージ import
5. `src/types/shop.ts` から `ShopProduct`, `PurchaseRequest` を削除 → パッケージ import
6. `illustration_variant` → `art_no` リネーム
7. `Announcement` のフィールド修正

### Phase 3: ゲームステート型の YAML 化 + C# 生成

#### common

1. models.yaml の `game_state` セクションを client view 型として書き換え（セクション C の通り）
2. `generate_constants.py` に C# View 型生成を追加
   - `[JsonPropertyName]` 属性でキー名を制御（ASP.NET CamelCase と一致させる）
   - nullable 型の適切なマッピング
3. 出力先: `packages/gamedata-dotnet/` 配下
4. `packages/gamedata-npm/src/` にゲームステート TS 型を追加
5. variant_types の AvailableAction フィールドを camelCase に変更

#### battle

1. `GameStateView.cs` の手書き View 型を生成コードに置き換え
2. `AvailableAction` の手書きクラスを生成コードに置き換え

#### client

1. `src/types/game.ts` の手書き型を削除 → パッケージ import

---

## 各リポジトリの変更サマリ

| リポ | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| **common** | — | models.yaml 再定義 + TS 生成追加 | game_state YAML 化 + C# 生成追加 |
| **gateway** | transform 廃止 + パススルー化 | DB モデルローカル化 + 生成型利用 | — |
| **battle** | faceUp/artNo 確認 | — | View 型を生成に置き換え |
| **client** | game.ts を C# 出力に合わせ修正 | REST 型をパッケージ import に切り替え | game.ts をパッケージ import に切り替え |
