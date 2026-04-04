# 引き継ぎ: マイグレーション廃止 + サポート張り替え

## 概要

ゲームルール単純化のため、以下の変更を battle リポで実施済み:

1. **マイグレーション廃止** — `migrate` アクションと関連ロジックを全削除
2. **サポート張り替え実装** — サポートカード（Platform/Attachment/Reactive）を占有スロットに配置可能に。旧サポートはトラッシュへ移動

リソース（Compute/Data）は引き続き空きスロットのみ配置可能。

---

## common リポの対応

### constants.yaml
- `action_types` から `migrate` を削除
- `event_types` から `migrate`, `migration_complete` を削除

### models.yaml
- `ResourceInstance` から以下3フィールドを削除:
  - `MigratingFrom` (`*string`)
  - `MigrationTarget` (`*string`)
  - `MigratingOnTurn` (`int64`)
- `AvailableAction` バリアントから `migrate` を削除

### event_schemas.yaml
- `migrate` イベントスキーマを削除
- `migration_complete` イベントスキーマを削除

### コード生成
上記 YAML 変更後に `python3 scripts/generate_constants.py` を実行。以下が自動更新される:
- `packages/gamedata-npm/src/constants.ts`
- `packages/gamedata-npm/src/variantTypes.ts`
- `packages/gamedata-npm/src/eventData.ts`
- `packages/gamedata-dotnet/GameConstants_gen.cs`
- `packages/gamedata-dotnet/EventData_gen.cs`
- `packages/gamedata/constants/constants_gen.go`

### ADR
- `docs/adr/007-deploy-turns-and-migration.md` のマイグレーションセクションに「廃止」を明記

### 注意
- カード名 "天気使い Migration" (TK-0021), "オープンソースマイグレーション" (NT-0012) はカードフレーバー。削除不要

---

## client リポの対応

### マイグレーション削除
- `src/features/battle/hooks/useBattleActions.ts` — `migrate` コールバッ��と export を削除
- `src/features/battle/hooks/__tests__/useBattleActions.test.ts` — migrate テスト削除
- `src/lib/ws/__tests__/schemas.test.ts` — migrate アクションのテストデータ削除

### サポート張り替え — 確認ダイアログ追加
サポートカードを **使用済みスロット** にデプロイする場合、確認ダイアログを表示する:
- 「既���のカード（{カード名}）がトラッシュされますがよろしいですか？」
- AvailableAction の `valid_zones` に占有スロットも含まれるようになったので、クライアント側でスロットの占有状態を判定してダイアログを出し分ける

### 依存パッケージ更新
- `@kenyamaneko/overload-party-gamedata` を common リポの新バージョンに更新

---

## gateway リポの対応

### game_state_transform.go
`battleResourceInstance` 構造体から以下3フィールドを削除:
```go
MigratingFrom   *string `json:"migratingFrom"`
MigrationTarget *string `json:"migrationTarget"`
MigratingOnTurn int64   `json:"migratingOnTurn"`
```

### game_state_transform_test.go
テストデータから上記3フィールドを削除

### data/daily_tips.json
マイグレーションに言及しているTipsを削除または書き換え:
- `"Migration を使えばカードをゾーン間で移動できます。状況に応じてリソースを再配置しましょう。"`

### Go モジュール更新
common リポの Go パッケージ更新後に `go get` + `go mod vendor`
