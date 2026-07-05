# ADR-026: オンボーディング進行状態を account の専用カラムで保持し、書き込みは Pub/Sub 経由に統一する (REST はバリデーション目的のみ)

## ステータス

Accepted (2026-04-26)

本 ADR は [ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) §1 (表示名を REST 同期書込で確定する設計) と §3 (オンボーディング進行を account の業務カラム `Name` / `SelectedFaction` の nullable から導出する設計) を上書きする。account に専用カラム `onboarding_status` を追加し、scenario が業務事実ごとに 3 トピック (`onboarding-name-set` / `onboarding-faction-set` / `player-onboarded`) を publish して account が subscribe する形に切り替える。account の REST はバリデーション目的のみに縮退し、業務データの書き込みはすべて Pub/Sub subscriber 経由に統一する。これに伴い [ADR-022](022-faction-selected-decomposition.md) §1 の `PlayerOnboardedEvent` subscriber 副作用 (account の `players.selected_faction` UPDATE + `player_factions` INSERT) を `onboarding-faction-set` 側へ移管し、`player-onboarded` は完了 status 遷移のみに縮退する。`PlayerOnboardedEvent` payload の `initial_faction_id` は維持する (card subscriber の `GrantInitialPack` で必要なため)。

## 結論

業務カラムの NULL 兼用では「オンボード未完了」と「データ消失」を区別できないため、`account.players` に専用カラム `onboarding_status` を追加し、オンボード進行を業務事実ごとの 3 トピック (`onboarding-name-set` / `onboarding-faction-set` / `player-onboarded`) で account に伝搬する。account の REST はバリデーション目的のみ (`POST /onboarding/name/validate`) に縮退する。`name IS NULL` の発生は異常検知の対象として独立に扱えるようになり、identity カラムがオンボード進行管理の責務から解放される。account 側の書き込み経路は Pub/Sub subscriber 1 系統に統一されて業務データと進行 status の永続化が同一 tx で原子的に行われ、REST 成功 + 後続処理失敗の中間状態が消滅する。1 event = 1 業務事実の原則 ([ADR-022](022-faction-selected-decomposition.md)) が維持され、ログイン時の status 取得は account の `GetPlayer` 1 RPC で完結する。

## 背景・課題

### 1. 業務カラム NULL 兼用の構造的欠陥

[ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) §3 では、オンボーディング再開判定を account の業務カラム (`players.name` / `players.selected_faction`) の nullable 状態から導出する設計を採用した。これは「業務真実から導出する」点で SSoT 原則に沿うが、**`name IS NULL` が「未入力 (オンボード未完了)」と「データ消失 (運用事故・移行ミス・障害)」のどちらを意味するか区別できない**という構造的欠陥を抱えている。

具体的な実害:

- 完了済みプレイヤーが事故で `players.name` を失った場合、resume API が `started` を返してオンボード画面に逆戻りさせる
- 「完了マークがあるのに業務データが欠けている」という矛盾を派生値方式では構造的に表現できず、データ消失の能動検知ができない
- `players.name` のスキーマが「オンボーディング進行の合図」と「表示名カラム」という独立した 2 つの責務を兼任している

### 2. ADR-025 の REST 直書込で発生する責務混合

[ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) §1 では scenario が account の `PUT /internal/v1/players/:playerId/name` を REST 同期書込で呼ぶ設計を採用した。これにより account 側の書き込み経路は **REST 直書込 + Pub/Sub subscriber 駆動** の 2 系統に分かれ、進行状態 (本 ADR で導入する `onboarding_status`) と name の永続化が別 tx となる。

REST 直書込の動機を分解すると、scenario が REST に依存する理由は **「account の `internal/model/name.go` (`MaxNameRunes=20`、空 / 全空白 / 制御文字 NG) のバリデーション結果を即時にユーザーへ返す」** という UX 要件のみであり、「name を account に永続化する」こと自体は Pub/Sub event でも成立する。バリデーションと書き込みを 1 つの REST でまとめていることが責務混合の起点である。

faction 側 (本 ADR で扱う `POST /onboarding/faction` 新設) については、バリデーション SSoT が `gamedesign.SelectableFactions` (共有定数 `overload-party-common/packages/game-design-constants`) であり、scenario 側で同等の検証が可能なので REST すら不要である。

### 3. ADR-022 の業務事実分解原則との整合

[ADR-022](022-faction-selected-decomposition.md) では旧 `FactionSelectedEvent` を業務事実 (`PlayerOnboardedEvent` / `FactionPurchasedEvent`) に分解した。この「**1 event = 1 業務事実**」原則を本 ADR にも適用すると、オンボード進行は次の 3 つの独立した業務事実に分解できる:

