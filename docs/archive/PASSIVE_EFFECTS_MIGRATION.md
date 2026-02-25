# パッシブ効果のデータ駆動設計への移行ガイド

## 概要

カードのパッシブ効果（継続効果）を、ハードコードからデータ駆動設計に移行します。
これにより、新しいカードを追加する際にコード変更が不要になります。

## 設計

### 1. 型定義 (`internal/model/passive_effect.go`)

```go
type PassiveEffectType string

const (
    PassiveTPPerBackendDB     // TP bonus per backend DB
    PassiveTPIfCardTypeOnField // TP bonus if card type exists
    PassiveDVPerOtherDB       // DV bonus per other DB
    PassiveDVIfCardOnField    // DV bonus if specific card exists
)

type PassiveEffect struct {
    Type   PassiveEffectType
    Params map[string]interface{}
}
```

### 2. cards.jsonへの追加例

#### カード#27（Aozora AI - 智の解放者）

**効果**: バックエンドのAozora DB系リソースおよびオブジェクトストレージ1体につきTP+200、#32は2枚分

```json
{
  "card_no": 27,
  "card_name": "Aozora AI - 智の解放者<オープナー>",
  "passive_effects": [
    {
      "type": "tp_per_backend_db",
      "params": {
        "faction": "Aozora",
        "bonus_per_card": 200,
        "multi_model_cards": [32]
      }
    }
  ]
}
```

#### カード#6（SWS ラム）

**効果**: SWS Storageがフィールドにあると TP+200

```json
{
  "card_no": 6,
  "card_name": "SWS Compute - ラム",
  "passive_effects": [
    {
      "type": "tp_if_card_type_on_field",
      "params": {
        "faction": "SWS",
        "card_types": ["ObjectStorage"],
        "flat_bonus": 200
      }
    }
  ]
}
```

#### カード#76（Miracle APEX）

**効果**: Miracle DBがフィールドにあると TP+400

```json
{
  "card_no": 76,
  "card_name": "Miracle AI - APEX",
  "passive_effects": [
    {
      "type": "tp_if_card_type_on_field",
      "params": {
        "faction": "Miracle",
        "card_types": ["Database", "NoSQL", "CacheDB"],
        "flat_bonus": 400
      }
    }
  ]
}
```

#### カード#8（SWS Aurora）

**効果**: 他のSWS DB 1体につき DV Gen +200

```json
{
  "card_no": 8,
  "card_name": "SWS RDB - アウローラ",
  "passive_effects": [
    {
      "type": "dv_per_other_db",
      "params": {
        "faction": "SWS",
        "bonus_per_card": 200,
        "exclude_self": true
      }
    }
  ]
}
```

#### カード#10（SWS Daikichi）

**効果**: #124（Smile Duck）がフィールドにあると DV Gen +200

```json
{
  "card_no": 10,
  "card_name": "SWS NoSQL - ダイキチ",
  "passive_effects": [
    {
      "type": "dv_if_card_on_field",
      "params": {
        "specific_card_nos": [124],
        "flat_bonus": 200
      }
    }
  ]
}
```

## パラメータ一覧

### 共通パラメータ

- `faction`: 派閥フィルター（例: "Aozora", "SWS"）
- `card_types`: カードタイプフィルター（例: ["Database", "NoSQL"]）
- `bonus_per_card`: カード1枚あたりのボーナス
- `flat_bonus`: 固定ボーナス値
- `zone`: ゾーンフィルター（"backend", "frontend", ""）
- `exclude_self`: 自分自身を除外するか

### 特殊パラメータ

- `multi_model_cards`: 2枚分としてカウントするカードのリスト（例: [32]）
- `specific_card_nos`: 特定のカード番号リスト（例: [124]）

## 移行手順

### 現在のハードコードされた実装

```go
// stats.go (Legacy)
func resourcePassiveTPBonusLegacy(...) {
    switch instance.CardID {
    case 27:
        dbCount := effect.CountBackendDBs(field, "Aozora", cc)
        for _, res := range field.Backend {
            if res.CardID == 32 {
                dbCount += 2
            }
        }
        bonus += int64(dbCount) * 200
    case 76:
        if effect.HasCardTypeOnField(field, "Database", "Miracle", cc) {
            bonus += 400
        }
    }
}
```

### 新しいデータ駆動実装

```go
// passive.go
func CalculatePassiveTPBonus(instance, field, cc) {
    card := cc.Get(instance.CardID)
    for _, pe := range card.PassiveEffects {
        bonus += applyPassiveEffect(pe, instance, field, cc, "tp")
    }
}
```

## メリット

1. **拡張性**: 新しいカードを追加する際、cards.jsonを編集するだけ
2. **保守性**: カード効果がコードではなくデータで管理される
3. **可読性**: カード定義とロジックが分離される
4. **テストしやすさ**: カード効果を簡単にモックできる

## 移行状態

### ✅ 実装済み
- パッシブ効果の型定義
- データ駆動の計算エンジン
- レガシー実装との互換性

### 🔄 移行中
- cards.jsonへのパッシブ効果追加（カード#6, #8, #10, #27, #76など）

### ⏳ TODO
- すべてのパッシブ効果を持つカードの移行
- レガシー実装の削除
- テストケースの追加

## 今後の拡張

新しいパッシブ効果タイプを追加する場合：

1. `PassiveEffectType`に新しい定数を追加
2. `applyPassiveEffect`にケースを追加
3. 必要に応じて計算関数を実装

例：
```go
const PassiveAVPerAllyCount PassiveEffectType = "av_per_ally_count"

func calculateAVPerAllyCount(...) int64 {
    // 実装
}
```
