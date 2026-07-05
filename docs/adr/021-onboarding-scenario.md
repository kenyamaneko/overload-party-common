# ADR-021: オンボーディングシナリオを scenario サービスに独立ユースケースとして実装し、transactional outbox で完了イベントを配信する

## ステータス

Proposed (2026-04-21)

**本 ADR の §5 (2 イベント publish) と §6.1 (2 イベント同一トランザクション enqueue) は [ADR-022](022-faction-selected-decomposition.md) で 1 イベント (`player-onboarded` のみ) に縮退する**。ADR-022 では `FactionSelectedEvent` を廃止し業務事実ベースで分解することで、onboarding 起因の faction 取得は `PlayerOnboardedEvent` 単体で表現され、shop 起因の faction 取得は新 `FactionPurchasedEvent` (topic: `faction-purchased`) に移る。結果として scenario は onboarding 完了時に `PlayerOnboardedEvent` 1 本のみ publish し、subscriber は account だけでなく card / gateway にも拡大する。本 ADR の他の節 (§1 サービス構造、§2 データモデル、§3 API 契約、§6.2 Publish 側 poller、§7 入力バリデーション 等) は引き続き有効。

**本 ADR の §5.1 (`player-onboarded` payload に `display_name` を載せる設計) と §7.2 (display_name のバリデーションを scenario 側 service 層に置く設計) は [ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) で部分的に上書きされる**。`PlayerOnboardedEvent` payload から `display_name` を撤去し、表示名はオンボード内 name 入力ステップで scenario が account の `PUT /internal/v1/players/:playerId/name` を同期 REST で呼んで確定する。バリデーション SSoT は account の `internal/model/name.go` に集約され、scenario 側で重ね書きしない。本 ADR の他の節 (テーブル設計、outbox 設計、faction 検証など) は引き続き有効。

## 結論

オンボーディングを scenario サービス内の **独立ユースケース** として実装し、既存 `ScenarioEpisode` 機構とはサービス層・テーブル・API・イベントいずれも分離する。完了に伴う 2 つのイベント publish を原子的に保証するため、scenario スキーマに **transactional outbox** を新設する。既存 `ScenarioEpisode` は「unlock 済みコンテンツを読む」ユースケースに専念でき、オンボ固有の例外が入らない。`scenario.player_onboarding` の PK 制約と outbox の同一トランザクション挿入により完了記録とイベント publish が atomic に保証されて部分失敗による詰みが消え、scenario はオンボ完了フラグとスクリプトの SSoT、account は identity の SSoT という分離が保たれる。faction 検証は `factions.yaml` → codegen → `SelectableFactions` の経路に一本化される。

> **既存設計文書との関係**: scenario の `docs/ARCHITECTURE.md` §「scenario が Outbox を持たない理由」および `docs/FEATURE_SPEC.md` §6.2 には「scenario は Transactional Outbox を持たない」と明記されている。これらは「DB 書き込み + publish を atomic に必要とする新規配線が出た時点で Outbox を導入し、その際は shop と同型の構造を再利用する」という将来条件を同時に記しており、本 ADR が扱うオンボーディング完了フロー（`scenario.player_onboarding` への INSERT + `player-onboarded` / `faction-selected` の 2 イベント publish）はまさにその条件に合致する。本 ADR の採用により、ARCHITECTURE.md 該当節と FEATURE_SPEC.md §6.2 は **更新される**（「Outbox を持つ」方針へ反転し、本 ADR を参照する）。更新は本 ADR 実装 PR 内で行う。

## 背景・課題

### 要件

ゲーム開始時、プレイヤーに一度だけ読ませる「オンボーディングシナリオ」を導入する。シナリオ読了に伴い以下の 2 つの副作用が同時に発生する:

- **表示名 (display_name) の登録**: プレイヤーが入力した名前を account サービスに保存する
- **初期 faction の選択**: プレイヤーが選んだ陣営を account / card / gateway に通知し、所持陣営と初期カード配布などの下流処理を走らせる

「一度だけ」であること、2 つの副作用が **同じユーザー操作から原子的に** 発生すること、そして再読込や再送信があっても状態が食い違わないことが要件である。

### 既存シナリオ機構との責務の差異

[ADR-014](014-db-schema-split-per-service.md) に基づき scenario サービスは `scenario` スキーマを所有し、`scenario.scenario_episodes` / `scenario.player_story_progress` で通常シナリオエピソードを管理している。既存エピソードは以下の特徴を持つ:

