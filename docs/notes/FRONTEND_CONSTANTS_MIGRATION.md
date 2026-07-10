# フロントエンド: 定数共通化の残タスク

**作成日:** 2026-02-25
**ステータス:** 未着手
**関連:** `src/generated/constants.ts`（`data/constants.json` から自動生成）

---

## 概要

サーバー・クライアント間でゲーム定数を共通化する仕組みが整った（`data/constants.json` → 自動生成）。
サーバー側は移行完了済み。クライアント側は **型定義 (`types/`)** の移行は完了したが、
**コンポーネント内のハードコード値** がまだ残っている。

以下のタスクを順次実施してください。

---

## デッキサイズ (DECK_SIZE = 30) の置き換え 【優先度: 高】

`INITIAL_VALUES.deckSize` を使用する。

| ファイル | 行 | 現状 |
|---------|-----|------|
| `features/card/hooks/useDeckEdit.ts` | 6 | `const DECK_SIZE = 30` |
| `features/card/hooks/useDeckValidation.ts` | 4 | `const DECK_SIZE = 30` |
| `stores/deckStore.ts` | 48, 76 | `req.cards.length === 30` |
| `features/card/components/DeckComposition.tsx` | 32 | `({cards.length}/30)` |
| `features/card/components/DeckEditPage.tsx` | 82 | `cards.length >= 30` |

```typescript
import { INITIAL_VALUES } from '@/generated/constants'
// const DECK_SIZE = 30  ← 削除
// INITIAL_VALUES.deckSize を使う
```

## Faction 文字列のハードコード除去 【優先度: 高】

`SELECTABLE_FACTIONS` / `FACTIONS` を使用する。

| ファイル | 内容 |
|---------|------|
| `features/navigation/components/StageFactionSelect.tsx` | `FACTIONS` 配列をハードコード定義（9-34行）→ `SELECTABLE_FACTIONS` からループ生成 |
| `features/card/components/CardDetailPage.tsx` | faction → 表示名マッピング（6-28行） |
| `features/home/components/PlayerInfoCard.tsx` | faction → 表示名マッピング（3-15行） |
| `features/card/components/CardFilterBar.tsx` | `<option value="sws">` 等（50-55行）→ ループ生成 |
| `features/battle/components/hand/HandCard.tsx` | faction → グラデーション/ボーダーマッピング（4-18行） |
| `features/battle/components/field/FieldSlot.tsx` | 同上（10-24行）→ HandCard.tsx と共通化推奨 |

**補足:** faction の表示名（`'SWS'`, `'Aozora'` 等）やカラー/グラデーションは UI 固有なので、
`constants.json` ではなくクライアント側の共通マッピングファイル（例: `lib/factions.ts`）を作って一元化するのが良い。

```typescript
// src/lib/factions.ts (例)
import { SELECTABLE_FACTIONS, FACTIONS } from '@/generated/constants'
import type { FactionId } from '@/generated/constants'

export const FACTION_DISPLAY: Record<FactionId | 'neutral', { name: string; color: string; gradient: string }> = {
  sws:      { name: 'SWS',      color: 'var(--color-faction-sws)',      gradient: '...' },
  aozora:   { name: 'Aozora',   color: 'var(--color-faction-aozora)',   gradient: '...' },
  guruguru: { name: 'Guruguru', color: 'var(--color-faction-guruguru)', gradient: '...' },
  miracle:  { name: 'Miracle',  color: 'var(--color-faction-miracle)',  gradient: '...' },
  neutral:  { name: 'Neutral',  color: 'var(--color-faction-neutral)',  gradient: '...' },
}
```

## Phase 文字列の置き換え 【優先度: 中】

`PHASES` 定数を使用する。

| ファイル | 行 | 内容 |
|---------|-----|------|
| `features/battle/components/BattleFieldPage.tsx` | 13-20 | `phaseLabels` オブジェクトのキー |
| `features/battle/lib/npcGame.ts` | 21 | `currentPhase: 'main'` |

## Zone 文字列の置き換え 【優先度: 中】

`ZONES` 定数を使用する。

| ファイル | 行 | 内容 |
|---------|-----|------|
| `features/battle/components/BattleFieldPage.tsx` | 67-84 | `'frontend'`, `'backend'`, `'support'` 文字列 |
| `features/battle/components/field/FieldLayout.tsx` | 39-50 | zone includes チェック |
| `features/card/components/CardFilterBar.tsx` | 65 | `<option value="support">` |

## Action Type 文字列の置き換え 【優先度: 中】

`ACTION_TYPES` 定数を使用する。

| ファイル | 行 | 内容 |
|---------|-----|------|
| `features/battle/hooks/useBattleActions.ts` | 21-41 | `'play_card'`, `'attack'`, `'scale_up'`, `'end_phase'` |

## NPC ゲームモックの初期値 【優先度: 低】

`INITIAL_VALUES` を使用する。

| ファイル | 行 | 現状 → 修正 |
|---------|-----|------------|
| `features/battle/lib/npcGame.ts` | 13 | `5` → `INITIAL_VALUES.handSize` |
| 同上 | 26 | `120` → `INITIAL_VALUES.timeBank` (※480のはず、要確認) |
| 同上 | 35 | `3` → `INITIAL_VALUES.slotsPerZone` |
| 同上 | 49 | `25` → `INITIAL_VALUES.deckSize - INITIAL_VALUES.handSize` |

## mockData.ts の整理 【優先度: 低】

`src/lib/api/mockData.ts` に 20+ のハードコード faction/card type 文字列がある。
モックデータなので優先度は低いが、将来的には API から取得する `cards.json` のデータで置き換えるのが理想。

---

## 完了済み（参考）

以下はサーバー側作業で移行完了済み：

- `types/game.ts`：`GamePhase`, `Rank`, `InstanceFamily`, `EffectDuration`, `Zone` → `generated/constants.ts` から re-export
- `types/ws.ts`：`GameActionType`, `InstanceFamily` → 生成版に変更
- `types/api.ts`：`FactionId` → 生成版に変更
- `types/card.ts`：`Restriction` → 生成版に変更、`request_cost` → `maintenance_cost` 修正
- `generated/constants.ts`：自動生成ファイル作成

## 生成ファイルの再生成方法

```bash
# server リポジトリから
make generate

# または直接
python3 /path/to/overload-party-common/scripts/generate_from_yaml.py \
  --server-dir /path/to/overload-party-server \
  --client-dir /path/to/overload-party-client
```

定数を変更する場合は `data/constants.json` を編集してから再生成してください。
