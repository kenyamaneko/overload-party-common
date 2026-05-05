# ADR-027: gateway の Pub/Sub fan-out (client 通知転用) を廃止し、Pub/Sub をサービス間連携専用に純化

- Status: Accepted
- Date: 2026-04-26
- Deciders: kenyamaneko
- Related: [ADR-011](011-repository-split.md) (gateway の責務スリム化), [ADR-012](012-matchmaking-pubsub.md) (matchmaking Pub/Sub 設計), [ADR-015](015-package-split.md) (WS message types 所有), [ADR-021](021-onboarding-scenario.md) (onboarding scenario), [ADR-022](022-faction-selected-decomposition.md) (FactionSelected 分解), [ADR-026](026-onboarding-status-as-account-responsibility.md) (onboarding status 責務)

> 本 ADR は Pub/Sub の利用方針を「サービス間連携専用」と明文化し、gateway が現状抱えている「他サービスが publish する Pub/Sub event を subscribe して WS message に変換し client に push する fan-out 配線」を廃止する。具体的には gateway の `PlayerOnboardedSubscriber` / `FactionPurchasedSubscriber` / `PremiumUpdatedSubscriber` を削除する。matchmaking 専用配送 (`MatchSubscriber`) は **gateway が唯一の subscriber** であり「サービス間連携 = matchmaking → gateway 配送経路」として正当な利用であるため維持する。

---

## Context

### gateway が現状持っている Pub/Sub subscriber 一覧

[overload-party-gateway/internal/config/config.go:35-37](../../../overload-party-gateway/internal/config/config.go) と [internal/adapter/pubsub/](../../../overload-party-gateway/internal/adapter/pubsub/) より、gateway は 4 つの Pub/Sub subscriber を持つ。

| Subscriber | topic | 同 topic の他 subscriber | 役割 |
|---|---|---|---|
| `MatchSubscriber` | `matchmaking-events` | **なし** (gateway 専用) | match 成立を WS `match_found` で client に push |
| `PlayerOnboardedSubscriber` | `player-onboarded` | account, card | WS `onboarding_complete` で client に push |
| `FactionPurchasedSubscriber` | `faction-purchased` | account, card | WS `faction_purchase_complete` で client に push |
| `PremiumUpdatedSubscriber` | `premium-updated` | account | WS `premium_update_complete` で client に push |

### 構造的問題: Pub/Sub の責務逸脱

[ADR-011](011-repository-split.md) §決定で gateway の責務は「WS 通信ハンドリング、ルーティング、認証検証」と定義されている。クロスサービス Pub/Sub event を subscribe して WS に変換する責務は **明文化されていない**。

実装上は [overload-party-gateway/internal/adapter/pubsub/eventsubscriber.go:1-6](../../../overload-party-gateway/internal/adapter/pubsub/eventsubscriber.go) のパッケージ doc に「1 subscriber = 1 topic = 1 WS message type の 1 対 1 対応」と書かれているが、この設計判断は ADR で承認されたものではなく、`PlayerOnboardedEvent` / `FactionPurchasedEvent` / `PremiumUpdatedEvent` が ADR-021 / ADR-022 で導入された際に副次的に追加された配線である。

この構造には以下の問題がある:

#### 1. Pub/Sub event の payload が「サービス間連携契約」と「client への通知契約」を兼任する

`PlayerOnboardedEvent` / `FactionPurchasedEvent` 等の payload は、本来サービス間連携 (account の DB 更新、card の初期パック配布 等) のためのスキーマである。これが gateway 経由で client にも転送されることで、**event スキーマ変更が client 互換性を破壊するリスク**を内包している。例として ADR-026 検討時に `PlayerOnboardedEvent.InitialFactionID` の撤去可否を議論する際、「card の業務処理」「client への通知」の両方を考慮する必要が生じ、責務が混合した状態となっていた。

#### 2. WS message type が gateway 自身ではなく上流 publisher に引きずられる

[ADR-015](015-package-split.md) §85 で「WS メッセージタイプは gateway リポの `data/ws_constants.yaml`」と所有が明示されているが、現状の `onboarding_complete` / `faction_purchase_complete` / `premium_update_complete` の各メッセージは Pub/Sub event の payload をそのまま `data` に転載するだけで、gateway が独自の WS contract を設計している実態がない。

