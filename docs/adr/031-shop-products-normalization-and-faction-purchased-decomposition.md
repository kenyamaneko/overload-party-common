# ADR-031: shop products テーブル正規化と faction-purchased の業務事実分割

- Status: Accepted (shop 実装は [overload-party-shop#60](https://github.com/kenyamaneko/overload-party-shop/pull/60) で完了)
- Date: 2026-05-05
- Deciders: kenyamaneko
- Related: [ADR-022](022-faction-selected-decomposition.md) (faction-selected 分解、本 ADR の前駆), [ADR-029](029-type-layer-separation.md) (型レイヤ分離), [ADR-015](015-package-split.md) (パッケージ分割と SSoT 分散), [ADR-012](012-matchmaking-pubsub.md) (Pub/Sub 設計原則)

## Context

[overload-party-shop#54](https://github.com/kenyamaneko/overload-party-shop/issues/54) の設計レビューで card 側に `card_pack` 概念 (どのカードを何枚配るかの SSoT マスター) を導入する方針が共有された。これに伴い shop 側で 2 つの問題が顕在化した。

### 1. shop の `products` テーブルが sparse 列・JSONB 多態を抱えている

現状の `shop.products` は単一テーブルで全 type (faction_set / cosmetic / subscription) を表現している。

- **削除済の `faction_id` 列**: faction_set 行のみ使用、他 type は NULL の sparse 列 ([overload-party-shop#55](https://github.com/kenyamaneko/overload-party-shop/issues/55) で削除)
- **`content` JSONB 列**: type ごとに中身が変わる多態 (`{"faction":"SHE"}` / `{"item_type":"stamp","item_no":1}` / `{}`)。列は常に存在するが「中身が type 依存」の点で実質 sparse

card_pack 概念導入で「shop の商品が card_pack を参照する」関係を追加するにあたり、素朴に `card_pack_id VARCHAR NULL` 列を追加すると同種の sparse 列を再生産する。`products` テーブルが「一言で説明できない表」になり続ける。

### 2. `faction-purchased` イベントが 2 つの業務事実を 1 イベントで運んでいる

shop が publish する `FactionPurchasedEvent { player_id, faction }` は subscriber 視点で 2 つの異なる事実を内包している:

| 事実 | subscriber | 副作用 |
|---|---|---|
| player が faction を獲得した (account ドメイン) | account | `player_factions` INSERT (authoritative 所有権) |
| player に該当 faction の card を配布せよ (card ドメイン) | card | `GrantFactionPack` で faction のカードを配布 |
| ユーザーへの通知 | gateway | WS push |

card 側で `card_pack` 概念に統一すると、card subscriber は **どのイベントでも `GrantPack(card_pack_id)` を呼ぶだけ**になる。つまり card の関心は「pack 配布の指示」であり、「player が faction を獲得した」という account ドメインの事実とは別。**[ADR-022](022-faction-selected-decomposition.md) で `FactionSelectedEvent` を業務事実単位に分解した精神**を、shop が publish する側でも貫く必要がある。

### 3. card_pack 粒度の決定 (本 ADR の前提)

card 側で `card_pack.pack_id` を **faction ごとに分ける** 設計が確定した (`faction_set_she` / `faction_set_tenki` / `faction_set_sugar` / `faction_set_tuners`)。当初検討された `selection: {"factions":["${faction}","Neutral"]}` プレースホルダ案は撤回。

理由:

- `${faction}` プレースホルダは「pack 自体は faction 非依存だが呼び出し時パラメータで挙動を変える」実行時バインディングで、pack 単独で配布内容が確定しない
- pack を分ければ selection は静的定義に統一でき、`GrantPack(pack_id)` の引数も `pack_id` 1 個で済む
- 「pack マスター = 配布の SSoT」という設計原則が強化される

これにより shop は **`card_pack_id` 1 個で配布内容が完全に決まる** 形になる (同期 RPC 不要、payload 自己完結)。

## Decision

### 1. shop products を type 別副表に分解する

副表は **singular `product_<type>`** 形式で命名統一する (1:1 派生の SQL 慣習に従い、master の plural との対比で役割が読み取れる形)。

```
shop.products (              -- type 横断の共通商品マスター
  product_id PK, name, type, price,
  requires_product_id, description, image_url, is_active
)

shop.product_card_pack (
  product_id   PK / FK -> products,
  card_pack_id VARCHAR(50) NOT NULL  -- card.card_pack.pack_id への論理参照
)
-- type IN ('faction_set','card_pack') の行が必ず 1 件持つ

shop.product_faction (
  product_id PK / FK -> products,
  faction    VARCHAR(20) NOT NULL CHECK (faction IN ('SHE','Tenki','Sugar','Tuners'))
)
-- type='faction_set' の行が必ず 1 件持つ
-- shop が faction-acquired publish 時に参照

shop.product_cosmetic (
  product_id PK / FK -> products,
  item_type  VARCHAR(20) NOT NULL,
  item_no    BIGINT NOT NULL,
  FOREIGN KEY (item_type, item_no) REFERENCES shop.cosmetic_items
)
-- type='cosmetic' の行が必ず 1 件持つ

shop.product_subscription (
  product_id    PK / FK -> products,
  period_months INT NOT NULL CHECK (period_months > 0)  -- 課金周期 (月数)
)
-- type='subscription' の行が必ず 1 件持つ
```

整合性ルール:

| type | 必須副表 |
|---|---|
| `faction_set` | `product_card_pack` + `product_faction` |
| `card_pack` | `product_card_pack` のみ |
| `cosmetic` | `product_cosmetic` のみ |
| `subscription` | `product_subscription` のみ |

`type` discriminator と副表の存在/不在の整合は **application 層**で担保する (DB CHECK で完全に縛ると `type` を副表側にも持たせる必要があり overengineering)。

`product_subscription` は subscription variant 拡張 (将来の `premium_yearly` / `premium_family` 等) を見据えて `period_months` 列を持つ。本 ADR 採用時点では `premium_monthly` のみ存在し `period_months=1` で seed する。

### 副次効果

- `Product.Content` JSONB 全廃 (`FactionSetContent` / `CosmeticContent` も削除)
- `cosmetic_items` への FK が DB レベルで成立 (現状 app 整合)
- 新 type 追加時は **新副表追加のみ**で `products` 共通表に変更が及ばない
- shop の domain 型は `Product` 共通型 + per-type 型 (`FactionSetProduct` / `CardPackProduct` / `CosmeticProduct` / `SubscriptionProduct`) に分離される ([ADR-029](029-type-layer-separation.md) の domain 層強化)
- 副表 dispatch は `domain.NewProductView(common, faction *string, itemType *string, itemNo *int64, periodMonths *int64) (ProductView, error)` の factory 関数として domain 層に閉じる (repository は Scan + factory 委譲のみ)

### 2. `faction-purchased` を 2 イベントに分割

shop が publish するイベントを業務事実単位に分解する。

#### 新イベント: `card-pack-purchased`

| 要素 | 値 |
|---|---|
| topic | `card-pack-purchased` |
| event_type | `card_pack_purchased` |
| payload | `{ event_type, event_id, timestamp, player_id, card_pack_id }` |
| publisher | shop |
| subscribers | card (pack 配布) |

card は `card_pack_id` を受け取り `GrantPack(card_pack_id)` で配布する。faction 情報は payload に含めない (card 側で `card_pack_id` から逆引きできるため)。

#### 新イベント: `faction-acquired`

| 要素 | 値 |
|---|---|
| topic | `faction-acquired` |
| event_type | `faction_acquired` |
| payload | `{ event_type, event_id, timestamp, player_id, faction }` |
| publisher | shop |
| subscribers | account (`player_factions` INSERT) / gateway (WS 一次通知) |

旧 `faction-purchased` から意図的に名前を変える: 購入由来のニュアンスを排除し、業務事実「player が faction を獲得した」に寄せる。

#### shop 内の publish 経路

faction_set 商品購入時、shop は **outbox に 2 行 enqueue** する (同一トランザクション):

1. `card-pack-purchased`: `product_card_pack.card_pack_id` から組み立て
2. `faction-acquired`: `product_faction.faction` から組み立て

card_pack 商品 (将来) 購入時は `card-pack-purchased` の 1 行のみ。

副表分解により、shop が faction-acquired publish に必要な faction 情報は **`product_faction` 副表に正規化された状態**で参照できる (sparse 列を引かなくて済む)。

### 3. 各 subscriber の副作用 (移行後)

| イベント | account | card | gateway |
|---|---|---|---|
| `card-pack-purchased` | — | `GrantPack(card_pack_id)` で配布 | (副次通知、判断は gateway 側) |
| `faction-acquired` | `player_factions` INSERT | — | WS 一次通知 (`faction_acquired` push) |
| `player-onboarded` (既存) | 変更なし | 変更なし | 変更なし |
| `premium-updated` (既存) | 変更なし | — | 変更なし |

card は `faction-acquired` を購読**しない** (card の関心は pack 配布のみ)。account は `card-pack-purchased` を購読しない (account の関心は所有権のみ)。**subscriber 視点の関心と event の業務事実が 1:1 で対応する**形に整理される。

### 4. Pub/Sub infra の変化

| 要素 | 現状 | 移行後 |
|---|---|---|
| `faction-purchased` topic + DLQ | 存在 | **削除** |
| `faction-purchased-{account,card,gateway}-sub` | 存在 | **削除** |
| `faction-acquired` topic + DLQ | — | **新設** |
| `faction-acquired-{account,gateway}-sub` | — | **新設** (card は購読しない) |
| `card-pack-purchased` topic + DLQ | — | **新設** |
| `card-pack-purchased-{card,gateway}-sub` | — | **新設** (account は購読しない) |
| IAM: shop SA | faction-purchased + premium-updated publisher | **faction-acquired + card-pack-purchased + premium-updated** publisher |

### 5. card 側との責務分界

| 領域 | SSoT | 物理的な所有 |
|---|---|---|
| card_pack マスター (どのカードを何枚配るか) | card | `card.card_pack` テーブル |
| 商品 → card_pack の関係 | shop | `shop.product_card_pack.card_pack_id` |
| card_pack_id の存在性 | card | shop は論理参照のみ (FK なし) |
| 整合性検証 | overload-party-common | CI で「shop seed の card_pack_id ⊂ card seed の pack_id」を検証 |

shop は **card_pack の中身を一切知らない**。`card_pack_id` という ID 文字列だけを握る。runtime に不正な `card_pack_id` が渡れば card subscriber が `port.ErrNotFound` で nack → DLQ する設計。

## 検討した代替案

### 案 1: `products` に `card_pack_id` / `faction` を NULL 列として追加

最小変更案。`shop.products` 単表に `card_pack_id VARCHAR NULL` / `faction VARCHAR NULL` を追加する。

却下理由:

- **#55 で削除した `faction_id` 列の問題を再生産する** (一部 type のみ使う sparse 列)
- `products` テーブルが「一言で説明できない表」のままになる
- 新 type 追加時に sparse 列が増える方向

### 案 2: `Product.Content` JSONB に `card_pack_id` を入れる

JSONB 多態を継続して `Content.CardPackID` を加える案。

却下理由:

- JSONB は型安全性がなく、type と中身の整合は app 層でしか担保できない
- card_pack_id は **「type 横断の共通参照」** (faction_set + card_pack の両方が使う) であり、type 固有属性と性質が違う。JSONB に閉じ込めるのは意味的に不自然
- DB レベルでの整合チェック・FK が張れない

### 案 3: `faction-purchased` を維持し `card-pack-purchased` だけ追加

[overload-party-shop#54](https://github.com/kenyamaneko/overload-party-shop/issues/54) で当初 shop 担当が推した方向。既存イベントを温存して破壊的変更を避ける。

却下理由:

- ADR-022 で `FactionSelectedEvent` を業務事実単位に分解した精神に反する (「事実の合成」を温存)
- card subscriber が `faction-purchased` (faction → 内部で pack に変換) と `card-pack-purchased` (card_pack_id 直接) の 2 系統を恒久維持することになり、card 側で `pack_id` 統一の意味が wire レベルで消える
- 稼働前なので破壊的変更の許容コストは低い

### 案 4: card 側で `card_pack_id → faction` 逆引き API を提供

shop は `card-pack-purchased` だけを publish し、account は card に同期 RPC を投げて faction を取得する。

却下理由:

- shop / card は battle/card 同様「試合フローで他サービスへ同期リクエストを発生させない」設計方針 ([ADR-012](012-matchmaking-pubsub.md))
- account に依存リスクを伝播させる
- 案 3 と同様、業務事実の混在を解消しない

## 結果

### 期待される効果

- **`products` テーブルの semantic 明確化**: 「商品の共通属性」だけを持つ表になり、「全列が全行で意味を持つ」原則を満たす
- **type 拡張の局所性**: 新 type 追加時に共通表に列が増えない。副表追加だけで済む
- **DB レベル FK の獲得**: cosmetic items の整合が DB で担保される
- **イベントの業務事実 1:1 対応**: subscriber 側コードから「Source 分岐」「event 内の用途分岐」が消える ([ADR-022](022-faction-selected-decomposition.md) 完成)
- **card 側の wire 統一**: card は `card-pack-purchased` 1 種類だけを購読すれば全 pack 配布が表現できる
- **将来拡張**: 限定カードパック商品 / 季節限定パック等を `card-pack-purchased` 経路で同型に乗せられる

### トレードオフ

- **Pub/Sub 契約の破壊的変更**: shop の publish 経路が 1 → 2 に増える。account / card / gateway の subscriber 全改修。本番稼働前なのでドレイン配慮は不要
- **shop 内の DB / domain refactor が大きい**: products 副表分解は Content JSONB 全廃を伴う。GetActiveProducts のクエリが multi-table LEFT JOIN になり、domain 型も per-type 型に分離される。実装ボリュームは L
- **outbox 行が 1 → 2 行/購入**: faction_set 商品購入時。既存 outbox パターンで自然に乗るがコード上は Builder の戻り値が `[]OutboxEvent` に変わる
- **subscription 数の増加**: account / gateway は新 2 topic を購読。card / gateway は subscription 数が増える (Pub/Sub の pull 並行数制限には抵触しない)

### 移行ステップ

`main` 直マージ運用 (ops / infra / common) と Git Flow リポ (shop / card / account / gateway) が混在するため、リポごとに適切なフローで進める。

1. **本 ADR 採用** (overload-party-common main にマージ)
2. **card 側 ADR 起票** (card_pack 概念導入の SSoT、本 ADR と相互参照)
3. **overload-party-shop**: products 副表分解 (refactor、`#56-a` 予定) → develop マージ
4. **overload-party-shop**: card_pack 受け入れ + 2 イベント分割 (feat、`#56-b` 予定)
   - `packages/api-shop`: `CardPackPurchasedEvent` / `FactionAcquiredEvent` 追加、`FactionPurchasedEvent` 削除
   - `internal/usecase/purchase`: outbox 2 行 enqueue 化
   - 新 topic env (`CARD_PACK_PURCHASED_TOPIC` / `FACTION_ACQUIRED_TOPIC`) 追加、`FACTION_PURCHASED_TOPIC` 削除
   - api-shop のタグ push (新 minor)
5. **overload-party-infra (Terraform)**:
   - `faction-purchased` topic / subscription / IAM を削除
   - `faction-acquired` topic + account/gateway subscription + IAM を新設
   - `card-pack-purchased` topic + card/gateway subscription + IAM を新設
6. **overload-party-card**:
   - 旧 `faction_purchased_subscriber` を削除
   - `card_pack_purchased_subscriber` を新設 (`GrantPack(card_pack_id)` を呼ぶ)
   - card_pack マスター (`card.card_pack` テーブル + faction ごとに分けた seed) を導入
   - api-shop bump
7. **overload-party-account**:
   - `faction_purchased_subscriber` → `faction_acquired_subscriber` に rename + payload 型差し替え
   - api-shop bump
8. **overload-party-gateway**:
   - `faction-purchased` 受信を `faction-acquired` (一次通知) + `card-pack-purchased` (副次) に分割
   - WS メッセージ名を 2 種類に分岐
   - api-shop bump
9. **overload-party-k8s**:
   - ConfigMap key rename (`faction-purchased-*` → `faction-acquired-*` / `card-pack-purchased-*`)
   - 各 deployment の env 差し替え
10. **overload-party-common (CI)**:
    - shop seed の `card_pack_id` ⊂ card seed の `pack_id` 整合検証 CI を追加 (両 repo の seed が見える共通基盤の責務)

shop / card 側は ADR 確定後に各 repo で実装 issue を再定義する。Phase 順序は `shop refactor → shop feat + card + account + gateway 同時切替` で進める。新 topic を先に流せる状態にしてから subscriber を切り替えるのが安全。

## 関連 ADR / Issue

- **[ADR-022](022-faction-selected-decomposition.md)**: 業務事実分解の前駆。shop publish 側でも同精神を貫く
- **[ADR-029](029-type-layer-separation.md)**: domain / wire / persistence の物理分離。本 ADR の products 副表分解は domain 層の表現強化
- **[ADR-015](015-package-split.md)**: 送信側型所有原則。新イベントも `shop/packages/api-shop` に配置
- **[ADR-012](012-matchmaking-pubsub.md)**: Pub/Sub 設計原則。同期 RPC を案 4 で却下した根拠
- **[overload-party-shop#54](https://github.com/kenyamaneko/overload-party-shop/issues/54)**: 設計レビュー
- **[overload-party-shop#55](https://github.com/kenyamaneko/overload-party-shop/issues/55)**: products.faction_id 列削除 (本 ADR の前段)
- card 側 ADR (番号確定後にリンク)

## Amendment 2026-06-16: card のデッキ検証で faction 所持を account に同期照会する

### 背景

本 ADR / ADR-022 で faction 所有権の SSoT は account に集約し、card は faction イベントを購読せず所有権を持たない方針とした。一方、デッキ機能のレビューで「プレイヤーが**所持していない**ファクションを宣言したデッキを作れてしまう」検証漏れが判明した。検証すべきタイミングはデッキ作成/編集時、データの権威は account にある。

### 決定

card はデッキ作成/編集時に account の内部エンドポイント `GET /internal/v1/players/{playerID}/factions` を**同期照会**し、宣言ファクション ∈ 所持ファクション を検証する。

- faction 所有権の SSoT は引き続き account。card は faction イベントを購読せず、所有権を永続化しない (本 ADR §3 の購読方針は不変)。card は検証時にオンデマンドで読むだけ。
- 照会は低頻度なデッキ構築操作に限る。デッキ READ 時の `is_valid` 再算出には含めない (READ 増幅を避ける)。

### 同期 RPC 方針との整合

案 4 で却下した同期 RPC は「**試合フロー**で他サービスへ同期リクエストを発生させない」(ADR-012) という方針に基づく。デッキ作成/編集は試合フローではなくデッキ構築操作であり、本決定はこの方針に抵触しない。faction 所有権は read-time に権威確認が必要 (取得直後のファクションを即使え、剥奪を即弾く) で、結果整合 (イベント購読) では要件を満たせないため同期照会が適切。

### 検討した代替

- **card が faction イベントを購読し read-model 構築**: 本 ADR の「card は faction を購読しない」方針に反する。結果整合のため取得直後のファクションが即使えない恐れ。却下。
- **gateway で検証**: デッキ検証ロジックが card と gateway に分散する。却下。

### スコープ

- account: 内部エンドポイント新設 (overload-party-account#36)
- card: `port.FactionClient` + accountClient + デッキ検証 (overload-party-card#49)
- k8s: card deployment に `ACCOUNT_SERVICE_URL` 注入 (overload-party-k8s#39)
