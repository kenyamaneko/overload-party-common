# ADR-006: Discriminated Union の YAML DSL 表現（棄却）

## ステータス

Superseded by [ADR-002](002-battle-server-csharp-separation.md)

> **注記**: この ADR は当時実際には起票されなかった設計判断を、後日、残存するメモから推測して再構築したもの。ADR-003 / ADR-004 と同一の検討パッケージに含まれていた。推測の根拠:
>
> - `docs/notes/PROMPT_WS_REPO_SPLIT.md` の「Discriminated Union（判別共用体）」セクションに DSL 案および Go/TS 生成イメージが詳細記載
> - 現在の YAML 定義（`data/` 配下）には `discriminator` / `variants` 構文を使った定義が存在しない
> - Battle の C# 側で `ActionData` を基底とするクラス階層が実装されていることを確認

## 結論

判別共用体を YAML DSL（`discriminator` + `variants`）で表現し Go/TS に生成する案を棄却する。ADR-004（WS 型の YAML codegen）ごと棄却されたため、この DSL も実装されなかった。

現行アーキテクチャ（Gateway + Battle）では判別共用体は以下で表現される：

- **Battle (C#)**: `ActionData` 抽象基底クラスと `PlayCardActionData` 等の派生クラス
- シリアライズ時に `type` フィールド + ポリモーフィックペイロードを出力
- Gateway は JSON を変換せずパススルー
- Client (TS) はエンベロープの `type` を見て手書きの discriminated union で分岐

結果：YAML DSL 不要、Go 側の生成不要、Python スクリプト不要、という構成に落ち着いた。

## 背景・課題

`AvailableAction` のように、`type` フィールドの値によってペイロードの構造が変わる型（判別共用体 / discriminated union）が複数存在した：

- `play_card` → hand_instance_id, card_id, valid_zones, valid_targets
- `attack` → source_instance_id, valid_targets
- `scale_up` → source_instance_id, target_rank, instance_family

これを Go と TS の両方で型安全に扱いたかった。

## 不採用案

### YAML DSL による判別共用体の一元定義（本 ADR の提案、棄却）

YAML に `discriminator` + `variants` を記述し、Go と TS それぞれに最適な形に生成する。

YAML DSL:

```yaml
types:
  AvailableAction:
    discriminator: type
    variants:
      play_card:
        - { name: hand_instance_id, type: string,   json: "handInstanceId" }
        - { name: card_id,          type: int,      json: "cardId" }
        - { name: valid_zones,      type: "string[]", json: "validZones",  optional: true }
        - { name: valid_targets,    type: "string[]", json: "validTargets", optional: true }
      attack:
        - { name: source_instance_id, type: string,   json: "sourceInstanceId" }
        - { name: valid_targets,      type: "string[]", json: "validTargets" }
      scale_up:
        - { name: source_instance_id, type: string,  json: "sourceInstanceId" }
        - { name: target_rank,        type: Rank,    json: "targetRank" }
        - { name: instance_family,    type: string?, json: "instanceFamily", optional: true }
```

Go 生成イメージ:

```go
type AvailableActionPlayCard struct {
    Type           string   `json:"type"`  // "play_card"
    HandInstanceID string   `json:"handInstanceId"`
    CardID         int64    `json:"cardId"`
    ValidZones     []string `json:"validZones,omitempty"`
    ValidTargets   []string `json:"validTargets,omitempty"`
}
```

TS 生成イメージ:

```typescript
export type AvailableAction =
  | { type: "play_card"; handInstanceId: string; cardId: number; validZones?: string[]; validTargets?: string[] }
  | { type: "attack"; sourceInstanceId: string; validTargets: string[] }
  | { type: "scale_up"; sourceInstanceId: string; targetRank: Rank; instanceFamily?: string };
```

棄却理由: ADR-004 の棄却に伴い前提となる codegen パイプラインが存在しなくなった。
