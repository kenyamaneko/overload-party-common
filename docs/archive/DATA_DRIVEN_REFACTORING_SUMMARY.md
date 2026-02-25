# データ駆動設計への移行 - 実装完了サマリー

## 概要

カードゲームの拡張性と保守性を向上させるため、ハードコードされたカードIDをデータ駆動設計に移行しました。
これにより、新しいカードを追加する際にコード変更が不要になります。

## 完了した項目

### ✅ Phase 1: パッシブ効果のデータ駆動化

**実装済み**: カード自身の継続効果（パッシブ効果）

#### 新規追加ファイル
- `internal/model/passive_effect.go` - パッシブ効果の型定義
- `internal/engine/passive.go` - データ駆動の計算エンジン

#### 対応効果タイプ
```go
PassiveTPPerBackendDB     // TP bonus per backend DB (e.g., #27 Aozora Opener)
PassiveTPIfCardTypeOnField // TP bonus if card type exists (e.g., #6 ラム, #76 APEX)
PassiveDVPerOtherDB       // DV bonus per other DB (e.g., #8 Aurora)
PassiveDVIfCardOnField    // DV bonus if specific card exists (e.g., #10 Daikichi)
PassiveScaleCostFree      // Scale cost is free (e.g., #74 Always Free)
```

#### 影響を受けるカード
- カード #6 (SWS ラム)
- カード #8 (SWS Aurora)
- カード #10 (SWS Daikichi)
- カード #27 (Aozora Opener)
- カード #76 (Miracle APEX)

---

### ✅ Phase 2: Platform & Attachment効果のデータ駆動化

**実装済み**: Platformカードによる効果とAttachmentカードによる効果

#### 新規追加関数（passive.go）
```go
CalculatePlatformBonus()              // Platform → リソースへのボーナス
CalculateAttachmentBonus()            // Attachment → ホストへのボーナス
CalculatePlatformScaleCostReduction() // Platform → スケールコスト削減
```

#### 対応効果タイプ

**Platform Effects:**
```go
PlatformTPBonus            // TP +X to allies
PlatformDVGenBonus         // DV Gen +X to allies
PlatformAVBonus            // AV +X to allies
PlatformScaleCostReduction // Scale Cost -X for allies
PlatformDeployCostReduction // Deploy Cost -X for allies (future)
```

**Attachment Effects:**
```go
AttachmentStatBonus // Generic stat bonus (TP, DV Gen, AV)
```

#### 影響を受けるカード

**Platform:**
- カード #13 (SWS Front) - SWS Compute TP +200, Scale Cost -200
- カード #35 (Aozora Hub) - Aozora Compute TP +200, Scale Cost -200
- カード #64 (Guruguru Cloud Run) - Guruguru Compute TP +200, Scale Cost -200
- カード #88 (Miracle RAC Platform) - Miracle Scale Cost -300

**Attachment:**
- カード #17 (SWS API Gateway) - TP +200
- カード #23 (Multi-AZ) - AV +500
- カード #60 (Guruguru Dataflow) - DV Gen +300, AV -100
- カード #62 (Guruguru Profiler) - TP +200
- カード #87 (Miracle RAC) - AV +400

---

## アーキテクチャ

### デュアルシステム設計

新旧システムの共存により、段階的な移行を実現：

```go
// stats.go の例
result += CalculatePlatformBonus(instance, field, "tp", cc)      // 新: データ駆動
result += platformTPBonusLegacy(instance, field, cc)             // 旧: レガシー（フォールバック）
```

### データフロー

```
cards.json
  ↓
CardDefinition {
  passive_effects: []    // 自身の継続効果
  platform_effects: []   // Platformとしての効果
  attachment_effects: [] // Attachmentとしての効果
}
  ↓
CalculateEffectiveTP/DV/AV
  ↓
データ駆動関数 + レガシー関数（フォールバック）
```

---

## cards.jsonの例

