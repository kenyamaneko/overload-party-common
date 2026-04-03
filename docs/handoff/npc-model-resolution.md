# NPC モデル一覧 API 追加 — 各リポ対応

## 背景

NPC バトル開始時、クライアントがファクション名（`"SHE"`）をハードコードで送っていたが、バトルサーバーの AI 設定はモデル名（`"SHE-easy"`, `"SHE-hard"`）をキーにしている。

NPC モデル一覧を API で返し、クライアントはハードコードをやめて API から取得する方針に変更。

## common（対応済み）

- `GET /npc/models` を API_REFERENCE に追加
- `npc_battle_start` の `npc_faction` → `npc_model` に変更
- `models.yaml` の `NPCBattleStartMessage.NPCFaction` → `NPCModel` に変更、codegen 済み
- gamedata パッケージ v0.1.18 で Go/TS 型を publish 済み

## battle

### 1. `GET /api/v1/npc/models` エンドポイント追加

ロード済みの `AiConfig` 一覧から NPC モデル情報を返す。

**レスポンス:**
```json
{
  "models": [
    { "model": "SHE-easy", "faction": "SHE", "difficulty": "easy" },
    { "model": "SHE-hard", "faction": "SHE", "difficulty": "hard" }
  ]
}
```

- `model`: `AiConfig.Model`（YAML の `model` フィールド、例: `SHE-easy`）
- `faction`: `AiConfig.Faction`（YAML の `faction` フィールド）
- `difficulty`: model から faction を除いた部分（`SHE-easy` → `easy`）

実装方針:
- `AiConfigLoader` がロード済みの全 `AiConfig` を保持しているので、それを列挙して返す
- Program.cs に `MapGet("/api/v1/npc/models", ...)` を追加

### 2. `npc_faction` → `npc_model` 対応

Gateway からの `StartNPCBattle` リクエストのフィールド名が変わる。

- `GameService.StartNPCBattle` のパラメータ名を確認
- Gateway からの内部 REST リクエストの JSON フィールド名が `npc_model` になる

現状の `_aiConfigs.TryGetValue(model)` はモデル名をキーにしているので、gateway から `npc_model` としてモデル名が渡されれば既存ロジックで動作する。

## gateway

### 1. `GET /api/v1/npc/models` プロキシ追加

Battle Server の `GET http://battle:9002/api/v1/npc/models` にプロキシする。

- `internal/handler/rest/` にハンドラ追加
- ルーティング: `api.GET("/npc/models", handler.GetNPCModels)` （認証必要）
- `battleClient` に `GetNPCModels()` メソッドを追加してレスポンスをそのまま返す

### 2. `npc_battle_start` WS ハンドラの更新

- `handleNpcBattleStart` で `NPCFaction` → `NPCModel` に変更
- Battle への内部 REST リクエストのフィールド名を `npc_model` に変更
- gamedata パッケージを更新: `go get .../packages/gamedata@latest` + `go mod vendor`

### 3. devdata パッケージ更新不要

今回は devdata（ローカルモック用データ）への変更はない。

## client

### 1. NPC モデル一覧を API から取得

現状 `NpcFactionSelectPage.tsx` にハードコードされた NPC 一覧を、API 取得に置き換える。

```
GET /api/v1/npc/models → { models: [...] }
```

- ファクションごとにグルーピングして選択 UI に表示
- 既存の `she-easy`（小文字）ハードコードを削除

### 2. `npc_battle_start` のフィールド変更

- `useNpcBattleStart.ts` で送信するフィールドを `npc_faction` → `npc_model` に変更
- 値はファクション名ではなく `/npc/models` で取得したモデル ID（例: `SHE-easy`）を送る
- gamedata パッケージを更新: `npm install @kenyamaneko/overload-party-gamedata@latest`

### 3. 型定義の更新

- `ShopProduct` 型の `description` / `image_url` 追加も gamedata パッケージ更新で入る
- `NPCBattleStartMessage` 型の `npc_faction` → `npc_model` 変更も同様
