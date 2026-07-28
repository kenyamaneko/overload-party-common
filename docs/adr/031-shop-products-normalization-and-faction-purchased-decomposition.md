# ADR-031: shop products テーブル正規化と faction-purchased の業務事実分割

## ステータス

Accepted (2026-05-05)。shop 実装は [overload-party-shop#60](https://github.com/kenyamaneko/overload-party-shop/pull/60) で完了

## 結論

card 側の card_pack 概念導入に合わせ、sparse 列と JSONB 多態を抱えた `shop.products` を **type 別副表に正規化**し、2 つの業務事実を運んでいた `faction-purchased` イベントを **`card-pack-purchased`（pack 配布指示）と `faction-acquired`（faction 所有権の獲得）に分割**する。`products` は「商品の共通属性」だけを持つ表になって全列が全行で意味を持ち、新 type 追加は副表追加だけで済む。cosmetic items への FK が DB レベルで成立し、イベントと業務事実が 1:1 対応して subscriber 側の用途分岐が消える ([ADR-022](022-faction-selected-decomposition.md) の完成)。card は `card-pack-purchased` 1 種類だけを購読すれば全 pack 配布を表現でき、限定パック等の将来拡張も同型に乗せられる。

## 背景・課題

[overload-party-shop#54](https://github.com/kenyamaneko/overload-party-shop/issues/54) の設計レビューで card 側に `card_pack` 概念 (どのカードを何枚配るかの SSoT マスター) を導入する方針が共有された。これに伴い shop 側で 2 つの問題が顕在化した。

### shop の `products` テーブルが sparse 列・JSONB 多態を抱えている

現状の `shop.products` は単一テーブルで全 type (faction_set / cosmetic / subscription) を表現している。

- **削除済の `faction_id` 列**: faction_set 行のみ使用、他 type は NULL の sparse 列 ([overload-party-shop#55](https://github.com/kenyamaneko/overload-party-shop/issues/55) で削除)
- **`content` JSONB 列**: type ごとに中身が変わる多態 (`{"faction":"SHE"}` / `{"item_type":"stamp","item_no":1}` / `{}`)。列は常に存在するが「中身が type 依存」の点で実質 sparse

card_pack 概念導入で「shop の商品が card_pack を参照する」関係を追加するにあたり、素朴に `card_pack_id VARCHAR NULL` 列を追加すると同種の sparse 列を再生産する。`products` テーブルが「一言で説明できない表」になり続ける。

### `faction-purchased` イベントが 2 つの業務事実を 1 イベントで運んでいる

shop が publish する `FactionPurchasedEvent { player_id, faction }` は subscriber 視点で 2 つの異なる事実を内包している:

| 事実 | subscriber | 副作用 |
|---|---|---|
| player が faction を獲得した (account ドメイン) | account | `player_factions` INSERT (authoritative 所有権) |
| player に該当 faction の card を配布せよ (card ドメイン) | card | `GrantFactionPack` で faction のカードを配布 |
| ユーザーへの通知 | gateway | WS push |

card 側で `card_pack` 概念に統一すると、card subscriber は **どのイベントでも `GrantPack(card_pack_id)` を呼ぶだけ**になる。つまり card の関心は「pack 配布の指示」であり、「player が faction を獲得した」という account ドメインの事実とは別。**[ADR-022](022-faction-selected-decomposition.md) で `FactionSelectedEvent` を業務事実単位に分解した精神**を、shop が publish する側でも貫く必要がある。

### card_pack 粒度の決定 (本 ADR の前提)

card 側で `card_pack.pack_id` を **faction ごとに分ける** 設計が確定した (`faction_set_she` / `faction_set_tenki` / `faction_set_sugar` / `faction_set_tuners`)。当初検討された `selection: {"factions":["${faction}","Neutral"]}` プレースホルダ案は撤回。card 側の設計は [ADR-032](032-card-pack-introduction-and-grant-unification.md) を参照。

理由:

- `${faction}` プレースホルダは「pack 自体は faction 非依存だが呼び出し時パラメータで挙動を変える」実行時バインディングで、pack 単独で配布内容が確定しない
- pack を分ければ selection は静的定義に統一でき、`GrantPack(pack_id)` の引数も `pack_id` 1 個で済む
- 「pack マスター = 配布の SSoT」という設計原則が強化される

これにより shop は **`card_pack_id` 1 個で配布内容が完全に決まる** 形になる (同期 RPC 不要、payload 自己完結)。

## 不採用案

### `products` に `card_pack_id` / `faction` を NULL 列として追加

最小変更案。`shop.products` 単表に `card_pack_id VARCHAR NULL` / `faction VARCHAR NULL` を追加する。

却下理由:

- **#55 で削除した `faction_id` 列の問題を再生産する** (一部 type のみ使う sparse 列)
- `products` テーブルが「一言で説明できない表」のままになる
- 新 type 追加時に sparse 列が増える方向

### `Product.Content` JSONB に `card_pack_id` を入れる

JSONB 多態を継続して `Content.CardPackID` を加える案。

却下理由:

- JSONB は型安全性がなく、type と中身の整合は app 層でしか担保できない
- card_pack_id は **「type 横断の共通参照」** (faction_set + card_pack の両方が使う) であり、type 固有属性と性質が違う。JSONB に閉じ込めるのは意味的に不自然
- DB レベルでの整合チェック・FK が張れない

### `faction-purchased` を維持し `card-pack-purchased` だけ追加

[overload-party-shop#54](https://github.com/kenyamaneko/overload-party-shop/issues/54) で当初 shop 担当が推した方向。既存イベントを温存して破壊的変更を避ける。

却下理由:

- ADR-022 で `FactionSelectedEvent` を業務事実単位に分解した精神に反する (「事実の合成」を温存)
- card subscriber が `faction-purchased` (faction → 内部で pack に変換) と `card-pack-purchased` (card_pack_id 直接) の 2 系統を恒久維持することになり、card 側で `pack_id` 統一の意味が wire レベルで消える
- 稼働前なので破壊的変更の許容コストは低い

### card 側で `card_pack_id → faction` 逆引き API を提供

shop は `card-pack-purchased` だけを publish し、account は card に同期 RPC を投げて faction を取得する。

却下理由:

- shop / card は battle/card 同様「試合フローで他サービスへ同期リクエストを発生させない」設計方針 ([ADR-012](012-matchmaking-pubsub.md))
- account に依存リスクを伝播させる
- 既存イベント温存案と同様、業務事実の混在を解消しない

## Amendment: 2026-05-24 整合性検証責務を overload-party-ops に移譲

本 ADR では整合性検証 (shop seed の `card_pack_id` ⊂ card seed の `pack_id`) を overload-party-common に置くと決定したが、移譲先を **overload-party-ops** に変更する。

移譲の理由:

- ops には cost-monitor / drift-monitor / nightly-shutdown / db-migrate と cron daily の cross-repo 監視 workflow が既に整っており、本検証も同 pattern (Slack 通知込みの定期実行) で実装できる
- ops は Cross-Repo Deps App token (`vars.CROSS_REPO_DEPS_APP_ID` / `secrets.CROSS_REPO_DEPS_APP_PRIVATE_KEY`) と `secrets.SLACK_WEBHOOK_URL` を既に保持しており、common には未設定
- 当初 common に置く根拠は「shop / card 両方の seed が見えるのは共通基盤のみ」だったが、ops からも同じ App token で両 repo を fetch 可能であり、根拠は成立しない
- common は設計 / データ SSoT を保持する役割であり、運用監視 cron は ops に集中させる方が repo 境界として明瞭

影響:

- 整合性検証の担当は overload-party-common から **overload-party-ops** に読み替える
- 実装は overload-party-ops/cross-repo-seeds/check.py + .github/workflows/validate-cross-repo-seeds.yaml に配置済 (kenyamaneko/overload-party-ops#36 / kenyamaneko/overload-party-ops#37)

## Amendment: 2026-06-16 card のデッキ検証で faction 所持を account に同期照会する

### 背景

本 ADR / ADR-022 で faction 所有権の SSoT は account に集約し、card は faction イベントを購読せず所有権を持たない方針とした。一方、デッキ機能のレビューで「プレイヤーが**所持していない**ファクションを宣言したデッキを作れてしまう」検証漏れが判明した。検証すべきタイミングはデッキ作成/編集時、データの権威は account にある。

### 決定

card はデッキ作成/編集時に account の内部エンドポイント `GET /internal/v1/players/{playerID}/factions` を**同期照会**し、宣言ファクション ∈ 所持ファクション を検証する。

- faction 所有権の SSoT は引き続き account。card は faction イベントを購読せず、所有権を永続化しない (card が faction を購読しない方針は不変)。card は検証時にオンデマンドで読むだけ。
- 照会は低頻度なデッキ構築操作に限る。デッキ READ 時の `is_valid` 再算出には含めない (READ 増幅を避ける)。

### 同期 RPC 方針との整合

不採用案「card 側で `card_pack_id → faction` 逆引き API を提供」で却下した同期 RPC は「**試合フロー**で他サービスへ同期リクエストを発生させない」(ADR-012) という方針に基づく。デッキ作成/編集は試合フローではなくデッキ構築操作であり、本決定はこの方針に抵触しない。faction 所有権は read-time に権威確認が必要 (取得直後のファクションを即使え、剥奪を即弾く) で、結果整合 (イベント購読) では要件を満たせないため同期照会が適切。

### 検討した代替

- **card が faction イベントを購読し read-model 構築**: 本 ADR の「card は faction を購読しない」方針に反する。結果整合のため取得直後のファクションが即使えない恐れ。却下。
- **gateway で検証**: デッキ検証ロジックが card と gateway に分散する。却下。

### スコープ

- account: 内部エンドポイント新設 (overload-party-account#36)
- card: `port.FactionClient` + accountClient + デッキ検証 (overload-party-card#49)
- k8s: card deployment に `ACCOUNT_SERVICE_URL` 注入 (overload-party-k8s#39)

## Amendment: 2026-07-12 gateway subscriber 記載の無効化

本文の subscriber 表と Pub/Sub infra 表にある gateway (WS 一次通知 / 副次通知、`faction-acquired-gateway-sub` / `card-pack-purchased-gateway-sub`) は、[ADR-027](027-gateway-pubsub-fanout-removal.md) が廃止した client 通知転用の配線であり、同 ADR の例外条件の正当化を経ていないため無効とする。`faction-acquired` の subscriber は account のみ、`card-pack-purchased` の subscriber は card のみ。infra に作成されていた gateway 向け subscription 2 本は削除した。
