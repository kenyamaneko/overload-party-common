# ADR-034: 外部 API 契約 SSoT を OpenAPI / AsyncAPI に統一し、配布物を Go / npm モジュールに集約する

## ステータス

Accepted (2026-05-09)。末尾の Amendment 3 件 (2026-05-09: Cloudsmith 配布・WS-AsyncAPI・client scope / 2026-05-10: 廃止 npm の特定とゲーム定数分類の訂正 / 2026-05-13: REST endpoint path の生成 client 化と operationId の扱い) を含めて現行方針とする

## 結論

独自 YAML + 自前 codegen による API 契約管理を業界標準に載せ替えるため、**外部公開 API 契約の SSoT を業界標準仕様 (OpenAPI 3.x / AsyncAPI 3.0) に統一し、配布物を Go モジュール (および必要に応じ npm モジュール) に集約する。NuGet と npm の cross-repo 配布チャンネルは GitHub Packages から Cloudsmith に切替え、battle 内の intra-repo self-NuGet は ProjectReference 化で廃止する。** spec viewer / mock server / contract test 等の OSS エコシステムが使えるようになり、自前 codegen (`overload-party-codegen-tools` / battle の `generate_types.py`) の API 契約用途保守から撤退できる。GitHub Packages の User-owned packages 制約による PAT 依存は Cloudsmith の OIDC 認証で解消し、domain と wire は独立進化が可能になり、Topic 名の三重管理は infra 一系統に集約される。breaking change は oasdiff / asyncapi-diff で機械検知される。

## 背景・課題

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

## 詳細

### 適用範囲

本 ADR の **OpenAPI / AsyncAPI 移行**は overload-party 配下の全サービスリポの **外部公開 API 契約**を対象とする。具体的には:

- REST エンドポイント (path / method / request / response / errors): OpenAPI 3.x
- wire 型 (request body / response body / webhook payload): OpenAPI 3.x の `components/schemas`
- Pub/Sub イベント (channel / message / payload schema / `event_type` discriminator): AsyncAPI 3.0
- **WebSocket プロトコル** (gateway ↔ client、battle 由来のゲーム状態フレーム等): **AsyncAPI 3.0 の WebSocket binding** で表現する。OpenAPI は WS を表現できないため AsyncAPI 側に寄せる。`gateway/data/ws_constants.yaml` のメッセージ型集合や `battle/packages/game-state-*/` のフレーム payload はこの一環として AsyncAPI に移行
- 上記に登場する **外部に流出する enum** (例: `Platform = "ios" | "android"`, `ProductType = "faction_set" | ...`)
- **client (overload-party-client) の npm 依存全般** も本 ADR の scope。`@kenyamaneko/*` 名前空間の npm パッケージは GitHub Packages から Cloudsmith に切替え、生成元 spec が OpenAPI/AsyncAPI に変わる場合は併せて追従

対象外 (本 ADR では現行構造を据え置く):

- 内部 domain 型 / 内部完結 enum (例: `SubscriptionStatus` の状態機械)
- ゲーム設計 / ゲームロジック定数 (`game-design-constants`, `game-logic-constants`): 性質が API 契約ではなく不変ルール定数であるため、別系統の SSoT + codegen を維持

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
- module path / package 名・公開型名は OpenAPI / AsyncAPI codegen 出力をそのまま採用する。**bit-identical な互換性は要件としない**: 本番稼働前のため、import 元の rename / リファクタは同 Phase の PR で対応する
- `publish.yaml` (semantic version tagging) は据え置く

#### npm モジュール (web/mobile 向け二次配布物)

- 既存 `packages/game-state-npm` の役割は `data/openapi.yaml` から `openapi-typescript` で生成する `packages/api-{service}-ts` 等に置き換える
- client が現在依存している 6 つの `@kenyamaneko/*` npm パッケージのうち、API 契約由来のものは本移行で OpenAPI 由来生成に置換する。分類の確定は末尾の Amendment (2026-05-10) を参照

