# ADR-036: gateway を完全パススルー化し、client 公開 API を各サービスが整備する

- Status: Accepted
- Date: 2026-05-10
- Deciders: kenyamaneko
- Related: ADR-034 (本 ADR の前提)、[overload-party-common#39](https://github.com/kenyamaneko/overload-party-common/issues/39) (ADR-034 全体トラッカー)

## Context

ADR-034 で client 依存の 3 層原則 (A: API 契約由来 / B: battle 特殊例外 / C: ゲームルール定数) が確定した一方、Layer A の **置換先** と **gateway の責務範囲** は scope 外として持ち越されていた。本 ADR で確定する。

### gateway 現状の handler 分類 (実調査)

`overload-party-gateway/internal/handler/rest/` の 13 handler を実コードで分類した結果、以下の構成だった。

| 分類 | 件数 | handler |
|---|---|---|
| 完全パススルー型 (型加工なし) | 4 | `card` / `game_log` / `npc` / `player_card` |
| 加工ありパススルー型 | 6 | `auth` / `deck` / `news` / `player` / `player_settings` / `scenario` / `shop` |
| gateway 内部状態型 | 2 | `spectate` (WS Manager 状態) / `static` (announcements.json / daily_tips.json) |

加工の中身:

- **型変換** (`deck` / `player_settings` / `shop`): `apigateway.X` → `apicard.X` / `apishop.X` の構造体マッピング
- **フィールドリネーム / 隠蔽** (`player`): `InitialFaction` → `SelectedFaction`、`OnboardingStatus` 隠蔽
- **JSON ラップ** (`scenario`): レスポンスに `episodeID` / `message` を追加
- **enum マッピング** (`shop`): `Platform` 値変換
- **検証** (`shop` の `validatePurchaseRequest`)
- **デフォルト値補完** (`news` の limit / offset)
- **エラー → HTTP status マッピング** (`auth` の `ErrPlayerAlreadyRegistered`)

これらは **ビジネスロジック (ゲームルール / ドメイン演算) ではなく、各サービスの内部 API を client 向けに正規化する変換層**である。各サービスの openapi が「gateway 内部用」として最適化されているため、client 公開には gateway での正規化が必要になっている、という現状認識。

### 現状の構造的問題

1. **型 SSoT の二重管理**: 各サービスが `apigateway.X` 系の型を持ち、gateway がそれを `apishop.X` 等に変換している。同じデータの形を 2 箇所で定義する状態
2. **battle 特殊例外**: ADR-034 amendment Layer B で `game-state-npm` を client 直接消費としたが、battle 以外も同様に直接消費させると例外が消える
3. **gateway server の責務肥大**: 認証 / WS / 集約 / 加工 / 静的データ保持 / 内部状態を全部抱える

## Decision

### 1. gateway 責務範囲の再定義

#### gateway に残すもの (gateway 必須)

- **認証** (`auth_handler`): Firebase ID Token 検証 + Firebase UID → player_id 解決。各サービスは gateway middleware から context 経由で player_id を受け取る前提
- **WS hub** (`game_relay` / `spectate_relay` / `turn_timer` / `exp_award`): 接続状態 / broadcast / 多重化 / プレイヤー導出
- **gateway 自身が保持する状態** (`spectate_handler` / `static_handler`): WS Manager 状態 / 静的データ

#### gateway から外すもの

REST handler のうち上記以外 (`card` / `deck` / `game_log` / `news` / `npc` / `player` / `player_card` / `player_settings` / `scenario` / `shop`) は gateway openapi.yaml から削除し、**transport は gateway を経由するが型契約は各サービスが直接公開する** 形に移行する。

### 2. 各サービスが client 公開 API を整備する

各サービス (shop / card / account / scenario / news / matchmaking 等) は **client 公開仕様** を `data/openapi.yaml` で直接表現する。現状 gateway で担われている変換層を各サービス側に内製化する。

具体的には以下の対応が各サービスで必要:

- **型変換の解消**: gateway が `apigateway.X` ↔ `apiservice.X` の変換をしている部分は、各サービスが client 向け型をそのまま公開し、変換不要にする
- **フィールド命名の正規化**: account の `InitialFaction` を `SelectedFaction` に rename する等、client 向け命名で公開
- **情報隠蔽**: `OnboardingStatus` のように client に見せたくないフィールドは、公開 API では含めない (内部 API と分けるか、公開仕様で除外する)
- **JSON ラップの解消**: scenario が `episodeID` / `message` を含むレスポンスをそのまま返す
- **検証の各サービス側実装**: gateway の `validatePurchaseRequest` 相当を shop 側で実装し、OpenAPI スキーマでも表現

### 3. client 依存構成

- **各サービス TS パッケージ**: `@kenyamaneko/overload-party-api-{service}` を各サービスが新設し、client が直接消費
- **battle**: 既存 `@kenyamaneko/overload-party-game-state` を直接消費 (ADR-034 amendment Layer B で確定済)
- **gateway**: `@kenyamaneko/overload-party-api-gateway` は **集約 API 用** (auth / spectate / static、および将来の集約エンドポイント) として残す
- **ゲームルール定数 (Layer C)**: ADR-034 amendment 通り直接消費維持

### 4. transport は単一 host (現状維持)

client から見たエンドポイントは引き続き gateway 1 つ (`VITE_API_BASE_URL`)。Ingress / Cloud Load Balancer による path-based routing で gateway パススルーを実現するか、gateway server 自身が path routing で各サービスにリレーするかは実装詳細とし、本 ADR では決めない。**型契約と transport は分離した設計** という原則だけ確定する。

### 5. 認証フローは現状維持

`auth_handler` は gateway 残置。Firebase ID Token 検証と Firebase UID → player_id 解決は gateway middleware の責務とし、各サービスは gateway から渡される player_id を信頼する。

将来的に Firebase custom claims に player_id を埋め込んで各サービスが独立検証する案もあり得るが、本 ADR の scope 外とする。

## Consequences

### Positive

- **型 SSoT の一元化**: 各サービスが client 公開仕様を持ち、gateway での再定義が不要になる
- **battle 特殊例外の解消**: 全サービスが「型は各サービス、transport は gateway」の同じパターンに揃う
- **gateway server の責務縮小**: 認証 + WS + 集約 + gateway 内部状態のみ
- **各サービスが UX 設計の主体**: client 公開仕様の改善が各サービスごとに進められる
- **二重実装の排除**: 検証 / 型変換 / リネーム等の作業が各サービス内で完結する

### Negative

- **各サービスでの追加作業**: TS パッケージ新設 + Cloudsmith publish workflow + 公開仕様への openapi リファクタ
- **client の依存パッケージ数増**: 単一 `api-gateway-npm` から複数 `api-{service}-npm` に分散
- **各サービスの責任範囲拡大**: 「client UX を考慮した API 設計」を各サービスチームが担う

### 緩和策

- **Phase 3c として段階移行**: 各サービスを順次対応し、gateway openapi を徐々に縮小する
- **既存の Phase 3b 成果は活用**: 各サービスが既に `data/openapi.yaml` を持っているため、それを「公開仕様」へリファクタする形で進める (新設ではなく既存の進化)
- **Phase 3c 着手前の方針整理**: 「公開仕様 vs 内部仕様」の分離方針 (例: openapi に `x-internal: true` 拡張で識別、または `data/openapi.yaml` と `data/openapi-internal.yaml` のファイル分離等) は本 ADR 範囲では決めず、各サービスの判断とする

## 実装計画

### gateway #26 スコープ調整

- `data/openapi.yaml` から各サービス path を削減、`auth` / `spectate` / `static` および集約 API のみ残す
- `packages/api-gateway-npm` も同範囲に絞る

### client #20 スコープ調整

- 各サービス TS パッケージへの依存追加 (Phase 3c 完了を待つ)
- 廃止予定 npm (`shop-constants` / `card-types` / `newsfeed-constants`) の依存削除
- gateway TS は最小依存 (集約 API のみ)

### Phase 3c (新規): 各サービス TS パッケージ整備

各リポで以下を実施:

- `packages/api-{service}-npm/` 新設
- `openapi-typescript` で client 向け型生成
- publish workflow に npm publish step 追加 (Cloudsmith)
- 公開仕様化のリファクタ (型変換 / リネーム / 検証等を吸収)

対象リポ: shop / card / account / scenario / news / support / matchmaking (7 リポ)

各リポで Phase 3c issue を起票する (本 ADR マージ後)。

## 関連 issue

- [overload-party-common#39](https://github.com/kenyamaneko/overload-party-common/issues/39) — ADR-034 全体トラッカー (本 ADR の進捗もここに集約)
- Phase 3c の各リポ issue は本 ADR マージ後に起票
