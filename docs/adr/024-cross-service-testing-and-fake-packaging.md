# ADR-024: サービス間結合テスト戦略とテストダブルのパッケージ同梱

## ステータス

Accepted (2026-04-22)

## 結論

サービス間結合検証の空白を埋めるため、テストピラミッドの語彙定義・**送信側パッケージへのテストダブル同梱**・**nightly cloud integration** の 3 点を採用する。[ADR-015](015-package-split.md) の「送信側所有」原則がテストダブル層にも一貫して適用され、契約変更時の consumer 側追従が import 更新だけで済む。テストの所有権が各サービス repo に閉じて「落ちたテストを誰が直すか」が自明になり、「アダプターテスト」と「サービス間結合テスト」の語彙分離により「このテストは何を証明しているか」が会話の前提として揃う。emulator / 本番の乖離は nightly cloud integration で継続的に検知され、build tag / CI ジョブ分離により unit ジョブが Docker 非依存になる。

## 背景・課題

[ADR-016](016-repository-testing-testcontainers.md) でリポジトリ層（DB 境界）のテスト戦略は決まったが、**サービス間** の結合テストをどこでどう書くかは未定義のまま各サービスが独自に進めている。現時点で次のばらつきが発生している：

- `overload-party-shop`: Pub/Sub emulator + Testcontainers + `//go:build integration` タグの運用が成熟しつつある
- `overload-party-account` / `overload-party-news` / `overload-party-scenario`: `integration` build tag 運用あり、CI でジョブ分離している
- `overload-party-card` / `overload-party-gateway` / `overload-party-matchmaking` / `overload-party-support`: 統合テストと単体テストが同一ジョブ・同一タグ空間に混在している
- `overload-party-battle` (C#): 言語差のため Go 側と別建ての整備が必要
- テストダブル（mock / fake）は各サービスが手書きしており、送信側サービスが型定義を所有する [ADR-015](015-package-split.md) の原則に沿った「fake も送信側が配布」という状態になっていない

また [ADR-016](016-repository-testing-testcontainers.md) は **Cloud SQL と同じ DB エンジンで検証する** ことを決めたが、「本物の Cloud SQL / 本物の Firestore / 本物の Cloud Pub/Sub」に対する検証は CI 経路に存在しない。emulator / Testcontainers と本番の乖離（Firestore インデックス要求、Cloud SQL 接続プール設定、Pub/Sub Exactly-Once 配信の挙動等）は手動動作確認に依存している。

さらに `overload-party-e2e` は空で実装されておらず、サービス横断のテストは事実上 E2E 層にも統合テスト層にも存在しない。**サービス間結合検証の空白を埋める設計判断** が必要である。

## 制約

- [ADR-015](015-package-split.md) の「送信側サービスが型を所有」原則との整合（fake もこの原則を拡張する）
- サービス単位でテストの所有権を閉じる（落ちたテストの担当が自明であること）
- ローカルで `go test ./...` / `dotnet test` / `pytest` 一発が継続できること（[ADR-016](016-repository-testing-testcontainers.md) 維持）
- emulator / fake と本番実装の乖離を CI で継続的に検知できること
- 新サービスを追加するときのテスト基盤立ち上げコストが低いこと

## 詳細

### 1. テストピラミッドと用語定義

従来「統合テスト」「結合テスト」と呼ばれていた範囲を、**検証対象が "外部インフラ境界" か "他サービスの契約" か** で明確に区別する。両者は同一テストファイル内で重なることもあるが、**"何を証明しようとしているか"** を表す語彙として分離する。

| 層 | 名称 | 目的 | 外部依存 | タグ / マーカー | 実行頻度 |
|---|---|---|---|---|---|
| 1 | **単体テスト** (unit) | 関数・ユースケース単位のロジック検証 | すべてテストダブル | タグなし | 毎 PR / ローカル常時 |
| 2 | **アダプターテスト** (adapter) | DB / Pub/Sub / 外部 HTTP 等、**クリーンアーキテクチャの adapter 層と外部インフラとの境界** | 本物のインフラ (Testcontainers / emulator) | `integration` | 毎 PR |
| 3 | **サービス間結合テスト** (inter-service) | 他サービスの契約を自サービスが正しく扱えるか | 送信側 fake。必要に応じて adapter 層と併用 | `integration` | 毎 PR |
| 4 | **クラウド検証テスト** (cloud-verified) | emulator / fake と本番実装の乖離検出 | 本物の Cloud SQL / Firestore / Cloud Pub/Sub (stg) | `cloud_integration` | nightly |
| 5 | **E2E** | クライアント視点の end-to-end フロー | 全サービス起動 | `overload-party-e2e` リポで実行 | nightly or on-demand |

Go では `//go:build` タグ、C# では xUnit Trait、Python では pytest マーカーで識別する。アダプターテスト (2) とサービス間結合テスト (3) は build tag を**共通で `integration`** とする（CI ジョブ分離のコストと投資対効果の観点で分ける価値が薄い）。両者の区別は**テストファイルのディレクトリ配置とレビュー時の語彙**で維持する。

#### 名称の位置づけ

- **アダプターテスト**: プロジェクト共通のクリーンアーキテクチャ用語（CLAUDE.md 参照）である "adapter" に揃えた呼称。DB 境界 (repository)、Pub/Sub 境界 (pubsub adapter)、外部 HTTP クライアント境界のいずれも adapter 層に該当する。[ADR-016](016-repository-testing-testcontainers.md) の「リポジトリ層テスト」は本名称のうち **DB 境界を扱うサブセット** として位置づけ直される（ADR-016 の方針自体は変更せず、テストコード自体にも変更は生じない）
- **サービス間結合テスト**: 送信側 fake を使って「他サービスの契約を自サービスがどう扱うか」を検証するテスト。subscriber テスト、REST クライアント呼び出しテスト等が該当する。fake は [ADR-015](015-package-split.md) の送信側所有原則に従って送信側パッケージから配布される（§2 参照）
- **クラウド検証テスト**: emulator / fake では検出できない、本番インフラ固有の挙動（Firestore インデックス要求、Cloud SQL 接続プール、Pub/Sub Exactly-Once 等）を検知する smoke テスト
- **E2E**: **クライアント動線のみ** を対象とする。サービス間の契約検証は (3) で行い、E2E には含めない（§6 参照）

#### 運用規則

- 単体テストとアダプターテストは `go test ./...` / `dotnet test` / `pytest` 一発で走る（[ADR-016](016-repository-testing-testcontainers.md) 維持）
- `integration` タグ付き (= アダプター + サービス間結合) は CI の integration job で別ジョブとして走らせ、unit ジョブは Docker に依存させない
- `cloud_integration` は stg 環境に対する nightly ワークフローでのみ起動（§4 参照）
- テストピラミッドの厚みは上ほど薄く：**1 つの観点を複数層で重複検証しない**。アダプター層で検証済みの SQL を service 層で再検証しない、など

### 2. テストダブルは送信側サービスが配布する

[ADR-015](015-package-split.md) の「送信側サービスが型を所有」原則をテストダブルに拡張する。送信側サービスの RPC / Pub/Sub パッケージに、以下を同梱する：

- **Mock**: 呼び出し期待値を設定する interactive な test double（gomock / Moq / unittest.mock）
- **Fake**: 本物の薄い in-memory 実装（例: `ShopPublisherFake` が `[]PublishedMessage` に publish 結果を記録する）
- **Broker**: Pub/Sub fake 群が共有する in-memory broker（トピック名ベースで配信、publisher と subscriber の両方 fake が参照する）

パッケージ内物理配置の例：

```
overload-party-shop/packages/api-shop/
├── faction_purchased.go          # 型 + トピック名（既存）
├── premium_updated.go            # 既存
├── apishopfake/                  # 新設
│   ├── broker.go                 # in-memory broker
│   ├── publisher.go              # 送信側が自テストで publish 結果を検証する fake
│   └── subscriber.go             # 受信側 (account / card) がテストで流し込むための fake
└── apishopmock/                  # 必要なら mock も併設（interactive 検証用）
```

- **送信側サービス自身のテスト**: 自リポ内で `apishopfake.NewPublisher()` を使い「自分が意図どおりに publish したか」を検証（shop repo 内の publisher テスト）
- **受信側サービスのテスト**: 送信側パッケージを import し `apishopfake.NewSubscriber(broker)` で「送信側イベントがこの内容で来たら自分はこう振る舞う」を検証（account / card repo 内の subscriber テスト）
- fake の契約変更は**必ず送信側リポで 1 PR として完結**する。consumer は型ごと fake を import しているため自動的に追従する

C# 側（battle）は `OverloadParty.Battle.Contracts.Testing` 相当の NuGet サブパッケージとして同じ構造で配布する。Python 側（newsfeed）は `overload-party-newsfeed` に `api_newsfeed_fake` パッケージを置く。

### 3. サービス間結合テストは各サービス repo に置く

横断リポジトリ（overload-party-integration のような構成）は**作らない**。各 consumer サービスが、自サービスの `integration` タグ付きテストとして「送信側 fake を使った結合テスト」を書く。

例：`faction-purchased` を consume する account サービスのテストは、`overload-party-account/internal/subscriber/faction_purchased_test.go` に配置し、`apishopfake` を import して流し込む。

### 4. emulator / fake と本番の乖離は nightly cloud integration で検知

`cloud_integration` タグ付きテストを nightly で stg 環境に対して実行する。対象は「emulator / fake では検出できない、本物環境固有の挙動」に限定する：

- **Cloud SQL**: マイグレーション適用（[ops/db-migrate](../../../overload-party-ops/db-migrate/) の union 結果）、代表クエリの `EXPLAIN` が想定プランになるか、接続プール・IAM 認証の経路
- **Firestore**: 複合インデックス要求の検出（[ADR-017](017-game-config-firestore.md) 参照の emulator では検出されない）、security rules の実評価、トランザクションの optimistic concurrency
- **Cloud Pub/Sub**: Exactly-Once Delivery の実挙動（[ADR-012](012-matchmaking-pubsub.md) が前提にする保証）、dead letter queue への遷移、メッセージ重複の実測

全テストを cloud integration で回すのはコスト・時間の無駄。**乖離検知 smoke に絞る**。具体対象テストは各サービスリポの `cloud_integration` タグ付きファイルで管理する。

CI 実装は `.github/workflows/nightly-cloud-integration.yaml` を各サービスリポに追加する（[ADR-016](016-repository-testing-testcontainers.md) の integration ジョブと同じ runner 方針）。

### 5. パイロット選定

本戦略は全サービスへの段階展開を前提とするが、最初の 2 サービスで戦略を実証・テンプレ化する。

#### First pilot: `overload-party-shop`

採用理由：

- [ADR-016](016-repository-testing-testcontainers.md) 準拠の Testcontainers 基盤が最も成熟（[postgrestest](../../../overload-party-shop/internal/repository/postgres/postgrestest/) 実装済み）
- Pub/Sub emulator 基盤あり（[pubsubtest](../../../overload-party-shop/internal/adapter/pubsub/pubsubtest/)）
- outbox pattern の publisher 実装があり、Pub/Sub fake 設計の代表例になる
- `//go:build integration` タグ運用実績あり
- [packages/api-shop](../../../overload-party-shop/packages/api-shop/) が既に存在し、`apishopfake` サブパッケージを追加する物理配置が自然

shop で実証する範囲：

- build tag / CI ジョブ分離
- 送信側パッケージへの fake 同梱パターン (`apishopfake`)
- nightly cloud_integration テストの書き方（Cloud SQL migration smoke、実 Pub/Sub Exactly-Once 検証）

shop では検証できない範囲（REST outbound fake、consumer-side subscribe テストの実運用形）は second pilot で補う。

#### Second pilot 候補と選定軸

| 候補 | カバーできる観点 | 制約 |
|---|---|---|
| `overload-party-gateway` | REST outbound × 6 サービス / subscribe (match-found, scenario-updated) / WebSocket 受信 / PostgreSQL + Firestore | 複雑度が高い。WebSocket は E2E 側に寄せるべきで、パイロットとしては荷が重い |
| `overload-party-account` | subscribe × 3 topics (faction-purchased, premium-updated, player-onboarded) / PostgreSQL + Firestore / `integration` タグ運用あり | REST outbound なし。fake 同梱 consumer 側の典型になるが REST fake の実証は別途必要 |
| `overload-party-scenario` | publish (scenario-updated) + outbox / PostgreSQL + Firestore / `integration` タグ運用あり | publisher-only の観点が shop と重複する。追加価値が限定的 |

**推奨は `overload-party-account`**：

- shop (publisher 側) と対称な consumer 側の典型パターンをカバーできる
- `apishopfake` を最初に import する consumer になるため、fake パッケージ同梱の往復が最速で閉じる
- 既に `integration` タグ運用があり、テンプレ適用のコストが低い
- REST outbound fake の実証は gateway で **third pilot** として後追いする（WebSocket は E2E へ分離）

### 6. 対象外と先送り

- **Contract Testing (Pact 等)** は本 ADR では導入しない。nightly cloud_integration で乖離検知を行い、乖離が実害として複数回検出された場合に consumer-driven contract test の導入を再検討する
- **overload-party-e2e の役割限定**: E2E 層は**クライアントからの動線確認のみ**を対象とする。サービス間の契約検証は本 ADR のサービス間結合テスト層で行い、E2E には持ち込まない。E2E リポの内部設計（どのクライアントフローを対象とするか、どの基盤で動かすか）は別 ADR に委ねる
- **Chaos / load testing** は本 ADR の対象外

### トレードオフ

- **fake パッケージのメンテナンスが送信側サービスに乗る**: 送信側サービスは自分の型だけでなく fake の振る舞いも保守する責務を持つ。`apishopfake` の挙動変更は shop repo の PR として扱う
- **fake と実装の乖離リスク**: in-memory fake は本物の Pub/Sub / HTTP の全挙動を再現しない。これは nightly cloud_integration で検知する設計だが、検知粒度は smoke レベルに留まる
- **stg 環境のコスト**: nightly cloud_integration のために stg の Cloud SQL / Firestore / Pub/Sub を常時維持する必要がある。db-f1-micro + Firestore 無料枠 + Pub/Sub 小額で月数千円規模
- **C# / Python での追従コスト**: Go 側で確立したパターンを C# (battle) / Python (newsfeed) に写経する工数が別途発生する

## 不採用案

### 案A: サービス間結合テスト専用のリポジトリを新設

却下。所有権が消える（テストが落ちたときどちらのサービスチームが直すかが自明でない）、追従コストが爆発する（送信側サービスの契約変更が別リポの PR として追いかける運用になる）、ローカル開発で全サービス起動が必須になり日常的に回らなくなる。`overload-party-e2e` が担うユーザー視点の E2E とも責務が重複する。

### 案B: 各サービスが相手サービスの fake を独自に手書きし続ける

却下。[ADR-015](015-package-split.md) で「送信側が契約を所有」と決めた原則に反する。契約変更のたびに consumer 側の手書き fake が古い契約を前提に動き続ける乖離が起きる（既に shop repo 内で `fakeShopServicer` 等が ad hoc に定義されている）。スケールしない。

### 案C: Contract Testing (Pact 等) の全面導入

見送り。consumer-driven contract test は乖離検知の正攻法だが、Go / C# / Python の 3 言語 × 7 サービスで導入・運用するには先行投資が大きい。**乖離検知の第一手段は nightly cloud integration test（本 ADR で採用）に任せ**、Pact は fake と実装の不整合が実害として顕在化したタイミングで再検討する。