- 名前入力ステップ完了 (player_id, name)
- faction 選択ステップ完了 (player_id, initial_faction_id)
- オンボーディング完了 (player_id, initial_faction_id を含む完了 snapshot)

これらを 1 トピック (`onboarding-progress-changed` のような汎用トピック) に集約し payload 内 `next_status` で分岐させると、payload と業務事実の対応が薄れ、ADR-022 の分解原則を逆行する。3 つを独立したトピックとして表現するほうが業務契約が明確になる。

## 制約

- 「オンボード未完了」と「データ消失」を構造的に区別できること (運用事故の能動検知と誤った再オンボード遷移の防止)
- account の identity カラム (`name` / `selected_faction`) を「オンボード進行管理」の責務から解放すること
- account 側の書き込み経路を Pub/Sub subscriber 1 系統に統一し、業務データの永続化と進行 status 遷移を同一 tx で原子的に行うこと
- ドメイン間 HTTP 直叩き経路を「scenario 側で validate 不可能な情報の validation のみ」に縮退すること ([ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) 例外条項の拡散抑制)
- 1 event = 1 業務事実の原則 ([ADR-022](022-faction-selected-decomposition.md)) を維持し、payload 設計を業務契約と一致させること
- ログイン時の status 取得を account の `GetPlayer` 1 RPC で完結させること

## 詳細

### 1. account に専用カラム `onboarding_status` を追加

`account.players` テーブルに以下のカラムを追加する。

```sql
ALTER TABLE account.players
  ADD COLUMN onboarding_status VARCHAR(20) NOT NULL DEFAULT 'not_started'
    CHECK (onboarding_status IN ('not_started', 'name_set', 'faction_set', 'completed'));
```

state machine は一方向遷移のみ (`not_started` → `name_set` → `faction_set` → `completed`)。逆方向遷移は仕様上発生しない。subscriber 側の冪等な UPDATE は state machine 順序で表現する (詳細 §4.4)。

本 ADR 採用時点で本番稼働前のため、既存データの移行は不要。`onboarding_status` カラムは DEFAULT `'not_started'` で追加すれば既存テストデータも整合する。

### 2. account の `GetPlayer` レスポンスに `onboarding_status` を同梱

`GET /internal/v1/players/:playerId` のレスポンスに `onboarding_status` フィールドを追加する。クライアントはログイン時にこのレスポンスを 1 度取るだけでオンボードフロー再開判定が可能となる。

### 3. scenario からの状態取得系エンドポイントを撤去

scenario の以下エンドポイントを撤去する (オンボード進行状態の取得経路を account の `GetPlayer` 1 本に集約)。

- `GET /internal/v1/players/:playerId/onboarding/status` (撤去)
- `GET /internal/v1/players/:playerId/onboarding/resume` (撤去)

scenario はオンボードフローの実行のみを担い、状態の問い合わせを持たない。

### 4. Pub/Sub トピックを業務事実ごとに 3 本に分離

#### 4.1 トピック構成

| topic 名 | publisher | subscriber | event type | 発火タイミング |
|---|---|---|---|---|
| `onboarding-name-set` | scenario | account | `onboarding_name_set` | scenario `PUT /onboarding/name` 受領後 (account の validate REST 成功後) |
| `onboarding-faction-set` | scenario | account | `onboarding_faction_set` | scenario `POST /onboarding/faction` 受領後 (scenario 内 validate 成功後) |
| `player-onboarded` (既存) | scenario | account, card | `player_onboarded` | scenario `POST /onboarding/complete` 受領後 |

publish はすべて scenario の outbox 経由で atomic に enqueue する (scenario 側のビジネス DB 書き込みと outbox 行 INSERT を同一 tx で実行)。

#### 4.2 event 型の所有

