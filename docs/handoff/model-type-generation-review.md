# レビュー依頼: モデル型の共通パッケージ化（Phase 1-3）

設計ドキュメント: [model-type-generation.md](model-type-generation.md)

---

## 変更の全体像

1. Gateway の game_state_transform 廃止（バトルステート JSON のパススルー化）
2. models.yaml を DB モデルから API コントラクトに再定義
3. パッケージ分割: gamedata（ゲームデータ）+ api（REST/WS コントラクト）
4. ゲームステート型の YAML → C#/TS 生成
5. Client の型定義をサーバー出力に統一

---

## Common リポ

### 変更概要

models.yaml を再構築し、パッケージを gamedata と api に分離した。

### 変更ファイル

**models.yaml:**
- 削除: DB モデル（Player with db tags, PlayerDailyBattle, Game, GameState, GameEvent, GameConfig, PlayerCard）
- 追加: REST API コントラクト型 15 種（`rest_api` セクション、`pkg: api`）
- 追加: ゲームステート View 型 10 種（`game_state_view` セクション、`pkg: gamedata`）
- 変更: 各セクションに `pkg: gamedata/api` フィールド追加
- 変更: variant_types の AvailableAction フィールドを snake_case → camelCase

**generate_constants.py:**
- 追加: `generate_ts_models(pkg_filter=...)` — models.yaml から TS interface 生成（pkg で振り分け）
- 追加: `generate_csharp_game_state_view()` — ゲームステート View 型の C# 生成
- 変更: `generate_go_models()` — pkg フィールドで出力先を gamedata/api に振り分け
- 変更: C# variant_types 生成の PascalCase 変換を camelCase 入力対応に修正

**新規パッケージ:**
- `packages/api/` — Go パッケージ（go.mod + model/）
- `packages/npm-api/` — npm パッケージ `@kenyamaneko/overload-party-api`（package.json + src/）

**生成ファイル:**
- `packages/npm/src/models.ts` — gamedata TS 型（CardDefinition, ComputeStats, ゲームステート型 等）
- `packages/npm-api/src/models.ts` — api TS 型（PlayerResponse, Deck, UserSettings 等）
- `packages/npm-api/src/wsMessages.ts` — WS メッセージ TS 型（npm から移動）
- `packages/dotnet/GameStateView_gen.cs` — C# View 型
- `packages/gamedata/model/game_state_view_gen.go` — Go View 型
- `packages/api/model/rest_api_gen.go`, `deck_gen.go`, `ws_messages_gen.go` — Go API 型

### 確認ポイント

- [ ] `python3 scripts/generate_constants.py` を実行して生成結果が正しいか
- [ ] gamedata npm (`packages/npm/src/models.ts`) に CardDefinition, ComputeStats, ゲームステート型のみ含まれること（REST API 型が混入していないこと）
- [ ] api npm (`packages/npm-api/src/models.ts`) に REST API 型のみ含まれること（CardDefinition 等が混入していないこと）
- [ ] `packages/gamedata && go build ./...` が通ること
- [ ] `packages/api && go build ./...` が通ること
- [ ] REST API 型のフィールドが gateway の実装と一致しているか（PlayerResponse の level_exp_current 等）
- [ ] ゲームステート型の JSON キーが C# ASP.NET CamelCase 出力と一致しているか（gameID, instanceID, myView 等）
- [ ] 生成される C# View 型が battle の GameStateView.cs の手書き型と互換か
- [ ] CI の publish ワークフローに api パッケージの追加が必要（別途対応）

---

## Gateway リポ

### 変更概要

game_state_transform.go を削除し、バトルステート JSON を json.RawMessage でパススルーにした。
DB モデルをローカル定義に移動した。

### 変更ファイル

**削除:**
- `internal/handler/ws/game_state_transform.go`（502 行 — flexString, battle*/client* struct, 全 transform 関数）
- `internal/handler/ws/game_state_transform_test.go`（582 行）

**修正:**
- `internal/handler/ws/game_relay.go` — transform 呼び出し 5 箇所をパススルーに変更。ターンタイマー用に最小限の `battleStateMeta` struct を追加
- `internal/handler/ws/spectate_relay.go` — transform 呼び出し 1 箇所をパススルーに変更

**追加:**
- `internal/model/player.go` — Player, PlayerDailyBattle, PlayerCard, GameConfig を db タグ付きでローカル定義

**修正:**
- `internal/model/gen.go` — 上記 4 型のエイリアス削除 + 将来の REST API 型切り替え TODO

**TODO 追加（common パッケージ publish 後に対応）:**
- player_handler.go, player_service.go, shop_service.go, story.go, news.go, user_settings.go, static_handler.go, spectate_handler.go

### 確認ポイント

- [ ] `go build ./...` が通ること
- [ ] `go vet ./...` が通ること
- [ ] `go test ./internal/...` が通ること
- [ ] game_relay.go の `battleStateMeta` が必要最小限のフィールドのみ抽出していること（ゲームステート変換ではなく、ターンタイマー管理のためのメタデータ取得）
- [ ] spectate_relay.go でパススルーが正しく動作すること
- [ ] DB モデル（player.go）の db タグが既存の DB スキーマと一致すること
- [ ] gen.go から削除されたエイリアスが他のファイルで直接参照されていないこと

