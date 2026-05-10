# アプリケーション設計

関連ドキュメント: [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) / [INFRASTRUCTURE.md](INFRASTRUCTURE.md) / [DATA_DESIGN.md](DATA_DESIGN.md)

---

## 目次

1. [データ設計](#1-データ設計)
2. [API 設計](#2-api-設計)
3. [認証・認可](#3-認証認可)
4. [課金システム](#4-課金システム)
5. [リアルタイム通信](#5-リアルタイム通信)
6. [セキュリティ](#6-セキュリティ)
7. [多言語対応](#7-多言語対応-i18n)

---

## 1. データ設計

PostgreSQL をデータストアとして使用。テーブル構成、カラム仕様、JSONスキーマの詳細は **[DATA_DESIGN.md](DATA_DESIGN.md)** を参照。

主要テーブル:
- **games / game_states / game_events / game_actions** — ゲームライフサイクル・状態・イベントログ・アクション入力ログ
- **players / player_daily_battle** — プレイヤー管理・デイリーバトル制限
- **card_definitions** — カード定義マスター（card サービスが所有。battle はインメモリキャッシュ経由で参照）
- **player_cards / decks / deck_cards** — 所持カード・デッキ構築
- **products / subscriptions / one_time_purchases** — ショップ・課金
- **cosmetic_items / player_items** — コスメティクス

### 1.1 スキーマ分割とオーナーシップ

Cloud SQL インスタンスは 1 つのまま維持したうえで、**PostgreSQL スキーマをサービス単位に分割する**。各サービスには専用の DB ユーザー（IAM サービスアカウント）を払い出し、自スキーマに対してのみ `USAGE` と `SELECT/INSERT/UPDATE/DELETE` を付与する。他スキーマには `USAGE` すら付与せず、アプリ側で誤って他サービスのテーブル名を書いたクエリを実行しても DB レイヤーで拒否される。

- **書き込みは所有サービスのみ**: テーブルの write は所有サービスに限定される
- **クロスサービス read も API 経由**: 他ドメインのデータが読みたい場合は、所有サービスが提供する REST API 経由で取得する。直接のクロススキーマ SELECT は権限上も設計上も許容しない
- **1 インスタンス維持**: Cloud SQL インスタンスを複数立てるコスト（固定費・運用・バックアップ）を避けるため、物理的には単一インスタンスを継続する。将来 DB インスタンスをサービス単位に分けたくなった場合でも、接続先変更とデータ移行だけで済み、アプリ側のクエリ書き換えは不要にできる

**スキーマ配置:**

| スキーマ | 所有サービス | 主な対象テーブル |
|---|---|---|
| `account` | account | `players`, `player_daily_battle`, `player_factions`, `user_settings` |
| `card` | card | `card_definitions`, `player_cards`, `decks`, `deck_cards` |
| `shop` | shop | `products`, `subscriptions`, `one_time_purchases`, `cosmetic_items`, `player_items` |
| `scenario` | scenario | `scenario_episodes`, `episode_required_factions`, `player_story_progress` |
| `battle` | battle | `games`, `game_npcs`, `game_decks`, `game_players`, `game_states`, `game_actions`, `game_events` |
| `news` | news | `news_articles`, `news_article_translations` |
| `support` | support | `announcements`, `announcement_translations`, `inquiries` |
| （なし） | matchmaking | キューは Upstash Redis、通知は Cloud Pub/Sub のため RDB スキーマを持たない |
| （なし） | newsfeed | Cloud Run Job。DB を持たず、記事を Pub/Sub `news-article-collected` に publish するのみ |

- **動的設定値**: サービス横断で参照する設定値（バトル上限数・経験値・タイムバンク等）は **Cloud Firestore (Native モード)** のコレクション `game_config` に格納し、各サービスは Firestore クライアントから KV で読み取る

### 1.2 カード定義のサービス間参照

`card_definitions` は **card スキーマの所有物** であり、card サービス以外は DB を直接参照せず、card サービスが提供する REST API 経由で取得する。

| 用途 | 参照方法 |
|------|----------|
| ゲーム中の効果計算（battle） | card サービスからカードマスターデータを取得し、battle プロセス内のインメモリキャッシュで参照 |
| デッキ構築画面（client） | card サービスの REST API `GET /api/v1/cards` で全カード定義を返却。クライアントはローカルキャッシュ |
| デッキバリデーション（card） | card サービス内部で `card_definitions` を直接参照 |

battle は対戦中に大量のカードデータを参照するため、毎回 card サービスに API コールする構成はレイテンシ・負荷の両面で現実的ではない。battle 側でカードマスターデータをインメモリキャッシュする前提で運用する。カードマスターは更新頻度が低く、バージョン付きで配布されている（`card_data_version` を `games` に記録済み）ため、キャッシュ戦略は比較的単純に組める。

### 1.3 カード定義キャッシュの更新通知

battle 側のインメモリキャッシュの更新戦略は以下のとおりとする。

- **初期ロード**: battle Pod 起動時に card サービスの REST API `GET /api/v1/cards` で全カード定義を取得し、プロセス内のインメモリキャッシュに保持する
- **更新通知**: card サービスがカードマスター更新時に、Google Cloud Pub/Sub のトピック `card-definitions-updated` に invalidation イベントを publish する。ペイロードは `{type: "invalidated"}` のようなシグナルのみで、どのカードが変わったかといった差分情報は含めない
- **到達保証**: このトピックの subscription は **at-least-once** で十分（Exactly-Once Delivery は不要）。重複受信しても battle 側は「キャッシュを破棄して REST API で全件再取得」するだけで、操作として冪等であるため
- **Subscription の設計**: battle Pod ごとに **別々の subscription** を割り当てる（broadcast 構成）。マッチメイキングイベント（`matchmaking-events-gateway`）が競合コンシューマで 1 Pod のみ受信するのと逆で、カード invalidation は **全 battle Pod に届く必要がある**（各 Pod が独立した in-memory キャッシュを持つため）。Pod 名や Pod インスタンス ID をサフィックスに含めた動的命名の subscription を起動時に作成・終了時に削除する運用を想定する
- **当面の前提**: 現行インフラ方針（GKE Standard 単一ノード・1 replica per service）下では battle Pod は 1 個しかないため、この broadcast 構成の挙動は単一 subscription とほぼ変わらない。ただし水平スケール時に即座に機能する設計として最初からこの形で組む
- **レスポンス形状**: card サービスの `GET /api/v1/cards` は全カード定義を 1 レスポンスで返却する。件数は 126 枚程度で、毎回全件返しても負荷上問題にならない。差分配信やページングは不要
- **バージョン整合性**: カードマスターにはバージョン番号が付与されており、`games.card_data_version` に記録される。battle が扱うゲーム状態と対応するカード定義バージョンのズレは、ゲーム開始時に battle が保持しているキャッシュのバージョンを `games.card_data_version` として記録することで検証可能にする

---

## 2. API 設計

- **REST API**（クライアント向け公開 API、入口は gateway）: プレイヤー管理、デッキ管理、NPC 対戦、ショップなど
- **WebSocket API**（クライアント ↔ gateway）: PvP マッチメイキング、リアルタイム対戦、スタンプ送信など
- **内部 REST API**（サービス間通信、クラスタ内部のみ）: gateway ↔ account / card / shop / scenario / matchmaking / battle / news / support、および battle ↔ card など。ドメインサービス間の HTTP 直叩きは原則禁止し、連携は Pub/Sub に集約する。例外として scenario の onboarding 内 name 確定と再開判定に限り scenario → account の直叩きを許容する（[ADR-025](../adr/025-onboarding-name-via-rest-and-cross-service-http.md)）

### 2.1 契約と実装の分離

外部公開 API 契約と内部実装は **SSoT を分離して独立に進化させる**（[ADR-034](../adr/034-api-contract-ssot-openapi-asyncapi-and-go-module-distribution.md)）。

- **wire は後方互換、domain は内部進化が必要**: subscriber が消費する wire 型は一度公開したフィールドを保持し続けたい一方で、domain 型は Go の型システム (custom enum / 値オブジェクト) を活かして strict に進化させたい。両者は構造的に対立するため、形状一致を強制せず `presenter` 層で境界変換する設計を採る
- **契約 SSoT を OpenAPI / AsyncAPI に揃える**: spec viewer / mock / 差分検査 (`oasdiff` / `asyncapi-diff`) といった既成ツールを CI / 開発フローに組み込めるようにし、契約進化のリスクを機械的に検知する
- **物理識別子は infra が SSoT**: Pub/Sub topic 名のような環境依存の物理識別子は Terraform を SSoT とし、app コードに焼き込まない。一方、payload に乗る discriminator (`event_type`) や schema は契約 SSoT 側に置く

client が消費する型契約は **各サービスが直接公開** する（[ADR-036](../adr/036-gateway-passthrough-and-service-public-api.md)）。gateway openapi に残るのは auth / spectate / static / 集約 API のみで、それ以外は型契約を持たず transport だけパススルーする。client UX を考慮した API 設計の主体を所有サービスに置くことで、gateway 側の二重実装と再定義を排除する。

ゲーム定数（`game-design-constants` / `game-logic-constants` 等）は不変ルールであって API 契約ではないため、独自 YAML SSoT を維持する。

具体的な配布物・ファイル配置・ツール・移行 Phase は ADR-034 / ADR-036 と各リポの README を参照。

各エンドポイントの詳細は以下を参照する。

| 種別 | ドキュメント |
|---|---|
| クライアント向け REST | [API_REFERENCE.md](API_REFERENCE.md) |
| クライアント向け WebSocket | [WS_REFERENCE.md](WS_REFERENCE.md) |
| サービス間 内部 REST | [internal/](internal/README.md) |

---

## 3. 認証・認可

### 3.1 Firebase Authentication

| 項目 | 内容 |
|------|------|
| サービス | Firebase Authentication |
| 対応ログイン方式 | Email/Password、Google Sign-In |
| トークン形式 | Firebase ID Token（JWT） |
| 検証方法 | Firebase Admin SDK で `VerifyIDToken` |

**通信経路別の認証方式:**

| 通信経路 | 認証タイミング | 理由 |
|---------|-------------|------|
| REST API | **毎リクエスト** | ステートレスな HTTP 通信のため、都度検証が必要 |
| WebSocket | **接続時のみ** | 接続確立後は同一セッション内で信頼。JWT検証は ~0.1ms のローカル CPU 処理（ネットワーク通信なし）だが、WebSocket メッセージごとに検証する必要はない |

**REST APIリクエスト認証フロー:**

```
クライアント                    GKE Pod
     │                              │
     │  Authorization: <ID Token>   │
     ├─────────────────────────────>│
     │                              │ Firebase Admin SDKで検証
     │                              │  ┌──────────────┐
     │                              │  │ 検証成功？    │
     │                              │  ├──────────────┤
     │                              │  │ Yes → 処理続行│
     │                              │  │ No  → 401返却 │
     │                              │  └──────────────┘
```

### 3.2 WebSocket認証

| 項目 | 内容 |
|------|------|
| トークン送信方法 | 接続時のクエリパラメータ `?token=<ID Token>` |
| 検証タイミング | WebSocket接続アップグレード前 |
| 失敗時の動作 | HTTP 401 を返してアップグレード拒否 |

### 3.3 内部サービス間認証

gateway は Firebase ID Token を検証して player_id を解決した後、下流サービスへの REST 呼び出しに HMAC 署名 JWT (HS256) を `X-Internal-Auth` header で付与する。各サービスは middleware で署名・有効期限・`iss` を検証し、`sub` クレームから player_id を context に書き込む。handler は context 経由で player_id を取得し、認証 header を直読しない (偽造耐性を失うため)。

| 項目 | 内容 |
|------|------|
| Header | `X-Internal-Auth` |
| 署名アルゴリズム | HS256 (対称鍵) |
| 共有秘密鍵 | 環境変数 `INTERNAL_AUTH_SECRET` (k8s Secret) |
| 鍵 ID | JWT header の `kid` (将来のローテーション余地) |
| TTL | 5 分 (`exp` クレーム) |
| Subject | `sub` = player_id |
| Issuer | `iss` = `overload-party-gateway` |

設計の詳細・移行段階・検討経緯は [ADR-037](../adr/037-internal-auth-hmac-signed-jwt.md) を参照。

---

## 4. 課金システム

> 課金プラン・スタミナ仕様・カード入手モデル等のビジネスルールは [MONETIZATION.md](../business/MONETIZATION.md) を参照。
> 本セクションではアーキテクチャとしての技術的実装方針を記載する。

### 4.1 決済基盤

| プラットフォーム | 決済手段 | SDK |
|----------------|---------|-----|
| iOS | App Store In-App Purchase | StoreKit 2 |
| Android | Google Play Billing | Google Play Billing Library 7+ |

> プレミアムプラン: Auto-renewable Subscription（月額サブスク）。カードセット・コレクション: Non-consumable（買い切り）。

### 4.2 サーバーサイド検証

購入レシートは**必ずサーバーサイドで検証**する。クライアント側の検証結果は信頼しない。検証処理は shop サービスが担当し、gateway は認証済みのリクエストを shop サービスに中継するのみ。所有スキーマが複数サービスに分かれているため、買い切り商品とサブスクリプションでフローが大きく異なる点に注意する（詳細は [internal/shop.md](internal/shop.md) / [internal/account.md](internal/account.md) 参照）。

**買い切り商品（`faction_set` / `card_pack` / `cosmetic`）の購入フロー:**

```
Client         gateway           shop サービス           Apple / Google
  │                │                    │                         │
  │  1. ストア購入UI起動                 │                         │
  │  ──(StoreKit/Billing)──>             │                         │
  │                │                    │                         │
  │  2. 決済完了    │                    │                         │
  │  (receipt /    │                    │                         │
  │   purchaseToken)│                    │                         │
  │  ─────────────>│                    │                         │
  │                │  2'. 内部 REST 転送 │                         │
  │                │  POST /internal/v1/players/{id}/purchases     │
  │                ├───────────────────>│                         │
  │                │                    │  3. Receipt 検証         │
  │                │                    │  GET history (Apple)    │
  │                │                    │  GET purchases (Google) │
  │                │                    ├───────────────────────>│
  │                │                    │<───────────────────────┤
  │                │                    │  4. 検証OK → shop Tx     │
  │                │                    │     - one_time_purchases │
  │                │                    │       INSERT (冪等:      │
  │                │                    │       purchase_token     │
  │                │                    │       UNIQUE)            │
  │                │                    │     - cosmetic の場合のみ│
  │                │                    │       player_items UPDATE│
  │                │                    │     - faction_set の場合: │
  │                │                    │       outbox に           │
  │                │                    │       card-pack-purchased │
  │                │                    │       + faction-acquired  │
  │                │                    │       を同一 tx で enqueue│
  │                │                    │     - card_pack の場合:   │
  │                │                    │       outbox に           │
  │                │                    │       card-pack-purchased │
  │                │                    │       のみ enqueue        │
  │                │<───────────────────┤                         │
  │  5. 購入結果   │                    │                         │
  │<───────────────┤                    │                         │
  │                │                    │                         │
  │  ６. shop outbox worker が Pub/Sub に publish:                  │
  │       - card-pack-purchased  → card  (GrantPack で配布)         │
  │       - faction-acquired     → account (player_factions INSERT) │
  │                              → gateway (WS 一次通知)            │
```

`faction_set` の場合、shop は `one_time_purchases` 更新と outbox 行 (card-pack-purchased + faction-acquired) を **同一トランザクションで書く** (Transactional Outbox)。後続の account へのファクションアンロック / card のカード付与 / gateway の WS 通知は、shop outbox worker が Pub/Sub に publish した後に各 subscriber が非同期に処理する。`card_pack` 商品 (将来追加) は shop が `card-pack-purchased` のみを publish し、card 側で `card_pack_id` 指定のパックを配布する (faction-acquired は発生しない)。

旧設計では gateway が account / card に同期 REST (`POST /internal/v1/players/{id}/factions` / `/grant-faction-pack`) を呼び分けるオーケストレーションを行っていたが、ADR-031 で **業務事実分割と shop publish への集約**が確定し、ADR-032 で card 側の REST grant エンドポイント (`/grant-initial-pack` / `/grant-faction-pack`) は完全削除された。所有権境界は §8.7、shop / card / account の責務分界は ADR-031 §5 を参照。

shop の DB 書き込みはアトミックで outbox 経由の eventually consistent 配送になるため、shop / 各 subscriber 間の補償トランザクションは不要。配送失敗は DLQ で観測し、手動再投入を行う。

**サブスクリプション（プレミアムプラン）:**

```
1. shop: サブスクリプション状態を更新
2. shop → Cloud Pub/Sub `premium-updated` に publish
3. account: subscribe してプレミアム状態を反映
4. gateway: subscribe して WS でクライアントに通知
```

shop → account の同期呼び出しは存在しない。eventually consistent。

### 4.3 検証API・サーバー通知

**買い切り商品の検証:**

| プラットフォーム | 検証方式 | エンドポイント |
|----------------|---------|---------------|
| Apple | App Store Server API v2 | `GET /inApps/v2/history/{transactionId}` |
| Google | Google Play Developer API | `GET /androidpublisher/v3/.../purchases/products/{productId}/tokens/{token}` |

**サブスク（プレミアムプラン）の状態管理:**

| プラットフォーム | サーバー通知 | 用途 |
|----------------|-------------|------|
| Apple | App Store Server Notifications V2 | 更新・解約・猶予期間・返金等のイベントを受信 |
| Google | Real-time Developer Notifications (RTDN) via Pub/Sub | 同上 |

> サブスクの状態変更（自動更新・解約・猶予期間・返金等）は shop サービスがサーバー通知 (webhook) で受信し、`shop.subscriptions` と `shop.subscription_outbox` を同一トランザクションで更新する。その後、`players.is_premium` / `players.premium_expires_at` は Outbox + Cloud Pub/Sub 経由で account サービスが非同期に更新する。クライアント起点のポーリングは行わない。責務分担の詳細は §8.6 / §8.8 / §9.6 を参照。

### 4.4 Webhook 受信（shop サービス）

Apple / Google からのサーバー通知は、**shop サービスが公開エンドポイントで直接受信する**。ユーザートラフィックの入口は gateway 一本に保ちつつ、課金プラットフォーム側の制約上 gateway 経由でルーティングできないため、shop にのみ例外的に公開エンドポイントを許可する。webhook 用の受信パスは他のクライアント API と明示的に区別し、レート制限も別建てで設定する。

```
Apple Server Notifications V2  ──>  shop (GKE Ingress)  ──>  Cloud SQL (shop スキーマ)
Google RTDN (Pub/Sub push)     ──>  shop (GKE Ingress)  ──>  Cloud SQL (shop スキーマ)
```

| 項目 | 内容 |
|------|------|
| 受信先 | shop サービス（GKE Ingress 経由で外部公開） |
| ランタイム | Go |
| 責務 | サーバー通知の受信・署名検証・`subscriptions` と `subscription_outbox` の同一トランザクション更新 |
| 認証 | Apple: JWS 署名検証 / Google: Pub/Sub push トークン検証 |
| エンドポイント | `POST /webhook/apple` / `POST /webhook/google` |

> account サービスの `players.is_premium` / `premium_expires_at` への伝搬は、shop が書き込んだ `subscription_outbox` を publisher goroutine が Cloud Pub/Sub (`subscription-events`) に publish し、account の subscriber goroutine が pull して反映する非同期経路で行われる。詳細は §9.6 を参照。

### 4.5 冪等性と不正対策

| 対策 | 実装方法 |
|------|---------|
| 重複購入防止 | `purchase_token`（Apple: `transactionId` / Google: `purchaseToken`）を shop スキーマの `one_time_purchases` / `subscriptions` に保存し、UNIQUE 制約で重複 INSERT を排除 |
| レシート再利用防止 | 検証済みトークンを shop スキーマに記録。同一トークンでの再リクエストは既存結果を返却 |
| クライアント改ざん防止 | 課金関連テーブルはすべてサーバー側のみが write。クライアントからの直接変更は不可（下表の所有権境界を参照） |

テーブル所有権の詳細は [DATA_DESIGN.md](DATA_DESIGN.md) を参照。

### 4.6 購入処理のトランザクション

**買い切り商品（`cosmetic`）:**

shop 単独のトランザクションで完結する。所有テーブルはすべて shop スキーマ内にあるため、アトミックに決済記録と所持反映が行われる。

```
BEGIN (shop)
  1. one_time_purchases に purchase_token が存在しないことを確認
  2. one_time_purchases に INSERT (purchase_token, player_id, product_id, verified_at)
  3. player_items に UPDATE / INSERT（cosmetic アイテム所持を反映）
COMMIT
```

> shop スキーマ内で完結するため、「決済済みだが所持反映されない」状態は発生しない。

**買い切り商品（`faction_set` / `card_pack`）:**

shop は `one_time_purchases` 更新と outbox 行を **同一トランザクションで書く** (Transactional Outbox / ADR-031 §2)。ファクションアンロック (account) / カード付与 (card) / WS 通知 (gateway) は outbox worker が publish する Pub/Sub event を各 subscriber が消費する形で eventually consistent に反映される。

```
1. BEGIN (shop)
     one_time_purchases に INSERT (purchase_token, player_id, product_id, verified_at)
     -- product.type = 'faction_set' の場合:
     outbox_events に INSERT (card-pack-purchased: pack_id = product_card_pack_refs.card_pack_id)
     outbox_events に INSERT (faction-acquired   : faction = product_faction_grants.faction)
     -- product.type = 'card_pack' の場合 (将来追加):
     outbox_events に INSERT (card-pack-purchased: pack_id = product_card_pack_refs.card_pack_id)
   COMMIT
2. shop outbox worker が ClaimUnpublished → Cloud Pub/Sub に publish
   → card    subscriber: card-pack-purchased を受け、GrantPack(pack_id) で配布
   → account subscriber: faction-acquired を受け、player_factions に INSERT
   → gateway subscriber: faction-acquired を一次通知 / card-pack-purchased を副次通知として WS push
```

> 2 で各 subscriber が失敗した場合、Pub/Sub の at-least-once 配送と DLQ で再試行し、最終的に DLQ から手動で再投入する。shop 側のトランザクションは既にコミット済みのため補償トランザクションは採用しない（`feedback_no_fallback` の方針に整合）。

> 旧設計では gateway が account / card に対して同期 REST (`/factions` / `/grant-faction-pack`) を呼び分けるオーケストレーションを行っていたが、ADR-031 (業務事実分割) と ADR-032 (card_pack 概念導入と GrantPack 統一) により **shop publish への集約 + Pub/Sub 駆動**へ移行した。card の REST grant エンドポイントは削除済み。

**サブスクリプション（プレミアムプラン）:**

webhook 受信・購入 API 受信のいずれの経路でも、shop は同一トランザクションで `subscriptions` と `shop.subscription_outbox` を更新する。account の `players.is_premium` / `premium_expires_at` は shop からは直接更新せず、Outbox + Cloud Pub/Sub 経由で伝搬させる。

```
1. BEGIN (shop)
     INSERT / UPDATE subscriptions
       （purchase_token, player_id, plan_id, status, expires_at 等）
     INSERT subscription_outbox
       （イベントペイロード: player_id, plan_id, status, expires_at 等）
   COMMIT
2. shop サービス内 publisher goroutine が subscription_outbox を poll
   → Cloud Pub/Sub トピック subscription-events に publish
   → publish 成功後、outbox 行を published 済みとしてマーク
3. account サービス内 subscriber goroutine が
   subscription-events-account subscription を pull
   → players.is_premium / premium_expires_at を UPDATE
```

- shop → account の同期 REST 呼び出しは存在しない
- 到達保証（at-least-once）・冪等性・DLQ・失敗時の挙動は §9.6 を参照
- 個別イベント種別（`subscription.activated` / `renewed` / `expired` / `revoked` 等）の一覧と扱いは §9.6 および [internal/account.md](internal/account.md) を参照

**猶予期間のポリシー:**

| 項目 | 内容 |
|------|------|
| Apple | Billing Retry Period（最大60日）中はプレミアム維持 |
| Google | Grace Period（通常3〜7日）中はプレミアム維持 |
| 猶予終了後 | account の Premium Subscriber が `subscription.expired` イベントを受信した時点で `players.is_premium = false` に更新し、スタミナ制に戻す |

> 猶予期間中もプレミアムを維持する方針。決済が復旧すれば自動更新され、復旧しなければ猶予終了後に失効する。ユーザー体験を優先し、一時的な決済エラーでプレミアムが途切れることを防ぐ。

---

## 5. リアルタイム通信

### 5.1 WebSocket接続管理

| 機能 | 内容 |
|------|------|
| 接続登録 | `playerID → WebSocket接続` のマップを gateway Pod 内インメモリ管理 |
| ゲーム参加 | `gameID → []playerID` のマップを gateway Pod 内で管理 |
| ブロードキャスト | gateway がゲーム内の全プレイヤーに状態更新を送信 |
| ドメイン処理の委譲 | gateway は認証・WS hub・集約 API・各サービスへのパススルーに専念し、ドメイン処理（ゲームロジック・マッチメイキング・カード・シナリオ等）は対応する内部サービス (battle / matchmaking / card / scenario / account / shop) に委譲する。client 公開 API の型契約は各サービスが直接公開する（[ADR-036](../adr/036-gateway-passthrough-and-service-public-api.md)） |
| スレッドセーフティ | `sync.RWMutex` で同時アクセスを制御 |

内部サービスとの通信方式は 4.1 の全体構成、および各サービスの内部 REST 契約（[internal/](internal/)）を参照。

### 5.2 再接続処理

```
再接続リクエスト
        │
        ▼
gateway が対戦中であれば battle サービスの
内部 REST で最新 GameState を取得
        │
        ▼
gateway Pod 内の WS セッションマップに接続を再登録
        │
        ▼
最新状態をクライアントに送信
```

### 5.3 切断検知とタイムアウト

| パラメータ | 値 |
|-----------|-----|
| Ping/Pong 間隔 | 15秒 |
| Pong 応答タイムアウト | 5秒（応答なしで切断と判定） |
| 再接続猶予時間 | **60秒** |
| 猶予超過時の処理 | 切断プレイヤーの**敗北**（不戦勝） |

**切断処理フロー:**

```
Pong 応答なし（5秒）
     │
     ▼
切断と判定
     │
     ├── マッチメイキング中 → 即座にキューから離脱
     │
     ├── 対戦中:
     │     ├── 対戦相手に `opponent_disconnected` 通知
     │     │
     │     ▼
     │   60秒タイマー開始
     │     │
     │     ├── 60秒以内に再接続 → 対戦相手に `opponent_reconnected` 通知、タイマー解除
     │     │
     │     └── 60秒超過 → 切断プレイヤーの敗北
     │          ├── forfeit アクション送信
     │          ├── game_over (reason: disconnect) を全プレイヤーに通知
     │          └── 経験値付与（通常の勝敗と同等に扱う）
     │
     └── その他（ホーム画面等） → 特別な処理なし
```

**切断時の処理中断方針:**

| 処理 | 切断時 | 理由 |
|------|--------|------|
| ゲームアクション (Battle Server HTTP) | タイムアウト付きで完了させる | 60秒猶予内の再接続時に最後のアクションが反映されている |
| 経験値付与 | タイムアウト付きで完了させる | ゲーム結果の永続化 |
| マッチメイキング | 即座にキャンセル | 切断＝対戦意思なし |
| NPC バトル開始 | 即座にキャンセル | 切断＝対戦準備未完了 |

> **切断ペナルティ:** 初期段階では導入しない。悪質な切断が増加した場合に、常習者への追加ペナルティを検討する。

### 5.4 WebSocket ヘルスチェック

| 項目 | 内容 |
|------|------|
| サーバー → クライアント | 15秒間隔で Ping 送信 |
| クライアント → サーバー | Pong 応答（WebSocket プロトコル標準） |
| タイムアウト | 5秒以内に Pong がなければ切断と判定 |

### 5.5 マッチメイキング

FIFO キュー方式のランダムマッチメイキング。待機時間順にペアリングする。詳細は matchmaking リポの `docs/ARCHITECTURE.md` を参照。

```
client → gateway → matchmaking (enqueue) → Redis キュー → マッチ成立
→ Cloud Pub/Sub (matchmaking-events) → gateway → WS push (match_found)
```

### 5.6 WS メッセージ一覧

gateway リポの `docs/API_REFERENCE.md` を参照。

---

## 6. セキュリティ

### 6.1 レート制限

| 項目 | 値 |
|------|-----|
| 通常リクエスト上限 | 10 req/sec |
| バースト上限 | 20 req |
| 超過時のレスポンス | HTTP 429 Too Many Requests |

### 6.2 CORS設定

環境変数 `ALLOWED_ORIGINS` で許可するオリジンを制御する。

| 環境 | AllowOrigins |
|------|-------------|
| dev | 未設定（全オリジン許可） |
| stg | `https://overloadparty-stg.keyandnotes.com`, `capacitor://localhost`, `http://localhost` |
| prod | `https://overloadparty-prod.keyandnotes.com`, `capacitor://localhost`, `http://localhost` |
| ローカル | 全オリジン許可 |

- REST: `middleware.CORS()` で HTTP レスポンスヘッダを設定
- WebSocket: `websocket.Upgrader.CheckOrigin` でアップグレード時に Origin ヘッダを検証
- `capacitor://localhost`, `http://localhost` は Capacitor (iOS/Android) ネイティブアプリ用

| 項目 | 値 |
|------|-----|
| `AllowMethods` | GET, POST, PUT, DELETE |
| `AllowHeaders` | Authorization, Content-Type |
| `MaxAge` | 12時間 |

### 6.3 ドメイン / DNS / TLS

| 項目 | 値 |
|------|-----|
| ドメイン | `keyandnotes.com`（お名前.com + Cloudflare DNS） |
| TLS 方式 | Cloudflare SSL Flexible（Cloudflare で TLS 終端 → GKE Ingress は HTTP） |

**サブドメイン構成:**

| 環境 | サブドメイン | IP |
|------|------------|-----|
| dev | `overloadparty-dev.keyandnotes.com` | 動的（Ingress 起動時に割当） |
| stg | `overloadparty-stg.keyandnotes.com` | 動的（Ingress 起動時に割当） |
| prod | `overloadparty-prod.keyandnotes.com` | 未定 |

- Cloudflare Universal SSL は `*.keyandnotes.com` をカバー（1 階層のみ）
- そのため `overloadparty-dev` 形式を採用（`dev.overloadparty.keyandnotes.com` は証明書対象外）
- Cloudflare DNS で Proxied (orange cloud) モードを使用
- 静的 IP は使用しない（コスト削減）。代わりに GitHub Actions で Cloudflare DNS を自動更新:
  - **起動時** (`env-lifecycle.yaml`): Ingress の外部 IP 取得後、Cloudflare API で A レコードを更新
  - **停止時** (`nightly-shutdown.yaml`): DNS を `127.0.0.1` に変更し、予約済み IP を削除
- Cloudflare 認証情報は `CLOUDFLARE_` プレフィックスで統一。DNS トークン (`CLOUDFLARE_DNS_API_TOKEN`) は secrets、ゾーン ID (`CLOUDFLARE_ZONE_ID`) は variables で管理

---

## 7. 多言語対応 (i18n)

---|------|------------------|------|
| UI テキスト (ボタン, ラベル等) | react-i18next (JSON) | 即時（再読み込み不要） | 実装済み |
| ナビゲーションストーリー | クライアントバンドル (.ks) | 即時 | 実装済み |
| シナリオストーリー | サーバー配信 (.ks) | 次回読み込み時 | 実装済み |
| カード名・効果テキスト | サーバー側翻訳テーブル | — | 未実装（設計のみ） |
| バトルログ | — | — | 未実装（日本語固定） |

### 7.1 アーキテクチャ

```
src/i18n/
  index.ts              # i18next 初期化 + settingsStore 連携
  locales/
    ja/                 # 日本語 (デフォルト / フォールバック)
      common.json       # 共通: ボタン、タブ、ラベル
      auth.json         # 認証画面
      navigation.json   # オンボーディング
      home.json         # ホーム画面
      battle.json       # バトル関連
      card.json         # カード・デッキ管理
      matchmaking.json  # マッチメイキング
      result.json       # バトル結果
      shop.json         # ショップ
      settings.json     # 設定 + ルールブック
      scenario.json     # シナリオ・ストーリー
    en/                 # 英語 (同構造)
```

### 7.2 仕組み

### 初期化フロー

1. `src/main.tsx` で `import '@/i18n'` を実行（React レンダリング前）
2. `src/i18n/index.ts` が `settingsStore` から永続化された言語設定を読み取り、i18next を初期化
3. `settingsStore.subscribe()` で言語変更を監視し、`i18next.changeLanguage()` を自動呼び出し

### コンポーネントでの使用

```tsx
import { useTranslation } from 'react-i18next'

function MyComponent() {
  const { t } = useTranslation('battle') // namespace を指定
  return <h1>{t('pageTitle')}</h1>
}
```

### クロスネームスペース参照

```tsx
const { t } = useTranslation('battle')
// 別の namespace のキーを参照
{t('common:cancel')}
{t('navigation:factionSelect.factionDescription.SHE')}
```

### 補間 (Interpolation)

```tsx
t('dailyBattle.battlesRemaining', { remaining: 5 })
// → "残り5回" (ja) / "5 battles remaining" (en)
```

### 7.3 翻訳キーの追加手順

1. `src/i18n/locales/ja/<namespace>.json` に日本語キーを追加
2. `src/i18n/locales/en/<namespace>.json` に英語キーを追加
3. コンポーネントで `t('newKey')` を使用

### キー命名規則

- キャメルケース: `pageTitle`, `emptyState`, `confirmDeleteMessage`
- ネスト可: `deck.pageTitle`, `stats.throughput`
- 補間変数: `{{count}}`, `{{name}}`

### 7.4 Namespace 一覧

| Namespace | 対象 | ファイル例 |
|---|---|---|
| `common` | 共通 UI (ボタン、タブ) | BottomTabBar, Button |
| `auth` | 認証画面 | TitleScreen, SignupScreen |
| `navigation` | オンボーディング | StageIntro, StageFactionSelect |
| `home` | ホーム画面 | HomePage, DailyBattleCard |
| `battle` | バトル関連 | BattleFieldPage, BattleTopPage |
| `card` | カード・デッキ | CardListPage, DeckEditPage |
| `matchmaking` | マッチメイキング | MatchmakingPage |
| `result` | バトル結果 | BattleResultPage |
| `shop` | ショップ | ShopPage, PurchaseModal |
| `settings` | 設定・ルールブック | SettingsPage, RulebookPage |
| `scenario` | シナリオ・ストーリー | ScenarioListPage, StoryPage |

### 7.5 カードデータの多言語化 (未実装)

カード名・効果テキストはサーバーが `Accept-Language` ヘッダーに応じて返す方針。
現状は DB・API ともに日本語のみで、翻訳テーブルもクライアントの `Accept-Language` 送信も未実装。

### テーブル設計案

```sql
-- カード名翻訳テーブル
CREATE TABLE card_name_translations (
  card_id   VARCHAR(10) NOT NULL,
  lang      VARCHAR(5) NOT NULL,  -- 'ja', 'en'
  card_name VARCHAR(100) NOT NULL,
  PRIMARY KEY (card_id, lang),
  FOREIGN KEY (card_id) REFERENCES card_definitions(card_id)
);

-- 効果テキスト翻訳テーブル
CREATE TABLE effect_text_translations (
  card_id     VARCHAR(10) NOT NULL,
  lang        VARCHAR(5) NOT NULL,
  effect_text VARCHAR(500) NOT NULL,
  PRIMARY KEY (card_id, lang),
  FOREIGN KEY (card_id) REFERENCES card_definitions(card_id)
);
```

### API フロー

1. クライアントが REST/WebSocket リクエストに `Accept-Language: ja` ヘッダーを付与
2. サーバーが翻訳テーブルを JOIN してローカライズ済みのカード名・効果テキストを返却
3. 翻訳が存在しない場合はデフォルト言語 (ja) にフォールバック

### クライアント側の対応 (未実装)

- API クライアントに `Accept-Language` ヘッダーを自動付与する仕組みを追加予定
- `settingsStore.language` を参照して動的にヘッダーを設定

### 7.6 バトルログの多言語化 (未実装)

バトルログ内のカード名は Battle サーバーのインメモリキャッシュから取得しており、日本語固定。
カードデータの多言語化と合わせて対応が必要。
