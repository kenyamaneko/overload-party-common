# Overload Party - データ設計 (Data Architecture)

## ID 設計方針

`player_id` をはじめとするユーザー関連の主キーには UUID（`gen_random_uuid()`）を採用している。連番 ID ではなく UUID を使う理由は、通信を傍受された場合に ID の値からゲーム数やユーザー数を推測されることを防ぐため。

ゲーム ID (`game_id`) には ULID を採用。時系列ソートが可能かつ衝突耐性が高い。

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
| Upstash Redis (Sorted Set) | マッチメイキングキュー | matchmaking |
| Cloud Pub/Sub (Exactly-Once) | マッチ成立イベント `matchmaking-events` | matchmaking → gateway |
| Cloud Pub/Sub (At-Least-Once) | ファクション選択イベント `faction-selected` | scenario, shop → account, card, gateway |
| Cloud Pub/Sub (At-Least-Once) | プレミアム状態変更 `premium-updated` | shop → account, gateway |
| Cloud Pub/Sub (At-Least-Once) | ニュース記事収集 `news-article-collected` | newsfeed → news |
| Google Cloud Storage | ストーリースクリプト | scenario |

matchmaking は RDB スキーマを持たない（Redis + Pub/Sub のみ）。

---

## スキーマ所有権マップ

| スキーマ | 所有サービス | テーブル |
|---|---|---|
| `account` | account | `players`, `player_daily_battle`, `player_factions`, `user_settings`, `processed_events` |
| `card` | card | `card_definitions`, `player_cards`, `decks`, `deck_cards`, `processed_events` |
| `shop` | shop | `products`, `subscriptions`, `one_time_purchases`, `cosmetic_items`, `player_items`, `player_owned_factions` |
| `scenario` | scenario | `scenario_episodes`, `episode_required_factions`, `player_story_progress` |
| `battle` | battle | `games`, `game_npcs`, `game_decks`, `game_states`, `game_actions`, `game_events` |
| `gateway` | gateway | `game_players` |
| `news` | news | `news_articles`, `news_article_translations` |
| `support` | support | `announcements`, `announcement_translations`, `inquiries` |

### ゲーム動的設定値 (Cloud Firestore)

サービス横断で参照する動的設定値（バトル上限数、経験値、タイムバンク等）は **Cloud Firestore (Native モード、asia-northeast1)** のコレクション `game_config` に格納する。ドキュメント ID = key、フィールド `value`（型は値ごとの number / string / bool）。各サービスは公式 Firestore クライアントから読み取り、キー不在は fail-fast。書き込みは運営オペレーター + ops SA に限定。

### 権限 (GRANT)

IAM 認証の権限付与 SQL は `ops/db-migrate/grant_iam.sql` が SSoT。

---

## 各テーブル詳細

各スキーマのテーブル設計は、所有サービスリポジトリの `docs/DATA_DESIGN.md` と `db/schema.sql` を参照。