#### NuGet / npm 配布 (intra-repo は ProjectReference 化、cross-repo は Cloudsmith に移行)

dotnet と npm の cross-repo 配布チャンネルを **GitHub Packages から Cloudsmith に全面移行**する。あわせて intra-repo の self-NuGet (battle が自リポを自リポに NuGet で配るパターン) は ProjectReference 化で廃止する。

レジストリ選定の経緯 (NuGet 完全廃止案 → AR 一本化案 → Cloudsmith) は末尾の Amendment (2026-05-09) を参照。

動機として、GitHub Packages には構造的な認証問題がある:

- kenyamaneko は **User account** であり、user-owned packages は **GitHub App token で読めない** (ADR-033 限界事項として記載済み)
- 結果として NuGet feed の認証は PAT 必須で、ADR-033 で全廃した PAT 運用パターンに逆戻りしていた
- `dotnet add package` には User-owned NuGet feed の限界が無いため、レジストリ側を切り替えれば PAT を全廃できる

Cloudsmith の特徴:

- SaaS package registry で 28 format に対応 (NuGet / npm / Docker / Maven / Python / Go 等)
- 認証は OIDC native で、**GitHub Actions から PAT 不要で short-lived token を取得**できる
- public repository として運用すれば Cloudsmith Free (Core) tier の範囲 (storage 500MB / delivery 1GB/月) で賄える見込み
- ストレージ region は `sg-singapore` (日本から最寄り)

##### intra-repo: ProjectReference 化 (battle 内 self-NuGet を廃止)

battle が自リポ内の `packages/*-dotnet/` を NuGet 経由で自分自身に参照しているのは無意味。sln 内ローカル参照に置換する:

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

##### cross-repo: Cloudsmith に切替 (NuGet と npm 双方)

cross-repo の dotnet / npm 依存 (例: battle が common の `OverloadParty.GameDesignConstants` を消費、client が common / battle / shop 等の `@kenyamaneko/*` npm パッケージを消費) は Cloudsmith を経由する:

```
[Publisher リポ]
  └─ CI: Cloudsmith OIDC で token 取得 → dotnet nuget push / npm publish to Cloudsmith

[Consumer リポ]
  └─ CI: Cloudsmith OIDC で token 取得 → nuget.config / .npmrc を Cloudsmith endpoint に向け restore/install
```

実装上の方針:

- Cloudsmith リソースを `overload-party-infra` の Terraform module (`providers/cloudsmith/`) でプロビジョン (NuGet repo / npm repo / 必要に応じ Go repo)。Google Cloud リソース専用の `providers/google-cloud/` とは別ディレクトリで分離管理する
- Cloudsmith service account と OIDC trust を整備し、publisher 用 (write) と consumer 用 (read) を分離 (`overload-party-publisher` / `overload-party-reader`)。OIDC trust scope は per-repo の明示リストで限定する
- `overload-party-common` に `setup-cloudsmith-auth` および `publish-to-cloudsmith` の **共通 composite action** を追加 (ADR-033 の `setup-go-private-modules` と同パターン)。各リポはこの composite を import するだけで Cloudsmith 認証が完了する
- `nuget.config` は **Cloudsmith endpoint (`https://nuget.cloudsmith.io/keyandnotes/overload-party-nuget/v3/index.json`) を指す形に書き換え** (撤去ではない)。`.npmrc` も同様に `https://npm.cloudsmith.io/keyandnotes/overload-party-npm/` を指す
- 認証 PAT (`COMMON_PKG_FETCH` 等) は **全廃**。OIDC が代替

廃止される認証経路 / 撤去されるもの:

- 各リポの `nuget.config` における `https://nuget.pkg.github.com/kenyamaneko/...` フィード設定
- `.github/workflows/*.yaml` における GitHub Packages の dotnet/npm 認証ステップ (`actions/setup-dotnet` の `nuget-auth-token` パラメタ等)
- 各リポの `.github/scripts/` 配下にある GitHub Packages 向け auth wrapper
- `COMMON_PKG_FETCH` などパッケージ取得用 PAT (organization secret / vars)

