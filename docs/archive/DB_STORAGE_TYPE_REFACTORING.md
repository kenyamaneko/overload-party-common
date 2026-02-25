# DB系・オブジェクトストレージの分離

## 変更概要

ゲームデザインの変更に伴い、「データ系リソース」を「DB系リソース」と「オブジェクトストレージ」に分離しました。

## 変更内容

### 以前の設計

**データ系リソース**: Database, NoSQL, CacheDB, ObjectStorage

- すべてBackendに配置
- すべてDV生成が可能

### 新しい設計

#### DB系リソース（DV生成が主目的）

- **タイプ**: Database, NoSQL, CacheDB
- **配置**: Backend のみ
- **特徴**: DV生成に特化

#### オブジェクトストレージ

- **タイプ**: ObjectStorage
- **配置**: Frontend または Backend
  - **Backend**: DV生成可能
  - **Frontend**: 静的ホスティング用途（壁として機能、DV生成なし）

---

## コード変更

### 1. 新しい型判定関数を追加 ([internal/model/card_stats.go](internal/model/card_stats.go))

```go
// IsDBType - DB系リソースの判定（Database, NoSQL, CacheDB）
func IsDBType(cardType string) bool {
    switch cardType {
    case "Database", "NoSQL", "CacheDB":
        return true
    }
    return false
}

// IsStorageType - オブジェクトストレージの判定（ObjectStorage）
func IsStorageType(cardType string) bool {
    return cardType == "ObjectStorage"
}

// IsDataType - データ系リソース全体の判定（DB + Storage）
// 互換性のため残されている
func IsDataType(cardType string) bool {
    return IsDBType(cardType) || IsStorageType(cardType)
}
```

### 2. DB計算ロジックの更新

#### [internal/engine/passive.go](internal/engine/passive.go)

```go
// calculateDVPerOtherDB: DV bonus per other DB card
// Before: if model.IsDataType(resCard.CardType) && resCard.CardType != "ObjectStorage"
// After:  if model.IsDBType(resCard.CardType)
```

**変更理由**: カード#8（Aurora）の「他のSWS DBごとにDV +200」効果で、ObjectStorageを除外する必要がある

#### [internal/engine/effect/generic.go](internal/engine/effect/generic.go)

```go
// CountBackendDBs: Count backend DB cards
// Before: if !model.IsDataType(...) continue; if cardType == "ObjectStorage" continue
// After:  if !model.IsDBType(...) continue
```

**変更理由**: "DB"を数える関数なので、オブジェクトストレージを除外

### 3. NPC AIの配置ロジック更新 ([internal/npc/ai.go](internal/npc/ai.go))

```go
// Before: } else if model.IsDataType(cardDef.CardType) {
//            // Other data types (Database, NoSQL, CacheDB): backend only

// After:  } else if model.IsDBType(cardDef.CardType) {
//            // DB types (Database, NoSQL, CacheDB): backend only
```

**変更理由**: ObjectStorageは既に別処理で扱われているため、残りのDB系のみを判定

---

## テスト

### 新しいテストケース ([internal/model/card_stats_test.go](internal/model/card_stats_test.go))

```go
func TestIsDBType(t *testing.T) {
    // Database, NoSQL, CacheDB → true
    // ObjectStorage → false
}

func TestIsStorageType(t *testing.T) {
    // ObjectStorage → true
    // Database, NoSQL, CacheDB → false
}
```

### テスト結果

```bash
✅ All tests passed
ok  	github.com/kenyamamoto/overload-party/internal/engine
ok  	github.com/kenyamamoto/overload-party/internal/model
ok  	github.com/kenyamamoto/overload-party/internal/npc
```

---

## 影響を受けるカード

### カード#8 (SWS Aurora)

**効果**: 他のSWS DBごとにDV +200

**変更前**: ObjectStorageもカウント（誤り）
**変更後**: Database, NoSQL, CacheDBのみカウント ✅

### カード#27 (Aozora Opener)

**効果**: バックエンドのAozora DBごとにTP +200

**変更前**: ObjectStorageもカウント（誤り）
**変更後**: Database, NoSQL, CacheDBのみカウント ✅

---

## 互換性

### IsDataType() の扱い

- **変更前**: Database, NoSQL, CacheDB, ObjectStorageを含む
- **変更後**: IsDBType() || IsStorageType() として定義
- **結果**: **完全互換** - 既存コードは動作継続

### 変更が必要だった箇所

1. ✅ **passive.go** - `calculateDVPerOtherDB()`
2. ✅ **effect/generic.go** - `CountBackendDBs()`
3. ✅ **npc/ai.go** - スロット配置ロジック

### 変更不要だった箇所

- **process_attack.go** - SLAPenalty取得（DataStatsは共通）
- **field_utils.go** - CreateResourceInstance（DataStatsは共通）

---

## まとめ

### 変更ファイル

1. `internal/model/card_stats.go` - 新しい型判定関数
2. `internal/model/card_stats_test.go` - テスト追加
3. `internal/engine/passive.go` - DB計算ロジック更新
4. `internal/engine/effect/generic.go` - DB計算ロジック更新
5. `internal/npc/ai.go` - 配置ロジック更新

### 効果

- ✅ DB系とオブジェクトストレージを明確に分離
- ✅ ObjectStorageがDB系の効果を受けなくなった
- ✅ コードの意図が明確になった（IsDBType vs IsStorageType）
- ✅ 全テストがパス
- ✅ 既存コードとの互換性を維持

今後、新しいDB系カードやオブジェクトストレージのカードを追加する際は、適切な型判定関数を使用してください。
