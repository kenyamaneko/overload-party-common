# ADR-025: オンボーディング表示名確定を REST 同期書込に切替 + ドメイン間 HTTP 直叩きを onboarding に限り例外許容

## ステータス

Accepted (2026-04-26)。§1 (表示名の REST 同期書込) と §3 (進行判定を業務カラムの nullable から導出する設計) は [ADR-026](026-onboarding-status-as-account-responsibility.md) により上書きされる

本 ADR は [ADR-021](021-onboarding-scenario.md) §5 (`PlayerOnboardedEvent.display_name` を outbox 経由で配信する設計) を部分的に上書きする。表示名はオンボーディング内の name 入力ステップで scenario が account に対し同期 REST で書き込み、`PlayerOnboardedEvent` payload からは `display_name` を撤去する。これに伴い、ドメインサービス間 HTTP 直叩きを **onboarding ユースケース内に限った例外** として明示的に許容する。

## 結論

表示名バリデーションの結果を入力時点でユーザーへ即時に返すため、オンボーディング内 name 入力ステップでは scenario が account の `PUT /internal/v1/players/:playerId/name` を同期 REST で呼んで表示名を確定し、`PlayerOnboardedEvent` payload から `display_name` を撤去する。これはドメイン間 HTTP 直叩き禁止というアーキ方針からの逸脱にあたるため、**原則禁止 + onboarding 限定の例外条項** として書面化し、狭い port と adapter 層への閉じ込めで直叩きの拡散を構造的に抑止する。account 側 subscriber の先行実装（`ev.DisplayName` を読まない）と契約の齟齬が解消され、オンボーディング再開判定は account の業務真実に一本化されて scenario 側の進行フラグ二重持ちがなくなる。

## 背景・課題

### 現行設計と顕在化した問題

[ADR-021](021-onboarding-scenario.md) §5 / [ADR-022](022-faction-selected-decomposition.md) §1 では、scenario はオンボーディング完了時に `PlayerOnboardedEvent` を 1 本 publish し、payload に `display_name` を載せて account / card / gateway へ伝搬する設計とした。account は subscriber 内で `players.name` を UPDATE する。

この設計を実装した結果、以下の問題が顕在化した。

#### 1. 表示名のバリデーション違反がオンボーディング完了時まで発覚しない

業務バリデーション (空 / 全空白 / 制御文字混入 / `MaxNameRunes=20` 超) の SSoT は account の [`internal/model/name.go`](../../../overload-party-account/internal/model/name.go) (`ValidateName` / `ErrInvalidName`) にある。現行設計ではバリデーションは subscriber 側で走るため、ユーザーがシナリオを最後まで読み終えてから「不正な表示名」で 400 相当のエラーを受ける形になり、ユーザビリティとして成立しない。即時バリデーションを実現するには、name 入力ステップで account に対し同期書込を行う必要がある。

#### 2. account 側 subscriber が既に `display_name` を読まない実装になっている

account の [`player_onboarded_subscriber.go`](../../../overload-party-account/internal/adapter/pubsub/player_onboarded_subscriber.go) は、コメント明記のうえで `ev.DisplayName` を参照しない。これは「scenario が REST 経由で account に確定済み」という前提で先行実装されており、対応する設計判断 (ADR) が無いまま実装と契約に齟齬が残っている。本 ADR でこの齟齬を正式化する。

#### 3. オンボーディング再開時の状態判定

オンボーディング途中で離脱したプレイヤーが再開したとき、「名前は確定済みか」「初期 faction は選択済みか」を業務真実 (account の `Player.Name` / `Player.SelectedFaction` の nullable) から判定したい。現行 `PlayerOnboardedEvent` 経由の非同期反映だと、再開時点で account の状態が確定している保証がなく、scenario 側でフラグ管理を二重化する必要が出る。

### 既存のアーキ方針: ドメイン間直叩きは存在しない

現行プロジェクトでは、**ドメインサービス同士は HTTP で直接通信しない**。

- `overload-party-gateway/internal/client/{account,card,shop,scenario,matchmaking}client/` のみがサービス間 HTTP 集約点で、gateway がスター型ハブを務める
- account / card / shop / scenario / matchmaking / battle / news / support のドメインサービスは、他ドメインへの outbound HTTP クライアントを一切持たない
- 他ドメインに置かれた HTTP クライアントは全て **外部** 向け (shop → Apple App Store、matchmaking → Secret Manager、support → SendGrid / Slack)
- ドメイン間の連携は Pub/Sub で疎結合化されている ([ADR-012](012-matchmaking-pubsub.md) / [ADR-021](021-onboarding-scenario.md) / [ADR-022](022-faction-selected-decomposition.md))

本 ADR で scenario → account の直叩きを導入することは、このアーキ方針からの **明示的な逸脱** にあたる。

### 直叩き以外の選択肢が要件を毀損する