### 動作確認

Gateway + Battle のローカル環境で:
1. PvP マッチ or NPC バトルを開始
2. クライアントがゲームステートを正しく受信できること（JSON キーが camelCase: gameID, myView 等）
3. 観戦（spectate）が正しく動作すること
4. TurnControls メッセージが正しく送信されること

---

## Client リポ

### 変更概要

ゲームステート型を C# ASP.NET CamelCase 出力に統一した。
REST API 型のフィールド名・型名をサーバーと一致させた。

### Phase 1: ゲームステート型の修正（game.ts + 30 ファイル以上）

**フィールドリネーム:**
- `gameId` → `gameID`, `instanceId` → `instanceID`, `cardId` → `cardID`, `sourceId` → `sourceID`
- `my` → `myView`, `opponent` → `oppView`
- `available_actions` → `availableActions`

**faceDown → faceUp（論理反転）:**
- ResourceInstance, SupportInstance: `faceDown` → `faceUp`
- HiddenSupportInstance: `faceDown` のまま（変更なし）
- 全ての条件式で論理が反転されていること

**nullable 対応:**
- currentTP, maxTP, currentYield, maxYield, rank, instanceFamily → optional (`?`)

**AvailableAction:**
- パッケージ import からローカル camelCase 定義に一時切り替え（TODO 付き）
- フィールド: hand_instance_id → handInstanceID 等

### Phase 2: REST API 型の修正

**型名リネーム:**
- `OwnedCard` → `PlayerCardWithDef`
- `Player` → `PlayerResponse`
- `AnnouncementItem` → `Announcement`
- `CloudNewsItem` → `NewsArticle`
- `ServerSettings` → `UserSettings`
- `ShopProduct` → `ProductResponse`

**フィールド修正:**
- `illustration_variant` → `art_no`（全箇所）
- Announcement: `createdAt` → `published_at`, `expiresAt` 追加, type enum `event` → `warning`
- CardDefinition: `effect_id` 削除, `deploy_turns`/effects 系フィールド追加
- CardStats: `deploy_turn` 削除（CardDefinition.deploy_turns に移動）

### 確認ポイント

- [ ] `npx tsc --noEmit` が通ること
- [ ] `npx vitest run` が全パスすること（462 テスト）
- [ ] `faceDown` → `faceUp` の論理反転が全箇所で正しいこと（特に条件分岐、三項演算子）
- [ ] `illustration_variant` の参照が残っていないこと
- [ ] 旧型名（OwnedCard, ServerSettings 等）の参照が残っていないこと
- [ ] destructuring パターン（`const { my, opponent } = state`）が全て更新されていること
- [ ] mockGameState.ts のモックデータが新フィールド名を使っていること

### 動作確認

Gateway + Battle + Client のローカル環境で:
1. バトル画面が正しく表示されること（フィールド、手札、リソースカード）
2. カードの表裏（faceUp）が正しく表示されること
3. アクション選択（AvailableAction）が正しく動作すること
4. デッキ編集画面で `art_no` が正しく反映されること
5. お知らせ画面で Announcement が正しく表示されること
6. ショップ画面で商品が正しく表示されること

---

## Battle リポ

### 変更概要

HiddenDeployedSupport に ArtNo を追加した。
View 型の生成型置き換え準備として調査と TODO 追加を行った。

### 変更ファイル

**修正:**
- `src/OverloadParty.Battle.Service/GameStateView.cs`
  - `HiddenDeployedSupport` に `ArtNo` プロパティ追加
  - `BuildOpponentField` で ArtNo を条件付きコピー（`FaceUp || peeked` の場合のみ公開、それ以外は 0）
  - 5 つの View 型に生成型置き換え TODO 追加

- `src/OverloadParty.Battle.Models/Field.cs`
  - UndeployedCard, TemporaryEffect に TODO 追加

- `src/OverloadParty.Battle.Engine/AvailableActions.cs`
  - TurnControls に TODO 追加

**テスト更新:**
- `tests/.../GameStateViewTests.cs` — ArtNo 関連のアサーション 3 件追加

### 確認ポイント

- [ ] `dotnet test` が全パスすること
- [ ] HiddenDeployedSupport.ArtNo の公開条件が正しいこと:
  - face-down かつ未 peek → ArtNo = 0（カード裏面、種類を推測させない）
  - face-up または peek 済み → ArtNo = 元の値
- [ ] TODO コメントが適切な箇所に追加されていること

### 将来の作業（今回のレビュー対象外）

View 型の生成型置き換えは以下の順で段階的に実施予定:
1. HiddenDeployedSupport, ClientGameState, OpponentField（容易）
2. PlayerView, OpponentView, TurnControls（AvailableAction 参照変更あり）
3. UndeployedCard, TemporaryEffect（エンジン全体 20+ ファイルに影響、set → init 移行が必要）
