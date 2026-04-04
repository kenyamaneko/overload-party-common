# パッケージ移行 残作業一覧

設計ドキュメント: [model-type-generation.md](model-type-generation.md)
Phase 1-3 レビュー: [model-type-generation-review.md](model-type-generation-review.md)
TurnControls 移動: [turn-controls-section-move.md](turn-controls-section-move.md)

## 完了済み

| リポ | 作業 | 状態 |
|---|---|---|
| common | models.yaml 再構築（gamedata/api 分割） | 完了 |
| common | TurnControlsMessage を ws_messages → game_state_view に移動 | 完了 (f48ca6e) |
| common | ARCHITECTURE.md にパッケージ責務セクション追加 | 完了 |
| gateway | game_state_transform 廃止（game state パススルー化） | 完了 |
| gateway | DB モデルをローカル定義に移動 | 完了 |
| battle | View 型を GameData 生成型に置き換え（Build() マッピング境界化） | 完了 |
| battle | GameData パッケージ 0.1.22 に更新 | 完了 |
| client | WS メッセージ型を api パッケージから import | ほぼ完了 |
| common | Phase 1: gamedata/api パッケージ型修正（CardDefinition, AvailableAction, GameState, API 型） | 完了 |

## 残作業の全体構造

```
Phase 1: Common パッケージ修正 ← ボトルネック（他リポの作業をブロック）
    ↓ publish
Phase 2: Gateway / Battle / Client が各自で追従（順不同、並行可）
```

稼働前のため breaking change の同時デプロイは不要。各リポが順次追従すればよい。

---

## Phase 1: Common リポ — パッケージ修正

### gamedata パッケージ

**パッケージ構成:**
- `./models` サブパス追加（package.json の exports + typesVersions）

**CardDefinition フィールド型修正:**

| フィールド | 現在 | 修正後 |
|---|---|---|
| stats | `Record<string, unknown>` | `CardStats` interface |
| effects | `Record<string, unknown>?` | `string[]` (required) |
| passive_effects | `PassiveEffect[]?` | `string[]` (required) |
| platform_effects | `PlatformEffect[]?` | `string[]` (required) |
| attachment_effects | `AttachmentEffect[]?` | `string[]` (required) |
| free_tier | `number?` | `boolean` (required) |
| effect_text | `string?` | `string` (required) |

**AvailableAction 修正:**

| 項目 | 修正内容 |
|---|---|
| attack.validTargets | required → optional |
| scale_up.needsFamily | required → optional |
| monetize.remainingCapacity | required → optional |
| use_effect.effectTargetType, requiredCount | required → optional |

**注意: 追加・変更しない項目:**
- ~~`set_reactive` バリアント追加~~ → バトルエンジン未実装。constants にアクション種別があるだけ
- ~~`discard_hand` バリアント追加~~ → AvailableAction として列挙されない。TurnControls.DiscardRequired でクライアントが直接送信するアクション
- `needsFamily` → optional のままで正しいが、battle エンジンの `EnumerateScaleUpActions` で Small → Medium/Large の場合に `NeedsFamily = true` を設定する修正が必要（現在未設定）。クライアントがバトルロジックを推論してはならない


**ゲームステート型の型安全化:**

| フィールド | 現在 | 修正後 |
|---|---|---|
| ClientGameState.currentPhase | `string` | `GamePhase` |
| DeployedResource.rank | `string?` | `Rank?` |
| DeployedResource.instanceFamily | `string?` | `InstanceFamily?` |
| TemporaryEffect.duration | `string` | `EffectDuration` |

**注意: 修正しない項目:**
- ~~HiddenDeployedSupport.cardID を required に~~ → **やらない**。battle サーバーは伏せカード（未 peek）で意図的に `null` を送信する（情報隠蔽）。`string?` が正しい

### api パッケージ

**PlayerCardWithDef:**
- `resource_label`, `deploy_turns` フィールド追加
- `faction`: `string` → `FactionId | 'Neutral'`
- `card_type`: `string` → `CardType`
- `stats`: `Record<string, unknown>` → `CardStats`
- `restriction`: `string` → `Restriction`

**Announcement:**
- `publishedAt` → `published_at`（snake_case に修正）
- `expiresAt` → `expires_at?`（snake_case + optional に修正）
- `type`: `string` → `'info' | 'warning' | 'maintenance'`

**その他:**
- `NewsArticle.source`: `string` → `CloudNewsSource`
- `ProductResponse.type`: `string` → `ProductType`
- `EpisodeWithStatus.LockReason.type`: `string` → `'level' | 'faction' | 'episode'`
- `ActionPerformedMessage.state`: `Record<string, unknown>` → `ClientGameState`
- `SpectateJoinedMessage.state`: `Record<string, unknown>` → `ClientGameState`

---

## Phase 2: 各リポ追従

### Gateway

**TurnControls パススルー化** ([詳細](turn-controls-section-move.md)):
- `battle_client.go`: TurnControls 構造体削除、戻り値を `json.RawMessage` に
- `game_relay.go`: `SendTurnControlsToPlayers` を raw JSON パススルーに変更
- `message.go`: `TurnControlsMessage` type alias 削除

**REST API 型の api パッケージ切り替え** (既存 TODO):
- player_handler.go, player_service.go, shop_service.go, story.go, news.go, user_settings.go, static_handler.go, spectate_handler.go

### Battle

**TurnControls 置き換え** ([詳細](turn-controls-section-move.md)):
- `AvailableActions.cs`: `TurnControls` クラス削除 → `GameData.TurnControlsMessage` に
- `ComputeTurnControls` の戻り値型変更
- `Program.cs`: 手動匿名オブジェクト投影削除、生成型を直接返す
- `GameService.cs`, `GameEngine.cs`: 戻り値型変更
- テスト更新

**AvailableAction 修正:**
- `EnumerateScaleUpActions`: Small からの昇格時に `NeedsFamily = true` を設定（現在未設定）

### Client

**Step 1: TurnControls 移行**
- `TurnControls` → `TurnControlsMessage`（gamedata パッケージから import）
- JSON キー: `can_end_phase` → `canEndPhase`, `discard_required` → `discardRequired`

**Step 2: ゲームステート型をパッケージに切り替え**
- game.ts のローカル型削除、`@kenyamaneko/overload-party-gamedata/models` から re-export
- codebase 全体リネーム:
  - `ResourceInstance` → `DeployedResource`
  - `SupportInstance` → `DeployedSupport`
  - `HiddenSupportInstance` → `HiddenDeployedSupport`
  - `HandCard` → `UndeployedCard`

**Step 3: REST API 型をパッケージに切り替え**
- api.ts, card.ts, settings.ts, scenario.ts, shop.ts のローカル定義を削除
- `@kenyamaneko/overload-party-api/models` から re-export
- パッケージにない型（HealthResponse, VersionResponse 等）はローカル維持

**Step 4: AvailableAction をパッケージに切り替え**
- パッケージの optionality 修正が入った後
- ローカル定義削除、`@kenyamaneko/overload-party-gamedata/variantTypes` から import

**Step 5: TODO 削除 + クリーンアップ**
