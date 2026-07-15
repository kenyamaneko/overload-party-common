# ADR-032: card_pack 概念導入と GrantPack 統一

## ステータス

Accepted (2026-05-05)

## 結論

code に分散していたカード配布の定義をデータドリブンに集約するため、`card.card_pack` マスターテーブルを新設し、配布 API を単一の `GrantPack(pack_id)` に統一する。配布の SSoT が card_pack マスターに集約されて運営チューニング (枚数調整 / 限定パック追加 / 一時停止) が DDL 変更なしの seed 操作で完結し、新しい配布シナリオ (季節限定 / ログインボーナス / イベント報酬) も `GrantPack` 1 個で受けられる。shop 側 [ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) の `card-pack-purchased` を card 側が正しく消費できるようになり、業務事実 (pack 配布) と業務文脈 (initial / 購入 / 限定) の分離 ([ADR-022](022-faction-selected-decomposition.md) の精神) が card の publish/subscribe 両端で完遂する。ADR-026 の波及で残っていた dead な REST grant エンドポイントも一掃する。

## 背景・課題

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

- **「カード配布の SSoT」が code に分散**: 配布枚数 / Neutral 同梱可否 / 対象 faction が code に散らばっており、運営チューニングや限定パック追加にコード変更が必要
- **shop 側 ADR-031 の `card-pack-purchased` イベントを受け取れない**: 新イベントは `card_pack_id` を運ぶ。card 側に `card_pack_id` → 配布内容のマッピングがないと処理不能
- **配布の業務事実が API 名に固定**: 「初期配布」「ショップ購入」という呼び出し文脈が API 名に焼き付いており、新しい配布シナリオ (限定パック、ログインボーナス等) を追加するたびに API が増える

### card_pack 粒度の決定 (本 ADR の前提)

[ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) の「card_pack 粒度の決定」の通り、`card_pack.pack_id` は **faction ごとに分割**する設計で確定:

- `initial_<faction>` (4 件): オンボーディング初期パック (faction + Neutral)
- `faction_set_<faction>` (4 件): faction 単独パック (ショップ購入で配布)
- `limited_xxx` (将来): 期間限定パック等

`${faction}` プレースホルダで pack 1 件を共有する案は、`pack 単独で配布内容が確定しない` 点で「pack マスター = 配布の SSoT」原則を弱めるため却下済み。

## 不採用案

### pack マスター不要、`GrantPack(pack_id)` の dispatch を Go switch で持つ

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

### pack マスターは持つが selection を JSONB ではなく専用テーブルで表現

```sql
CREATE TABLE card.card_pack_factions (pack_id, faction, ...);
CREATE TABLE card.card_pack_cards    (pack_id, card_id, ...);
```

却下理由:

- type discriminator (by_factions / by_card_ids) を表現するために 2 表に分かれ、selection の意味が読みづらい
- pack 追加時に複数表へ整合性のある INSERT が必要で seed 管理が煩雑
- `selection.type` を将来増やすときにテーブルが増殖する

JSONB は [ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) で shop 側が反対した「型ごとに中身が変わる sparse 列」とは性質が違う: ここでは pack マスター 1 行が必ず selection を持ち (sparse でない)、polymorphic なのは「pack の指定方式」というドメイン概念そのもの。「pack 1 件 = 配布ルール 1 セット」を 1 行で表現する自然な設計。

### faction-purchased を維持して card_pack 概念だけ内部導入 (subscriber 内部マッピング)

card 側 subscriber が `ev.Faction` を `"faction_set_<faction>"` に内部マップして `GrantPack` を呼ぶ。shop 側のイベントは無改修で済む。

却下理由:

- shop 側 [ADR-031](031-shop-products-normalization-and-faction-purchased-decomposition.md) で `card-pack-purchased` への移行が確定済み (業務事実分解、ADR-022 の精神的踏襲)
- card 側だけ「faction 文字列 → pack_id」の変換を持つと、変換ルールが card にだけ存在することになり、shop が新しい pack 商品 (`limited_xxx` 等) を売り始めたときに card subscriber が無対応になる
- 「shop の商品種別が増えるたびに card 側 mapping が増える」という結合方向の問題が残る

## Amendment: 2026-05-24 seed 整合性検証責務を overload-party-ops に移譲

本 ADR では shop seed の `card_pack_id` ⊂ card seed の `pack_id` 整合検証 CI を overload-party-common に追加すると決定したが、移譲先を **overload-party-ops** に変更する。詳細な理由は [ADR-031 の Amendment](031-shop-products-normalization-and-faction-purchased-decomposition.md) を参照。

実装: overload-party-ops/cross-repo-seeds/ (kenyamaneko/overload-party-ops#36 / kenyamaneko/overload-party-ops#37)
