# Overload Party - データ設計 (Data Architecture)

## ID 設計方針

ID 採番方式は用途別に 4 分類する（詳細は [ADR-046](../adr/046-cross-repo-id-issuance-policy.md)）:

- **マスタデータ ID**: 人間可読 slug（`SH-0001` 等）。domain knowledge として人間が直接読み書きするため
- **対外露出する長寿命エンティティ ID**（`player_id` 等）: UUID v4。連番だと件数が、時系列 ID だと生成時刻が ID から推測できてしまうため、ランダムな UUID v4 で情報漏えいと enumeration を防ぐ
- **内部ログ / セッション / 履歴系 ID**（`game_id` 等）: UUID v7。append-heavy なテーブルで時系列挿入により B-tree を密に保ち、時間範囲クエリ・cursor pagination・障害調査に ID 単体で使えるようにする
- **Pub/Sub `event_id`**: UUID v4。subscriber の重複排除キー専用で時系列性は不要

slug を除く全 ID はアプリ側で採番し、ID 列は native `UUID` 型で宣言する。既存の ULID 採用箇所（news `article_id` / matchmaking `match_id`）は据え置き。

---

## スキーマ分割方針 (Service-owned Schemas)

Overload Party の RDB は **1 つの PostgreSQL インスタンスの上で、サービスごとに PostgreSQL スキーマを分離配置する** 構成を採る。物理インスタンスを分けずに論理境界だけを引く狙いは、Cloud SQL インスタンスを増やすコスト（固定費・運用・バックアップ）を避けつつ、将来的に物理 DB 分割へ進む際にアプリコードの書き換えが不要な状態を今から作っておくことにある。

基本ルール:

- 各サービスには専用の DB ユーザー（IAM サービスアカウント）が払い出され、**自分のスキーマに対してのみ** `USAGE` と CRUD 権限を持つ
- **書き込みは所有サービスのみ** が行う。このルールは DB 権限レベルで強制される
- **クロスサービスの read は所有サービスの REST API 経由** で行う
- スキーマ名は所有サービス名と揃える
- クロススキーマ FK は張らず、アプリ層整合性で担保する

---

## データストア配置マップ

| ストア | 用途 | 利用サービス |
|---|---|---|
| PostgreSQL (Cloud SQL) | サービス別スキーマによる永続化 | 各サービス |
| Cloud Firestore (Native, asia-northeast1) | サービス横断の動的設定値 `game_config` コレクション ([ADR-017](../adr/017-game-config-firestore.md)) | account, shop, battle, scenario, gateway |
| Upstash Redis (Sorted Set) | マッチメイキングキュー | matchmaking |
| Cloud Pub/Sub (Exactly-Once) | マッチ成立イベント `matchmaking-events` | matchmaking → gateway |
| Cloud Pub/Sub (At-Least-Once) | オンボーディング完了イベント `player-onboarded` ([ADR-022](../adr/022-faction-selected-decomposition.md)) | scenario → account, card |
| Cloud Pub/Sub (At-Least-Once) | カードパック購入イベント `card-pack-purchased` ([ADR-031](../adr/031-shop-products-normalization-and-faction-purchased-decomposition.md), [ADR-032](../adr/032-card-pack-introduction-and-grant-unification.md)) | shop → card |
| Cloud Pub/Sub (At-Least-Once) | ファクションアンロックイベント `faction-acquired` ([ADR-031](../adr/031-shop-products-normalization-and-faction-purchased-decomposition.md)) | shop → account |
| Cloud Pub/Sub (At-Least-Once) | プレミアム状態変更 `premium-updated` | shop → account |
| Cloud Pub/Sub (At-Least-Once) | ニュース記事収集 `news-article-collected` | newsfeed → news |
| Google Cloud Storage | ストーリースクリプト | scenario |

matchmaking は RDB スキーマを持たない（Redis + Pub/Sub のみ）。

---

## 定数／設定値の配置ルール

サービス横断で参照される値は、**変更頻度と参照形態**で 3 分類し、それぞれ置き場を分ける。

| 種類 | 性質 | 置き場 | SSoT | 変更反映 |
|---|---|---|---|---|
| ゲーム語彙 | コンパイル時固定。switch 判定・型判別子・DB 列値としてコードにリテラル参照される | common パッケージ配信 | `overload-party-common/data/{game_design_constants,factions}.yaml` → `scripts/generate_constants.py` で Go/C#/TS に codegen | パッケージ再配信（go get / nuget / npm） |
| 運営チューニング値 | 実行時に調整する動的値（バトル上限、経験値係数、タイムバンク等） | Cloud Firestore `game_config` コレクション | 初期値: `overload-party-common/data/game_config_defaults.yaml` / 運用中: Firestore が SSoT | 初期投入: `overload-party-ops/firestore-seed/seed_game_config.py`。運用中の変更: Google Cloud コンソール / Firestore admin SDK で即時反映（[ADR-017](../adr/017-game-config-firestore.md)） |
| サービス固有設定 | サービス単位・環境（dev/stg/prod）単位で変わる値（DB URL、`FIRESTORE_PROJECT_ID` 等） | env var | 各サービスの `internal/config/` + `overload-party-infra` が管理する Cloud Run の環境変数 | デプロイ |

### 判断の境界

- **コードが文字列リテラルを知っている必要があるか？** → Yes なら「ゲーム語彙」。タイポをコンパイルで捕まえる価値の方が、実行時の柔軟性より重い
- **運営がバランス調整で触るか？** → Yes なら「運営チューニング値」。PostgreSQL マイグレーション経由ではなく Firestore 書き込みで即時反映する
- **環境（dev/stg/prod）で値が変わるか？** → Yes なら env var。common にも Firestore にも置かない

### Firestore `game_config` の詳細

- コレクション `game_config`、ドキュメント ID = key、フィールド `value`（型は値ごとの number / string / bool）
- 各サービスは公式 Firestore クライアントから読み取る（Go: `cloud.google.com/go/firestore` / C#: `Google.Cloud.Firestore` / Python: `google-cloud-firestore`）
- キー不在は **fail-fast**（`port.ErrNotFound` を即伝播）
- 書き込みは運営オペレーター + ops SA のみ

---

## スキーマ所有権マップ

| スキーマ | 所有サービス | テーブル |
|---|---|---|
| `account` | account | `players`, `player_progression`, `player_daily_battle`, `battle_count_reversals`, `player_factions`, `player_settings`, `processed_events` |
| `card` | card | `card_definitions`, `player_cards`, `decks`, `deck_cards`, `processed_events` |
| `shop` | shop | `products`, `subscriptions`, `one_time_purchases`, `cosmetic_items`, `player_items`, `player_owned_factions` |
| `scenario` | scenario | `scenario_episodes`, `episode_required_factions`, `player_story_progress` |
| `battle` | battle | `games`, `game_npcs`, `game_decks`, `game_states`, `game_actions`, `game_events` |
| `gateway` | gateway | `game_players` |
| `news` | news | `news_articles`, `news_article_translations` |
| `support` | support | `announcements`, `announcement_translations`, `inquiries` |

### 権限 (GRANT)

IAM 認証の権限付与 SQL は `ops/db-migrate/grant_iam.sql` が SSoT。

---

## 各テーブル詳細

各スキーマのテーブル設計は、所有サービスリポジトリの `docs/DATA_DESIGN.md` と `db/schema.sql` を参照。
