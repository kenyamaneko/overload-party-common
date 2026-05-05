# ADR-015: 共通パッケージ分割と SSoT 分散

**Status:** Accepted (Phase 6/7 完了)
**Date:** 2026-04-11

---

## 背景

[ADR-011](011-repository-split.md) でリポジトリ単位のサービス分割を決定したが、common リポジトリの `packages/` 配下は依然としてモノリス時代の構造のままである。全サービスが参照する契約・型・マスターデータが 1 箇所に集約されており、「どのパッケージを誰が所有するか」がサービス境界と一致していない。本 ADR ではその解消方針を定める。

### 現状の課題

1. **責務の混在**: `packages/gamedata-dotnet` が以下 4 種類の責務を抱えている。
   - `BattleGatewayRpc_gen.cs` — battle ↔ gateway の RPC envelope 契約
   - `GameStateView_gen.cs` / `EventData_gen.cs` — battle が生成し client が表示する state / event payload
   - `GameConstants_gen.cs` / `VariantTypes_gen.cs` — ゲームロジック enum とゲームデザイン定数が混在
   - `cache/cards_gen.json` — カードマスターデータの embed
   これは `packages/gamedata-npm` でも同様である。

2. **カードマスターの所有権のズレ**: [ADR-011](011-repository-split.md) の責務分担では card サービスがカードマスター (`card_definitions`) の所有者となる。しかし現状は `packages/devdata/cache/cards_gen.json` や `packages/gamedata-dotnet/cache/cards_gen.json` として複数の embed が並存しており、「所有は card サービス、配布は embed」という状態が責務境界と食い違っている。

3. **SSoT が common に集中**: `data/constants.yaml`、`data/models.yaml`、`data/event_schemas.yaml` の全てが common 配下にあり、各サービスが自分の契約や定数を編集するには必ず common を経由する。サービスが「自分の契約 = 自分の所有物」として扱えない。

4. **契約の所有者が不明確**: 各 RPC パッケージをどのサービスが publish・バージョニングするかの責任が決まっていない。現状は common が全部まとめて publish しているため、例えば account の API 型を 1 フィールド追加するだけで common 全体のパッケージバージョンが上がる。

5. **ゲーム定数の分類不足**: `data/constants.yaml` に全ての enum・定数が混在している。実際に gateway のコードベースを調べると、gateway が参照しているのは以下のようにごく一部である。
   - WS メッセージタイプ (gateway 自身が所有すべき)
   - `WinReason` / `EventType` / `ActionType` の一部（battle との RPC 判定で使う）
   - `Faction` / `DeckSize` / `RestrictionCopyCount`（ゲームデザイン定数）
   にもかかわらず、現状では gateway が `TriggerType` や `EffectOp` や `BuffType` といったバトルエンジンの内部 enum まで同じパッケージから読み込む状態になっており、依存範囲が不必要に広い。

## 決定

パッケージを **責務単位（RPC / 共通データ / ゲームデザイン）** に分類し直し、**所有サービスのリポジトリに物理配置する**。あわせて SSoT (YAML) も所有サービスのリポジトリに分散させ、各サービスが自分の契約と定数を完全に所有する構造を採る。

### パッケージの 3 分類

#### (A) RPC パッケージ — 2 者間の通信契約

各 RPC パッケージは **メッセージの送信側サービスが所有**する。受信側は consume のみ。gateway は複数サービスの RPC パッケージを consume する「ハブ」になる。

| RPC チャネル | 所有 | 言語 | 主な consumer |
|---|---|---|---|
| client ↔ gateway (REST / WS envelope) | gateway | Go + TS | client (TS), gateway 自身 (Go) |
| gateway ↔ account | account | Go | gateway, account |
| gateway ↔ card | card | Go | gateway, card |
| gateway ↔ shop | shop | Go | gateway, shop |
| gateway ↔ scenario | scenario | Go | gateway, scenario |
| gateway ↔ matchmaking | matchmaking | Go | gateway, matchmaking |
| gateway ↔ battle (RPC envelope) | battle | Go + C# | gateway (Go), battle (C#) |
| battle → client (state / event payload、gateway 透過中継) | battle | C# + TS | battle (C#), client (TS)、gateway は `json.RawMessage` で中継するため型依存なし |
| shop → account (Outbox `subscription-events`) | shop | Go | shop (publisher), account (subscriber) |
| card → battle (Pub/Sub `card-definitions-updated`) | — | — | ペイロードは invalidation signal のみの極小シグナルであり、型パッケージ化しない。両側で手書き |

