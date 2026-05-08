# ADR-034: 外部 API 契約 SSoT を OpenAPI / AsyncAPI に統一し、配布物を Go / npm モジュールに集約する

- Status: Accepted
- Date: 2026-05-09
- Deciders: kenyamaneko
- Related: TBD (移行 issue は本 ADR Accepted 後に各リポへ起票)

## Context

組織配下の各サービスは外部公開する API 契約 (REST エンドポイント、wire 型、Pub/Sub イベント、定数) を **リポごとに自前の YAML SSoT + Python codegen** で生成し、**言語ごとにパッケージ化** して配布している。実装言語が混在していること (Go / C#) と、サービスごとに codegen 構造が独立していることから、共通基盤 `overload-party-codegen-tools` に依存しつつもリポ単位で運用が分岐している。

### 現状の配布構造 (棚卸し結果)

| サービス | 内部実装 | SSoT | codegen | 配布物 (現状) | 外部消費先 |
|---|---|---|---|---|---|
| **shop** | Go | `data/{models.yaml, endpoints.yaml}` | `overload-party-codegen-tools` (Python) | `packages/api-shop` (Go module) | gateway / card / account |
| **battle** | C# | `data/{models.yaml, endpoints.yaml, event_schemas.yaml, game_logic_constants.yaml}` | 自前 `scripts/generate_types.py` (Python, 多言語並行生成) | `packages/api-battle-rpc-{dotnet, go}`, `packages/game-state-{dotnet, npm}`, `packages/game-logic-constants-{dotnet, go, npm}` | gateway (Go) / client (npm) / battle 自身 (NuGet) |
| その他サービス (account / card / scenario 等) | Go | 同型 | 同型 | (各リポの api-* Go module) | 関連サービス |

加えて、shop は Pub/Sub event 型を `targets: [domain, wire]` で **同じ YAML から domain と wire の両層に同形出力** する仕組みを持っており、publisher (shop の domain 型) と subscriber (apishop の wire 型) の JSON 形状一致を **codegen の同一性で暗黙保証** している。

### 配布構造の構造的問題

1. **API 契約のスキーマ表現が独自フォーマット**: `data/{models, endpoints}.yaml` は overload-party 内でしか通じないスキーマで、業界標準の OpenAPI / AsyncAPI とのインターオペラビリティが無い。spec viewer / mock server / contract test 等の OSS エコシステムを活用できない
2. **codegen 自体を自前で運用している**: `overload-party-codegen-tools` (共通) と `scripts/generate_types.py` (battle 独自) を継続保守する負担を負っている。oapi-codegen 等のデファクトに乗れていない
3. **多言語並行生成の運用負担**: battle は Python codegen で 3 言語 × 3 ドメイン = 9 パッケージを生成しており、追加言語・追加パッケージを増やすたびに codegen 改修が要る
4. **NuGet 配布チャンネルが事実上死蔵**: `packages/*-dotnet` の NuGet パッケージは GitHub Packages に発行しているが、`PackageReference` で消費しているのは **battle リポ自身の csproj だけ** (Server / Models / Engine / Npc / Service / Data / Tests)。他リポからの参照はゼロ。**自リポを自リポに NuGet で配っているだけ**の状態
5. **wire ↔ domain 一致前提の非対称性**: `targets: [domain, wire]` は publisher / subscriber 間の JSON 形状一致を担保するために導入されたが、wire は外部公開契約 / domain は内部ロジック型で本来責務が異なる。今後の進化で形状を分けたい場面 (`schema_version` / discriminator / Timestamp 表現の差替) が来ると、SSoT 一本縛りが障害になる
6. **Topic 名・subscription 名の三重管理**: `overload-party-infra/.../pubsub/main.tf` で topic を Terraform プロビジョン → `overload-party-k8s/k8s/base/platform/config-map.yaml` で env var として配信 → さらに `models.yaml` で `TopicCardPackPurchased` 定数を生成、と同じ文字列が 3 箇所に重複している
7. **client (TS) の依存先が npm に分散**: `overload-party-client/package.json` は 6 つの `@kenyamaneko/*` 名前空間 npm パッケージに依存しているが、それぞれ別 SSoT・別 codegen から生成されており、TS 側から見て「契約の出処」が一元化されていない

## Decision

**外部公開 API 契約の SSoT を業界標準仕様 (OpenAPI 3.x / AsyncAPI 3.0) に統一し、配布物を Go モジュール (および必要に応じ npm モジュール) に集約する。NuGet 配布チャンネルは廃止する。**

### 適用範囲

本 ADR の **OpenAPI / AsyncAPI 移行**は overload-party 配下の全サービスリポの **外部公開 API 契約**を対象とする。具体的には:

- REST エンドポイント (path / method / request / response / errors)
- wire 型 (request body / response body / webhook payload)
- Pub/Sub イベント (channel / message / payload schema / `event_type` discriminator)
- 上記に登場する **外部に流出する enum** (例: `Platform = "ios" | "android"`, `ProductType = "faction_set" | ...`)

**対象外** (本 ADR では現行構造を据え置く):

- 内部 domain 型 / 内部完結 enum (例: `SubscriptionStatus` の状態機械)
- ゲーム設計 / ゲームロジック定数 (`game-design-constants`, `game-logic-constants`) — 性質が API 契約ではなく不変ルール定数であるため、別系統の SSoT + codegen を維持

### SSoT 構成

各サービスリポの `data/` 配下を以下に再編する:

| 旧 | 新 | 役割 |
|---|---|---|
| `data/endpoints.yaml` | `data/openapi.yaml` | REST 契約の SSoT |
| `data/models.yaml` の wire / event エントリ | `data/openapi.yaml` (REST 系 schemas) / `data/asyncapi.yaml` (event 系 messages) | wire 型 / event payload の SSoT |
| `data/models.yaml` の domain エントリ | **廃止** (各サービスの `internal/domain/` で手書き Go) | 内部型は SSoT 化しない |
| `data/event_schemas.yaml` (battle) | `data/asyncapi.yaml` | event payload の SSoT |
| `data/game_logic_constants.yaml` (battle) / `overload-party-common/data/game_design_constants.yaml` | 据え置き | ゲーム定数の SSoT (本 ADR 対象外) |

### codegen ツール

業界デファクトに移行する。自前 `overload-party-codegen-tools` および battle 独自 `scripts/generate_types.py` の API 契約用途は本 ADR 完了時点で撤退する。

| 言語 | ツール | 用途 |
|---|---|---|
| Go | `oapi-codegen` (REST) / `lerenn/asyncapi-codegen` ないし同等 (Pub/Sub) | 外部公開 SDK の生成 |
| C# | NSwag | battle 内部の DTO 生成 (NuGet ではなく sln 内 ProjectReference で消費) |
| TypeScript | `openapi-typescript` | client (web/mobile) 向け型生成 |

### 配布物の再設計

#### Go モジュール (一次配布物)

- 各サービスリポは `packages/api-{service}` を Go module として保持する
- module path / package 名・公開型名は OpenAPI / AsyncAPI codegen 出力をそのまま採用する。**bit-identical な互換性は要件としない (L3)**: 本番稼働前のため、import 元の rename / リファクタは同 Phase の PR で対応する
- `publish.yaml` (semantic version tagging) は据え置く

#### npm モジュール (web/mobile 向け二次配布物)

- 既存 `packages/game-state-npm` の役割は `data/openapi.yaml` から `openapi-typescript` で生成する `packages/api-{service}-ts` 等に置き換える
- client が現在依存している 6 つの `@kenyamaneko/*` npm パッケージのうち、API 契約由来のものは本移行で OpenAPI 由来生成に置換する。ゲーム定数由来 (`game-design-constants`, `game-logic-constants`) は据え置き

#### NuGet モジュール (廃止して ProjectReference 化)

`packages/*-dotnet` の NuGet 配布チャンネルを **完全廃止**する。対象は API 契約用 (`api-battle-rpc-dotnet`, `game-state-dotnet`) およびゲーム定数用 (`game-logic-constants-dotnet`, `game-design-constants-dotnet`) を含む全 dotnet パッケージ。

廃止する理由は、`PackageReference` の消費先が battle 自身の csproj に限られており、**他リポからの NuGet 参照が一件も存在しない**ため (Go services は Go module 経由、TS client は npm 経由で別途消費しているため、NuGet パッケージ化する必要がない)。

代替として、battle リポ内では sln 内ローカル参照 (`<ProjectReference>`) で csproj 同士の依存を解決する。例:

```xml
<!-- 旧: src/OverloadParty.Battle.Server/OverloadParty.Battle.Server.csproj -->
<ItemGroup>
  <PackageReference Include="OverloadParty.GameLogicConstants" Version="0.1.0" />
  <PackageReference Include="OverloadParty.GameState" Version="0.1.0" />
  <PackageReference Include="OverloadParty.ApiBattleRpc" Version="0.1.0" />
</ItemGroup>

<!-- 新: -->
<ItemGroup>
  <ProjectReference Include="../../packages/game-logic-constants-dotnet/OverloadParty.GameLogicConstants.csproj" />
  <ProjectReference Include="../../packages/game-state-dotnet/OverloadParty.GameState.csproj" />
  <ProjectReference Include="../../packages/api-battle-rpc-dotnet/OverloadParty.ApiBattleRpc.csproj" />
</ItemGroup>
```

`OverloadParty.Battle.slnx` 内で `packages/*-dotnet/*.csproj` を solution-level に追加する形になる。

廃止に伴い以下も撤去する:

- `battle/.github/workflows/publish.yaml` の `dotnet pack` / `dotnet nuget push` ステップ
- `nuget.config` ファイルおよび GitHub Packages の dotnet feed 認証関連
- battle CI で dotnet feed 認証用に使用していた PAT (例: `COMMON_PKG_FETCH`)

C# 側 csproj およびソース (`packages/*-dotnet/`) 自体は **ファイルとして残す**。発行先が NuGet feed から sln 内 ProjectReference に変わるだけで、C# 内部消費の必要性自体は維持される (battle の minimal API は controller ハンドラ引数に DTO 型をバインドするため、何らかの C# 型が server 内に必要)。

API 契約用の `packages/api-{service}-dotnet/` のソース生成は OpenAPI (NSwag) に切替、ゲーム定数用の `packages/game-*-constants-dotnet/` は現行 codegen を維持する。

### domain 型と wire 型の関係 — 形状一致前提を取らない

wire 型 (外部公開契約) と domain 型 (内部ロジック表現) は **責務が異なるため SSoT を分離し、両者の JSON 形状一致を保証しない**。一致しているように見える現状はリリース直後のたまたまであり、進化方向として:

- wire には `schema_version` / `trace_id` / discriminator が将来追加される可能性がある
- domain は Go の型システム (custom enum 型 / 値オブジェクト) を活かして strict に進化させたい
- wire は subscriber 後方互換のため一度公開したフィールドを保持し続けたい

これらは構造的に対立するため、**両層を別 SSoT で別個に進化させる**方が自然。一致を強制する CI チェックは導入しない。

代わりに、publisher 経路の **`presenter` 層に境界変換を集約する**。`presenter` は本プロジェクトで既に確立されたパッケージで (例: shop は `internal/presenter/` に `Package presenter は domain ↔ wire DTO の境界変換を集約する` と doc 定義済)、`To{Wire型名}(domain入力) (wire出力, error)` 形式の関数で domain → wire の詰め替えを行う。

現状の `internal/presenter/event.go` の `ToCardPackPurchasedEvent` 等は domain と wire が bit-identical であるため `domain.CardPackPurchasedEvent` を返しているが、本 ADR 移行後は戻り値型を wire 側 (`apishop.CardPackPurchasedEvent`) に変更し、本来の境界変換責務を担う形に揃える:

```go
// shop/internal/presenter/event.go (移行後の例)
func ToCardPackPurchasedEvent(eventID, playerID, cardPackID string, ts time.Time) apishop.CardPackPurchasedEvent {
    return apishop.CardPackPurchasedEvent{
        EventType:  apishop.EventTypeCardPackPurchased,
        EventID:    eventID,
        Timestamp:  ts,
        PlayerID:   playerID,
        CardPackID: cardPackID,
    }
}
```

usecase 層は domain 型のみを扱い、adapter 層 (`presenter`) で wire 型に変換してから marshal する。clean architecture の依存方向 (presenter → wire パッケージを import) と整合し、内部完結型 (`internal/domain`) が外部契約 (`packages/api-*`) に依存することを禁ずる lang/go 方針に沿う。

subscriber 側 (card / account / gateway 等) も同原則 (wire → 自サービス domain への presenter 変換) を推奨するが、各リポの判断とし強制はしない。

### enum の取り扱い

外部に流出する値 (例: `PurchaseRequest.Platform = "ios"` / `ProductType = "faction_set"`) は OpenAPI / AsyncAPI の `components/schemas` に enum として記述し、codegen 出力に含める。oapi-codegen は enum を独自型 + 定数として生成するため、現状の `string` 定数より一段強い型付けが得られる。

内部完結する enum (subscription の状態機械等) は YAML SSoT 化せず、`internal/domain/` の手書き Go に置く。

各 enum がどちらに属するかは実装時にコードを追って判定する (本 ADR では切り分け方針のみ定める)。

### Topic 名と event_type の取り扱い

Pub/Sub の **物理 topic 名** (例: `card-pack-purchased`) は `overload-party-infra` リポの Terraform module (`providers/google-cloud/.../pubsub/main.tf`) が SSoT であり、`overload-party-k8s` の ConfigMap → env var 経由でアプリケーションに配信される。**app コードに定数として焼き込まない**:

- `models.yaml` で生成していた `TopicCardPackPurchased` 等の Go 定数は廃止する
- shop の publisher / subscriber は ConfigMap 由来の env var で topic 名を解決する
- AsyncAPI spec の channel address にも topic 名は書かない (binding として infra 側を参照する形を取る)

一方、payload の中身に含まれる **`event_type` discriminator** (例: `"card_pack_purchased"`) は infra に登場しない概念であり、**AsyncAPI codegen から定数として生成する**。subscriber が `ev.EventType != EventTypeCardPackPurchased` で検証する用途に充てる。

| 識別子 | 例 | SSoT |
|---|---|---|
| Topic 名 (物理) | `"card-pack-purchased"` | infra リポ (Terraform → ConfigMap → env var) |
| event_type (payload 内 discriminator) | `"card_pack_purchased"` | AsyncAPI codegen |
| Payload schema | `CardPackPurchasedEvent { ... }` | AsyncAPI codegen |

### 互換性チェック CI

OpenAPI / AsyncAPI spec の breaking change を機械的に検出するため、以下の CI ジョブを各サービスリポに追加する:

- `oasdiff` — OpenAPI spec の breaking change 検知
- `asyncapi diff` — AsyncAPI spec の breaking change 検知

`publish.yaml` の semantic version bump (patch / minor / major) は将来的にこれらの diff 結果から自動判定できる素地となるが、本 ADR では検知のみを導入し、判定は人手継続とする。

### fake / test helper の同梱

shop の `packages/api-shop/apishopfake/`, `packages/api-shop/apishopserverfake/` のように、各 Go パッケージ配下に **手書きの fake サブパッケージを同梱する方針を全リポへ展開する**。

- `apishopfake` 相当: in-memory broker / typed publisher / typed expecter
- `apishopserverfake` 相当: `httptest.Server` ラッパー (各エンドポイントの応答を `Fn` callback で制御可能)

これらは codegen 出力の型を import するが、**手書きのまま**とする。OpenAPI codegen の出力に fake は含まれないため、各リポで初回手書きしてその後継続保守する。

battle は現状 fake を持っていないため、本移行を機に追加する。

### ゲーム定数パッケージの取り扱い

ゲーム定数 (`game-logic-constants`, `game-design-constants`, `card-types`, `shop-constants`, `newsfeed-constants` 等) は API 契約ではなく **ゲームルールの不変定数** であり、OpenAPI / AsyncAPI のスキーマ表現に乗せにくい性質を持つ。本 ADR では以下のように扱う:

- **SSoT と codegen は本 ADR の対象外**: 現行の独自 YAML (`overload-party-common/data/`, `overload-party-battle/data/game_logic_constants.yaml`) + Python codegen (`overload-party-codegen-tools` および `overload-party-battle/scripts/generate_types.py`) を維持する。OpenAPI への移行は積極的に追求しない
- **配布方式は API 契約と同方針**: NuGet 配布チャンネルは廃止し、Go module / npm 配布は維持する。前述の「NuGet モジュール (廃止して ProjectReference 化)」が API 契約用 dotnet パッケージとゲーム定数用 dotnet パッケージの双方に等しく適用される

将来 SSoT/codegen 自体を見直す余地は残すが、本 ADR の scope では配布チャンネル整理のみ対象とする。

### 限界事項 / scope 外

- **Pub/Sub backend (Google Cloud Pub/Sub) のクライアント抽象化**: AsyncAPI binding を活用して publisher / subscriber コードまで自動生成するか、既存の Go SDK ラッパー (`internal/adapter/pubsub/`) を維持するかは本 ADR の対象外。当面はラッパー維持

## Consequences

### Positive

- **業界標準スキーマでの相互運用性**: OpenAPI / AsyncAPI に乗ることで、spec viewer (Swagger UI / Redoc / AsyncAPI Studio)、mock server (Prism)、contract test (Pact) 等の OSS エコシステムを活用できる
- **自前 codegen 保守からの撤退**: `overload-party-codegen-tools` および `battle/scripts/generate_types.py` の API 契約用途部分を廃止できる。oapi-codegen / NSwag / openapi-typescript / asyncapi-codegen はそれぞれデファクトであり、コミュニティ保守に委ねられる
- **NuGet 配布チャンネルの撤廃**: GitHub Packages の dotnet feed、`nuget.config`、`publish.yaml` の dotnet pack/push ステップ、CI 認証 (PAT 経由の NuGet feed 認証) が一斉に不要になる
- **domain と wire の独立進化**: 形状一致縛りが消えるため、wire に schema 進化フィールドを追加したり、domain で型を強くしたりが片方ずつ実施可能になる
- **Topic 名の三重管理解消**: infra → ConfigMap → env var の一系統に集約。app から定数が消える
- **client (TS) の契約源一元化**: web client が依存する型のうち API 契約由来のものは OpenAPI 派生に揃う
- **breaking change の機械検知**: oasdiff / asyncapi-diff により spec 進化のリスクが事前可視化される
- **C# server のみ生成**: battle の C# server は OpenAPI から DTO を生成するため、spec と実装の乖離リスクが低減する

### Negative

- **大規模リファクタ**: 全リポの `data/*.yaml` 再編 / codegen ツール置換 / packages/* の生成物入れ替え / publisher 経路への mapper 層追加 / NuGet 廃止に伴う battle 内 csproj の `<ProjectReference>` 化 / client の npm 依存切替が一斉に走る
- **互換性配慮を捨てる**: 本番稼働前の前提に立ち、`packages/api-*` の struct 名 / フィールド名 / module path を rename することを許容する。import 元 (gateway / card / account / client 等) も同 Phase で修正する
- **新ツールチェインへの習熟**: oapi-codegen / NSwag / openapi-typescript / asyncapi-codegen / oasdiff / asyncapi-diff の運用知識が CI 各所に必要になる
- **AsyncAPI Go codegen の成熟度**: OpenAPI における oapi-codegen と比べると AsyncAPI Go codegen のデファクト度合いは低い。spike で生成物を確認した上で採用判定する
- **fake の手書き継続**: codegen に含まれないため、各リポで初回手書きと継続保守を担う

### 緩和策

- **Phase 分けで進める** (リポ単位で独立に実施可能):
  - **Phase 1 (shop)**: `data/openapi.yaml` 作成 / wire 型を OpenAPI codegen 由来に切替 / domain → wire mapper 層導入 / `data/asyncapi.yaml` 作成 / Pub/Sub 型を AsyncAPI codegen 由来に切替 / Topic 名定数を env var 取得に変更 / oasdiff・asyncapi-diff CI 追加 / import 元 (card / account / gateway) の追従 PR
  - **Phase 2 (battle)**: `data/openapi.yaml` 作成 / wire 型を OpenAPI codegen 由来に切替 (Go + C# + TS) / NuGet 廃止 → 内部 csproj を `<ProjectReference>` 化 / `publish.yaml` から dotnet pack/push 削除 / `nuget.config` 撤去 / fake 新規追加 / import 元 (gateway / client) の追従 PR
  - **Phase 3 (その他サービス)**: account / card / scenario / gateway 等を順次同パターンで移行
- **各 Phase 内で旧生成物と新生成物の並走期間は設けない**: 本番稼働前であり互換性配慮不要のため、リポ単位で一気に切替える
- **AsyncAPI codegen は spike を先行**: Phase 1 着手前に shop 1 イベント分で生成物を確認し、`packages/api-shop` で許容できる出力スタイルかを判定。許容できない場合は自前 emitter (現 codegen-tools の Go emitter 流用) を一時併用する選択肢を残す
- **Pub/Sub の domain 型はリポ内手書きで残置**: shop の `internal/domain/shop_event_*_gen.go` は本 ADR で生成方式が変わる (codegen-tools → 手書き Go) が、ファイル位置と型名は据え置き、mapper 層導入の安全策とする

## 関連 issue

- TBD: ADR Accepted 後、Phase 1 (shop) / Phase 2 (battle) / Phase 3 (その他) の各リポに移行 issue を起票し、本 ADR 冒頭の Related に追記する
