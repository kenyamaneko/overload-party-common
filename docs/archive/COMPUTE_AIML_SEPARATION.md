# コンピュート系リソースとAI/ML系リソースの分離 (2026-02-21)

## 変更概要

ゲームデザインの変更に伴い、**コンピュート系リソース**と**AI/ML系リソース**を明確に分離しました。

---

## 変更内容

### 以前の設計

**コンピュート系リソース**: Compute, Container, Orchestrator, Serverless, **AI/ML**
- すべて同じカテゴリとして扱われていた
- CDN系Platformカードなどが全てに効果を適用

### 新しい設計

#### コンピュート系リソース

- **タイプ**: Compute, Container, Orchestrator, Serverless
- **AI/MLは除外**

#### AI/ML系リソース（新しい独立カテゴリ）

- **タイプ**: AI/ML
- **独立したカテゴリ**として扱う
- CDN系Platformカードの効果を受けない

---

## コード変更

### 1. 型判定関数の更新 ([internal/model/card_stats.go](internal/model/card_stats.go))

```go
// Before:
func IsComputeType(cardType string) bool {
    switch cardType {
    case "Compute", "Container", "Orchestrator", "Serverless", "AI/ML":
        return true
    }
    return false
}

// After:
func IsComputeType(cardType string) bool {
    switch cardType {
    case "Compute", "Container", "Orchestrator", "Serverless":
        return true
    }
    return false
}

// New function:
func IsAIMLType(cardType string) bool {
    return cardType == "AI/ML"
}
```

### 2. リソースタイプ判定の更新

```go
// IsResourceType now includes AI/ML separately
func IsResourceType(cardType string) bool {
    return IsComputeType(cardType) || IsAIMLType(cardType) || IsDataType(cardType)
}

// Zone eligibility also updated
func IsFrontendEligible(cardType string) bool {
    return IsComputeType(cardType) || IsAIMLType(cardType) || cardType == "ObjectStorage"
}

func IsBackendEligible(cardType string) bool {
    return IsDataType(cardType) || IsComputeType(cardType) || IsAIMLType(cardType)
}
```

### 3. CDNカードの更新 ([data/cards.json](data/cards.json))

#### カード#13 (SWS Front), #35 (Aozora CDN), #60 (Guruguru CDN)

**変更前**:
```json
{
  "target_card_types": ["Compute", "AI/ML", "Orchestrator", "Container", "Serverless"]
}
```

**変更後**:
```json
{
  "target_card_types": ["Compute", "Container", "Orchestrator", "Serverless"]
}
```

**効果**: CDN系Platformカードは**AI/ML系リソースに効果を適用しない**

#### カード#60の追加修正

**問題**: `platform_effects` が null で、誤って `attachment_effects` が設定されていた

**修正**:
- `attachment_effects` → `platform_effects` に移動
- 他のCDNカードと同じ構造に統一

---

## カード仕様の修正

### カード#64 (Guruguru だんごフロー)

**変更前**:
- DV Gen を +300 する
- 可用性を -200 する

**変更後**:
- DV Gen を **+400** する
- SLAペナルティを **+100** する

**実装**:
```json
{
  "card_no": 64,
  "attachment_effects": [
    {"type": "stat_bonus", "params": {"stat_type": "dv_gen", "bonus": 400}},
    {"type": "stat_bonus", "params": {"stat_type": "sla_penalty", "bonus": 100}}
  ]
}
```

### その他のカード

以下のカードのeffect_textを修正（CARDS.mdとの整合性確保）:
- **カード#46** (Aozora Traffic): フロントエンドリソース → コンピュート系リソース
- **カード#62** (Guruguru Profiler): フロントエンドリソース → Guruguru コンピュート系リソース
- **カード#63** (Guruguru ぱくぱくサブレ): フロントエンド → Guruguru コンピュート系リソース

---

## 影響範囲

### 変更したファイル

1. `internal/model/card_stats.go` - IsComputeType(), IsAIMLType() を更新
2. `internal/model/card_stats_test.go` - テストを追加/更新
3. `data/cards.json` - カード#13, #35, #60, #64, #46, #62, #63 を更新

### ゲームプレイへの影響

#### AI/ML系リソースの特徴

**変更前**:
- CDN系Platformカードの効果を受ける（TP +200）
- コンピュート系と同じ扱い

**変更後**:
- CDN系Platformカードの効果を受けない
- 独立したカテゴリとして扱われる
- Zone配置ルールは変更なし（Frontend/Backendどちらも可能）

#### 影響を受けるカード

| カードNo | カード名 | 変更内容 |
|---------|---------|---------|
| 5 | SWS ML - ラフメイカー | CDN効果を受けなくなる |
| 27 | Aozora AI - オープナー | CDN効果を受けなくなる |
| 51 | Guruguru AI - バター X | CDN効果を受けなくなる |
| 52 | Guruguru AI - Dr. テンソルベ | CDN効果を受けなくなる |

---

## テスト結果

```bash
✅ All tests passed
ok  	github.com/kenyamamoto/overload-party/internal/engine
ok  	github.com/kenyamamoto/overload-party/internal/engine/effect
ok  	github.com/kenyamamoto/overload-party/internal/model
ok  	github.com/kenyamamoto/overload-party/internal/npc
```

---

## まとめ

### 完了項目

- ✅ IsComputeType() から AI/ML を除外
- ✅ IsAIMLType() を新規追加
- ✅ Zone eligibility functions を更新
- ✅ CDNカード (#13, #35, #60) から AI/ML を除外
- ✅ カード#60 の platform_effects 修正
- ✅ カード#64 の効果更新（DV Gen +400, SLA Penalty +100）
- ✅ カード#46, #62, #63 の effect_text 修正
- ✅ 全テスト通過

### ゲームバランスへの影響

**AI/ML系リソース**は高スペック（高TP、高コスト）な代わりに：
- CDN系Platformカードの恩恵を受けない
- より戦略的な使い方が必要

これにより、AI/MLカードの強すぎる問題を緩和し、ゲームバランスが改善されます。