#### (B) 共通データパッケージ — 特定サービスに属さないゲームデザインの SSoT

| パッケージ | 内容 | 所有 | 参照元 |
|---|---|---|---|
| ゲームデザイン定数 | `Faction`, `SelectableFactions`, `DeckSize`, `Restriction`, `RestrictionCopyCount`, `InstanceFamily`, `MatchType`, `StatType`, `CardType`, カード配置判定ヘルパー | common | 全サービス + client |
| ファクションマスター | `factions.yaml` 由来の表示名・ソート順 (ADR-014 参照) | common | 全サービス + client |
| カード定義型 | `Card`, `CardStats`, `PassiveEffect`, `VariantTypes` 等のカード定義構造型 | common | battle (エンジン), card (配信), client (表示) |

共通データパッケージの SSoT は引き続き common に置き、Go / C# / TS の各言語版を common から publish する。これらは「ゲームデザイン = ゲームのルール」であり、どのランタイムサービスにも属さない領域である。

#### (C) サービスロジック定数パッケージ — サービスが自分のロジックのために所有する enum

| 定数群 | 所有 | 内容 |
|---|---|---|
| **ゲームロジック enum** | battle | `WinReason`, `EventType`, `ActionType`, `Phase`, `Zone`, `Rank`, `GameStatus`, `TriggerType`, `EffectOp`, `EffectDuration`, `BuffType`, `BuffMode`, `EffectCategory`, `EffectTargetType`, `PlayerRef`, `UseLimit`, `GuardType`, `SelectorPickMode`, `CustomEffect` |
| **WS メッセージタイプ** | gateway | `WSServerMsg*`, `WSClientMsg*` |
| **Product タイプ** | shop | `ProductTypeFactionSet`, `ProductTypeCosmetic`, `ProductTypeSubscription` |
| **CloudNews source** | newsfeed | `CloudNewsSource*` |

ゲームロジック enum はバトルエンジンが生成・消費する概念であり、battle が所有すべき。gateway や他サービスが少数参照するケース（WS 中継時の判定や結果集計）は、battle の RPC 契約パッケージ経由で取得する。これにより battle の内部 enum が他サービスに漏れ出さず、かつ contract 経由で必要な分だけ参照できる。

### SSoT の分散配置（案 Y の採用）

SSoT の YAML は common に一元集約せず、所有サービスのリポジトリに分散させる。common には「ゲームデザイン」領域の SSoT だけが残る。

| SSoT | 移動後の場所 |
|---|---|
| ゲームロジック enum (`WinReason` / `EventType` / `ActionType` / `TriggerType` 等) | **battle リポ**の `data/game_logic_constants.yaml` |
| バトル RPC / state / event 契約型 | **battle リポ**の `data/models.yaml` と `data/event_schemas.yaml` |
| WS メッセージタイプ | **gateway リポ**の `data/ws_constants.yaml` |
| gateway の REST / WS envelope 型 | **gateway リポ**の `data/models.yaml` |
| account / card / shop / scenario / matchmaking の内部 REST 契約型 | **各サービスリポ**の `data/models.yaml` |
| Product タイプ | **shop リポ**の `data/shop_constants.yaml` |
| CloudNews source | **newsfeed リポ**の `data/newsfeed_constants.yaml` |
| ゲームデザイン定数 (`Faction`, `DeckSize`, `Restriction`, `CardType`, `InstanceFamily` 等) | **common リポ**の `data/game_design_constants.yaml`（現 `data/constants.yaml` から分離） |
| カードマスター (`data/cards/*.yaml`) | 当面は **common リポ**に残し、将来 card リポへの移管を検討（カード定義と game_design 資料の密結合があるため先送り） |
| ファクションマスター (`data/factions.yaml`) | **common リポ** |
| event_schemas.yaml のうちバトルイベント部分 | **battle リポ**（ゲームロジック enum と一体で管理） |

#### common に残る SSoT / 資産 (Phase 6/7 完了後の最終形)

Phase 6/7 完了時点で common に残るのは以下のみ。カード定義 (`data/cards/`)・カード定義型 (`packages/card-data*`)・モデル定義・API 契約・WS 定数・ゲームロジック定数・ショップ定数・newsfeed 定数・各サービス独自スキーマは**すべて対応するサービスリポジトリに移管済み**。