##### Go module の扱い

Go module は ADR-033 で `setup-go-private-modules` composite action 経由の App token 認証が確立済みで、現状で破綻していない。本 ADR 改訂の **Cloudsmith 移行は Go については任意 (将来的選択肢として残す)**。Go module だけ GitHub の git protocol で引き続き ADR-033 経路を使ってよい。

##### C# 側 csproj とソースの所在は不変

`packages/*-dotnet/` のディレクトリ・csproj 構成は維持。発行先が GitHub Packages から Cloudsmith に変わるだけで、C# 側からの consumption 体験 (`<PackageReference>` で書く) は変わらない。

API 契約用の `packages/api-{service}-dotnet/` のソース生成は OpenAPI (NSwag) に切替、ゲーム定数用の `packages/game-*-constants-dotnet/` は現行 codegen を維持する。

### domain 型と wire 型の形状一致前提を取らない

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

Pub/Sub の domain 型はリポ内手書きで残置する: shop の `internal/domain/shop_event_*_gen.go` は本 ADR で生成方式が変わる (codegen-tools → 手書き Go) が、ファイル位置と型名は据え置き、presenter 層導入の安全策とする。

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

- `oasdiff`: OpenAPI spec の breaking change 検知
- `asyncapi diff`: AsyncAPI spec の breaking change 検知

`publish.yaml` の semantic version bump (patch / minor / major) は将来的にこれらの diff 結果から自動判定できる素地となるが、本 ADR では検知のみを導入し、判定は人手継続とする。

### fake / test helper の同梱

shop の `packages/api-shop/apishopfake/`, `packages/api-shop/apishopserverfake/` のように、各 Go パッケージ配下に **手書きの fake サブパッケージを同梱する方針を全リポへ展開する**。

- `apishopfake` 相当: in-memory broker / typed publisher / typed expecter
- `apishopserverfake` 相当: `httptest.Server` ラッパー (各エンドポイントの応答を `Fn` callback で制御可能)

これらは codegen 出力の型を import するが、**手書きのまま**とする。OpenAPI codegen の出力に fake は含まれないため、各リポで初回手書きしてその後継続保守する。battle は現状 fake を持っていないため、本移行を機に追加する。

### ゲーム定数パッケージの取り扱い

ゲーム定数 (`game-logic-constants`, `game-design-constants` 等) は API 契約ではなく **ゲームルールの不変定数** であり、OpenAPI / AsyncAPI のスキーマ表現に乗せにくい性質を持つ。本 ADR では以下のように扱う (パッケージの分類は末尾 Amendment 2026-05-10 で訂正あり):

- **SSoT と codegen は本 ADR の対象外**: 現行の独自 YAML (`overload-party-common/data/`, `overload-party-battle/data/game_logic_constants.yaml`) + Python codegen (`overload-party-codegen-tools` および `overload-party-battle/scripts/generate_types.py`) を維持する。OpenAPI への移行は積極的に追求しない
- **配布方式は API 契約と同方針**: NuGet 配布チャンネルの整理 (intra-repo は ProjectReference 化、cross-repo は Cloudsmith) が API 契約用 dotnet パッケージとゲーム定数用 dotnet パッケージの双方に等しく適用される

将来 SSoT/codegen 自体を見直す余地は残すが、本 ADR の scope では配布チャンネル整理のみ対象とする。

### 移行の進め方

リポ単位で独立に Phase 分けして進める:

