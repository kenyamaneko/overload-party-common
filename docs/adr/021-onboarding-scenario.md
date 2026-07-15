# ADR-021: オンボーディングシナリオを scenario サービスに独立ユースケースとして実装し、transactional outbox で完了イベントを配信する

## ステータス

Proposed (2026-04-21)

本 ADR のイベント設計（オンボーディング完了時に 2 イベントを publish し、同一トランザクションで enqueue する部分）は [ADR-022](022-faction-selected-decomposition.md) で 1 イベント（`player-onboarded` のみ）に縮退した。表示名の扱い（`PlayerOnboardedEvent` payload に `display_name` を載せ、検証を scenario 側に置く部分）は [ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) で REST 同期書込に上書きされ、オンボーディング進行の管理は [ADR-026](026-onboarding-status-as-account-responsibility.md) で account に集約された。scenario 内の独立ユースケース化と transactional outbox 導入という中核の決定は有効。

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

## 不採用案

### 既存 `ScenarioEpisode` にオンボを乗せる（例: `episode_id = "onboarding"` の特殊行）

既存 `ListEpisodes` / `GetScript` / `CompleteEpisode` の配管を再利用し、`script_path = scripts/onboarding/{lang}.ks` の特殊エピソードとして登録する。

却下理由:

- unlock 判定モデル（level / required_factions / required_episodes）にオンボ固有の条件（「他の全エピソードはオンボ未完ならロック」など）を横串注入する必要があり、`checkUnlock` の純粋性が崩れる
- `GetScript` に完了ガードを足す必要があるが、通常エピソードは完了後も再読可能という既存仕様と衝突する。条件分岐で分けると「1 関数 1 責務」方針に反する
- `CompleteEpisode` に identity 副作用（display_name 書き込み / 初期 faction publish）を足すと、通常エピソード完了との責務境界が曖昧になる

### オンボーディング完了フラグを account 側に持たせる

account が `account.players.onboarded_at` を持ち、`CompleteOnboarding` 時に scenario → account 同期 RPC でフラグを書く。

却下理由:

- scenario の `CompleteOnboarding` トランザクションに account 可用性が巻き込まれる。account ダウン時にオンボ完了が受け付けられなくなる
- 「2 度目の POST を弾く」ためだけに同期 RPC を必要とし、scenario 単独で閉じられない。非同期イベントの思想と不整合
- scenario はスクリプト配信と完了記録の SSoT を同じテーブルで持てるのに、その整合性を account に委譲することで跨サービス整合の問題を自作する

### account の `username IS NOT NULL` を完了フラグとして流用

フラグテーブルを持たず、account の display_name が入っているかで判定する。

却下理由:

- 「表示名の有無」と「オンボーディング完了」は本来別の semantic であり、将来 display_name 変更機能や「表示名リセット」を入れたときに破綻する
- scenario が完了判定のために account に同期問い合わせする必要がある（「オンボーディング完了フラグを account 側に持たせる」案と同じ可用性問題）

### Outbox を導入せず、sequential publish で 2 イベントを発行

`INSERT player_onboarding` を commit した後、`Publish(player-onboarded)` → `Publish(faction-selected)` を順次実行する。既存 `FactionPublisher` と同じパターン。

却下理由:

- `player-onboarded` publish 成功 / `faction-selected` publish 失敗 の部分失敗で、account は username 更新済み / card は初期カード未配布という食い違いが発生する
- 「一度きり」の操作であり、再 POST は 409 で弾かれるため、クライアント主導のリトライでは復旧できない
- CLAUDE.md 「エラーを握りつぶさない / 根本解決する」方針に対し、部分失敗を「運用でカバー」に寄せるのは根本対処ではない

### イベントを 1 本に統合（`player-onboarded` のみ、`faction-selected` を廃止）

`player-onboarded` のペイロードに `initial_faction_id` を含め、card / gateway の `faction-selected` subscriber を `player-onboarded` に振り替える。

却下理由（ただし有力案で、採否は紙一重）:

- live publisher がまだ居ないため切り替えコスト自体は低い
- ただし faction 変更機能（将来追加される可能性のある「転籍」等）が入った場合、`faction-selected` は onboarding と独立に再発火する必要が生じる。そのたびにトピックを新設するより、最初から「faction 選択イベント」という粒度を保つ方が将来の再設計コストが低い
- [ADR-012](012-matchmaking-pubsub.md) の「イベントは業務上の 1 事実 1 トピック」の原則に照らし、`player-onboarded`（オンボ完了）と `faction-selected`（faction 選択）は別の事実として分離する
