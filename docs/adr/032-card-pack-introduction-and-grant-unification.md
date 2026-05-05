# ADR-032: card_pack 概念導入と GrantPack 統一

- Status: Proposed (shop 担当による draft、card 担当レビュー待ち)
- Date: 2026-05-05
- Deciders: kenyamaneko
- Related: [ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) (shop 側、本 ADR と相互補完), [ADR-022](022-faction-selected-decomposition.md) (業務事実分解、本 ADR の精神的前駆), [ADR-021](021-onboarding-scenario.md) (player-onboarded、本 ADR で subscriber 改修対象), [ADR-014](014-db-schema-split-per-service.md) (schema 分離原則)

## Context

[overload-party-shop#54](https://github.com/kenyamaneko/overload-party-shop/issues/54) の設計レビューで、shop 側が `card_pack` 参照を商品マスターに持ち、`card-pack-purchased` イベントで `card_pack_id` を直接 publish する設計が確定した ([ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md))。これに伴い card 側も内部設計を `card_pack` 概念に合わせて統一する必要がある。

### 現状: ハードコードされた配布 API が 2 つ存在

card 側は現在以下の 2 つの配布 API を持つ ([overload-party-card/internal/usecase/grant.go](https://github.com/kenyamaneko/overload-party-card/blob/main/internal/usecase/grant.go)):

| API | 配布対象 | 呼び出し元 |
|---|---|---|
| `GrantInitialPack(playerID, faction)` | faction + Neutral 各 3 枚 | `player-onboarded` subscriber |
| `GrantFactionPack(playerID, faction)` | faction のみ各 3 枚 | `faction-purchased` subscriber |

両者とも:

- `copiesPerGrant = 3` を const としてハードコード
- `gamedesign.SelectableFactions` で値域検査
- `cardRepo.FindCardIDsByFactions(factions)` で対象カードを faction から動的計算
- 「何を配るか」が code に埋まっており、データドリブンに変更できない

### 問題点

1. **「カード配布の SSoT」が code に分散**: 配布枚数 / Neutral 同梱可否 / 対象 faction が code に散らばっており、運営チューニングや限定パック追加にコード変更が必要。
2. **shop 側 ADR-031 の `card-pack-purchased` イベントを受け取れない**: 新イベントは `card_pack_id` を運ぶ。card 側に `card_pack_id` → 配布内容のマッピングがないと処理不能。
3. **配布の業務事実が API 名に固定**: 「初期配布」「ショップ購入」という呼び出し文脈が API 名に焼き付いており、新しい配布シナリオ (限定パック、ログインボーナス等) を追加するたびに API が増える。

### card_pack 粒度の決定 (本 ADR の前提)

[ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) Context §3 の通り、`card_pack.pack_id` は **faction ごとに分割**する設計で確定:

- `initial_<faction>` (4 件): オンボーディング初期パック (faction + Neutral)
- `faction_set_<faction>` (4 件): faction 単独パック (ショップ購入で配布)
- `limited_xxx` (将来): 期間限定パック等

`${faction}` プレースホルダで pack 1 件を共有する案は、`pack 単独で配布内容が確定しない` 点で「pack マスター = 配布の SSoT」原則を弱めるため却下済み。

## Decision

### 1. `card.card_pack` マスターテーブルを新設

```sql
CREATE TABLE card.card_pack (
  pack_id          VARCHAR(50) NOT NULL,                         -- e.g. "initial_she" / "faction_set_she" / "limited_2026_summer"
  description      VARCHAR(200),                                  -- 運営用説明 (UI には出さない)
  selection        JSONB NOT NULL,                                -- 配布対象の指定方式 (後述)
  copies_per_card  INT NOT NULL CHECK (copies_per_card > 0),     -- 配布対象の各カードを何枚配るか
  is_active        BOOLEAN NOT NULL DEFAULT true,                -- 配布停止用フラグ
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (pack_id)
);
```

#### `selection` JSONB の仕様

配布対象カードの指定方式を type discriminator で表現する。初期サポートは 2 種類:

```jsonc
// type='by_factions': 指定 faction(s) に属する全 active card を配布対象とする
{"type": "by_factions", "factions": ["SHE", "Neutral"]}

// type='by_card_ids': 指定 card_id のみを配布対象とする (限定カード等)
{"type": "by_card_ids", "card_ids": ["LM-0001", "LM-0002"]}
```

新 type が必要になった時点で extend する (現状の 2 種類で initial / faction_set / 将来の limited をすべて表現可能)。

#### 初期 seed (本 ADR 採用と同時に投入)

| pack_id | selection | copies_per_card | 用途 |
|---|---|---|---|
| `initial_she` | `{"type":"by_factions","factions":["SHE","Neutral"]}` | 3 | オンボーディング (SHE 選択時) |
| `initial_tenki` | `{"type":"by_factions","factions":["Tenki","Neutral"]}` | 3 | オンボーディング (Tenki 選択時) |
| `initial_sugar` | `{"type":"by_factions","factions":["Sugar","Neutral"]}` | 3 | オンボーディング (Sugar 選択時) |
| `initial_tuners` | `{"type":"by_factions","factions":["Tuners","Neutral"]}` | 3 | オンボーディング (Tuners 選択時) |
| `faction_set_she` | `{"type":"by_factions","factions":["SHE"]}` | 3 | ショップ faction_set 商品 (SHE) |
| `faction_set_tenki` | `{"type":"by_factions","factions":["Tenki"]}` | 3 | ショップ faction_set 商品 (Tenki) |
| `faction_set_sugar` | `{"type":"by_factions","factions":["Sugar"]}` | 3 | ショップ faction_set 商品 (Sugar) |
| `faction_set_tuners` | `{"type":"by_factions","factions":["Tuners"]}` | 3 | ショップ faction_set 商品 (Tuners) |

### 2. 配布 API を `GrantPack(pack_id)` に統一

既存 `GrantInitialPack(playerID, faction)` / `GrantFactionPack(playerID, faction)` を廃止し、単一の:

```go
// GrantPack は card_pack マスターから対象 pack を取得し、selection に従って
// プレイヤーへカードを配布する。
func (s *GrantInteractor) GrantPack(ctx context.Context, playerID, packID string) (int, error)
```

**実装方針**:

1. `card_pack` テーブルから `packID` の行を取得 (存在しなければ `port.ErrNotFound`)
2. `is_active = false` なら `port.ErrPackInactive` (運用停止 pack の防御)
3. `selection.type` で分岐し対象 card_id 集合を決定:
   - `by_factions`: `cardRepo.FindCardIDsByFactions(factions)` を呼ぶ (既存 repo 流用)
   - `by_card_ids`: そのまま使う
4. `playerCardRepo.AddCards(playerID, cardIDs, copies_per_card)` で配布

**廃止される hard-coded 値**:

- `copiesPerGrant = 3` 定数 → `card_pack.copies_per_card` 列
- `gamedesign.SelectableFactions` の値域検査 → DB 上の pack マスターに存在する pack_id か否かで判定 (selectable faction という概念自体が card 側から消える)
- `validateSelectableFaction` 関数 → 削除

### 3. subscriber 改修

| subscriber | 旧 | 新 |
|---|---|---|
| `player-onboarded` | `GrantInitialPack(playerID, ev.InitialFactionID)` | `GrantPack(playerID, "initial_" + ev.InitialFactionID)` |
| `faction-purchased` | `GrantFactionPack(playerID, ev.Faction)` | **subscriber 削除** (event 自体が ADR-031 で廃止) |
| `card-pack-purchased` (新規) | — | `GrantPack(playerID, ev.CardPackID)` |

新 subscriber `card_pack_purchased_subscriber.go` を新設し、`apishop.CardPackPurchasedEvent` を購読して `GrantPack` を呼ぶ。実装は既存 `faction_purchased_subscriber.go` の構造をそのまま流用 (processed_events 冪等チェック → handler 実行)。

`player-onboarded` subscriber は pack_id を **`"initial_" + faction` で組み立てる** ため、`PlayerOnboardedEvent` payload 自体は変更不要。

### 4. faction という概念の card 側からの撤退

card 側 code から `gamedesign.SelectableFactions` 依存を削除。faction の値域検証は **card_pack マスターの pack_id 存在性**で代替される (例: 不正 faction で `initial_xxx` を引こうとすると pack マスターヒットせず `ErrNotFound`)。

ただし `card.card_definitions.faction` 列は残す (カード自体は faction 属性を持つドメインデータ)。これは「**カードに対する faction**」と「**配布フローの faction**」を分離する整理:

- card_definitions.faction: カードの内在属性 (デッキ構築・効果計算で利用)
- pack の selection に書かれた faction: pack 側の配布ルール記述

両者は同じ値の集合を取りうるが、責務が違う。

### 5. ADR-031 との接続

shop / card 跨ぎの責務分界:

| 領域 | SSoT | 物理 |
|---|---|---|
| card_pack マスター | card | `card.card_pack` テーブル (本 ADR で新設) |
| 商品 → card_pack の関係 | shop | `shop.product_card_pack.card_pack_id` ([ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md)) |
| card_pack_id の存在性 | card | shop は論理参照のみ (FK なし、DLQ 経由で検出) |
| seed 整合性 | overload-party-common | shop seed の `card_pack_id` ⊂ card seed の `pack_id` を CI 検証 |

## 検討した代替案

### 案 A: pack マスター不要、`GrantPack(pack_id)` の dispatch を Go switch で持つ

```go
func GrantPack(ctx, playerID, packID string) error {
    switch packID {
    case "initial_she": return s.grantFactions(ctx, playerID, []string{"SHE","Neutral"}, 3)
    case "faction_set_she": return s.grantFactions(ctx, playerID, []string{"SHE"}, 3)
    ...
    }
}
```

却下理由:

- pack 追加のたびに code 変更 + デプロイが必要 (運営チューニング不能)
- 「配布の SSoT を pack マスターに集約」という ADR の目的に反する
- shop 側 [ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) の seed 整合性検証 (CI で `card_pack_id ⊂ pack_id` を確認) がやりにくい (pack_id 一覧を grep するだけになる)

### 案 B: pack マスターは持つが selection を JSONB ではなく専用テーブルで表現

```sql
CREATE TABLE card.card_pack_factions (pack_id, faction, ...);
CREATE TABLE card.card_pack_cards    (pack_id, card_id, ...);
```

却下理由:

- type discriminator (by_factions / by_card_ids) を表現するために 2 表に分かれ、selection の意味が読みづらい
- pack 追加時に複数表へ整合性のある INSERT が必要で seed 管理が煩雑
- `selection.type` を将来増やすときにテーブルが増殖する

JSONB は[ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) で shop 側が反対した「型ごとに中身が変わる sparse 列」とは性質が違う: ここでは pack マスター 1 行が必ず selection を持ち (sparse でない)、polymorphic なのは「pack の指定方式」というドメイン概念そのもの。「pack 1 件 = 配布ルール 1 セット」を 1 行で表現する自然な設計。

### 案 C: faction-purchased を維持して card_pack 概念だけ内部導入 (subscriber 内部マッピング)

card 側 subscriber が `ev.Faction` を `"faction_set_<faction>"` に内部マップして `GrantPack` を呼ぶ。shop 側のイベントは無改修で済む。

却下理由:

- shop 側 [ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) で `card-pack-purchased` への移行が確定済み (業務事実分解、ADR-022 の精神的踏襲)
- card 側だけ「faction 文字列 → pack_id」の変換を持つと、変換ルールが card にだけ存在することになり、shop が新しい pack 商品 (`limited_xxx` 等) を売り始めたときに card subscriber が無対応になる
- 「shop の商品種別が増えるたびに card 側 mapping が増える」という結合方向の問題が残る

## 結果

### 期待される効果

- **配布の SSoT が card_pack マスターに集約**: 運営チューニング (枚数調整 / 限定パック追加 / 一時停止) が DDL 変更なしの seed 操作で完結
- **配布フローが単一 API (`GrantPack`) に統一**: subscriber は pack_id を渡すだけ。新しい配布シナリオ (季節限定 / ログインボーナス / イベント報酬) を追加しても `GrantPack` 1 個で受けられる
- **shop / card のイベント契約整合**: [ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) の `card-pack-purchased` を card 側が正しく消費できる
- **ADR-022 の精神を card publish/subscribe 両端で完遂**: 業務事実 (pack 配布) と業務文脈 (initial / 購入 / 限定) を分離し、後者は subscriber 側の組み立てに残す

### トレードオフ

- **DDL 変更**: `card.card_pack` テーブル新設 + seed
- **既存 API 削除に伴う呼び出し元改修**: `player-onboarded` subscriber と `faction-purchased` subscriber が改修対象 (faction-purchased 自体は shop 側 ADR-031 で削除される)
- **`gamedesign.SelectableFactions` の card 側依存削除**: 値域検査が pack マスター存在性に置き換わる (機能的には等価、振る舞いは緩やかに変化)
- **副表ではなく別 schema 内のマスター**: shop は `shop.product_card_pack` (副表) で参照、card は `card.card_pack` (master) を所有。クロス schema 参照は app-level 整合 ([ADR-014](014-db-schema-split-per-service.md))

### 移行ステップ

`develop` → `main` のリリースフローに乗せるため Git Flow リポは feature ブランチ → develop で進める。

1. **本 ADR 採用** (overload-party-common main にマージ)
2. **overload-party-card**: `card.card_pack` テーブル + seed 投入 (`initial_<faction>` / `faction_set_<faction>`)
3. **overload-party-card**: `GrantPack(pack_id)` 実装 + 既存 `GrantInitialPack` / `GrantFactionPack` の置換
4. **overload-party-card**: `player-onboarded` subscriber を `"initial_" + faction` 組み立てに変更
5. **overload-party-card**: `card_pack_purchased_subscriber` 新設、`faction_purchased_subscriber` 削除 (shop 側の topic 切替と同期)
6. **overload-party-shop**: [shop#59](https://github.com/kenyamaneko/overload-party-shop/issues/59) で `card-pack-purchased` / `faction-acquired` の 2 イベント分割を実装 + api-shop bump
7. **overload-party-account**: `faction-purchased` subscriber を `faction-acquired` subscriber にリネーム
8. **overload-party-gateway**: `faction-purchased` 受信を `faction-acquired` (一次通知) + `card-pack-purchased` (副次) に分割
9. **overload-party-infra**: Pub/Sub topic / subscription / IAM の付け替え ([ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) §4)
10. **overload-party-k8s**: 新 env (`CARD_PACK_PURCHASED_SUBSCRIPTION` 等) 追加、旧 env 削除
11. **overload-party-common (CI)**: shop seed の `card_pack_id` ⊂ card seed の `pack_id` 整合検証 CI を追加

各リポの実装 issue は ADR-031 / 本 ADR の合意後に起票する。順序は `card_pack マスター追加 → card 側 GrantPack 実装 → shop 側 publish 切替 → 他 subscriber 切替 → infra 反映` で進める。

## 関連 ADR / Issue

- **[ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md)**: shop 側の対応 ADR。本 ADR と相互補完
- **[ADR-022](022-faction-selected-decomposition.md)**: 業務事実分解の前駆。card 側でも同精神を貫く
- **[ADR-021](021-onboarding-scenario.md)**: player-onboarded。本 ADR で card 側 subscriber が改修対象
- **[ADR-014](014-db-schema-split-per-service.md)**: schema 分離原則。card.card_pack はクロス schema 参照されるが FK は張らない
- **[overload-party-shop#54](https://github.com/kenyamaneko/overload-party-shop/issues/54)**: 元の設計レビュー
- card 側実装 issue (本 ADR 採用後に起票予定)