#### 3. fan-out 配信は冪等性とタイミング保証が弱い

Pub/Sub の Exactly-Once Delivery は subscription 単位で保証されるが、subscription を跨いだ順序保証はない。client への通知が「業務処理 (account DB 更新等) より早く届く」ケースが理論上あり、client が古い状態を REST で取りに行く競合が発生し得る。

#### 4. 「Pub/Sub = サービス間連携専用」という当初意図からの逸脱

プロジェクト方針として Pub/Sub は ADR-012 / ADR-021 / ADR-022 でサービス間の async コーディネーションに使う想定だった。client 通知への転用は当初意図に含まれていない。明文化された設計判断のないまま fan-out 構造が拡大しており、将来同種の subscriber が無秩序に追加されるリスクがある。

### client 通知が業務上必要かの再検討

各 WS message について、client が同情報を取得できる代替経路があるかを整理する。

| WS message | 起動契機 | client が同情報を取れる代替経路 | 削除可否 |
|---|---|---|---|
| `onboarding_complete` | scenario `POST /onboarding/complete` 後 | `POST /onboarding/complete` の REST レスポンス | ✓ 削除可 |
| `faction_purchase_complete` | shop の faction 購入処理後 | 購入 REST のレスポンス、ホーム画面再訪時の REST 取得 | ✓ 削除可 |
| `premium_update_complete` | shop の premium 状態変更後 (含 App Store Server Notification) | ホーム画面再訪時の REST 取得 | ✓ 削除可 (即時性は犠牲になるが許容) |
| `match_found` | matchmaking のマッチ成立 | **代替経路なし**。matchmaking は完全 async でユーザーは待機中、結果は WS push でしか届かない | ✗ 削除不可 (ADR-012 設計の中核) |

`onboarding_complete` / `faction_purchase_complete` / `premium_update_complete` は、いずれも **client 自身が起動した REST リクエストの完了通知**、または **次のホーム画面再訪 REST で十分取得可能**なものであり、WS による即時 push は冗長である。`premium_update_complete` の Apple Server Notification 起点ケースは即時性を失うが、premium ステータスは秒単位の即時性が必要な情報ではないため許容する。

`match_found` は matchmaking 完全 async という業務特性上、WS でしか届けられない。

### matchmaking のみが構造的に Pub/Sub を必要とする理由

matchmaking-events の subscription は `matchmaking-events-gateway` 1 本のみで、**gateway が唯一の subscriber** である ([ADR-012](012-matchmaking-pubsub.md) §94)。これは「他サービスが業務処理のために subscribe する fan-out」とは構造が異なり、「matchmaking → gateway という配送経路を Pub/Sub で実装している」と解釈すべきである。

具体的には:

- gateway が複数 Pod で水平スケールしており、ある player の WS 接続を保持しているのは特定の Pod のみ。matchmaking 側は player が「どの gateway Pod に繋がっているか」を知らない
- Pub/Sub の競合 consumer pattern で 1 メッセージは 1 Pod にのみ配送され、自 Pod に該当 player の接続があれば push、なければ ack drop する
- これにより matchmaking 側に「player → Pod の対応表」を持たせる必要がなく、gateway を水平スケールしても配線変更不要

この用途における Pub/Sub は「gateway クラスタ向けの配送バス」であり、サービス間連携の event bus とは性質が異なるが、「他サービスの event を覗き見る fan-out」ではなく「matchmaking → gateway 専用配送」なので、本 ADR の禁止対象には該当しない。

---

## Decision Drivers

- Pub/Sub の責務を「サービス間連携 (DB 反映、副作用処理の駆動)」に純化し、client 通知への転用を排除すること
- gateway の責務を [ADR-011](011-repository-split.md) で定義された「WS 通信ハンドリング、ルーティング、認証検証」に揃えること
- WS message contract を gateway 所有として独立させ、Pub/Sub event スキーマの変更が client 契約に伝搬しない構造にすること
- `match_found` のように業務特性上 WS でしか届けられない通知経路は維持すること
- 削除対象の WS message が client UX を毀損しないこと (代替経路で同情報が取得可能)

