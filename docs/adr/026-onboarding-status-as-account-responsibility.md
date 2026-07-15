# ADR-026: オンボーディング進行状態を account の専用カラムで保持し、書き込みは Pub/Sub 経由に統一する (REST はバリデーション目的のみ)

## ステータス

Accepted (2026-04-26)

本 ADR は [ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) の表示名確定を REST 同期書込に切り替える決定と、オンボーディング進行の業務真実を account に集約する決定（業務カラム `Name` / `SelectedFaction` の nullable から進行を導出する設計）を上書きする。account に専用カラム `onboarding_status` を追加し、scenario が業務事実ごとに 3 トピック (`onboarding-name-set` / `onboarding-faction-set` / `player-onboarded`) を publish して account が subscribe する形に切り替える。account の REST はバリデーション目的のみに縮退し、業務データの書き込みはすべて Pub/Sub subscriber 経由に統一する。これに伴い [ADR-022](022-faction-selected-decomposition.md) で account subscriber の副作用としていた `PlayerOnboardedEvent` の処理 (account の `players.selected_faction` UPDATE + `player_factions` INSERT) を `onboarding-faction-set` 側へ移管し、`player-onboarded` は完了 status 遷移のみに縮退する。`PlayerOnboardedEvent` payload の `initial_faction_id` は維持する (card subscriber の `GrantInitialPack` で必要なため)。

## 結論

業務カラムの NULL 兼用では「オンボード未完了」と「データ消失」を区別できないため、`account.players` に専用カラム `onboarding_status` を追加し、オンボード進行を業務事実ごとの 3 トピック (`onboarding-name-set` / `onboarding-faction-set` / `player-onboarded`) で account に伝搬する。account の REST はバリデーション目的のみ (`POST /onboarding/name/validate`) に縮退する。`name IS NULL` の発生は異常検知の対象として独立に扱えるようになり、identity カラムがオンボード進行管理の責務から解放される。account 側の書き込み経路は Pub/Sub subscriber 1 系統に統一されて業務データと進行 status の永続化が同一 tx で原子的に行われ、REST 成功 + 後続処理失敗の中間状態が消滅する。1 event = 1 業務事実の原則 ([ADR-022](022-faction-selected-decomposition.md)) が維持され、ログイン時の status 取得は account の `GetPlayer` 1 RPC で完結する。

## 背景・課題

### 業務カラム NULL 兼用の構造的欠陥

[ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) の「オンボーディング進行の業務真実は account に集約」では、オンボーディング再開判定を account の業務カラム (`players.name` / `players.selected_faction`) の nullable 状態から導出する設計を採用した。これは「業務真実から導出する」点で SSoT 原則に沿うが、**`name IS NULL` が「未入力 (オンボード未完了)」と「データ消失 (運用事故・移行ミス・障害)」のどちらを意味するか区別できない**という構造的欠陥を抱えている。

具体的な実害:

- 完了済みプレイヤーが事故で `players.name` を失った場合、resume API が `started` を返してオンボード画面に逆戻りさせる
- 「完了マークがあるのに業務データが欠けている」という矛盾を派生値方式では構造的に表現できず、データ消失の能動検知ができない
- `players.name` のスキーマが「オンボーディング進行の合図」と「表示名カラム」という独立した 2 つの責務を兼任している

### ADR-025 の REST 直書込で発生する責務混合

[ADR-025](025-onboarding-name-via-rest-and-cross-service-http.md) の REST 同期書込設計では scenario が account の `PUT /internal/v1/players/:playerId/name` を REST 同期書込で呼ぶ。これにより account 側の書き込み経路は **REST 直書込 + Pub/Sub subscriber 駆動** の 2 系統に分かれ、進行状態 (本 ADR で導入する `onboarding_status`) と name の永続化が別 tx となる。

REST 直書込の動機を分解すると、scenario が REST に依存する理由は **「account の `internal/model/name.go` (`MaxNameRunes=20`、空 / 全空白 / 制御文字 NG) のバリデーション結果を即時にユーザーへ返す」** という UX 要件のみであり、「name を account に永続化する」こと自体は Pub/Sub event でも成立する。バリデーションと書き込みを 1 つの REST でまとめていることが責務混合の起点である。

faction 側 (本 ADR で扱う `POST /onboarding/faction` 新設) については、バリデーション SSoT が `gamedesign.SelectableFactions` (共有定数 `overload-party-common/packages/game-design-constants`) であり、scenario 側で同等の検証が可能なので REST すら不要である。

### ADR-022 の業務事実分解原則との整合

[ADR-022](022-faction-selected-decomposition.md) では旧 `FactionSelectedEvent` を業務事実 (`PlayerOnboardedEvent` / `FactionPurchasedEvent`) に分解した。この「**1 event = 1 業務事実**」原則を本 ADR にも適用すると、オンボード進行は次の 3 つの独立した業務事実に分解できる:

- 名前入力ステップ完了 (player_id, name)
- faction 選択ステップ完了 (player_id, initial_faction_id)
- オンボーディング完了 (player_id, initial_faction_id を含む完了 snapshot)

これらを 1 トピック (`onboarding-progress-changed` のような汎用トピック) に集約し payload 内 `next_status` で分岐させると、payload と業務事実の対応が薄れ、ADR-022 の分解原則を逆行する。3 つを独立したトピックとして表現するほうが業務契約が明確になる。

## 不採用案

### 専用カラム + 1 トピック (`onboarding-progress-changed`) + REST 直書込維持

- `onboarding_status` カラム追加までは採用案と同じ
- scenario が account の `PUT /name` / `PUT /faction` を REST 直書込し、別途 `onboarding-progress-changed (next_status)` を Pub/Sub publish

却下理由: account 側の書き込み経路が REST + Pub/Sub の 2 系統に分散したまま残り、業務データ (`name` / `selected_faction`) と進行 status の永続化が別 tx となる。「REST 成功 + outbox publish 失敗」の中間状態 (例: `players.name` は更新済みだが `onboarding_status` は `not_started` のまま) が発生し、subscriber 冪等性で吸収する必要がある。1 トピック化で payload と業務事実の対応も薄れる ([ADR-022](022-faction-selected-decomposition.md) 分解原則からの逆行)。

### scenario 側に進行ステートテーブル `scenario.player_onboarding_progress` を追加

- 進行状態を scenario の責務として永続化 (`player_id`, `status`, `updated_at`)
- account は完了通知 (`player-onboarded`) のみ受信して既存通り処理

却下理由: 「ログイン時の status 取得」を scenario への RPC に依存させることになり、account の `GetPlayer` 1 RPC で済まない。クライアント観点では「player profile を取る」のに account と scenario の両方を呼ぶ非対称性が生じる。さらに状態の SSoT が account の identity (`name` / `selected_faction`) と scenario の進行ステートに二重存在し、整合性担保の仕組みが必要になる。

### account の `name` / `selected_faction` を NOT NULL + sentinel 値で「未設定」を表現

- `name = '__pending__'` のような sentinel で未設定を表現し、NULL を「データ欠損 (異常)」専用にする

却下理由: sentinel は表示やバリデーションを必ずすり抜けて表面化する事故が発生する (空文字を許可しないバリデーションをすり抜ける、UI に誤って表示される、検索クエリで意図せずヒットする)。識別可能性のために sentinel を選ぶのは構造的に脆い。
