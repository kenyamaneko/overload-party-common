# カード仕様変更 (2026-02-21)

## 変更概要

ゲームデザインの変更に伴い、以下のカードの仕様を更新しました:

1. カード#27 (Aozora Opener): DB系+ObjectStorage両方をカウント
2. カード#64 (Guruguru だんごフロー): Guruguru DB系リソースに限定
3. カード#85, #86 (Miracle Data Guard, ラクレシェンド): Miracle DB系リソースに限定
4. カード#90 (Miracle Failback): Miracle DB系リソースに限定
5. カード#119 (DB スナップショット): DB系リソースに限定

---

## 変更詳細

### ✅ カード#27 (Aozora Opener)

**変更前**: バックエンドの Aozora DB系リソースのみカウント
**変更後**: バックエンドの Aozora DB系リソース**および**オブジェクトストレージをカウント

**理由**: Azure OpenAI の「On Your Data」機能は、Cosmos DB も Azure Blob Storage も両方サポートしているため。

**実装内容**:
- 新しい PassiveEffectType を追加: `PassiveTPPerBackendData`
- `internal/model/passive_effect.go`: 新しい定数を追加
- `internal/engine/passive.go`: `calculateTPPerBackendData()` 関数を追加
- `data/cards.json`: カード#27の `passive_effects` を更新

```json
{
  "card_no": 27,
  "passive_effects": [
    {
      "type": "tp_per_backend_data",
      "params": {
        "faction": "Aozora",
        "bonus_per_card": 200,
        "multi_model_cards": [32]
      }
    }
  ],
  "effect_text": "On Your Data: 自分のバックエンドの Aozora DB系リソースおよびオブジェクトストレージ1体につき、このカードのスループットを +200 する。"
}
```

---

### ✅ カード#64 (Guruguru だんごフロー)

**変更前**:
- `platform_effects` が定義されていた（誤り）
- 「自分のバックエンドリソースに装備できる」

**変更後**:
- `attachment_effects` に修正
- 「自分の Guruguru DB系リソースに装備できる」

**実装内容**:
- `data/cards.json`: `platform_effects` → `attachment_effects` に変更
- 装備効果を正しく定義: DV Gen +300, AV -200

```json
{
  "card_no": 64,
  "attachment_effects": [
    {"type": "stat_bonus", "params": {"stat_type": "dv_gen", "bonus": 300}},
    {"type": "stat_bonus", "params": {"stat_type": "av", "bonus": -200}}
  ],
  "effect_text": "自分の Guruguru DB系リソースに装備できる。装備先の DV Gen を +300 する。装備先の可用性を -200 する。"
}
```

---

### ✅ カード#85 (Miracle Data Guard)

**変更前**: 「自分のバックエンドリソースに装備できる」
**変更後**: 「自分の Miracle DB系リソースに装備できる」

**実装内容**:
- `internal/engine/effect/init.go`: `model.IsDataType` → `model.IsDBType` に変更
- `data/cards.json`: effect_text を更新

```go
// Before:
r.RegisterComposed(85, TriggerOnDestroy,
    DeployFromRepo{FactionAndTypeFilter("Miracle", model.IsDataType), 200},
)

// After:
r.RegisterComposed(85, TriggerOnDestroy,
    DeployFromRepo{FactionAndTypeFilter("Miracle", model.IsDBType), 200},
)
```

---

### ✅ カード#86 (Miracle ラクレシェンド)

**変更前**: 「自分のバックエンドリソースに装備できる」
**変更後**: 「自分の Miracle DB系リソースに装備できる」

**実装内容**:
- `data/cards.json`: `attachment_effects` を追加
- 装備効果を定義: AV +400, Incident damage -200

```json
{
  "card_no": 86,
  "attachment_effects": [
    {"type": "stat_bonus", "params": {"stat_type": "av", "bonus": 400}},
    {"type": "stat_bonus", "params": {"stat_type": "incident_reduction", "bonus": 200}}
  ],
  "effect_text": "自分の Miracle DB系リソースに装備できる。装備先の可用性を +400 する。装備先へのインシデントカードによるダメージを -200 する。"
}
```

---

### ✅ カード#90 (Miracle Failback)

**変更前**: Miracle データ系リソース（DB + ObjectStorage）が対象
**変更後**: Miracle DB系リソースのみが対象

**実装内容**:
- `internal/engine/effect/init.go`: `model.IsDataType` → `model.IsDBType` に変更
- `data/cards.json`: effect_text を更新