|案|即時バリデーション (a)|name 確定と進行更新の原子性 (b)|業務真実 SSoT 維持 (c)|備考|
|---|---|---|---|---|
|Pub/Sub で name 確定要求を非同期化|✗|✗|○|同期 req/res が成立せず即時 400 を返せない|
|gateway を中継 (scenario → gateway → account)|○|○|○|gateway は Firebase Token 認証必須で scenario はトークン取得手段がない。internal バイパスを足すと結局新規穴を開ける|
|クライアントが gateway → account で確定し、scenario に別途 checkpoint 通知|△|✗|○|クライアントが向き先を判断する不自然さ + 2 段階呼び出しで原子性を失う|
|オンボーディングから name 入力ステップ自体を撤去 (設定画面で後から入力)|—|—|○|機能仕様の変更となり、オンボード演出 (「お名前は？」) を諦めることになる|
|**scenario → account 直叩き**|○|○|○|アーキ方針からの逸脱と引き換えに全要件を満たす|

要件 (a) (b) (c) を全て満たす経路は直叩きしかない。

## 制約

- オンボーディング内 name 入力で account のバリデーションを即時中継できること (UX 要件)
- name 確定と onboarding 進行管理 (checkpoint) を scenario が原子的に保持できること
- 業務真実 (`players.name`) の SSoT は account に維持すること
- ドメイン間 HTTP 直叩きの拡散を防ぎ、今回の例外を再利用条件で縛ること
- 既存の Pub/Sub 経路 (`PlayerOnboardedEvent`) は引き続き card / gateway / account の他副作用 (faction 反映 / 初期パック配布 / WS 通知) のために保持すること
- account 側 subscriber の先行実装と契約の齟齬を解消すること

## 詳細

### 1. 表示名確定経路を REST 同期書込に切替

オンボーディング内の name 入力ステップでは、scenario が account の `PUT /internal/v1/players/:playerId/name` を同期 REST で呼び出して表示名を確定する。account 側 `ErrInvalidName` (400) はそのまま scenario REST のレスポンスとして中継し、ユーザーに即時再入力を促す。

scenario には `internal/adapter/http/accountclient.go` を新設し、onboarding service には `OnboardingNameUpdater` / `OnboardingPlayerReader` 等の **狭い port** を切って注入する（汎用的な「account クライアント」として共有しない）。

`PlayerOnboardedEvent` payload から `display_name` フィールドを撤去する。`scripts/generate_types.py` を使った再生成と、scenario / account / card / gateway の関連箇所を本 ADR 採用 PR で同時に更新する。

表示名 SSoT を account に一本化することで、scenario の `displayNameMaxRunes = 21` (当時の値) と account の `MaxNameRunes = 20` の齟齬は scenario 側削除によって解消する。境界値テストは account 側 [`internal/model/name_test.go`](../../../overload-party-account/internal/model/name_test.go) が網羅する。

### 2. ドメイン間 HTTP 直叩きの例外許容ルール

ドメインサービス間の HTTP 直叩きは **原則禁止** とする。これは現行の Pub/Sub + gateway ハブ構造を維持するためのルールである。本 ADR では以下の例外を **onboarding 内に限定** して許容する。将来別ユースケースで同種の要件 (即時バリデーション中継) が出てきたときは §2.1 の例外条項を再評価する起点とし、安易に「ADR-025 で許容されているから」を拡大解釈しないこと。

#### 2.1 例外を許容する条件

以下の 3 条件をすべて満たす場合に限り、ドメイン間 HTTP 直叩きを許容する。新規に直叩きを追加する場合は本 ADR を参照し、当該ユースケースが 3 条件を満たすことを別 ADR で正当化すること。

1. **即時 UX フィードバックが業務要件**: ユーザーの 1 回の入力に対し、業務バリデーションの結果を同一トランザクション粒度で返す必要があること。Pub/Sub では成立しない場合
2. **業務真実の SSoT が呼び出し先に存在**: 呼び出し先サービスが当該ドメインの SSoT を保持しており、呼び出し元は中継のみを行うこと (呼び出し元に同等のデータを複製しない)
3. **gateway 経由ルートが認証境界の都合で成立しない**: クライアントから直接呼ぶ既存ルートが authentication / authorization の制約で再利用不可能であること

#### 2.2 実装上の制約

例外を許容する場合でも以下の制約を全て守ること。

- **狭い port インターフェースで注入**: `OnboardingNameUpdater` のように利用ユースケース名を冠した port を切り、`AccountClient` のような汎用型を service 層から見せない
- **adapter 層に閉じ込め**: HTTP の概念 (status code、URL、ヘッダ) は `internal/adapter/http/<callee>client.go` 内に閉じ込め、service 層ではドメイン例外 (`ErrInvalidName` 相当) のみを扱う
- **共有しない**: 呼び出し元サービス内専用とし、他のドメインサービスからの再利用 (例: scenario の accountclient を他サービスが import) を構造的に禁ずる。`internal/adapter/http/` 配下に置き、`packages/` に出さない
- **エラー中継**: 呼び出し先の業務エラー (400) は呼び出し元の API レスポンスへそのまま中継する。呼び出し先のインフラエラー (5xx / timeout) は呼び出し元の 5xx として再現する。握り潰しは禁止
- **接続先 URL は env 注入**: `<CALLEE>_BASE_URL` の env で URL を受け取り、Kubernetes ClusterIP DNS (`http://<callee>.<ns>.svc.cluster.local:<port>` 形式) を想定する。リテラルでハードコードしない