---

## Options Considered

### 案 A (採用): gateway の fan-out subscriber を削除し、matchmaking 配送のみ維持

- gateway から `PlayerOnboardedSubscriber` / `FactionPurchasedSubscriber` / `PremiumUpdatedSubscriber` を削除
- 対応する subscription / IAM / WS message type 定義を削除
- `MatchSubscriber` は維持 (gateway 専用配送経路として正当)
- Pub/Sub の利用方針を「原則サービス間連携専用」「matchmaking → gateway 配送のみ単一 subscriber 例外」と ADR で明文化

採用理由: 本来の責務分離を回復しつつ、ADR-012 で確立した matchmaking 設計を破壊しない。client UX も代替経路で維持される。

### 案 B (却下): すべての Pub/Sub→WS subscriber を削除し、matchmaking も別経路に変更

- matchmaking → gateway を Pub/Sub から別の経路に変更
- 候補 a: matchmaking が gateway の internal REST を直叩き (ドメイン間 HTTP 直叩きが新規 1 経路追加)
- 候補 b: gateway が matchmaking に gRPC stream で接続して match 結果を pull
- 候補 c: gateway が matchmaking に long polling

却下理由: ADR-012 の Pub/Sub 設計は競合 consumer による Pod 分散・Exactly-Once 配送・matchmaking 側の player→Pod マッピング不要、というメリットが整理されており、これらを別経路で再現するコストが高い。直叩きは [ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) の例外条項を不要に拡張する。matchmaking-events の subscription が gateway 専用 1 本である事実を踏まえれば、これは「fan-out の責務逸脱」ではなく「専用配送経路」と整理すれば構造的問題はない。

### 案 C (却下): subscriber は維持しつつ、payload 変換層を入れて Pub/Sub event と WS message contract を分離

- gateway 内に Pub/Sub event → WS message の変換アダプタを置き、WS message は gateway 所有の構造体で表現
- subscriber 自体は残す

却下理由: 責務逸脱の本質的な解決にならない。「Pub/Sub event を subscribe して WS に変換する」という構造が残る限り、Pub/Sub event スキーマ変更が gateway の WS 変換層に伝搬する依存は残り続ける。さらに `onboarding_complete` / `faction_purchase_complete` / `premium_update_complete` は client UX 上必要性が低いため、変換層を整備する価値が薄い。

### 案 D (却下): 現状維持 + ADR で fan-out パターンを正式化

- 既存の subscriber を維持し「Pub/Sub を client 通知 fan-out にも使う」設計を ADR で承認

却下理由: 案 C と同じ責務混合問題が解決されない。「将来同種の subscriber を追加する基準」を ADR で書けば書くほど Pub/Sub の責務範囲が肥大化する。元の意図 (サービス間連携専用) から離れる方向への正当化となり、長期的に設計が劣化する。

---

## Decision

### 1. Pub/Sub 利用方針の明文化

Pub/Sub の利用は以下に限定する。

- **原則**: サービス間連携 (他サービスの DB 反映、副作用処理の駆動、Transactional Outbox の配信) のみ
- **例外**: matchmaking → gateway の専用配送経路 (`matchmaking-events` topic + `matchmaking-events-gateway` subscription)。subscription が gateway クラスタ 1 本のみで、「他サービスの fan-out 通信を覗き見る」構造ではないため、責務逸脱に該当しない

新規に「他サービスが publish する topic を gateway が subscribe して client に push する」配線を追加することは禁止する。client への通知が業務上必要な場合は、以下のいずれかで対応する。

- client 起動の REST リクエストのレスポンスに含める
- client が次のホーム画面再訪等で REST を取得する際に最新状態を返す
- どうしても async の即時 push が必要な業務要件があれば、本 ADR の例外条件として別 ADR で正当化する

### 2. gateway から削除する subscriber

以下を gateway から削除する。

- `PlayerOnboardedSubscriber` ([overload-party-gateway/internal/adapter/pubsub/eventsubscriber.go](../../../overload-party-gateway/internal/adapter/pubsub/eventsubscriber.go) の該当部分)
- `FactionPurchasedSubscriber` (同)
- `PremiumUpdatedSubscriber` (同)