- プレイヤーの **現在状態（レベル / 所持 faction / 完了済みエピソード）に基づく unlock 判定** が入口（`internal/service/story/service.go` の `checkUnlock`）
- 完了しても本文は再読可能（`GetScript` は完了状態を参照しない）
- エピソード完了は **進行マーカーの記録のみ** で、プレイヤー identity には副作用を持たない

オンボーディングはこのいずれにも該当しない:

- **unlock 条件が逆転している**: faction もレベルも無い状態で最初に走るため、既存 unlock モデル（level / required_factions / required_episodes）に条件を注入できない
- **完了後は読ませない**: 「一度だけ」セマンティクス
- **副作用が identity に及ぶ**: display_name の書き込みと初期 faction の hand-off

既存の `ScenarioEpisode` に乗せるには、unlock 判定の例外注入、`GetScript` への完了ガード、`CompleteEpisode` の副作用分岐の 3 点を横串で組み込む必要があり、「一つの関数に複数の責務を負わせない」という CLAUDE.md 方針に反する。

### 既存 `NotifyInitialFactionSelected` の位置づけ

scenario には `Service.NotifyInitialFactionSelected`（`internal/service/story/service.go:110-118`）が実装済みで、`FactionPublisher` 経由で `faction-selected` を publish する想定だった。ただし:

- このメソッドは **REST router に配線されていない**（`internal/router/router.go` を参照）
- 本番コード内で呼び出している箇所はなく、テストのみ（`service_test.go`）に存在

つまり「初期 faction 選択」を駆動するエンドポイントはまだ存在せず、`faction-selected` の live publisher はいない。account / card / gateway 側の subscriber 配線のみが先行して整っている状態である。

### Outbox パターンの不在

現 `FactionPublisher` は Pub/Sub `Publish()` の ack を待つだけの単純な実装で、DB コミットと publish を atomic にまとめる仕組みは存在しない。これは `NotifyInitialFactionSelected` が live でなかったため顕在化していなかった。

オンボーディングは「一度きり」の操作であるため、DB への完了記録と publish の部分失敗が起きると:

- 完了記録のみ成功 → 再 POST は 409 で弾かれ、account / card は何も知らないままプレイヤーが詰む
- publish のみ成功（理論上は稀）→ 再送しようとしても完了記録が無いため 2 重発火の余地が残る

このリスクを解消する仕組みが必要である。

## 詳細

### 1. サービス構造

本 ADR の outbox 実装は **shop サービスで先行採用済みのパターン**（`overload-party-shop/internal/port/outbox.go`, `overload-party-shop/db/schema.sql` の `shop.outbox_events`）に揃える。scenario 独自の命名・配置は行わず、プロジェクト横断の一貫性を優先する。

```
internal/service/onboarding/
  service.go          OnboardingService
  errors.go           ErrAlreadyOnboarded / ErrInvalidFaction / ErrInvalidDisplayName / ErrScriptNotFound
internal/service/outbox/
  publisher.go        Outbox poller（claim → publish → mark/fail のオーケストレーション）
internal/port/
  onboarding_repo.go  OnboardingRepo（MarkComplete は OutboxEventBuilder を受け取り同一トランザクションで outbox 挿入）
  outbox.go           OutboxEvent / ClaimedOutboxEvent / OutboxEventBuilder / OutboxStore
internal/repository/postgres/
  onboarding_repo.go  PostgreSQL 実装
  outbox_repo.go      OutboxStore 実装（ClaimUnpublished / MarkPublished / RecordFailure）
internal/adapter/pubsub/
  publisher.go        薄い Pub/Sub ラッパ（topic map → Publish）
  event_builder.go    OutboxEventBuilder 実装（pubsubevents スキーマの詳細を閉じ込める）
internal/handler/worker/
  outbox_ticker.go    定期駆動エントリ（常駐 goroutine の起動とシャットダウン配線）
```

`OnboardingService` は既存 `story.Service` が再利用する `port.ScriptStore`（GCS / local）を共有し、スクリプト配信の配管を二重化しない。

### 2. データモデル

#### 2.1 `scenario.player_onboarding` テーブル

```sql
CREATE TABLE scenario.player_onboarding (
  player_id    UUID        NOT NULL,
  completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id)
);
```

- `PRIMARY KEY (player_id)` により 2 度目の `INSERT` は一意制約違反となり、`ErrAlreadyOnboarded` として 409 に昇格する
- display_name / faction_id は保存しない。publish 後は outbox が保持するため、scenario 側のスナップショットを持たない方が SSoT が一本化される（account が identity の SSoT）
- `scenario.player_story_progress` と同じ方針で、`player_id` は cross-schema 参照として FK は張らない（[ADR-014](014-db-schema-split-per-service.md) に準拠）

