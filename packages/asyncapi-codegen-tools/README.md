# asyncapi-codegen-tools

AsyncAPI 3.0 spec から Go 型を生成する共通 codegen ライブラリ。

## 背景

[ADR-034](../../docs/adr/034-api-contract-ssot-openapi-asyncapi-and-go-module-distribution.md) で AsyncAPI 3.0 を Pub/Sub 契約の SSoT に採用したが、有力候補だった `lerenn/asyncapi-codegen` は以下の理由で採用できなかった:

- broker controller code を強制同梱し、消費側に lerenn extensions パッケージへの transitive 依存を入れる
- `ChannelsPaths` 定数を生成し、Topic 名 SSoT を infra リポに置く方針と矛盾する
- payload schema 型に `Schema` suffix が付き命名がカジュアルでない

ADR-034 が foresee した「自前 emitter 一時併用」を実装したのが本パッケージ。codegen-tools の `go_emitter` を流用し、入力 parser だけ AsyncAPI 用に書いている。

## 使い方

### CLI

```bash
asyncapi-codegen \
  --input data/asyncapi.yaml \
  --output packages/api-shop/asyncapi_gen.go \
  --package apishop
```

### ライブラリ

```python
from pathlib import Path
from asyncapi_codegen_tools import generate

generate(
    spec_path=Path("data/asyncapi.yaml"),
    output_path=Path("packages/api-shop/asyncapi_gen.go"),
    package="apishop",
)
```

## 生成ルール

入力 `components/schemas/*` の全 schema が対象。扱えない定義は Go 型に落とさずエラーで停止する。

### struct

```yaml
CardPackPurchasedEvent:
  type: object
  description: プレイヤーが card_pack を含む商品を購入した際の業務事実。
  required: [event_type, event_id, timestamp, player_id, card_pack_id]
  properties:
    event_type:
      type: string
      const: card_pack_purchased
    event_id:
      type: string
    timestamp:
      type: string
      format: date-time
    player_id:
      type: string
    card_pack_id:
      type: string
```

→

```go
// CardPackPurchasedEvent は プレイヤーが card_pack を含む商品を購入した際の業務事実。
type CardPackPurchasedEvent struct {
    EventType  string    `json:"event_type"`
    EventID    string    `json:"event_id"`
    Timestamp  time.Time `json:"timestamp"`
    PlayerID   string    `json:"player_id"`
    CardPackID string    `json:"card_pack_id"`
}
```

### const と単一値 enum

`const` フィールドは struct のフィールドとして残しつつ、トップレベル const も生成:

```yaml
event_type:
  type: string
  const: card_pack_purchased
```
→ `EventTypeCardPackPurchased = "card_pack_purchased"` (`{FieldGoName}{StripEventSuffix(SchemaName)}`)

`enum` 値が 1 つだけのフィールドはトップレベル const のみ:

```yaml
source:
  type: string
  enum: [shop]
```
→ `PremiumUpdatedSourceShop = "shop"` (`{StripEventSuffix(SchemaName)}{FieldGoName}{ValueGoName}`)

## 命名規則

### snake_case → CamelCase

`{event_type, event_id}` → `{EventType, EventID}`. 既知 acronym (`id`, `url`, `uri`, `api`, `http`, `json`, `ws`) は ALL_CAPS 化される。

明示的に上書きしたい場合は `x-go-name` 拡張を property に書く:

```yaml
weird_field:
  type: string
  x-go-name: CustomName
```

### required vs optional

`required` リストにあるフィールド:
- 値型 (`string`, `int64`, `time.Time` 等)
- JSON tag は `json:"snake_name"`

`required` にないフィールド:
- pointer 型 (`*string`, `*int64`, `*time.Time` 等)
- JSON tag は `json:"snake_name,omitempty"`

## 制約 / scope 外

spec の誤りが型なしフィールドとして本番の wire に届かないよう、以下はエラーで停止する。

- `type: object` 以外のトップレベル schema (string-typed enum 等)
- `type` を書いていない property、対応する Go 型が無い `type`、`items` の無い `array`
- `components` / `components.schemas` の欠落、mapping でない schema / property
- ローカル component 以外を指す `$ref`

以下は生成の対象外。

- 多値 enum (例: `enum: [a, b, c]`) の定数 (typed enum を生成したい場合は別途検討)
- channels / operations / bindings (payload schema のみが対象)
- `oneOf` / `allOf` の解決

## 開発

```bash
pip install -e .
pip install -e ../codegen-tools  # 依存
pytest
```
