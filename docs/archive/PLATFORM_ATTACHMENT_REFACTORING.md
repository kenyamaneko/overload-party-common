# Platform & Attachment効果のデータ駆動化

## 設計案

### 1. 型定義の拡張

```go
// internal/model/passive_effect.go

// PlatformEffectType represents effects that Platform cards provide to other cards.
type PlatformEffectType string

const (
    PlatformTPBonus            PlatformEffectType = "tp_bonus"
    PlatformDVGenBonus         PlatformEffectType = "dv_gen_bonus"
    PlatformAVBonus            PlatformEffectType = "av_bonus"
    PlatformScaleCostReduction PlatformEffectType = "scale_cost_reduction"
    PlatformDeployCostReduction PlatformEffectType = "deploy_cost_reduction"
)

// PlatformEffect defines effects a Platform card provides to ally cards.
type PlatformEffect struct {
    Type   PlatformEffectType     `json:"type"`
    Params map[string]interface{} `json:"params"`
}

// PlatformEffectConfig stores the configuration for a platform effect.
type PlatformEffectConfig struct {
    TargetFaction    string   `json:"target_faction,omitempty"`     // "SWS", "Aozora", etc.
    TargetCardTypes  []string `json:"target_card_types,omitempty"`  // ["Compute", "AI/ML"]
    Bonus            int64    `json:"bonus,omitempty"`              // Bonus amount
    Reduction        int64    `json:"reduction,omitempty"`          // Cost reduction amount
    ApplyToSelf      bool     `json:"apply_to_self,omitempty"`      // Include self
}

// AttachmentEffect defines effects an Attachment provides to its host.
type AttachmentEffect struct {
    Type   string                 `json:"type"` // "tp_bonus", "dv_gen_bonus", "av_bonus"
    Params map[string]interface{} `json:"params"`
}

// AttachmentEffectConfig stores the configuration for an attachment effect.
type AttachmentEffectConfig struct {
    StatType string `json:"stat_type"` // "tp", "dv_gen", "av"
    Bonus    int64  `json:"bonus"`     // Can be negative
}
```

### 2. CardDefinition への追加

```go
type CardDefinition struct {
    // ... existing fields ...
    PassiveEffects    []PassiveEffect    `json:"passive_effects,omitempty"`    // Own passive effects
    PlatformEffects   []PlatformEffect   `json:"platform_effects,omitempty"`   // Effects to allies (Platform cards)
    AttachmentEffects []AttachmentEffect `json:"attachment_effects,omitempty"` // Effects to host (Attachment cards)
}
```

### 3. cards.json の例

#### Platform カード例: #13 SWS Front

```json
{
  "card_no": 13,
  "card_name": "SWS Front",
  "faction": "SWS",
  "card_type": "Platform",
  "platform_effects": [
    {
      "type": "tp_bonus",
      "params": {
        "target_faction": "SWS",
        "target_card_types": ["Compute", "AI/ML", "Orchestrator", "Container", "Serverless"],
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

#### Attachment カード例: #17 SWS API Gateway

```json
{
  "card_no": 17,
  "card_name": "SWS API Gateway",
  "faction": "SWS",
  "card_type": "Attachment",
  "attachment_effects": [
    {
      "type": "stat_bonus",
      "params": {
        "stat_type": "tp",
        "bonus": 200
      }
    }
  ]
}
```

#### 複数効果を持つカード例: #60 Guruguru Dataflow

```json
{
  "card_no": 60,
  "card_name": "Guruguru Dataflow",
  "faction": "Guruguru",
  "card_type": "Attachment",
  "attachment_effects": [
    {
      "type": "stat_bonus",
      "params": {
        "stat_type": "dv_gen",
        "bonus": 300
      }
    },
    {
      "type": "stat_bonus",
      "params": {
        "stat_type": "av",
        "bonus": -100
      }
    }
  ]
}
```

### 4. 計算エンジンの実装

```go
// internal/engine/platform.go

// CalculatePlatformBonus calculates bonuses from Platform cards in support zone.
func CalculatePlatformBonus(instance *model.ResourceInstance, field *model.Field, statType string, cc *cache.CardCache) int64 {
    bonus := int64(0)

    for _, sup := range field.Support {
        if sup == nil {
            continue
        }

        platformCard := cc.Get(sup.CardID)
        if platformCard == nil || len(platformCard.PlatformEffects) == 0 {
            continue
        }

        for _, pe := range platformCard.PlatformEffects {
            bonus += applyPlatformEffect(pe, instance, statType, cc)
        }
    }

    return bonus
}