[ADR-022](022-faction-selected-decomposition.md) の所有原則 (events with a single publisher should live in that publisher's api-<svc> package) に従い、`OnboardingNameSetEvent` / `OnboardingFactionSetEvent` / 既存 `PlayerOnboardedEvent` はすべて `scenario/packages/api-scenario` に置く。topic 定数 (`TopicOnboardingNameSet` / `TopicOnboardingFactionSet`) と event type 定数も同パッケージで定義する。

#### 4.3 payload 定義

`OnboardingNameSetEvent` (新規):

```go
type OnboardingNameSetEvent struct {
    EventType string    `json:"event_type"` // = "onboarding_name_set"
    EventID   string    `json:"event_id"`
    Timestamp time.Time `json:"timestamp"`
    PlayerID  string    `json:"player_id"`
    Name      string    `json:"name"`       // バリデーション済み (account の validate REST を通過)
}
```

`OnboardingFactionSetEvent` (新規):

```go
type OnboardingFactionSetEvent struct {
    EventType        string    `json:"event_type"` // = "onboarding_faction_set"
    EventID          string    `json:"event_id"`
    Timestamp        time.Time `json:"timestamp"`
    PlayerID         string    `json:"player_id"`
    InitialFactionID string    `json:"initial_faction_id"` // SHE / Tenki / Sugar / Tuners
}
```

`PlayerOnboardedEvent` (既存、payload 維持):

```go
type PlayerOnboardedEvent struct {
    EventType        string    `json:"event_type"` // = "player_onboarded"
    EventID          string    `json:"event_id"`
    Timestamp        time.Time `json:"timestamp"`
    PlayerID         string    `json:"player_id"`
    InitialFactionID string    `json:"initial_faction_id"`
}
```

`PlayerOnboardedEvent.InitialFactionID` を残す根拠は card subscriber の `GrantInitialPack(playerID, faction)` (初期パック配布: 選択 faction のカード + Neutral カード) が faction を業務処理の引数として必須とするため。card に account `GetPlayer` への REST 直叩きを新設するのは [ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) §2.1 の例外条項を subscriber コンテキストに無理筋で拡張することになり、責務的には「すでに account に書かれた事実を payload で snapshot として伝搬する」ほうが自然 (faction の書き込み権限は account のみで、SSoT 集約は維持される)。

#### 4.4 account 側 subscriber 処理

各 subscriber は同一 tx 内で「業務データの永続化 + `onboarding_status` 遷移」を実行する。

| subscriber | 処理内容 (1 tx) |
|---|---|
| `OnboardingNameSetSubscriber` | `players.name` UPDATE + `players.onboarding_status = 'name_set'` UPDATE |
| `OnboardingFactionSetSubscriber` | `players.selected_faction` UPDATE + `player_factions` INSERT (`source='initial_selection'`、ON CONFLICT DO NOTHING) + `players.onboarding_status = 'faction_set'` UPDATE |
| `PlayerOnboardedSubscriber` (改修) | `players.onboarding_status = 'completed'` UPDATE のみ。`selected_faction` UPDATE / `player_factions` INSERT は `OnboardingFactionSetSubscriber` に移管したため撤去 |

冪等性は既存 `account.processed_events` テーブルでの event_id dedup (`event_type = 'onboarding_name_set'` / `'onboarding_faction_set'`) と、state machine 順序を活用した条件付き UPDATE (`UPDATE ... WHERE onboarding_status < new_status` 相当) で担保する。再配信で同じ event を受け取っても二重適用が起きない。

card 側 `PlayerOnboardedSubscriber` は変更しない (引き続き payload の `InitialFactionID` を `GrantInitialPack` の引数に使う)。gateway は [ADR-027](027-gateway-pubsub-fanout-removal.md) で `PlayerOnboardedSubscriber` ごと撤去済みのため本 ADR の対象外。

### 5. account の REST はバリデーション目的のみに縮退

#### 5.1 新エンドポイント `POST /internal/v1/players/:playerId/onboarding/name/validate`

```
POST /internal/v1/players/:playerId/onboarding/name/validate
Body: { "name": "..." }
Response: 200 (valid) / 400 (ErrInvalidName 等) / 404 (player not found)
```

account 側はバリデーション (`internal/model/name.go` の `ValidateName`) のみ実行し、`players.name` には書き込まない。書き込みは scenario が後続で publish する `onboarding-name-set` event を account 自身が subscribe して行う。

scenario 側は本 endpoint の 4xx をユーザーへそのまま中継し、200 を受け取った場合のみ outbox に `onboarding-name-set` を enqueue する (validate 失敗時は publish しない)。

#### 5.2 既存 `PUT /internal/v1/players/:playerId/name` は維持

[ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) §1 で導入された REST 直書込エンドポイントは **撤去しない**。本エンドポイントは scenario のオンボードフロー専用ではなく、gateway 経由のクライアント発名前変更 (オンボード完了後の設定画面等からの通常名前変更) でも利用されているため。

本 ADR で変えるのは「scenario のオンボードフロー」のみ:

- scenario はオンボード内 name 入力ステップで `PUT /name` を呼ばなくなり、`POST /name/validate` (validation only) を呼んで成功時に `onboarding-name-set` event を publish する
- account 側 `players.name` の書き込み経路は 2 系統となる:
  - **scenario オンボード経路**: `OnboardingNameSetSubscriber` が subscribe して書き込む
  - **gateway 経由のクライアント名前変更経路**: 既存 `PUT /name` ハンドラが書き込む

これは「業務ユースケースが 2 つ存在する」ことへの対応であり、責務違反ではない。subscriber と REST ハンドラはどちらも同じ `players.name` カラムを update するが、起動契機 (オンボード完了通知 / クライアント発名前変更) と冪等性担保方法 (event_id dedup / リクエスト単発) が異なる業務経路として独立する。

#### 5.3 faction は REST 不要

faction のバリデーション SSoT は `gamedesign.SelectableFactions` (共有定数) であり、scenario 側で `slices.Contains(gamedesign.SelectableFactions, factionID)` 相当の検証が可能。scenario は自分で validate し、成功時のみ outbox に `onboarding-faction-set` を enqueue する。account 側に faction 用 REST endpoint は新設しない。

### 6. scenario の API 構成

| エンドポイント | 処理 |
|---|---|
| `GET /internal/v1/players/:playerId/onboarding/script?lang=` | 変更なし (script 配信、完了済みは 409) |
| `PUT /internal/v1/players/:playerId/onboarding/name` | account の `POST /name/validate` を REST で呼ぶ → validate 成功時に outbox に `onboarding-name-set` を enqueue |
| `POST /internal/v1/players/:playerId/onboarding/faction` (新規) | scenario 内で `gamedesign.SelectableFactions` で validate → 成功時に outbox に `onboarding-faction-set` を enqueue |
| `POST /internal/v1/players/:playerId/onboarding/complete` | body 空。`scenario.player_onboarding` INSERT + outbox に `player-onboarded` を enqueue (1 tx) |
| `GET /internal/v1/players/:playerId/onboarding/status` | 撤去 |
| `GET /internal/v1/players/:playerId/onboarding/resume` | 撤去 |

`POST /onboarding/complete` の `OnboardingCompleteRequest` から `InitialFactionID` を撤去する (faction は `POST /onboarding/faction` 経由で account に永続化済み)。`PlayerOnboardedEvent.InitialFactionID` の値は scenario が `account.GetPlayer` で取得して payload に詰める (publish 前に必ず存在する)。この `GetPlayer` 呼び出しは [ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) §2.3 で許容済みの経路の利用に該当し、新規例外条項の追加にはあたらない。`POST /onboarding/faction` で account に書き込み済みのため、`GetPlayer` 呼び出し時点で `selected_faction` は必ず non-nil。nil なら scenario 側でフロー違反とみなして 409 等で弾く (faction 選択ステップを経ずに完了 API を叩いた異常状態)。

### 7. 状態遷移タイムライン

```
[register]
  account.players INSERT (onboarding_status = 'not_started')

[scenario: PUT /onboarding/name {name}]
  → scenario が account の POST /name/validate を REST で呼ぶ (validation only)
  → 4xx ならクライアントへ中継、200 なら次へ
  → scenario: outbox に onboarding-name-set (player_id, name) を enqueue (scenario 側に永続化対象がないので outbox 行のみの 1 tx)
  → (eventual) account subscriber: players.name + onboarding_status='name_set' を 1 tx で UPDATE

[scenario: POST /onboarding/faction {initial_faction_id}]
  → scenario が gamedesign.SelectableFactions で validate
  → 不正なら 400 (REST 呼び出しなし、scenario 内で完結)
  → scenario: outbox に onboarding-faction-set (player_id, initial_faction_id) を enqueue
  → (eventual) account subscriber: selected_faction UPDATE + player_factions INSERT + onboarding_status='faction_set' を 1 tx で UPDATE

[ユーザーが scenario 本文を最後まで読む]

[scenario: POST /onboarding/complete (body 空)]
  → scenario: account.GetPlayer を呼んで selected_faction を取得 (PlayerOnboardedEvent payload 用)
  → scenario: scenario.player_onboarding INSERT + outbox に player-onboarded を enqueue (1 tx、ErrAlreadyOnboarded は PK 一意制約違反で検出)
  → (eventual) account subscriber: onboarding_status='completed' UPDATE
  → (eventual) card subscriber: GrantInitialPack(player_id, initial_faction_id)
```

### 8. ADR-022 / ADR-025 の supersede

ADR-025 / ADR-022 の本文は触らず、本 ADR で supersede 範囲を明記する。

#### 8.1 ADR-025 の supersede

- §1 「表示名確定経路を REST 同期書込に切替」→ 本 ADR §5 で **REST はバリデーション目的のみに縮退**。scenario のオンボード経路は `PUT /name` を呼ばなくなり `POST /name/validate` に置き換える。書き込みは `onboarding-name-set` event subscriber が行う
- §2.3 許容経路リスト「`PUT /internal/v1/players/:playerId/name`」→ scenario のオンボード経路からは呼ばなくなるが、エンドポイント自体は維持 (gateway 経由のクライアント名前変更で使用)。代わりに「`POST /internal/v1/players/:playerId/onboarding/name/validate`」を ADR-025 §2.1 の 3 条件 (即時 UX フィードバック / 業務真実 SSoT が呼び出し先 / gateway 経由不可) を満たす許容経路として追加する。「`GET /internal/v1/players/:playerId`」は本 ADR でも維持
- §3 「進行 checkpoint を account の業務カラム nullable から導出」→ 本 ADR §1 で撤回。専用カラム `onboarding_status` の参照に変更
- ADR-025 で導入した `GET /onboarding/resume` / `GET /onboarding/status` は本 ADR §3 で撤去

#### 8.2 ADR-022 の supersede

- §1 「scenario は onboarding 完了時に `PlayerOnboardedEvent` 1 本だけを publish する」→ 本 ADR §4.1 で **`onboarding-name-set` / `onboarding-faction-set` / `player-onboarded` の 3 本に拡張**。`PlayerOnboardedEvent` 自体は維持
- §1 副作用テーブル「account: `players.selected_faction` UPDATE + `player_factions` INSERT」→ 本 ADR §4.4 で `OnboardingFactionSetSubscriber` に移管。`PlayerOnboardedSubscriber` は `onboarding_status='completed'` UPDATE のみに縮退
- `PlayerOnboardedEvent` payload の `initial_faction_id` フィールドは維持 (本 ADR §4.3 / §5.3)

### トレードオフ

- account 側スキーマ変更 (カラム追加 + バリデーション) と既存 `player_onboarded_subscriber` の振る舞い変更を伴う
- Pub/Sub トピックが 2 本増える (`onboarding-name-set` / `onboarding-faction-set`)。account 側に新 subscriber 配線、IAM (publish/subscribe permission) 追加、k8s deployment / Pub/Sub 側 subscription 作成が必要
- scenario 側に新エンドポイント (`POST /onboarding/faction`) が追加される
- `PUT /onboarding/name` 受領時、scenario は account への REST validate を待ってから outbox publish するため、account 障害時に name 入力ステップが 5xx になる ([ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) のトレードオフと同等の依存関係。バリデーションが SSoT 集約の必然なので業務上の依存と等価)

## 不採用案

### 案 B: 専用カラム + 1 トピック (`onboarding-progress-changed`) + REST 直書込維持

- `onboarding_status` カラム追加までは採用案と同じ
- scenario が account の `PUT /name` / `PUT /faction` を REST 直書込し、別途 `onboarding-progress-changed (next_status)` を Pub/Sub publish

却下理由: account 側の書き込み経路が REST + Pub/Sub の 2 系統に分散したまま残り、業務データ (`name` / `selected_faction`) と進行 status の永続化が別 tx となる。「REST 成功 + outbox publish 失敗」の中間状態 (例: `players.name` は更新済みだが `onboarding_status` は `not_started` のまま) が発生し、subscriber 冪等性で吸収する必要がある。1 トピック化で payload と業務事実の対応も薄れる ([ADR-022](022-faction-selected-decomposition.md) 分解原則からの逆行)。

### 案 C: scenario 側に進行ステートテーブル `scenario.player_onboarding_progress` を追加

- 進行状態を scenario の責務として永続化 (`player_id`, `status`, `updated_at`)
- account は完了通知 (`player-onboarded`) のみ受信して既存通り処理

却下理由: 「ログイン時の status 取得」を scenario への RPC に依存させることになり、account の `GetPlayer` 1 RPC で済まない。クライアント観点では「player profile を取る」のに account と scenario の両方を呼ぶ非対称性が生じる。さらに状態の SSoT が account の identity (`name` / `selected_faction`) と scenario の進行ステートに二重存在し、整合性担保の仕組みが必要になる。

### 案 D: account の `name` / `selected_faction` を NOT NULL + sentinel 値で「未設定」を表現

- `name = '__pending__'` のような sentinel で未設定を表現し、NULL を「データ欠損 (異常)」専用にする

却下理由: sentinel は表示やバリデーションを必ずすり抜けて表面化する事故が発生する (空文字を許可しないバリデーションをすり抜ける、UI に誤って表示される、検索クエリで意図せずヒットする)。識別可能性のために sentinel を選ぶのは構造的に脆い。