- **SSoT YAML**
  - `data/factions.yaml` — ファクションマスター
  - `data/game_design_constants.yaml` — ゲームデザイン定数 (Faction / DeckSize / Restriction / CardType / InstanceFamily / StatType / MatchType / Zone / Rank 等)
- **パッケージ** (全リポジトリが consume)
  - `packages/game-design-constants/` — Go module
  - `packages/game-design-constants-dotnet/` — NuGet `OverloadParty.GameDesignConstants`
  - `packages/game-design-constants-npm/` — npm `@kenyamaneko/overload-party-game-design-constants`
- **code-gen / バリデーションスクリプト**
  - `scripts/generate_constants.py` — game-design constants を Go / C# / npm に生成
  - `scripts/generate_schema_doc.py` — `db/schema_postgres.sql` のインラインコメントから DATA_DESIGN.md のマーカー区間を自動更新
  - `scripts/ci/detect-changes.sh` — publish 対象検知 (CI 専用)
- **DB (shared スキーマのみ)**
  - `db/schema_postgres.sql` — `shared.game_config` と `shared.update_updated_at()` トリガ関数のみ
  - `db/grant_iam.sql` — IAM 認証用権限付与 (ops リポが実行、psqldef 対象外)
- **横断ドキュメント**
  - `docs/architecture/` — ARCHITECTURE / DATA_DESIGN / I18N / CI_CD 等の横断設計書
  - `docs/game_design/` — ゲームデザイン資料 (RULEBOOK / CARD_DESIGN_GUIDE / FACTION_GUIDE / TUTORIAL_DESIGN / UI_DESIGN 等)
  - `docs/business/` — ビジネス・法務資料
- **CI/CD**
  - `.github/workflows/publish.yaml` — game-design-constants の Go / NuGet / npm 一括 publish
  - `.github/workflows/validate.yaml` — Python unit tests + codegen-sync check
  - `.github/workflows/dispatch-migration.yaml` — `db/schema_postgres.sql` 変更時に ops リポへ repository_dispatch

### パッケージの物理配置

SSoT の分散に伴い、publish される package も所有サービスのリポジトリから出す。

```
overload-party-gateway/
  packages/
    api-client/           Go: client ↔ gateway の REST/WS 契約
    api-client-npm/       TS: 同上 (client が consume)
    ws-constants/         Go: WS メッセージタイプ enum
    ws-constants-npm/     TS: 同上

overload-party-battle/
  packages/
    api-rpc/              Go: gateway ↔ battle RPC 契約
    api-rpc-dotnet/       C#: 同上
    game-state-dotnet/    C#: GameStateView / EventData (battle と将来の C# client が共有)
    game-state-npm/       TS: 同上 (client が consume)
    game-logic-constants/ Go: ゲームロジック enum (gateway が必要な分を consume)
    game-logic-constants-dotnet/ C#: 同上
    game-logic-constants-npm/    TS: 同上

overload-party-account/
  packages/
    api-rpc/              Go: gateway ↔ account RPC

overload-party-card/
  packages/
    api-rpc/              Go: gateway ↔ card RPC

overload-party-shop/
  packages/
    api-rpc/              Go: gateway ↔ shop RPC
    subscription-events/  Go: Outbox イベント型 (account が subscribe)
    shop-constants/       Go: Product タイプ enum

overload-party-scenario/
  packages/
    api-rpc/              Go: gateway ↔ scenario RPC

overload-party-matchmaking/
  packages/
    api-rpc/              Go: gateway ↔ matchmaking RPC

overload-party-newsfeed/
  packages/
    newsfeed-constants/   Go: CloudNews source 等

overload-party-common/  (縮小後)
  packages/
    game-design-constants/        Go: Faction / DeckSize / Restriction / CardType / InstanceFamily 等
    game-design-constants-dotnet/ C#: 同上
    game-design-constants-npm/    TS: 同上
    card-data/                    Go: Card / CardStats / PassiveEffect 等 + カードマスター参照クライアント相当
    card-data-dotnet/             C#: 同上
    card-data-npm/                TS: 同上
  data/
    cards/*.yaml           カードマスター SSoT
    factions.yaml          ファクション SSoT
    game_design_constants.yaml   ゲームデザイン定数 SSoT
  docs/
    architecture/          横断設計書のみ
    game_design/           ゲームデザイン資料
```

