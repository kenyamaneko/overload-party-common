# ADR-027: gateway の Pub/Sub fan-out (client 通知転用) を廃止し、Pub/Sub をサービス間連携専用に純化

## ステータス

Accepted (2026-04-26)

## 結論

Pub/Sub の利用方針を「サービス間連携専用」と明文化し、gateway が現状抱えている「他サービスが publish する Pub/Sub event を subscribe して WS message に変換し client に push する fan-out 配線」を廃止する。具体的には gateway の `PlayerOnboardedSubscriber` / `FactionPurchasedSubscriber` / `PremiumUpdatedSubscriber` を削除する。matchmaking 専用配送 (`MatchSubscriber`) は **gateway が唯一の subscriber** であり「サービス間連携 = matchmaking → gateway 配送経路」として正当な利用であるため維持する。

Pub/Sub event payload の設計が client 契約に引きずられなくなってサービス間契約変更の自由度が回復し、gateway の責務が [ADR-011](011-repository-split.md) で定義された境界 (WS hub + 認証 + REST proxy) に揃う。WS message type は gateway 所有として独立し、「Pub/Sub event を subscribe して WS に流す」配線の将来追加への抑止が書面化される。

## 背景・課題

### gateway が現状持っている Pub/Sub subscriber 一覧

[overload-party-gateway/internal/config/config.go:35-37](../../../overload-party-gateway/internal/config/config.go) と [internal/adapter/pubsub/](../../../overload-party-gateway/internal/adapter/pubsub/) より、gateway は 4 つの Pub/Sub subscriber を持つ。

| Subscriber | topic | 同 topic の他 subscriber | 役割 |
|---|---|---|---|
| `MatchSubscriber` | `matchmaking-events` | **なし** (gateway 専用) | match 成立を WS `match_found` で client に push |
| `PlayerOnboardedSubscriber` | `player-onboarded` | account, card | WS `onboarding_complete` で client に push |
| `FactionPurchasedSubscriber` | `faction-purchased` | account, card | WS `faction_purchase_complete` で client に push |
| `PremiumUpdatedSubscriber` | `premium-updated` | account | WS `premium_update_complete` で client に push |

### 構造的問題: Pub/Sub の責務逸脱

[ADR-011](011-repository-split.md) で gateway の責務は「WS 通信ハンドリング、ルーティング、認証検証」と定義されている。クロスサービス Pub/Sub event を subscribe して WS に変換する責務は **明文化されていない**。

実装上は [overload-party-gateway/internal/adapter/pubsub/eventsubscriber.go:1-6](../../../overload-party-gateway/internal/adapter/pubsub/eventsubscriber.go) のパッケージ doc に「1 subscriber = 1 topic = 1 WS message type の 1 対 1 対応」と書かれているが、この設計判断は ADR で承認されたものではなく、`PlayerOnboardedEvent` / `FactionPurchasedEvent` / `PremiumUpdatedEvent` が ADR-021 / ADR-022 で導入された際に副次的に追加された配線である。

この構造には以下の問題がある:

#### Pub/Sub event の payload が「サービス間連携契約」と「client への通知契約」を兼任する

`PlayerOnboardedEvent` / `FactionPurchasedEvent` 等の payload は、本来サービス間連携 (account の DB 更新、card の初期パック配布 等) のためのスキーマである。これが gateway 経由で client にも転送されることで、**event スキーマ変更が client 互換性を破壊するリスク**を内包している。例として ADR-026 検討時に `PlayerOnboardedEvent.InitialFactionID` の撤去可否を議論する際、「card の業務処理」「client への通知」の両方を考慮する必要が生じ、責務が混合した状態となっていた。

#### WS message type が gateway 自身ではなく上流 publisher に引きずられる

