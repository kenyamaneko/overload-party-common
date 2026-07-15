# ADR-022: FactionSelectedEvent の廃止と業務事実ベースへの分解

## ステータス

Proposed (2026-04-22)

本 ADR は [ADR-021](021-onboarding-scenario.md) のイベント設計（`player-onboarded` + `faction-selected` の 2 イベント）を部分的に上書きする。scenario の onboarding 完了に伴う publish は `player-onboarded` 1 本に縮退し、shop 起因の faction 取得は新トピック `faction-purchased` として独立する。

**本 ADR で account subscriber の副作用に挙げた `players.display_name` UPDATE は [ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) で除外された**。表示名はオンボード内 name 入力ステップで scenario が account の `PUT /internal/v1/players/:playerId/name` を同期 REST で呼んで確定するため、`PlayerOnboardedEvent` payload には `display_name` を載せず、subscriber では表示名の反映を行わない (account 側 subscriber は `player_factions` INSERT + `players.selected_faction` UPDATE のみ)。card / gateway 側の副作用は変更なし。

## 結論

一つのイベントに二つの業務事実が同居する歪みを解消するため、`FactionSelectedEvent` を廃止し、業務事実単位で `PlayerOnboardedEvent`（オンボーディング完了）と `FactionPurchasedEvent`（課金による faction 取得）の 2 イベントに分解する。イベント名と業務事実が 1 対 1 対応し、Source 分岐が全 subscriber から消えて handler がフラット化する。ADR-021 の 2 イベント atomic 設計は 1 イベントに縮退して outbox 配線が単純化し、`common/packages/pubsub-events` は完全廃止できて module 管理・Dockerfile secret・go.mod require の運用負債が 5 リポから消える。`PremiumUpdatedEvent` (shop 単独) が送信側所有原則 (ADR-015 / ADR-012) に違反したまま common にあったズレも解消される。

## 背景・課題

[ADR-021](021-onboarding-scenario.md) の実装直後、`FactionSelectedEvent` の設計を改めて検証したところ、以下の問題が顕在化した。

### 一つのイベントに二つの業務事実が同居している

`FactionSelectedEvent` は `Source` フィールド (`scenario_initial` / `shop_purchase`) で発火起因を区別する。subscriber 側の [account/internal/adapter/pubsub/faction_selected_subscriber.go](../../../overload-party-account/internal/adapter/pubsub/faction_selected_subscriber.go) は実際にこの Source で分岐し、大きく異なる副作用を選ぶ。

| Source | 業務事実 | account の副作用 | card の副作用 | gateway の副作用 |
|---|---|---|---|---|
| `scenario_initial` | オンボーディング完了時の初期 faction 設定 | `player_factions` INSERT + `players.selected_faction` UPDATE | **faction + Neutral** の初期パック配布 | WS `faction_selection_complete` push |
| `shop_purchase` | 課金による追加 faction 取得 | `player_factions` INSERT のみ | faction のカードのみ (Neutral 無し) | 同上 |

「Selected」という名前が示唆するのは「現在使用中の faction を確定する」挙動だが、`shop_purchase` ケースでは `players.selected_faction` を変更しない (所有権追加のみ)。つまり**名前が実態の半分しか表していない**。

これは「業務事実の合成 (merge) が topic 単位で行われた設計妥協」の典型で、subscriber 側で Source 分岐を強制する副作用が残っていた。

### オンボーディング起因の発火が `PlayerOnboardedEvent` と情報重複している

[ADR-021](021-onboarding-scenario.md) では scenario が onboarding 完了時に以下の 2 イベントを同時 publish する設計とした:

- `PlayerOnboardedEvent { player_id, display_name, initial_faction_id, ... }`
- `FactionSelectedEvent { player_id, faction, source=scenario_initial, ... }`

両者は **`player_id` と `faction` という同じ情報** を別パス・別 event_id で運ぶ。account が display_name と faction の両方を反映するには 2 イベントを待ち合わせる形になり、冪等化の配線コストが不必要に上がる。単一イベント `PlayerOnboardedEvent` で identity + 初期 faction をまとめて表現する方が自然。

### `common/packages/pubsub-events` の役割が過剰

events.go package doc の原則は "events with a single publisher should live in that publisher's api-<svc> package"。`PlayerOnboardedEvent` は既に scenario 側に、`PremiumUpdatedEvent` は shop に移動予定。`FactionSelectedEvent` を分解すれば **cross-publisher event は残らず**、common/pubsub-events そのものが不要になる。package 自体を維持する運用コスト (タグ管理・Dockerfile fetch・go.mod require × 5 repo) に対して、残る型が無い。

## 不採用案

### 現状維持 (FactionSelectedEvent を残す)

Source フィールドで分岐する現行設計をそのまま維持する。

却下理由:

- 「selected」の命名が実態 (scenario_initial 以外は所有権追加のみ) と乖離
- subscribers に Source 分岐ロジックを恒久的に残すことになる
- `PlayerOnboardedEvent` との情報重複が消えない
- common/pubsub-events 廃止の道が閉ざされる

### `FactionSelectedEvent` を shop/api-shop に移動 (前回検討した案 β)

2 publisher (scenario + shop) を維持したまま、型の配置だけを shop 側に寄せる。

却下理由:

- 業務事実の合成という本質的な問題が残る (Source 分岐も継続)
- scenario が shop の型を import して publish するという方向が不自然 (scenario は onboarding の責務であり、shop の契約に縛られる理由がない)
- 現状維持案と同じく `PlayerOnboardedEvent` との冗長性が解消されない

### `PlayerOnboardedEvent` に Source を追加して faction-purchased をぶら下げる

単一イベントで 2 業務事実を扱う方向で統合。

却下理由:

- shop 購入時に "onboarded" を名乗るのは意味的におかしい
- 分岐の方向が逆転するだけで本質は現状維持案と同じ