### カードマスターデータの扱い

現状 `packages/devdata/cache/cards_gen.json`、`packages/gamedata-dotnet/cache/cards_gen.json` に embed として埋め込まれているカードマスターデータは、**リポジトリ分割後は card サービスが REST API 経由で配布する**方式に改める。

- ランタイムは card サービスが `card_definitions` テーブルから読み出して `GET /internal/v1/cards` で返却する
- battle は起動時に card サービスから取得して in-memory キャッシュ化する（ARCHITECTURE.md §5.3 参照）
- client も gateway 経由で card サービスから取得する
- `packages/*/cache/cards_gen.json` の embed は原則廃止。ただしローカル開発用の devdata だけは、card サービスを毎回起動しなくて済む利便性のために残す余地がある
- カード定義の**型**（`Card`, `CardStats`, `PassiveEffect` 等）は common の `card-data-*` パッケージとして配布する。型とデータを分離する

### code-gen パイプラインの分散

SSoT が各リポに分散するため、code-gen スクリプトも分散させる必要がある。

**方針**:

- common の `scripts/` のうち、汎用部分（YAML パーサ、Go/C#/TS テンプレートエンジン）を Python パッケージ化して各サービスリポから利用できるようにする
- 各サービスリポが自分の `data/*.yaml` に対して生成スクリプトを走らせ、自リポ内の `packages/` を更新する
- common の CI は common 自身の `data/` と `packages/` だけを対象にする
- ドキュメント内の `<!-- BEGIN GENERATED: TypeName -->` / `<!-- BEGIN GENERATED: table_name -->` マーカーも、各サービスリポ内のドキュメントを各リポの CI が更新する

共通ジェネレータの配布形態（Python パッケージ publish / git submodule / テンプレートの複製）は次フェーズで詳細設計する。現時点では「各サービスリポが自立して code-gen を走らせる」という方針だけを確定する。

### 段階的なロードマップ

一気に全パッケージを分割すると影響範囲が広すぎるため、以下の順序で段階的に進める。

**Phase 1: 定数の分類整理 (common 内で先行)**

- `data/constants.yaml` を以下 3 ファイルに分割する
  - `data/game_design_constants.yaml` — common に残すゲームデザイン定数
  - `data/game_logic_constants.yaml` — 将来 battle リポへ移管予定のゲームロジック enum（当面 common 内）
  - `data/gateway_ws_constants.yaml` — 将来 gateway リポへ移管予定の WS メッセージタイプ（当面 common 内）
  - `data/shop_constants.yaml` — 将来 shop リポへ移管予定の Product タイプ（当面 common 内）
  - `data/newsfeed_constants.yaml` — 将来 newsfeed リポへ移管予定（当面 common 内）
- `scripts/generate_constants.py` を拡張し、それぞれ別のパッケージに生成する
- 既存の `packages/gamedata` は後方互換のため残しつつ、内部で新パッケージを re-export する形にする

**Phase 2: battle の外向き同期通信を gateway 経由化**

- matchmaking → battle の直接 RPC を廃止し、matchmaking → (Pub/Sub) → gateway → battle へ切り替える
- battle → card の同期 REST も gateway → card にルーティング変更する
- ただし Pub/Sub `card-definitions-updated` は battle が直接購読を継続する（極小シグナルで型依存がないため）
- これにより battle の外向き対向は gateway 単一となり、パッケージ依存関係がシンプルになる

**Phase 3: Go 側の新 RPC パッケージを common 内で作成**

- common 内に `packages/api-gateway`, `api-account`, `api-card`, `api-shop`, `api-scenario`, `api-matchmaking`, `api-battle-rpc` を新設する
- `data/models.yaml` をサービス別セクションに再編する
- 既存の `packages/api` はクライアント向け REST/WS 契約専用として縮小する（または gateway のものと統合する）
- この段階では **まだ物理的には common 内に置いたまま**

**Phase 4: battle-client 用 C# パッケージの責務整理**

- `packages/gamedata-dotnet` を以下に分離する
  - `packages/game-state-dotnet` — GameStateView / EventData / ゲームロジック enum / VariantTypes
  - `packages/api-battle-rpc-dotnet` — BattleGatewayRpc 契約
  - `packages/game-design-constants-dotnet` — Faction / DeckSize 等
  - `packages/card-data-dotnet` — Card 型 (データは含まない)