#### 2.2 `scenario.outbox_events` テーブル

shop の `shop.outbox_events` と **同一スキーマ** とする。カラム・インデックスを個別に最適化せず、運用・監視・コードレビューの認知負荷を下げる。

```sql
CREATE TABLE scenario.outbox_events (
  event_id          UUID         NOT NULL,                     -- payload 内 eventId と一致
  topic             VARCHAR(100) NOT NULL,                     -- Pub/Sub topic 名
  payload           JSONB        NOT NULL,                     -- JSON Marshal 済みイベント本体
  created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),       -- enqueue 日時
  published_at      TIMESTAMPTZ,                               -- NULL = 未配信
  failure_count     INT          NOT NULL DEFAULT 0,           -- 連続失敗回数
  last_error        TEXT,                                      -- 直近エラーメッセージ
  last_attempted_at TIMESTAMPTZ,                               -- 直近 publish 試行日時
  PRIMARY KEY (event_id)
);
CREATE INDEX idx_outbox_events_unpublished
  ON scenario.outbox_events (created_at)
  WHERE published_at IS NULL;
```

- `published_at IS NULL` の部分インデックスで未 publish 行だけを効率的に poll する
- `event_id` は `uuid.NewString()`（既存 publisher と揃える）
- `published_at` は publish 成功後に `UPDATE` する。失敗時は `failure_count` をインクリメントし `last_error` / `last_attempted_at` を記録した上で再試行対象として残る
- `failure_count` が閾値超過した行は claim 対象から自動的に外れ、監視・人手介入に委ねる
- 配信済み行は削除せず保持（監査・障害調査）。定期 purge は別 Issue で扱う
- subscriber 側の `<schema>.processed_events`（[ADR-012](012-matchmaking-pubsub.md) / ARCHITECTURE 参照）が `event_id` で重複排除するため、at-least-once で問題ない

#### 2.3 `data/models.yaml` に追加する型

```yaml
- name: OnboardingStatus
  comment: "OnboardingStatus indicates whether a player has completed onboarding."
  fields:
    - {name: PlayerID,    type: string,      json: "player_id"}
    - {name: Onboarded,   type: bool,        json: "onboarded"}
    - {name: CompletedAt, type: "*time.Time", json: "completed_at,omitempty"}

- name: OnboardingScriptResponse
  fields:
    - {name: Script, type: string, json: "script"}

- name: OnboardingCompleteRequest
  fields:
    - {name: DisplayName,      type: string, json: "display_name"}
    - {name: InitialFactionID, type: string, json: "initial_faction_id"}

- name: OnboardingCompleteResponse
  fields:
    - {name: Message,  type: string, json: "message"}
    - {name: PlayerID, type: string, json: "player_id"}
```

生成は `python3 scripts/generate_types.py` 経由で scenario 所有の `packages/api-scenario` に出力される。手書き編集は禁止（CLAUDE.md）。

### 3. API 契約

`data/endpoints.yaml` に以下のエンドポイント群を追加する。パスは既存シナリオと対称的な `/internal/v1/players/:playerId/onboarding/...` 配下に置く。

| Method | Path | 用途 | 主なエラー |
|---|---|---|---|
| GET  | `/internal/v1/players/:playerId/onboarding/status` | クライアント起動時のオンボ画面表示判定 | 500 |
| GET  | `/internal/v1/players/:playerId/onboarding/script?lang=ja\|en` | 本文取得 | 409 already_onboarded / 404 script_not_found |
| POST | `/internal/v1/players/:playerId/onboarding/complete` | 完了登録 + 2 イベント publish | 400 invalid_input / 409 already_onboarded |

- 認証は既存シナリオと同様に ClusterIP + URL `playerId` 信頼（CLAUDE.md 「クライアント認証を行わない」）
- 言語フォールバックなし（`scripts/onboarding/{lang}.ks` 不在なら 404）。既存 `readScript` のロジックをそのまま再利用する
- API_REFERENCE.md は `endpoints.yaml` から生成されるため手書き更新は不要

### 4. スクリプト配置

GCS 上の既存 `ScriptStore` にて以下のパスに配置する:

```
scripts/onboarding/ja.ks
scripts/onboarding/en.ks
```

