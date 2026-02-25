# コードレビュー：ハードコードされたカードIDの改善提案

## 概要

現在のコードベースには、カードIDがハードコードされている箇所が多数あります。
これらを**データ駆動設計**に移行することで、拡張性と保守性を大幅に向上できます。

## 問題箇所の分類

### 🔴 優先度：高（すでに改善済み）

#### ✅ 1. リソース固有のパッシブ効果 (stats.go)
**現状**: `resourcePassiveTPBonusLegacy()`, `resourcePassiveDVGenBonusLegacy()`
```go
case 27: // Aozora Opener
case 76: // Miracle APEX
case 6:  // ラム
case 8:  // Aurora
case 10: // Daikichi
```

**改善**: ✅ **完了** - データ駆動のパッシブ効果システムに移行済み

---

### 🟡 優先度：中（改善推奨）

#### 2. Platform/Support効果 (stats.go)

**問題箇所**:
- `platformTPBonus()` (272-297行)
- `ScaleUpCostReduction()` (192-230行)

**ハードコード例**:
```go
switch sup.CardID {
case 13: // SWS Front: SWS Compute TP +200
case 35: // Aozora Hub: Aozora Compute TP +200
case 64: // Guruguru Cloud Run: Guruguru Compute TP +200
case 88: // Miracle RAC Platform: Scale Cost -300
}
```

**影響**: Platformカードを追加するたびにコード修正が必要

**改善案**: Platformカード自体に効果を定義
```json
{
  "card_no": 13,
  "card_name": "SWS Front",
  "card_type": "Platform",
  "platform_effects": [
    {
      "type": "tp_bonus_to_allies",
      "params": {
        "target_faction": "SWS",
        "target_card_types": ["Compute", "AI/ML", "Orchestrator"],
        "bonus": 200
      }
    },
    {
      "type": "scale_cost_reduction",
      "params": {
        "target_faction": "SWS",
        "reduction": 200
      }
    }
  ]
}
```

---

#### 3. Attachment効果 (stats.go)

**問題箇所**:
- `attachmentTPBonus()` (374-382行)
- `attachmentDVGenBonus()` (384-392行)
- `attachmentAVBonus()` (394-407行)

**ハードコード例**:
```go
case 17: // SWS API Gateway: TP +200
case 62: // Guruguru Profiler: TP +200
case 60: // Guruguru Dataflow: DV Gen +300, AV -100
case 23: // Multi-AZ: AV +500
case 87: // Miracle RAC: AV +400
```

**影響**: Attachmentカードを追加するたびにコード修正が必要

**改善案**: Attachmentカード自体に効果を定義
```json
{
  "card_no": 17,
  "card_name": "SWS API Gateway",
  "card_type": "Attachment",
  "attachment_effects": [
    {
      "type": "tp_bonus",
      "params": {
        "bonus": 200
      }
    }
  ]
}
```

---

#### 4. 特殊効果 (stats.go)

**問題箇所**:
```go
// #74 Katastrophe: Always Free
if instance.CardID == 74 && instance.Rank == model.RankSmall {
    reduction = 999999 // Effectively free
}

// #10 Daikichi + #124 Duck synergy
if instance.CardID == 10 {
    if effect.HasCardOnField(field, 124) {
        bonus += 200
    }
}
```

**改善案**: パッシブ効果として定義（すでに対応可能）

---

### 🟢 優先度：低（将来的な改善）

#### 5. NPC デプロイ時の選択 (npc/ai.go)

**問題箇所**: `deployChoiceFor()` (757-767行)
```go
switch cardNo {
case 7:   // Smile RDS: "use"
case 11:  // Egao Cache: "redis"
case 125: // Guruguru Cache: "redis"
}
```

**影響**: 選択肢付きカードを追加するたびにNPC AIコードの修正が必要

**改善案**: カード定義に推奨選択を追加
```json
{
  "card_no": 7,
  "card_name": "Smile RDS",
  "recommended_choice": "use",
  "choice_reasoning": "use saves budget long-term"
}
```

---

#### 6. effect/init.go のカード効果登録

**問題**: 各カードの効果を手動で登録
```go
r.RegisterComposed(27, TriggerActivate, ...)
r.RegisterComposed(76, TriggerActivate, ...)
r.RegisterComposed(100, TriggerActivate, SearchRepo{""})
```

**改善案**: cards.jsonに効果定義を統合
```json
{
  "card_no": 100,
  "effects": [
    {
      "trigger": "activate",
      "ops": [
        {"op": "search_repo", "faction": ""}
      ]
    }
  ]
}
```

---

## 改善の優先順位

### Phase 1 (完了 ✅)
- [x] リソース固有のパッシブ効果 → データ駆動化

### Phase 2 (推奨)
1. **Platform効果のデータ駆動化**
   - 影響: カード#13, #35, #64, #88など
   - 工数: 中
   - メリット: Platformカード追加が容易に

2. **Attachment効果のデータ駆動化**
   - 影響: カード#17, #23, #60, #62, #87など
   - 工数: 中
   - メリット: Attachmentカード追加が容易に

### Phase 3 (将来的)
1. NPC選択ロジックのデータ駆動化
2. effect/init.goの効果登録の自動化

---

## 設計パターン

### 推奨パターン：エフェクトベース設計

```
CardDefinition
├── passive_effects[]      // リソース自身の継続効果
├── platform_effects[]     // Platformとしての効果（他カードへの影響）
├── attachment_effects[]   // Attachmentとしての効果（装着先への影響）
├── triggered_effects[]    // トリガー型効果（既存のeffects）
└── recommended_choice     // NPCの推奨選択
```

### データ駆動化のメリット

| 項目 | Before | After |
|------|--------|-------|
| **カード追加** | コード修正 + JSON追加 | JSON追加のみ |
| **効果変更** | コード修正 + 再コンパイル | JSON修正のみ |
| **テスト** | カードごとにテストコード | 汎用テストで対応 |
| **バランス調整** | エンジニアが必要 | プランナーが可能 |

---

## 次のステップ

1. **Platform効果のデータ駆動化** を優先的に実装
2. **Attachment効果のデータ駆動化** を次に実装
3. 段階的に移行し、レガシーコードを削除

各フェーズの詳細な実装ガイドは別途作成予定。
