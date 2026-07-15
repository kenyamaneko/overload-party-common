# ADR-025: オンボーディング表示名確定を REST 同期書込に切替 + ドメイン間 HTTP 直叩きを onboarding に限り例外許容

## ステータス

Accepted (2026-04-26)。本 ADR の表示名確定を REST 同期書込に切り替える決定と、オンボーディング進行の業務真実を account に集約する決定は、[ADR-026](026-onboarding-status-as-account-responsibility.md) で上書きされた。

本 ADR は [ADR-021](021-onboarding-scenario.md) のイベント設計（`PlayerOnboardedEvent.display_name` を outbox 経由で配信する部分）を部分的に上書きする。表示名はオンボーディング内の name 入力ステップで scenario が account に対し同期 REST で書き込み、`PlayerOnboardedEvent` payload からは `display_name` を撤去する。これに伴い、ドメインサービス間 HTTP 直叩きを **onboarding ユースケース内に限った例外** として明示的に許容する。

## 結論

表示名バリデーションの結果を入力時点でユーザーへ即時に返すため、オンボーディング内 name 入力ステップでは scenario が account の `PUT /internal/v1/players/:playerId/name` を同期 REST で呼んで表示名を確定し、`PlayerOnboardedEvent` payload から `display_name` を撤去する。これはドメイン間 HTTP 直叩き禁止というアーキ方針からの逸脱にあたるため、**原則禁止 + onboarding 限定の例外条項** として書面化し、狭い port と adapter 層への閉じ込めで直叩きの拡散を構造的に抑止する。account 側 subscriber の先行実装（`ev.DisplayName` を読まない）と契約の齟齬が解消され、オンボーディング再開判定は account の業務真実に一本化されて scenario 側の進行フラグ二重持ちがなくなる。

## 背景・課題

### 現行設計と顕在化した問題

[ADR-021](021-onboarding-scenario.md) と [ADR-022](022-faction-selected-decomposition.md) では、scenario はオンボーディング完了時に `PlayerOnboardedEvent` を 1 本 publish し、payload に `display_name` を載せて account / card / gateway へ伝搬する設計とした。account は subscriber 内で `players.name` を UPDATE する。

この設計を実装した結果、以下の問題が顕在化した。

#### 表示名のバリデーション違反がオンボーディング完了時まで発覚しない

業務バリデーション (空 / 全空白 / 制御文字混入 / `MaxNameRunes=20` 超) の SSoT は account の [`internal/model/name.go`](../../../overload-party-account/internal/model/name.go) (`ValidateName` / `ErrInvalidName`) にある。現行設計ではバリデーションは subscriber 側で走るため、ユーザーがシナリオを最後まで読み終えてから「不正な表示名」で 400 相当のエラーを受ける形になり、ユーザビリティとして成立しない。即時バリデーションを実現するには、name 入力ステップで account に対し同期書込を行う必要がある。

#### account 側 subscriber が既に `display_name` を読まない実装になっている

account の [`player_onboarded_subscriber.go`](../../../overload-party-account/internal/adapter/pubsub/player_onboarded_subscriber.go) は、コメント明記のうえで `ev.DisplayName` を参照しない。これは「scenario が REST 経由で account に確定済み」という前提で先行実装されており、対応する設計判断 (ADR) が無いまま実装と契約に齟齬が残っている。本 ADR でこの齟齬を正式化する。

#### オンボーディング再開時の状態判定

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

したがって本 ADR は直叩きを onboarding ユースケース内に限った例外として許容する。将来同種の直叩きを追加する場合は、(1) 即時バリデーション中継が業務要件であること、(2) 業務真実の SSoT が呼び出し先サービスにあり呼び出し元は中継のみを行うこと、(3) gateway 経由ルートが認証境界の都合で成立しないこと、の 3 条件をすべて満たすことを別 ADR で正当化する。

## 不採用案

### 既存 `PlayerOnboardedEvent` を維持し、subscriber 側でバリデーションをするだけに留める

却下理由: ユーザーがシナリオ完了まで進んでから 400 で弾かれる UX が成立しない。account 側 subscriber が既に `ev.DisplayName` を読まなくなっており、現実装と矛盾する。

### gateway を経由してドメイン間通信を集約する

却下理由: gateway は Firebase Token 認証必須で、scenario が認証トークンを取得する手段がない。internal バイパスを足すと「クライアント認証の単一責務」を破壊し、認証境界の信頼性を損なう。

### クライアントが gateway → account で表示名を確定し、scenario には別途 checkpoint 通知 API を呼ぶ

却下理由: オンボーディングのスクリプト所有者は scenario であるにもかかわらず、name 入力結果だけクライアントが向き先を判断する非対称性が残る。さらに「name 確定は成功したが checkpoint 通知に失敗」した中間状態の補償責務がクライアント実装に依存する (原子性を失う)。

### 機能仕様を変更し、オンボーディングから name 入力ステップを撤去

却下理由: オンボード演出 (「お名前は？」) を諦めることになり、サービス側都合でユーザー体験を犠牲にする。本 ADR のスコープを越える機能仕様変更で、設計判断ではなくプロダクト判断になる。