既存 `stories/{lang}/*.ks`（[FEATURE_SPEC.md §2](../../../overload-party-scenario/docs/FEATURE_SPEC.md) の `script_path` 規約）とは別ツリーに置き、検索・管理の視線を分離する。`ScriptStore` port の実装は変更しない（key を受け取って bytes を返すだけの単機能）。

スクリプト本文は KAG 系の `.ks` フォーマットで記述され、サーバは opaque なバイト列として client に渡す。スクリプト内の選択肢・入力フィールドの表現方法（「選んだ時点では確定せず、読了後の `POST /onboarding/complete` で初めて送信する」セマンティクスを `.ks` 上でどう表現するか）は本 ADR のスコープ外で、**別 ADR で扱う**。サーバ側契約（endpoint / outbox / DB）は client パーサ仕様と独立に実装可能。

### 5. イベント契約

`CompleteOnboarding` は以下の 2 イベントを **同一トランザクションで outbox に挿入** する。outbox poller は `published_at IS NULL` を順に publish する。

#### 5.1 `player-onboarded`（新トピック、subscriber: account）

```json
{
  "event_id":           "uuid-v4",
  "player_id":          "uuid",
  "display_name":       "...",
  "initial_faction_id": "SHE | Tenki | Sugar | Tuners",
  "occurred_at":        "2026-04-21T..."
}
```

account は受信して `account.players.display_name` と所持 faction を更新する。`processed_events` で dedup。

#### 5.2 `faction-selected`（既存トピック、subscriber: account / card / gateway）

既存の `FactionPublisher` ペイロード形式（`player_id` / `faction_id` / `event_id` / `occurred_at`）を踏襲する。card は初期カード配布、gateway は購読していれば client 側通知、account は（`player-onboarded` と併せて）冪等に所持 faction を更新する。

account は 2 イベントを受け取りうるが、同じプレイヤーに対して faction_id は不変であり、処理は冪等なので問題ない。

### 6. Transactional outbox の実装方針

shop の実装（`overload-party-shop/internal/service/outbox/publisher.go`, `overload-party-shop/internal/repository/postgres/outbox_repo.go`）を参照実装として踏襲する。port インターフェース・SQL クエリ構造・visibility timeout 方式をそのまま移植し、scenario 固有の改変は加えない。

#### 6.1 書き込み側（scenario service）

`OnboardingRepo.MarkComplete` は `OutboxEventBuilder` で構築した 2 件の `OutboxEvent` を受け取り、ビジネス行の INSERT と outbox の INSERT を同一トランザクションで実行する:

```go
// 擬似コード
func (s *OnboardingService) Complete(ctx, playerID, displayName, factionID) error {
    evPlayerOnboarded, err := s.eventBuilder.BuildPlayerOnboarded(playerID, displayName, factionID)
    if err != nil { return err }
    evFactionSelected, err := s.eventBuilder.BuildFactionSelected(playerID, factionID)
    if err != nil { return err }

    return s.repo.MarkComplete(ctx, playerID, evPlayerOnboarded, evFactionSelected)
}

func (r *PostgresOnboardingRepo) MarkComplete(ctx, playerID, events ...port.OutboxEvent) error {
    return r.db.BeginTx(ctx, func(tx) error {
        if _, err := tx.Exec(`INSERT INTO scenario.player_onboarding (player_id) VALUES ($1)`, playerID); err != nil {
            if isUniqueViolation(err) { return port.ErrAlreadyOnboarded }
            return err
        }
        for _, ev := range events {
            if err := r.outbox.EnqueueTx(tx, ev); err != nil { return err }
        }
        return nil
    })
}
```

`OutboxEventBuilder` は shop と同じく `BuildFactionSelected(playerID, faction)` を持ち、本 ADR で `BuildPlayerOnboarded(playerID, displayName, factionID)` を追加する。scenario の `pubsubevents` スキーマ詳細は `adapter/pubsub/event_builder.go` 内に閉じる。

#### 6.2 Publish 側（outbox poller）

`internal/service/outbox/publisher.go` が常駐 goroutine として以下を繰り返す（shop と同一フロー）:

1. `OutboxStore.ClaimUnpublished(ctx, limit, visibilityTimeout, failureThreshold)` で未配信行を claim
2. 各行について `adapter/pubsub.Publisher.Publish(topic, payload)` を実行
3. 成功 → `OutboxStore.MarkPublished(eventID)` / 失敗 → `OutboxStore.RecordFailure(eventID, errMsg)`