#### 2.3 本 ADR で許容する具体的な直叩き

scenario → account の以下 2 経路を本 ADR で許容する。これ以外の経路は別 ADR の対象。

|呼び出し|目的|エラー中継|
|---|---|---|
|`PUT /internal/v1/players/:playerId/name`|オンボーディング内 name 入力ステップでの表示名確定|400 `ErrInvalidName` を scenario の 400 に中継|
|`GET /internal/v1/players/:playerId`|オンボーディング再開判定 (`Name` / `SelectedFaction` の nullable から次の checkpoint を導出)|404 はオンボーディング前段階で発生し得ない (Register 必須) ため 5xx 扱いで上層に伝搬|

### 3. オンボーディング進行の業務真実は account に集約

オンボーディング再開判定は account の Player 状態 (`Name` / `SelectedFaction`) を SSoT として導出する。再開判定エンドポイント (`GET /internal/v1/players/:playerId/onboarding/resume`) で account の Player を取得し、次の checkpoint を導出する。scenario 側で進行 checkpoint を独自に永続化することは行わない (`scenario.player_onboarding` テーブルは [ADR-021](021-onboarding-scenario.md) 既存の「完了マーク (PK once-only)」専用のまま)。

| account の状態 | 次の checkpoint |
|---|---|
| `Name == nil` | `started` (名前入力から再生) |
| `Name != nil && SelectedFaction == nil` | `name_set` (初期 faction 選択から再生) |
| `Name != nil && SelectedFaction != nil && player_onboarding に行なし` | `faction_set` (最終演出から再生) |
| `player_onboarding に行あり` | `completed` (ホームへ) |

[ADR-021](021-onboarding-scenario.md) §2.1 が「`scenario.player_onboarding` は display_name / faction_id を保存しない」と定めた SSoT 集約方針と整合する。

### 4. ADR-021 / ADR-022 の supersede

- ADR-021 §5 の `display_name` を outbox 経由で伝搬する設計を本 ADR で部分上書きする。`PlayerOnboardedEvent` から `display_name` を撤去し、payload は `event_id` / `event_type` / `timestamp` / `player_id` / `initial_faction_id` のみとする。ADR-021 本文には本 ADR への supersede note を追記する
- ADR-022 §1 の subscriber 副作用テーブル「account: `players.display_name` UPDATE + ...」から display_name UPDATE を除外する形に更新する。account の `player_onboarded_subscriber` 実装は既に本 ADR と整合しており、契約だけが追従する形となる

### トレードオフ

- プロジェクト最初のドメイン間 HTTP 直叩きが導入される。アーキ方針上の例外条項を新設する必要がある
- scenario の可用性が account の可用性に直接連動する (account ダウン時に scenario の name 入力ステップが 5xx)。ただし name 確定できなければオンボーディング進行できないという業務上の依存関係と等価で、隠蔽すべき情報ではない
- scenario の運用対象が「DB + GCS + Pub/Sub + outbox + account REST」に増える
- account の REST 契約 (`PUT /name` のリクエスト/レスポンス schema) 変更が scenario の動作と直結する。subscriber 経路と異なり Pub/Sub の `event_type` で版を分離できないため、契約変更時は両者を同時にデプロイする必要がある

## 不採用案

### 案 B: 既存 `PlayerOnboardedEvent` を維持し、subscriber 側でバリデーションをするだけに留める

却下理由: ユーザーがシナリオ完了まで進んでから 400 で弾かれる UX が成立しない。account 側 subscriber が既に `ev.DisplayName` を読まなくなっており、現実装と矛盾する。

### 案 C: gateway を経由してドメイン間通信を集約する

却下理由: gateway は Firebase Token 認証必須で、scenario が認証トークンを取得する手段がない。internal バイパスを足すと「クライアント認証の単一責務」を破壊し、認証境界の信頼性を損なう。

### 案 D: クライアントが gateway → account で表示名を確定し、scenario には別途 checkpoint 通知 API を呼ぶ

却下理由: オンボーディングのスクリプト所有者は scenario であるにもかかわらず、name 入力結果だけクライアントが向き先を判断する非対称性が残る。さらに「name 確定は成功したが checkpoint 通知に失敗」した中間状態の補償責務がクライアント実装に依存する (原子性を失う)。

### 案 E: 機能仕様を変更し、オンボーディングから name 入力ステップを撤去

却下理由: オンボード演出 (「お名前は？」) を諦めることになり、サービス側都合でユーザー体験を犠牲にする。本 ADR のスコープを越える機能仕様変更で、設計判断ではなくプロダクト判断になる。