func applyPlatformEffect(pe model.PlatformEffect, target *model.ResourceInstance, statType string, cc *cache.CardCache) int64 {
    cfg := pe.GetConfig()
    targetCard := cc.Get(target.CardID)
    if targetCard == nil {
        return 0
    }

    // Check faction match
    if cfg.TargetFaction != "" && targetCard.Faction != cfg.TargetFaction {
        return 0
    }

    // Check card type match
    if len(cfg.TargetCardTypes) > 0 {
        matched := false
        for _, ct := range cfg.TargetCardTypes {
            if targetCard.CardType == ct {
                matched = true
                break
            }
        }
        if !matched {
            return 0
        }
    }

    switch pe.Type {
    case model.PlatformTPBonus:
        if statType == "tp" {
            return cfg.Bonus
        }
    case model.PlatformDVGenBonus:
        if statType == "dv_gen" {
            return cfg.Bonus
        }
    case model.PlatformAVBonus:
        if statType == "av" {
            return cfg.Bonus
        }
    }

    return 0
}

// CalculateAttachmentBonus calculates bonuses from attached cards.
func CalculateAttachmentBonus(instance *model.ResourceInstance, statType string, cc *cache.CardCache) int64 {
    bonus := int64(0)

    for _, att := range instance.Attachments {
        attCard := cc.Get(att.CardID)
        if attCard == nil || len(attCard.AttachmentEffects) == 0 {
            continue
        }

        for _, ae := range attCard.AttachmentEffects {
            if cfg := ae.GetConfig(); cfg.StatType == statType {
                bonus += cfg.Bonus
            }
        }
    }

    return bonus
}
```

### 5. stats.go の更新

```go
// Before (Legacy)
result += platformTPBonus(instance, field, cc)
result += attachmentTPBonus(instance, cc)

// After (Data-driven)
result += CalculatePlatformBonus(instance, field, "tp", cc)
result += platformTPBonusLegacy(instance, field, cc)  // Fallback

result += CalculateAttachmentBonus(instance, "tp", cc)
result += attachmentTPBonusLegacy(instance, cc)  // Fallback
```

### 6. ScaleUpCostReduction の更新

```go
// Before
func ScaleUpCostReduction(...) {
    switch sup.CardID {
    case 13: reduction += 200
    case 35: reduction += 200
    // ...
    }
}

// After
func ScaleUpCostReduction(...) {
    // Check platform effects
    for _, sup := range field.Support {
        platformCard := cc.Get(sup.CardID)
        for _, pe := range platformCard.PlatformEffects {
            if pe.Type == model.PlatformScaleCostReduction {
                cfg := pe.GetConfig()
                if matchesTarget(instance, cfg, cc) {
                    reduction += cfg.Reduction
                }
            }
        }
    }

    // Check own passive (e.g., #74 Always Free)
    card := cc.Get(instance.CardID)
    for _, pe := range card.PassiveEffects {
        if pe.Type == model.PassiveScaleCostReduction {
            reduction += evaluateScaleCostReduction(pe, instance)
        }
    }
}
```

## 移行計画

### Step 1: 型定義とヘルパー関数 ✅
- [x] PlatformEffect, AttachmentEffect型を定義
- [x] GetConfig()メソッドを実装

### Step 2: 計算エンジン ✅
- [x] CalculatePlatformBonus()を実装
- [x] CalculateAttachmentBonus()を実装
- [x] CalculatePlatformScaleCostReduction()を実装

### Step 3: stats.goの更新 ✅
- [x] platformTPBonus → platformTPBonusLegacy
- [x] platformDVGenBonus → platformDVGenBonusLegacy
- [x] attachmentTPBonus → attachmentTPBonusLegacy
- [x] attachmentDVGenBonus → attachmentDVGenBonusLegacy
- [x] attachmentAVBonus → attachmentAVBonusLegacy
- [x] 新しいCalculatePlatformBonusを呼び出し
- [x] 新しいCalculateAttachmentBonusを呼び出し
- [x] ScaleUpCostReductionの更新

### Step 4: cards.jsonへの移行 🔄
- [ ] Platform カード (#13, #35, #64, #88) に platform_effects 追加
- [ ] Attachment カード (#17, #23, #60, #62, #87) に attachment_effects 追加

### Step 5: テストと検証 ✅
- [x] 既存のユニットテストが全てパス
- [ ] シミュレーションテストで動作確認
- [ ] レガシーコード削除（JSONへの移行完了後）

## メリット

1. **Platformカード追加が容易**: JSONにeffectsを記述するだけ
2. **バランス調整が簡単**: コード変更不要で効果値を調整可能
3. **保守性向上**: カードロジックとゲームエンジンが分離
4. **テストしやすい**: 汎用テストでカバレッジ向上