`ClaimUnpublished` の SQL は shop と同じ CTE + `FOR UPDATE SKIP LOCKED`:

```sql
WITH claimed AS (
  SELECT event_id FROM scenario.outbox_events
  WHERE published_at IS NULL
    AND failure_count < $3
    AND (last_attempted_at IS NULL OR last_attempted_at < now() - $2::interval)
  ORDER BY created_at
  LIMIT $1
  FOR UPDATE SKIP LOCKED
)
UPDATE scenario.outbox_events o
  SET last_attempted_at = now()
FROM claimed c
WHERE o.event_id = c.event_id
RETURNING o.event_id, o.topic, o.payload, o.failure_count;
```

- `FOR UPDATE SKIP LOCKED` により複数 scenario Pod が走っても多重 publish は発生しない
- `visibilityTimeout` と `failureThreshold` は `internal/handler/worker/outbox_ticker.go` の起動時に env 経由で注入（shop の値と揃える）
- publish 失敗は `RecordFailure` で永続化し、閾値超過した行は自動的に claim 対象外となる。握りつぶさず log + metrics に出す（CLAUDE.md 「エラーを握りつぶさない」）
- poll 間隔は 500ms 〜 1s を想定（onboarding は低頻度イベントなので遅延許容）

#### 6.3 運用観測

shop と同じメトリクス名体系に揃える（サービス名プレフィックスのみ差し替え）:

- `scenario_outbox_unpublished_gauge`: `published_at IS NULL` の行数
- `scenario_outbox_oldest_unpublished_seconds`: 最古の未 publish 行の経過時間
- `scenario_outbox_publish_errors_total`: publish 失敗カウンタ
- `scenario_outbox_failure_threshold_exceeded_gauge`: `failure_count >= threshold` の行数（人手介入が必要な行）

メトリクス実装は別 Issue で具体化するが、本 ADR で観測項目を明示しておく。

### 7. 入力バリデーション

#### 7.1 faction 検証

`initial_faction_id` は **[overload-party-common の `factions.yaml` codegen による `packages/game-design-constants.SelectableFactions`](../../packages/game-design-constants/constants_gen.go)** に対して membership を検証する。

- `is_collectible=false` の `Neutral` を選択不可にする仕様が codegen フィルタとして自動導出されるため、service 層で重ね書きしない
- Firestore `game_config`（[ADR-017](017-game-config-firestore.md)）は faction 列挙を持たず、ゲームバランス値（バトル上限・経験値など）の KV のみ。本検証で `game_config` は参照しない
- schema.sql 側に置かれている `CHECK (faction IN (...))` のハードコード列挙は既存テーブル (`scenario_episodes` / `episode_required_factions`) に残っているが、本 ADR の新テーブルでは CHECK を持たず、service 層の `SelectableFactions` 検証に一元化する

#### 7.2 display_name 検証

- **長さ・文字種のみ service 層で検証**（MVP 仕様は別 Issue で具体化）
- **一意性は要件に入れない**。playerID が identity の SSoT であり、表示名は衝突してよい
- 将来一意性が必要になれば account 側で制約を追加し、scenario は publish するだけの責務を保つ

### 8. 既存 `NotifyInitialFactionSelected` の削除

オンボーディング導入により、初期 faction 選択は `CompleteOnboarding` 内から `faction-selected` を publish することで完結する。以下を本 ADR 採用と同じ PR で削除する:

- `internal/service/story/service.go` の `NotifyInitialFactionSelected` メソッド
- `internal/service/story/service_test.go` の対応テストケース
- `Service` コンストラクタから `FactionPublisher` 引数を外し、`OnboardingService` 側に配線し直す（`story.Service` は publisher を持たない方が責務として素直）

`NotifyInitialFactionSelected` は router に未配線のため、外部互換性を壊す影響はない。

### トレードオフ

