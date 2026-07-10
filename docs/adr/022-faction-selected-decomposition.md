# ADR-022: FactionSelectedEvent の廃止と業務事実ベースへの分解

## ステータス

Proposed (2026-04-22)

本 ADR は [ADR-021](021-onboarding-scenario.md) の「イベント契約」節の 2 イベント設計 (`player-onboarded` + `faction-selected`) を部分的に上書きする。scenario の onboarding 完了に伴う publish は `player-onboarded` 1 本に縮退し、shop 起因の faction 取得は新トピック `faction-purchased` として独立する。

**本 ADR の「オンボーディング起因」節で account subscriber の副作用に挙げた `players.display_name` UPDATE は [ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) で除外される**。表示名はオンボード内 name 入力ステップで scenario が account の `PUT /internal/v1/players/:playerId/name` を同期 REST で呼んで確定するため、`PlayerOnboardedEvent` payload には `display_name` を載せず、subscriber では表示名の反映を行わない (account 側 subscriber は `player_factions` INSERT + `players.selected_faction` UPDATE のみ)。card / gateway 側の副作用は変更なし。

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

[ADR-021](021-onboarding-scenario.md) の「イベント契約」節で scenario は onboarding 完了時に以下の 2 イベントを同時 publish する設計とした:

- `PlayerOnboardedEvent { player_id, display_name, initial_faction_id, ... }`
- `FactionSelectedEvent { player_id, faction, source=scenario_initial, ... }`

両者は **`player_id` と `faction` という同じ情報** を別パス・別 event_id で運ぶ。account が display_name と faction の両方を反映するには 2 イベントを待ち合わせる形になり、冪等化の配線コストが不必要に上がる。単一イベント `PlayerOnboardedEvent` で identity + 初期 faction をまとめて表現する方が自然。

### `common/packages/pubsub-events` の役割が過剰

events.go package doc の原則は "events with a single publisher should live in that publisher's api-<svc> package"。`PlayerOnboardedEvent` は既に scenario 側に、`PremiumUpdatedEvent` は shop に移動予定。`FactionSelectedEvent` を分解すれば **cross-publisher event は残らず**、common/pubsub-events そのものが不要になる。package 自体を維持する運用コスト (タグ管理・Dockerfile fetch・go.mod require × 5 repo) に対して、残る型が無い。

## 詳細

### オンボーディング起因 → `PlayerOnboardedEvent` 単体で完結

- scenario は onboarding 完了時に `PlayerOnboardedEvent` 1 本だけを publish する (現行の 2 イベント atomic 設計を 1 イベントに縮退)
- ペイロードは既存の `player_id` / `display_name` / `initial_faction_id` で充分
- subscriber が account / **card** / **gateway** の 3 つに拡大 (従来 account のみの想定を card / gateway まで広げる)

各 subscriber の副作用 (移行後):

| subscriber | 副作用 |
|---|---|
| account | `players.display_name` UPDATE + `player_factions` INSERT + `players.selected_faction` UPDATE |
| card | faction + Neutral の初期カードパック配布 |
| gateway | WS `onboarding_complete` 通知 push (旧 `faction_selection_complete` 相当) |

scenario の outbox は `PlayerOnboardedEvent` 1 行のみ enqueue する。ADR-021 の「書き込み側（scenario service）」節の「2 イベント同一トランザクション」は `PlayerOnboardedEvent` 1 本の enqueue に縮退する。

### shop 購入起因 → `FactionPurchasedEvent` を新設

- shop は faction 購入 commit 時に `FactionPurchasedEvent` を publish する (既存の `faction-selected` topic は rename)
- 新トピック: `faction-purchased` (subscribers: account / card / gateway)
- ペイロード: `player_id` / `faction` / `event_id` / `timestamp` (Source フィールドは不要)

各 subscriber の副作用 (移行後):

| subscriber | 副作用 |
|---|---|
| account | `player_factions` INSERT のみ (`selected_faction` は変更しない) |
| card | faction のカードのみ配布 (Neutral 無し) |
| gateway | WS `faction_purchase_complete` push |

### イベント型の配置 (ADR-015 の送信側所有原則に完全準拠)

| 型 / 定数 | 配置 |
|---|---|
| `PlayerOnboardedEvent`, `TopicPlayerOnboarded`, `EventTypePlayerOnboarded` | `scenario/packages/api-scenario` (ADR-021 で決定済み、現状維持) |
| `FactionPurchasedEvent`, `TopicFactionPurchased`, `EventTypeFactionPurchased` | `shop/packages/api-shop` (新規追加) |
| `PremiumUpdatedEvent`, `TopicPremiumUpdated`, `EventTypePremiumUpdated`, `PremiumUpdatedSourceShop` | `shop/packages/api-shop` (common から移動) |

### `common/packages/pubsub-events` の廃止

削除対象:

- `FactionSelectedEvent` / `EventTypeFactionSelected` / `FactionSourceScenarioInitial` / `FactionSourceShopPurchase`
- `PremiumUpdatedEvent` / `EventTypePremiumUpdated` / `PremiumUpdatedSourceShop`
- 全 `Topic*` / `Sub*` / `DLQ*` 定数

結果として package の中身が空になるため、**`packages/pubsub-events` ディレクトリごと削除** し、関連する publish workflow も撤去する。

### Pub/Sub infra の変化

| 要素 | 現状 | 移行後 |
|---|---|---|
| `faction-selected` topic + DLQ | 存在 (まだ未使用、ADR-021 後に使用予定だった) | **削除** |
| `faction-selected-{account,card,gateway}-sub` | 存在 | **削除** |
| `faction-purchased` topic + DLQ | — | **新設** |
| `faction-purchased-{account,card,gateway}-sub` | — | **新設** |
| `player-onboarded` topic | ADR-021 で新設予定 | 変更なし (新設) |
| `player-onboarded-account-sub` | ADR-021 で新設予定 | 変更なし (新設) |
| `player-onboarded-card-sub` | — | **新設** |
| `player-onboarded-gateway-sub` | — | **新設** |
| IAM: scenario SA | faction-selected topic publisher + player-onboarded topic publisher | **player-onboarded topic publisher のみ** (faction-purchased は発行しない) |
| IAM: shop SA | faction-selected topic publisher + premium-updated topic publisher | **faction-purchased topic publisher** + premium-updated topic publisher |

### トレードオフ

- **Pub/Sub 契約の破壊的変更**: `faction-selected` topic → `faction-purchased` topic への rename、`player-onboarded` subscriber の拡大。本番稼働前なのでメッセージドレイン配慮は不要だが、同期が必要な repo が 8 リポに広がる
- **card / gateway が 2 subscription を持つ**: 従来 `faction-selected` 1 本だったのが `player-onboarded` と `faction-purchased` の 2 本に。subscription 接続数が倍増するが、Pub/Sub の pull 並行数制限には引っかからない
- **ADR-021 の supersede**: ADR-021 の「イベント契約」「書き込み側（scenario service）」両節の「2 イベント同一トランザクション」設計を本 ADR で縮退させる必要がある (ADR-021 本文に note を追記)
- **scenario の event_builder が 1 メソッドに減る**: `BuildFactionSelected` 削除で、scenario 側の outbox 行の種類は 1 種類のみに

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