対応する以下も削除する。

- `internal/config/config.go` の `PlayerOnboardedSubscription` / `FactionPurchasedSubscription` / `PremiumUpdatedSubscription` フィールドと env 読み取り
- `cmd/main/main.go` の subscriber 起動配線
- 各 subscriber の test ファイル
- `data/ws_constants.yaml` から `onboarding_complete` / `faction_purchase_complete` / `premium_update_complete` を削除 → `python3 scripts/generate_types.py`

#### 維持するもの

- `MatchSubscriber` および `matchmaking-events-gateway` subscription (ADR-012 の中核設計、本 ADR §Decision.1 の例外条項に該当)

### 3. インフラ側の追従

GCP Pub/Sub 側も対応する subscription を削除する。

| 削除対象 subscription | 削除対象 IAM (gateway SA) |
|---|---|
| `player-onboarded-gateway-sub` | `roles/pubsub.subscriber` on `player-onboarded-gateway-sub` |
| `faction-purchased-gateway-sub` | 同 `faction-purchased-gateway-sub` |
| `premium-updated-gateway-sub` | 同 `premium-updated-gateway-sub` |

`player-onboarded` / `faction-purchased` / `premium-updated` topic 自体は **削除しない** (account / card が引き続き subscribe しているため)。

### 4. client 側影響

以下の WS message を受信する client 側ロジックを削除する (client は別リポなので本 ADR は移行 PR の指示のみ)。

- `onboarding_complete`: client は `POST /onboarding/complete` の REST レスポンスで完了を確認する
- `faction_purchase_complete`: client は購入 REST のレスポンスと、ホーム画面再訪時の REST で確認する
- `premium_update_complete`: client はホーム画面再訪時の REST で premium 状態を取得する

特に premium ステータスは Apple Server Notification 起点の自動更新等で「client が能動的にトリガーしないサーバ側変更」が発生し得るため、ホーム画面遷移時に必ず account / shop の最新状態を REST で取得する実装方針を client 側に伝達する必要がある。

### 5. ADR-012 / ADR-015 との関係

- [ADR-012](012-matchmaking-pubsub.md) §Decision の matchmaking-events 設計は **維持**。本 ADR §Decision.1 の例外条項として明示的に位置づける
- [ADR-015](015-package-split.md) §85 「WS メッセージタイプは gateway リポの `data/ws_constants.yaml`」は維持。本 ADR では当該 yaml から 3 つの message type を削除する
- [ADR-011](011-repository-split.md) §決定の gateway 責務「WS 通信ハンドリング、ルーティング、認証検証」を本 ADR で再確認・補強する

---

## Consequences

### Positive

- Pub/Sub の利用責務が「サービス間連携」に純化される。event payload の設計が client 契約に引きずられなくなり、サービス間契約変更の自由度が回復する
- gateway の責務が ADR-011 で定義された境界に揃う (WS hub + 認証 + REST proxy)。クロスサービス Pub/Sub の責務を持たなくなる
- WS message type が gateway 所有として独立し、上流 publisher の event スキーマと分離される
- 「Pub/Sub event を subscribe して WS に流す」配線が将来追加されることへの抑止が ADR で書面化される
- `PlayerOnboardedEvent` 等の payload 設計議論 (ADR-026 で発生した `InitialFactionID` の扱い等) が、サービス間連携の純粋な責務だけで決定できるようになる

### Negative

- `onboarding_complete` / `faction_purchase_complete` / `premium_update_complete` の即時 WS 通知が消える。client は REST レスポンスまたはホーム画面再訪時の REST 取得で代替する必要があり、サーバ起点の状態変更 (Apple Server Notification 等) は次回 REST 取得まで client に届かない
- client 側のコード変更が必要 (3 つの WS handler 削除、ホーム画面遷移時の REST 取得の確実性確保)
- インフラ側で 3 つの subscription / IAM を削除する作業が必要

### Neutral / Follow-ups