- **outbox インフラの新設**: `scenario.outbox_events` テーブルと poller goroutine が追加される。scenario の運用対象が「DB + GCS + Pub/Sub + outbox」に増える。ただし shop で先行採用済みの実装パターン（`shop.outbox_events` / `OutboxStore` / `service/outbox/publisher.go`）を踏襲するため、プロジェクト全体では 2 サービス目の採用であり、テンプレートが確立されている。将来 `ScenarioComplete` など他の副作用付き完了処理にも流用できる
- **publish 遅延**: outbox poll 間隔分（500ms〜1s 想定）の遅延が入る。onboarding は低頻度・非リアルタイムなので許容範囲
- **scenario スキーマの所有範囲拡大**: identity 関連イベントの中継（display_name の受け渡し）を scenario が担うことで、「scenario = ストーリー配信」の直感から微妙にはみ出す。ただし identity データを **持たず通過させるだけ** なので SSoT は account のまま
- **event_id 生成の統一漏れ**: 他サービス（matchmaking 等）では ULID を使うケースがあるが、scenario は既存 `FactionPublisher` と揃えて `uuid.NewString()` を継続する。将来的にプラットフォーム横断で統一する動きが出たら別 ADR で扱う
- **API 定数化の負債は本 ADR では解消しない**: `internal/router/router.go` にはエンドポイントパスが直書きされている。CLAUDE.md「API 契約はリテラルで書かない」方針との乖離は既存論点であり、本 ADR では onboarding エンドポイントの追加のみを行い、定数化は別 Issue で扱う

## 不採用案

### 案 1: 既存 `ScenarioEpisode` にオンボを乗せる（例: `episode_id = "onboarding"` の特殊行）

既存 `ListEpisodes` / `GetScript` / `CompleteEpisode` の配管を再利用し、`script_path = scripts/onboarding/{lang}.ks` の特殊エピソードとして登録する。

却下理由:

- unlock 判定モデル（level / required_factions / required_episodes）にオンボ固有の条件（「他の全エピソードはオンボ未完ならロック」など）を横串注入する必要があり、`checkUnlock` の純粋性が崩れる
- `GetScript` に完了ガードを足す必要があるが、通常エピソードは完了後も再読可能という既存仕様と衝突する。条件分岐で分けると「1 関数 1 責務」方針に反する
- `CompleteEpisode` に identity 副作用（display_name 書き込み / 初期 faction publish）を足すと、通常エピソード完了との責務境界が曖昧になる

### 案 2: オンボーディング完了フラグを account 側に持たせる

account が `account.players.onboarded_at` を持ち、`CompleteOnboarding` 時に scenario → account 同期 RPC でフラグを書く。

却下理由:

- scenario の `CompleteOnboarding` トランザクションに account 可用性が巻き込まれる。account ダウン時にオンボ完了が受け付けられなくなる
- 「2 度目の POST を弾く」ためだけに同期 RPC を必要とし、scenario 単独で閉じられない。非同期イベントの思想と不整合
- scenario はスクリプト配信と完了記録の SSoT を同じテーブルで持てるのに、その整合性を account に委譲することで跨サービス整合の問題を自作する

### 案 3: account の `username IS NOT NULL` を完了フラグとして流用

フラグテーブルを持たず、account の display_name が入っているかで判定する。

却下理由:

- 「表示名の有無」と「オンボーディング完了」は本来別の semantic であり、将来 display_name 変更機能や「表示名リセット」を入れたときに破綻する
- scenario が完了判定のために account に同期問い合わせする必要がある（案 2 と同じ可用性問題）

### 案 4: Outbox を導入せず、sequential publish で 2 イベントを発行

`INSERT player_onboarding` を commit した後、`Publish(player-onboarded)` → `Publish(faction-selected)` を順次実行する。既存 `FactionPublisher` と同じパターン。

却下理由:

- `player-onboarded` publish 成功 / `faction-selected` publish 失敗 の部分失敗で、account は username 更新済み / card は初期カード未配布という食い違いが発生する
- 「一度きり」の操作であり、再 POST は 409 で弾かれるため、クライアント主導のリトライでは復旧できない
- CLAUDE.md 「エラーを握りつぶさない / 根本解決する」方針に対し、部分失敗を「運用でカバー」に寄せるのは根本対処ではない

### 案 5: イベントを 1 本に統合（`player-onboarded` のみ、`faction-selected` を廃止）

`player-onboarded` のペイロードに `initial_faction_id` を含め、card / gateway の `faction-selected` subscriber を `player-onboarded` に振り替える。

却下理由（ただし有力案で、採否は紙一重）:

- live publisher がまだ居ないため切り替えコスト自体は低い
- ただし faction 変更機能（将来追加される可能性のある「転籍」等）が入った場合、`faction-selected` は onboarding と独立に再発火する必要が生じる。そのたびにトピックを新設するより、最初から「faction 選択イベント」という粒度を保つ方が将来の再設計コストが低い
- [ADR-012](012-matchmaking-pubsub.md) の「イベントは業務上の 1 事実 1 トピック」の原則に照らし、`player-onboarded`（オンボ完了）と `faction-selected`（faction 選択）は別の事実として分離する