- **Phase 1 (shop)**: `data/openapi.yaml` 作成 / wire 型を OpenAPI codegen 由来に切替 / domain → wire presenter 層導入 / `data/asyncapi.yaml` 作成 / Pub/Sub 型を AsyncAPI codegen 由来に切替 / Topic 名定数を env var 取得に変更 / oasdiff・asyncapi-diff CI 追加 / import 元 (card / account / gateway) の追従 PR
- **Phase 2 (battle)**: `data/openapi.yaml` 作成 / wire 型を OpenAPI codegen 由来に切替 (Go + C# + TS) / intra-repo NuGet を `<ProjectReference>` 化 / cross-repo NuGet と npm の publish 先を Cloudsmith に切替 (`publish.yaml` 改修 + `nuget.config` / `.npmrc` を Cloudsmith endpoint に書き換え) / fake 新規追加 / import 元 (gateway / client) の追従 PR
- **Phase 3 (その他サービス)**: account / card / scenario / gateway 等を順次同パターンで移行

各 Phase 内で旧生成物と新生成物の並走期間は設けない (本番稼働前であり互換性配慮不要のため、リポ単位で一気に切替える)。AsyncAPI codegen は Phase 1 着手前に shop 1 イベント分で spike し、`packages/api-shop` で許容できる出力スタイルかを判定する (許容できない場合は自前 emitter を一時併用する選択肢を残す)。

### 限界事項 / scope 外

- **Pub/Sub backend (Cloud Pub/Sub) のクライアント抽象化**: AsyncAPI binding を活用して publisher / subscriber コードまで自動生成するか、既存の Go SDK ラッパー (`internal/adapter/pubsub/`) を維持するかは本 ADR の対象外。当面はラッパー維持

### トレードオフ

- **大規模リファクタ**: 全リポの `data/*.yaml` 再編 / codegen ツール置換 / packages/* の生成物入れ替え / publisher 経路への presenter 層追加 / NuGet 廃止に伴う battle 内 csproj の `<ProjectReference>` 化 / client の npm 依存切替が一斉に走る
- **互換性配慮を捨てる**: 本番稼働前の前提に立ち、`packages/api-*` の struct 名 / フィールド名 / module path を rename することを許容する。import 元 (gateway / card / account / client 等) も同 Phase で修正する
- **新ツールチェインへの習熟**: oapi-codegen / NSwag / openapi-typescript / asyncapi-codegen / oasdiff / asyncapi-diff の運用知識が CI 各所に必要になる
- **AsyncAPI Go codegen の成熟度**: OpenAPI における oapi-codegen と比べると AsyncAPI Go codegen のデファクト度合いは低い。spike で生成物を確認した上で採用判定する
- **fake の手書き継続**: codegen に含まれないため、各リポで初回手書きと継続保守を担う

## Amendment: 2026-05-09 Cloudsmith 配布 / WS-AsyncAPI / client scope

本 Amendment では以下の 3 点を追加する (いずれも本文各セクションに反映済み):

1. **NuGet / npm の cross-repo 配布チャンネルを Cloudsmith に切替** (本文「NuGet / npm 配布」)。GitHub Packages 経由の dotnet/npm 配布を全廃する
2. **WebSocket プロトコルは AsyncAPI 3.0 で記述** (本文「適用範囲」)。OpenAPI は WS を扱えない。`gateway/data/ws_constants.yaml` および `battle/packages/game-state-*/` の WS payload schemas は Phase 2/3b で AsyncAPI に移行する
3. **client (overload-party-client) を本 ADR scope に正式に組み込む** (本文「適用範囲」)。`@kenyamaneko/*` の 6 npm パッケージを GitHub Packages から Cloudsmith に切替、AsyncAPI/OpenAPI 由来の生成物に追従させる

### 経緯 (NuGet 完全廃止案 → AR 一本化案 → Cloudsmith)

初版 ADR-034 (NuGet 完全廃止) → 中間案 (Artifact Registry に一本化) → 最終案 (Cloudsmith) へと判断が変遷した。両中間判断とも稼働には至っていないが、再検討時の参照のため経緯を残す。

#### 中間判断: cross-repo dotnet 依存の発覚で「NuGet 完全廃止」を撤回

shop Phase 1 完了後、battle Phase 2 で **cross-repo dotnet 依存** (battle の C# csproj が `overload-party-common/packages/game-design-constants-dotnet/` を NuGet 経由で消費) という、shop では遭遇しなかったケースが顕在化した。初版の「NuGet 完全廃止 + ProjectReference 化」方針は intra-repo の self-NuGet を念頭に置いた論拠で、cross-repo dotnet には適用できないことが判明。配布チャンネル自体を再検討する必要が生じた。

#### 中間判断: Artifact Registry 一本化案 (採用に至らず)

GitHub Packages の User-owned packages 制約 (App token で読めない / PAT 必須) を回避し、かつ Google Cloud を既に本番インフラとして利用している点から、Google Cloud Artifact Registry (AR) を NuGet / npm の cross-repo 配布チャンネルに一本化する案を一度採用した。WIF (Workload Identity Federation) で short-lived token を取得して PAT を全廃する構想だった。

#### 最終判断: AR が NuGet 未対応のため Cloudsmith に変更

`overload-party-infra` で AR プロビジョン作業 ([overload-party-infra#22](https://github.com/kenyamaneko/overload-party-infra/issues/22)) を開始したところ、**Google Cloud Artifact Registry が NuGet を native format としてサポートしていない**ことが判明した:

- AR がサポートする format は `DOCKER / MAVEN / NPM / PYTHON / APT / YUM / GENERIC / GO / KFP` の 9 種類のみ
- NuGet は 2021 年から open feature request 状態 ([Google Issue Tracker #180810242](https://issuetracker.google.com/issues/180810242))。2026-05 時点で未実装
- GENERIC format に .nupkg を置くワークアラウンドは、NuGet client (`dotnet add package` / `dotnet restore`) が V2/V3 protocol を喋れず読めないため成立しない (CLAUDE.md「ワークアラウンド禁止」にも抵触)

つまり「言語横断で同一機構」という AR 一本化の前提は npm では成立するが NuGet では成立せず、技術的に不可能。代わりに 28 format 対応かつ OIDC native の SaaS である **Cloudsmith** を採用した (AR は本 ADR scope の NuGet/npm 配布用途では採用しない。Docker container image など他用途は別話)。

### 影響を受ける既存決定 / 撤回

- (初版の) 「NuGet 完全廃止」 → 「intra-repo self-NuGet は ProjectReference 化、cross-repo は Cloudsmith 経由」に絞り直し
- (初版の) 「nuget.config 撤去」 → 「Cloudsmith endpoint を指す形に書き換え」に変更
- (初版の) 「NuGet 認証 PAT (`COMMON_PKG_FETCH`) revoke」 → 引き続き revoke (代替が Cloudsmith OIDC になっただけで方針は維持)

### 必要な前提作業

Phase 2 / Phase 3b 着手前に以下が完了している必要がある:

- `overload-party-infra` で Cloudsmith リソースを Terraform プロビジョン (NuGet repo + npm repo + service account + OIDC trust)。管理ディレクトリは `providers/cloudsmith/`
- `overload-party-common` に `setup-cloudsmith-auth` / `publish-to-cloudsmith` 共通 composite action を追加
- 各 publisher リポ (common / battle / shop / 各サービス) の publish workflow を Cloudsmith 向けに書き換え

### コスト・運用上の留意点

- Cloudsmith Free (Core) tier: storage 500MB / delivery 1GB/月 (overage なし、超過で停止)
- Pro plan: $89/月 (overage $1.50/GB)
- 本プロジェクトでは **public repository** として運用する (overload-party の source code が GitHub 公開のため、package を private にする必然性が薄く、Free tier で運用可能)
- storage region は `sg-singapore` (日本から最寄り)

## Amendment: 2026-05-10 廃止 npm の特定とゲーム定数分類の訂正

Phase 3b 着手時に各 npm パッケージの中身を実調査した結果、初版で「ゲーム定数」(本 ADR scope 外) として扱っていた 3 つのパッケージが **API レスポンス型 / enum** であり、Layer A (API 契約由来) として廃止対象であることが判明した。

| パッケージ | 中身 | 真の性質 |
|---|---|---|
| `shop-constants` | `ProductType` (3 値の enum) | shop API レスポンス型 |
| `card-types` | `CardDefinition` / `CardStats` (`ComputeStats \| DataStats`) / `NpcModel` / Effect 系 | card / battle API レスポンス型 |
| `newsfeed-constants` | `CloudNewsSource` (5 値の enum) | newsfeed API レスポンス型 |

### client 依存の分類 (確定)

| 分類 | 性質 | 依存先 |
|---|---|---|
| **A. API 契約由来型** | サービス公開型 (REST レスポンス / 一般 WS event) | 廃止対象。置換先は別 ADR で確定する |
| **B. battle 特殊例外** | バトル描画ドメイン型 (`BattleStartEventData` / `ClientGameState` 等) | `@kenyamaneko/overload-party-game-state` (battle 由来) を直接消費維持 |
| **C. ゲームルール定数** | 不変ルール定数 (`Faction` / `Phase` / `WinReason` 等) | `@kenyamaneko/overload-party-game-design-constants` (common) / `@kenyamaneko/overload-party-game-logic-constants` (battle) を直接消費維持 |

廃止対象 (Layer A 再分類):

- `@kenyamaneko/overload-party-shop-constants`
- `@kenyamaneko/overload-party-card-types`
- `@kenyamaneko/overload-party-newsfeed-constants`

### 初版記述の更新

初版の以下の記述を本 Amendment で更新する:

> client が現在依存している 6 つの `@kenyamaneko/*` npm パッケージのうち、API 契約由来のものは本移行で OpenAPI 由来生成に置換する。ゲーム定数由来 (`game-design-constants`, `game-logic-constants`) は据え置き

→ Layer A / B / C への分類は上記表の通り。**Layer A の置換先 (gateway 集約 vs 各サービス TS 直接) と gateway の責務範囲は別 ADR で確定する** (本 ADR の scope ではない)。

### 本 ADR の scope 外として別 ADR に持ち越す事項

- gateway の責務再定義 (完全パススルー化、加工ロジックの逃し先、認証・WS hub・gateway 内部状態保持機能 [auth_handler / spectate_handler / static_handler] の維持範囲)
- 各サービスの「client 公開 API」整備方針 (現在の openapi が gateway 内部用に最適化されているため、client 公開には型変換 / フィールドリネーム / 検証等が gateway で発生している)
- Layer A の置換先確定 (gateway openapi 集約 / 各サービス TS パッケージ直接 / ハイブリッド)
- 各サービスの TS パッケージ (`packages/api-{service}-npm`) 整備の有無

これらは互いに影響するため一つの別 ADR でまとめて扱う。

## Amendment: 2026-05-13 REST endpoint path を生成 client 由来に切替、operationId を consumer API 表面の識別子として扱う

`rules/principles.md` の「アプリ間の契約 (エンドポイント・イベント名・ヘッダ名) はリテラルで書かず、所有サービスが発行する API 契約パッケージを参照する」は wire 型 (schemas) には適用されているが、**REST endpoint path** には未適用であることが棚卸しで判明した ([overload-party-common#91](https://github.com/kenyamaneko/overload-party-common/issues/91))。全 api-* の `openapi-codegen.yaml` が `generate.models: true` のみで、path 定数も typed client も生成されていなかった結果、consumer (gateway/* clients、scenario/internal/adapter/http/* 等) が path をリテラルで直書きする状態になっていた。

### 決定

各サービスの `packages/api-{service}/openapi-codegen.yaml` に **`generate.client: true` を追加**し、oapi-codegen が生成する **typed client (`*ClientWithResponses`)** を export する。consumer 側は API 契約パッケージの生成 client を経由してエンドポイントにアクセスし、path をリテラル文字列で書かない。

### 配置: サービス側に SDK サブパッケージ、consumer 側は port impl 委譲のみ

oapi-codegen が生成する `*Response` 型は、OpenAPI spec で schema が付いている response にだけ `JSON{200,201,...}` フィールドを生やす。本プロジェクトの 4xx response は説明文 (`description`) のみで schema を持たないため、生成 client の戻り値からは status code と raw body しか読めない (例: [overload-party-account/data/openapi.yaml:189-199](https://github.com/kenyamaneko/overload-party-account/blob/main/data/openapi.yaml#L189-L199))。

この status code 解釈ロジック (例: `404 → ErrNotFound`, `400 → ErrDeckInvalid`) を consumer 側 adapter で書くと、各 consumer (gateway / scenario / future consumers) で同等のロジックが重複する。加えて gateway を薄く保つ ADR-036 の方針とも反する。

これを避けるため、**ラッパの責務を分解してサービス側と consumer 側に再配置**する:

| 責務 | 配置 | 理由 |
|---|---|---|
| status code → sentinel error 変換 | サービス側 (`packages/api-{service}/api{service}client/`) | wire 契約由来 (404 = not found は OpenAPI spec が定義する意味)。サービス側で 1 回書けば全 consumer が再利用 |
| port インタフェース実装 | consumer 側 (`internal/adapter/http/<service>client.go`) | port は consumer 内部の clean architecture 概念 (consumer ごとに port 形状が異なる) |

#### サービス側: SDK サブパッケージ (`api{service}client/`)

各 API 契約パッケージは既存の `api{service}serverfake/` と並べて `api{service}client/` サブパッケージを同梱する。これは AWS SDK / Stripe SDK 等で一般的な「公式 client SDK」pattern と同型。

- 内部で生成 `*ClientWithResponses` をラップする
- 各 endpoint method を operationId 由来 method 名で公開し、戻り値は wire 型 (`*apicard.Deck` 等)
- status code を sentinel error に変換 (例: `apicardclient.ErrNotFound`, `ErrUnauthorized`, `ErrForbidden`, `ErrDeckInvalid`) し、sentinel は SDK サブパッケージ自身で export
- `WithHTTPClient` / `WithRequestEditorFn` の Option pattern を提供 (InternalAuth 注入は `WithRequestEditorFn(internalauth.SignRequest)` で 1 行)

#### consumer 側: port impl は委譲のみ (`internal/adapter/http/<service>client.go`)

consumer adapter は port インタフェースを実装し、SDK method に **委譲するだけ** に痩せる:

```go
type CardClient struct{ api *apicardclient.Client }

func (c *CardClient) GetDeck(ctx context.Context, deckID int64) (*apicard.Deck, []apicard.DeckCard, error) {
    return c.api.GetDeck(ctx, deckID)
}
```

- 生成 client / status code 解釈に触れるのは SDK 内部のみ。consumer adapter は wire 型と sentinel error をそのまま port 層に通す
- service 層 (`internal/usecase/`) は port インタフェースのみを参照し、生成 client 型 / SDK 型を一切 import しない (clean architecture の依存方向を維持)
- gateway adapter から HTTP 組み立てロジックが消え、ADR-036 の「gateway 薄く保つ」方針と整合する

### operationId を consumer API 表面の識別子として扱う

OpenAPI 3.x の `operationId` は operation を一意識別する optional フィールドで、HTTP プロトコル上には登場しない。OpenAPI 仕様自身が `operationId` の用途として「Tools and libraries MAY use the operationId to uniquely identify an operation」と明示しており、oapi-codegen / openapi-generator / NSwag 等の主要 codegen は揃って **生成 client のメソッド名** のソースとして使う (`operationId: getDeck` → `(c *Client) GetDeck(ctx, ...)`)。本プロジェクトでは全 api-* の全 endpoint で operationId が既に定義されており、本 Amendment 採用にあたり追加整備は不要。

本 Amendment 採用前は path 文字列が consumer のコードに直接書かれていたため、operationId は server 内部の識別子に過ぎなかった。**採用後は path が生成 client の関数本体に隠蔽される代わりに、operationId が consumer のコードに焼き付く** (consumer は `client.GetDeck(ctx, deckId)` のようにメソッド名で呼び出す)。このため operationId の rename / 削除は consumer 全リポのビルドを壊す変更となる:

- operationId の追加: 後方互換 (consumer は新メソッドを使い始められるだけ)
- operationId の削除: breaking (consumer のメソッド呼び出しが解決しなくなる)
- operationId の rename: breaking (同上)

なお、これは HTTP wire 契約 (path / method / payload schema / status code) とは別軸の **consumer API 表面 (compile-time contract)** の話である。runtime の HTTP 契約自体の SSoT は OpenAPI の `paths` フィールドであり、operationId とは独立に管理する。

破壊判定は `oasdiff` の standard rule では検出されないため、PR レビューで運用判断する。

### 適用順序

- **pilot: card** ([overload-party-common#91](https://github.com/kenyamaneko/overload-party-common/issues/91) 内で進捗管理)
  - caller が gateway/cardclient のみで完結し、ADR-037 の展開と独立
  - endpoint 11 件で pilot として効果検証に十分な量
- **横展開**: pilot 完了後に shop / account / scenario / matchmaking / news / battle / support / gateway を順次同パターンで適用。横展開フェーズで並走規模が大きくなる場合は別途トラッカー issue を切る

### OpenAPI schema 命名の制約（oapi-codegen 生成型との衝突回避）

`generate.client: true` を有効にすると oapi-codegen は operationId を起点に以下の予約名を Go の同パッケージ内に生成する:

- `<OperationIdPascal>Response`: typed wrapper (ClientWithResponses の戻り値)
- `<OperationIdPascal>JSONRequestBody`: request body の型エイリアス
- `<OperationIdPascal>Params`: query / header / path params の構造体

`components/schemas/` の名前がこれら予約名のいずれかと **完全一致** すると Go パッケージ内で型名衝突しビルドが失敗する (実例: support の `components/schemas/SubmitInquiryResponse` ↔ wrapper `SubmitInquiryResponse` で `operationId: submitInquiry`)。

ルール (本 Amendment 以降の新規 schema に適用):

1. schema 名は **resource を表す名詞** (`Deck`, `Inquiry`, `Player` 等) を中心とする
2. 以下 4 つの suffix は schema 名に使わない (oapi-codegen wrapper 専用予約):
   - `<X>Response`
   - `<X>RequestBody`
   - `<X>JSONRequestBody`
   - `<X>Params`
3. request / response 型に動詞ニュアンスを残したい場合は `<Resource>Detail` / `<Resource>Result` / `<Resource>Submission` など `Response` / `Request` / `Params` を含まない suffix で表現する
4. 既存 schema は本 Amendment 適用日 (2026-05-13) 以降の改名・新設のみに適用し、衝突していない既存 schema は据え置く
5. 既存で実際に衝突している schema は本 Amendment 適用時に rename する (support の `SubmitInquiryResponse` 等)

衝突回避手段として `x-go-name` で Go 型名だけを別名にする方法もあるが、spec と Go 表現が乖離して可読性を損ねるため spec 側の rename を優先する。

### イベント名 / ヘッダ名の扱い

本 Amendment は **REST endpoint path のみ**を対象とする。principles の「契約リテラル禁止」の残る 2 項は以下のとおり別経路で扱う:

- **イベント名 (Pub/Sub `event_type` discriminator)**: 既に AsyncAPI codegen 由来で定数化済み (本文「Topic 名と event_type の取り扱い」参照)。本 Amendment 範囲外
- **ヘッダ名 (`X-OP-Internal-Auth` 等)**: ADR-039 の `internalauth-go` で定数化済み (RequestEditorFn 経由で header 注入する接続点)。各リポの実装が当該定数を参照しているかは pilot 横展開時に併せて棚卸しする