- `data/ws_constants.yaml` 編集後の型再生成 (`packages/ws-constants/` Go と `packages/ws-constants-npm/` TS の両方)
- gateway の `cmd/main/main.go` で削除 subscriber の初期化配線を撤去
- gateway の test (`player_onboarded_subscriber_test.go` 等) を削除
- `overload-party-k8s` 側の deployment / IAM 設定からも対応 subscription を削除
- `account` / `card` 側の subscriber は **変更不要** (これらは引き続き Pub/Sub topic を subscribe して業務処理を行う)
- `overload-party-common/docs/SYSTEM_OVERVIEW.md` の通信方針節に本 ADR で明文化した Pub/Sub 利用原則を転記

---

## Implementation Plan

本 ADR 採用後、以下の順序で実装する。

1. **本 ADR を Accepted に昇格** (kenyamaneko レビュー後)
2. **client 側の WS handler 削除と REST 取得実装** (client リポでの先行対応)
   - `onboarding_complete` / `faction_purchase_complete` / `premium_update_complete` の WS handler 削除
   - ホーム画面遷移時に account / shop の最新状態を REST で取得するフローを確実化
3. **gateway 側 subscriber 削除** (PR-1)
   - `internal/adapter/pubsub/eventsubscriber.go` から該当 3 subscriber 削除
   - `internal/config/config.go` から該当 subscription / env 削除
   - `cmd/main/main.go` から起動配線削除
   - 関連 test 削除
   - `data/ws_constants.yaml` から 3 つの WS message type 削除 → `python3 scripts/generate_types.py`
4. **k8s / Pub/Sub インフラ側 subscription 削除** (overload-party-k8s 側 PR)
   - 3 つの subscription resource 削除
   - gateway SA の IAM 該当エントリ削除
5. **ADR-026 と本 ADR 採用順の調整**
   - ADR-026 (onboarding status 責務) は本 ADR とは独立に進められる
   - ただし `PlayerOnboardedEvent` の payload 設計判断 (ADR-026 §5.1 で `InitialFactionID` 維持と決定) の前提として「gateway は subscribe しなくなる = client 契約への影響を考慮しなくて良い」が確定するため、本 ADR が先に Accepted になることが望ましい

---

## Notes

### 1. matchmaking 例外条項の安易な拡大は避ける

本 ADR §Decision.1 で matchmaking → gateway の Pub/Sub 配送を例外として認めるが、これを根拠に「subscriber が単一なら Pub/Sub で client 通知してよい」と一般化することは禁止する。matchmaking は以下の 3 条件をすべて満たすため例外と認められている:

1. 業務特性上、async (player の待機中の事後通知) であり client 起動 REST のレスポンスでは表現できない
2. gateway の水平スケールに対して publisher (matchmaking) が player → Pod マッピングを持たず、Pub/Sub の競合 consumer pattern に依存する必然性がある
3. 同 topic を subscribe する他サービスが存在しない (gateway 専用配送)

将来別ユースケースで「単一 subscriber だから例外として gateway の subscriber を増やしたい」要望が出た場合は、上記 3 条件をすべて満たすかを別 ADR で正当化すること。

### 2. PremiumUpdatedEvent の即時性犠牲

本 ADR で `premium_update_complete` WS push を削除すると、Apple Server Notification 起点の premium 状態変更 (自動更新成功、返金、ファミリー共有解除等) が client に即時届かなくなる。許容理由:

- premium 状態は秒単位の即時性が必要な情報ではない (UI 上の表示優先度が高くなく、「次回起動時に最新状態を取得すれば十分」)
- ホーム画面遷移時に account / shop の最新状態を REST で取得する実装が確実化されていれば、ユーザーが premium 機能にアクセスする時点では必ず最新状態となる
- account 側の `PremiumUpdatedSubscriber` は維持されるため、`account.players.is_premium` / `premium_expires_at` カラムの DB 更新は引き続き Pub/Sub 経由で即時に反映される (これはサービス間連携であり本 ADR の対象外)

ただしこの判断が適切でないと判明した場合 (例: client から「premium 機能の表示が古い」というフィードバックが多発する等) は、別 ADR で代替手段 (client 側の short polling、ホーム画面以外でも premium 状態を refresh する契機の追加 等) を検討する。