[ADR-015](015-package-split.md) で「WS メッセージタイプは gateway リポの `data/ws_constants.yaml`」と所有が明示されているが、現状の `onboarding_complete` / `faction_purchase_complete` / `premium_update_complete` の各メッセージは Pub/Sub event の payload をそのまま `data` に転載するだけで、gateway が独自の WS contract を設計している実態がない。

#### fan-out 配信は冪等性とタイミング保証が弱い

Pub/Sub の Exactly-Once Delivery は subscription 単位で保証されるが、subscription を跨いだ順序保証はない。client への通知が「業務処理 (account DB 更新等) より早く届く」ケースが理論上あり、client が古い状態を REST で取りに行く競合が発生し得る。

#### 「Pub/Sub = サービス間連携専用」という当初意図からの逸脱

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

matchmaking-events の subscription は `matchmaking-events-gateway` 1 本のみで、**gateway が唯一の subscriber** である ([ADR-012](012-matchmaking-pubsub.md))。これは「他サービスが業務処理のために subscribe する fan-out」とは構造が異なり、「matchmaking → gateway という配送経路を Pub/Sub で実装している」と解釈すべきである。

具体的には:

- gateway が複数 Pod で水平スケールしており、ある player の WS 接続を保持しているのは特定の Pod のみ。matchmaking 側は player が「どの gateway Pod に繋がっているか」を知らない
- Pub/Sub の競合 consumer pattern で 1 メッセージは 1 Pod にのみ配送され、自 Pod に該当 player の接続があれば push、なければ ack drop する
- これにより matchmaking 側に「player → Pod の対応表」を持たせる必要がなく、gateway を水平スケールしても配線変更不要

この用途における Pub/Sub は「gateway クラスタ向けの配送バス」であり、サービス間連携の event bus とは性質が異なるが、「他サービスの event を覗き見る fan-out」ではなく「matchmaking → gateway 専用配送」なので、本 ADR の禁止対象には該当しない。

## 不採用案

### すべての Pub/Sub→WS subscriber を削除し、matchmaking も別経路に変更

- matchmaking → gateway を Pub/Sub から別の経路に変更
- 候補 a: matchmaking が gateway の internal REST を直叩き (ドメイン間 HTTP 直叩きが新規 1 経路追加)
- 候補 b: gateway が matchmaking に gRPC stream で接続して match 結果を pull
- 候補 c: gateway が matchmaking に long polling

却下理由: ADR-012 の Pub/Sub 設計は競合 consumer による Pod 分散・Exactly-Once 配送・matchmaking 側の player→Pod マッピング不要、というメリットが整理されており、これらを別経路で再現するコストが高い。直叩きは [ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) の例外条項を不要に拡張する。matchmaking-events の subscription が gateway 専用 1 本である事実を踏まえれば、これは「fan-out の責務逸脱」ではなく「専用配送経路」と整理すれば構造的問題はない。

### subscriber は維持しつつ、payload 変換層を入れて Pub/Sub event と WS message contract を分離

- gateway 内に Pub/Sub event → WS message の変換アダプタを置き、WS message は gateway 所有の構造体で表現
- subscriber 自体は残す

却下理由: 責務逸脱の本質的な解決にならない。「Pub/Sub event を subscribe して WS に変換する」という構造が残る限り、Pub/Sub event スキーマ変更が gateway の WS 変換層に伝搬する依存は残り続ける。さらに `onboarding_complete` / `faction_purchase_complete` / `premium_update_complete` は client UX 上必要性が低いため、変換層を整備する価値が薄い。

### 現状維持 + ADR で fan-out パターンを正式化

- 既存の subscriber を維持し「Pub/Sub を client 通知 fan-out にも使う」設計を ADR で承認

却下理由: 変換層案と同じ責務混合問題が解決されない。「将来同種の subscriber を追加する基準」を ADR で書けば書くほど Pub/Sub の責務範囲が肥大化する。元の意図 (サービス間連携専用) から離れる方向への正当化となり、長期的に設計が劣化する。
