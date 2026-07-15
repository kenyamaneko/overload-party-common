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

## Amendment: 2026-05-09 Cloudsmith 配布 / WS-AsyncAPI / client scope

本 Amendment では以下の 3 点を追加する:

1. **NuGet / npm の cross-repo 配布チャンネルを Cloudsmith に切替**。GitHub Packages 経由の dotnet/npm 配布を全廃する
2. **WebSocket プロトコルは AsyncAPI 3.0 で記述**。OpenAPI は WS を扱えない。`gateway/data/ws_constants.yaml` および `battle/packages/game-state-*/` の WS payload schemas は Phase 2/3b で AsyncAPI に移行する
3. **client (overload-party-client) を本 ADR scope に正式に組み込む**。`@kenyamaneko/*` の 6 npm パッケージを GitHub Packages から Cloudsmith に切替、AsyncAPI/OpenAPI 由来の生成物に追従させる

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

### typed client の生成と export

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

- **イベント名 (Pub/Sub `event_type` discriminator)**: 既に AsyncAPI codegen 由来で定数化済み。本 Amendment 範囲外
- **ヘッダ名 (`X-OP-Internal-Auth` 等)**: ADR-039 の `internalauth-go` で定数化済み (RequestEditorFn 経由で header 注入する接続点)。各リポの実装が当該定数を参照しているかは pilot 横展開時に併せて棚卸しする