- battle-client の更新が追随できない間は過渡期として `gamedata-dotnet` を残し、新パッケージを並行して publish する

**Phase 5: カードマスターデータの embed 廃止**

- `packages/*/cache/cards_gen.json` を順次削除する
- battle は card サービスの `GET /internal/v1/cards` から取得する実装に置き換える
- client も gateway 経由で取得する実装に置き換える
- devdata を残すかは運用の利便性次第で決める

**Phase 6: 各サービスリポへのパッケージ物理移管**

- common 内で完成している各 RPC パッケージを、所有サービスのリポジトリへ移管する
- SSoT YAML も同時に移管する
- common の code-gen スクリプトを各サービスリポから参照できるように整備する
- CI パイプラインを各サービスリポの個別 publish に切り替える

**Phase 7: ドキュメント・DB スキーマの各サービスリポ移管**

- `docs/architecture/internal/*.md` の各サービス分を各サービスリポに移管する
- `db/schema_postgres.sql` の各サービススキーマ分を各サービスリポに切り出し、マイグレーション責務を各サービスに移管する（ops リポのマイグレーションジョブは各リポを集約する形に再設計する）
- common の `docs/architecture/` は横断的な設計書のみに縮小する

### 段階間の依存関係

- Phase 1 は単独で実施可能
- Phase 2 は Phase 1 完了後が望ましい（battle が参照する enum を battle 所有にした後で、通信経路を変える方が整合的）
- Phase 3 は Phase 1 と並行可能
- Phase 4 は Phase 3 完了後
- Phase 5 は Phase 2 完了後
- Phase 6 は Phase 3〜5 完了後
- Phase 7 は Phase 6 完了後

## 結果

### 期待される効果

- **所有権の明確化**: 各サービスが自分の契約と定数を完全に所有し、変更の影響範囲が所有サービスに閉じる
- **依存の最小化**: gateway はバトルエンジンの内部 enum（`TriggerType` / `EffectOp` / `BuffType` 等）を知る必要がなくなる。battle の RPC contract 経由で必要な enum だけ consume する
- **battle の責務集約**: ゲームロジックに関する型・enum・RPC 契約が全て battle に集約され、「ゲームロジックの変更は battle だけで完結する」という ADR-002 の精神がパッケージレベルでも実現される
- **common の役割縮小**: common は「ゲームデザインの SSoT + 横断設計書」のみに責務を絞り、ランタイム依存がなくなる
- **カードマスターの一元化**: カードマスターデータの配布経路が card サービスに一本化され、embed による SSoT 分散が解消される

### トレードオフ

- **code-gen の分散**: 各サービスリポが自前で code-gen を走らせることになり、共通ジェネレータの配布・バージョニングが必要になる
- **publish パイプラインの複雑化**: 現状は common の CI で一括 publish だが、各サービスリポが個別に publish する形になる。バージョン依存の組み合わせが増え、サービス間のリリース順序を意識する必要がある
- **過渡期の二重管理**: Phase 1〜6 の途中では旧パッケージと新パッケージが並行して存在し、型の二重管理リスクが一時的に発生する。Phase ごとに旧パッケージを退役させるスケジュールを明確にする
- **client の import 増加**: client は現状 `api-npm` + `gamedata-npm` の 2 つだけ consume しているが、分割後は `api-client-npm`（gateway から）+ `game-state-npm`（battle から）+ `card-data-npm`（common から）+ `game-design-constants-npm`（common から）のように増える。package.json が賑やかになる
- **境界引き直しコストの集中**: 一度決めたパッケージ境界を後から引き直すコストは高い。Phase 1〜2 の段階でゲーム定数の分類判断を誤ると、後続フェーズで戻りが発生する

### 関連 ADR

- [ADR-011](011-repository-split.md): リポジトリ分割。本 ADR の前提となるサービス境界を定義する
- [ADR-002](002-battle-server-csharp-separation.md): battle サーバーの C# 分離。本 ADR の「ゲームロジックを battle に集約する」方針はその延長
- [ADR-014](014-db-schema-split-per-service.md): DB スキーマのサービス単位分割。パッケージ分割と同じく「所有権の明確化」という思想を DB レイヤーに適用したもの
- [ADR-012](012-matchmaking-pubsub.md): マッチメイキングのハイブリッド設計。本 ADR が定める「Pub/Sub イベントは送信側が型を所有」というルールに整合する