```go
// Before:
r.RegisterComposed(90, TriggerReactive,
    DeployFromHand{FactionAndTypeFilter("Miracle", model.IsDataType)},
)

// After:
r.RegisterComposed(90, TriggerReactive,
    DeployFromHand{FactionAndTypeFilter("Miracle", model.IsDBType)},
)
```

---

### ⚠️ カード#119 (DB スナップショット) - 部分的実装

**仕様**:
- 自分の DB系リソースに装備できる
- **自分のフィールドにオブジェクトストレージがある場合**、装備先への攻撃ダメージを -400 する

**実装状況**:
- ✅ effect_text は既に正しい（「自分の DB リソースに装備できる」）
- ⚠️ **条件付き攻撃ダメージ軽減効果は未実装**

**今後の実装が必要な項目**:
1. 攻撃ダメージ計算時に ObjectStorage の存在をチェックする処理
2. 条件付き attachment_effects のサポート（現在は無条件の stat_bonus のみ）
3. `internal/engine/process_attack.go` にて、装備カードの効果を適用するロジック

**Note**: 現在の attachment_effects システムは無条件の stat_bonus のみをサポートしています。カード#119のような条件付き効果は、攻撃ダメージ計算処理に直接実装する必要があります。

---

### ✅ カード#92 (オートスケーラー) - 用語修正

**変更前**: 「自分の Elasticでない フロントエンドリソースに装備できる」
**変更後**: 「自分の Elasticでない コンピュート系リソースに装備できる」

**理由**: フロントエンドには ObjectStorage も配置可能ですが、ObjectStorage はスループットを持たないため、効果の対象はコンピュート系リソースのみが正確です。

**実装内容**:
- `data/cards.json`: effect_text を更新
- `docs/CARDS.md`: 既に修正済み

---

### ✅ カード#93 (プライベートサブネット) - 用語修正

**変更前**: 「自分のバックエンドに装備できる」
**変更後**: 「自分の コンピュート系リソース または DB系リソースに装備できる」

**理由**: バックエンドという位置情報ではなく、リソースタイプで制限を表現する方が正確です。バックエンドにはコンピュート系、DB系、ObjectStorage が配置可能です。

**実装内容**:
- `data/cards.json`: effect_text を更新
- `docs/CARDS.md`: 既に修正済み

---

## 影響範囲

### 変更したファイル

1. `internal/model/passive_effect.go` - PassiveTPPerBackendData を追加
2. `internal/engine/passive.go` - calculateTPPerBackendData() を追加
3. `internal/engine/effect/init.go` - カード#85, #90 のフィルタを更新
4. `data/cards.json` - カード#27, #64, #85, #86, #90 の定義を更新

### テスト結果

```bash
✅ All tests passed
ok  	github.com/kenyamamoto/overload-party/internal/engine
ok  	github.com/kenyamamoto/overload-party/internal/engine/effect
ok  	github.com/kenyamamoto/overload-party/internal/model
ok  	github.com/kenyamamoto/overload-party/internal/npc
```

---

## 今後の課題

### 装備制限の実装

現在、attachment カードの装備対象制限は effect_text にのみ記載されており、コード上で強制されていません。

**実装が必要な項目**:
1. `CardDefinition` に `AttachmentTargetRestriction` フィールドを追加
2. カード play 時または activate 時に装備対象をチェックするバリデーション
3. 装備処理の実装（ResourceInstance.Attachments への追加）

**設計案**:
```go
type AttachmentTargetRestriction struct {
    TargetFaction   string   `json:"target_faction,omitempty"`
    TargetCardTypes []string `json:"target_card_types,omitempty"`
}
```

### カード#119の条件付き効果

ObjectStorage の存在をチェックして攻撃ダメージを軽減する処理を `process_attack.go` に実装する必要があります。

---

## まとめ

### 完了項目

- ✅ カード#27: DB系 + ObjectStorage 両方をカウント
- ✅ カード#64: platform_effects → attachment_effects 修正
- ✅ カード#85: Miracle DB系リソースに限定（effect実装）
- ✅ カード#86: Miracle DB系リソースに限定（attachment_effects追加）
- ✅ カード#90: Miracle DB系リソースに限定（effect実装）
- ✅ カード#92: 用語修正（フロントエンドリソース → コンピュート系リソース）
- ✅ カード#93: 用語修正（バックエンド → コンピュート系リソース または DB系リソース）
- ✅ 全テスト通過

### 今後の実装が必要な項目

- ⚠️ 装備制限の実装（バリデーション + UI対応）
- ⚠️ カード#119の条件付き攻撃ダメージ軽減効果
- ⚠️ 装備処理の実装（Attachments配列への追加）