### Platform カード例
```json
{
  "card_no": 13,
  "card_name": "SWS Front",
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

### Attachment カード例
```json
{
  "card_no": 60,
  "card_name": "Guruguru Dataflow",
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

---

## レガシーコードの状態

### リネーム済み関数（今後削除予定）

**stats.go:**
```go
resourcePassiveTPBonusLegacy()    // 旧: resourcePassiveTPBonus
resourcePassiveDVGenBonusLegacy() // 旧: resourcePassiveDVGenBonus
platformTPBonusLegacy()           // 旧: platformTPBonus
platformDVGenBonusLegacy()        // 旧: platformDVGenBonus
attachmentTPBonusLegacy()         // 旧: attachmentTPBonus
attachmentDVGenBonusLegacy()      // 旧: attachmentDVGenBonus
attachmentAVBonusLegacy()         // 旧: attachmentAVBonus
scaleUpCostReductionLegacy()      // 旧: ScaleUpCostReduction の一部
```

これらの関数は、cards.jsonへのデータ移行が完了次第削除します。

---

## ✅ 完了した作業

### ✅ Step 4: cards.jsonへのデータ移行

1. **Platformカード** ✅
   - [x] #13 SWS Front に `platform_effects` 追加
   - [x] #35 Aozora CDN に `platform_effects` 追加
   - [x] #64 Guruguru だんごフロー に `platform_effects` 追加

2. **Attachmentカード** ✅
   - [x] #17 SWS Gateway に `attachment_effects` 追加
   - [x] #23 Aozora VM - ソラ に `attachment_effects` 追加
   - [x] #60 Guruguru CDN に `attachment_effects` 追加
   - [x] #62 Guruguru Profiler に `attachment_effects` 追加

3. **Passiveカード** ✅
   - [x] #6 SWS Serverless - ラム に `passive_effects` 追加
   - [x] #8 SWS DestributedDB - オオロバ に `passive_effects` 追加
   - [x] #10 SWS NoSQL - ダイナ に `passive_effects` 追加
   - [x] #27 Aozora AI - 智の解放者<オープナー> に `passive_effects` 追加
   - [x] #74 Miracle Orchestrator - Konzernetes に `passive_effects` 追加
   - [x] #76 Miracle Low-Code - アピエッタ に `passive_effects` 追加

### ✅ Step 5: レガシーコードの削除

- [x] `resourcePassiveTPBonusLegacy` 削除
- [x] `resourcePassiveDVGenBonusLegacy` 削除
- [x] `platformTPBonusLegacy` 削除
- [x] `platformDVGenBonusLegacy` 削除
- [x] `attachmentTPBonusLegacy` 削除
- [x] `attachmentDVGenBonusLegacy` 削除
- [x] `attachmentAVBonusLegacy` 削除
- [x] `scaleUpCostReductionLegacy` 削除
- [x] Legacy関数呼び出しを削除
- [x] 不要なインポート (`effect` パッケージ) を削除
- [x] Legacyテストを削除
- [x] 統合テストで全カードの動作確認

---

## メリット

| 項目 | Before | After |
|------|--------|-------|
| **カード追加** | コード修正 + JSON追加 | JSON追加のみ ✅ |
| **効果変更** | コード修正 + 再コンパイル | JSON修正のみ ✅ |
| **テスト** | カードごとにテストコード | 汎用テストで対応 ✅ |
| **バランス調整** | エンジニアが必要 | プランナーが可能 ✅ |

---

## テスト結果

```bash
$ go test ./internal/engine/...
ok  	github.com/kenyamamoto/overload-party/internal/engine	0.544s
ok  	github.com/kenyamamoto/overload-party/internal/engine/effect	0.308s
```

✅ 全てのテストが成功

---

## まとめ

- ✅ **Phase 1完了**: パッシブ効果のデータ駆動化
- ✅ **Phase 2完了**: Platform & Attachment効果のデータ駆動化
- 🔄 **Phase 3進行中**: cards.jsonへのデータ移行
- ⏳ **Phase 4予定**: レガシーコードの削除

これにより、今後の新カード追加時にコード変更が不要になり、
バランス調整もJSONファイルの編集だけで可能になります。
