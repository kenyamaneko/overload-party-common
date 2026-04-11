-- Overload Party - PostgreSQL DDL (SSoT)
-- All tables with foreign keys and indexes
--
-- Schema layout (ADR-014): 各サービスが自スキーマを所有し、他サービスは API 経由で参照する。
-- スキーマ越境 FK はアプリ層整合性に委ねて張らない。
--
--   shared    : 全サービス read-only の共通設定
--   account   : プレイヤーアカウント (overload-party-account)
--   card      : カードマスター / 所持 / デッキ (overload-party-card)
--   shop      : 商品 / 購入 / アイテム (overload-party-shop)
--   scenario  : ストーリーエピソード / 進捗 (overload-party-scenario)
--   battle    : ゲーム実行時状態 / アクション / イベント (overload-party-battle)
--   newsfeed  : ニュースフィード (overload-party-newsfeed)

-- =============================================================================
-- Schemas
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS shared;
CREATE SCHEMA IF NOT EXISTS account;
CREATE SCHEMA IF NOT EXISTS card;
CREATE SCHEMA IF NOT EXISTS shop;
CREATE SCHEMA IF NOT EXISTS scenario;
CREATE SCHEMA IF NOT EXISTS battle;
CREATE SCHEMA IF NOT EXISTS newsfeed;

-- =============================================================================
-- Shared: updated_at auto-update trigger function
-- =============================================================================

CREATE OR REPLACE FUNCTION shared.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 4.1 Game Management (schema: battle)
-- =============================================================================

CREATE TABLE battle.games (
  game_id              VARCHAR(26) NOT NULL,           -- ULID
  status               VARCHAR(20) NOT NULL,           -- 'waiting' / 'playing' / 'finished'
  first_player         SMALLINT NOT NULL,              -- 先攻プレイヤー番号 (1 or 2)
  winning_player_num   SMALLINT,                       -- NULL=進行中, 0=引分, 1=P1勝, 2=P2勝
  win_reason           TEXT,                           -- 'budget_zero', 'turn_timeout' 等
  engine_version       TEXT NOT NULL DEFAULT '',        -- バトルエンジンバージョン（ゲーム作成時に記録）
  card_data_version    TEXT NOT NULL DEFAULT '',        -- カードデータバージョン（ゲーム作成時に記録）
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(), -- 作成日時
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(), -- 更新日時
  finished_at          TIMESTAMPTZ,                    -- 終了日時
  PRIMARY KEY (game_id)
);

CREATE INDEX idx_games_status ON battle.games(status, created_at DESC);
CREATE TRIGGER trg_games_updated_at BEFORE UPDATE ON battle.games FOR EACH ROW EXECUTE FUNCTION shared.update_updated_at();

-- 4.1a Game NPC Settings (child of games, NPC 戦のみ。PvP では行なし)

CREATE TABLE battle.game_npcs (
  game_id       VARCHAR(26) NOT NULL REFERENCES battle.games(game_id), -- 親テーブル参照
  player_num    SMALLINT NOT NULL,              -- NPC が座っているスロット番号 (1 or 2)
  npc_model     VARCHAR NOT NULL,               -- NPC モデル名
  PRIMARY KEY (game_id, player_num)
);

-- 4.1b Game Decks (child of games, 常に 2 行)

CREATE TABLE battle.game_decks (
  game_id        VARCHAR(26) NOT NULL REFERENCES battle.games(game_id), -- 親テーブル参照
  player_num     SMALLINT NOT NULL,             -- 1 or 2
  deck_snapshot  JSONB NOT NULL,                -- デッキスナップショット
  PRIMARY KEY (game_id, player_num)
);

-- 4.1c Game Players (child of games, 人間スロットのみ。Gateway が書き込む)

CREATE TABLE battle.game_players (
  game_id       VARCHAR(26) NOT NULL REFERENCES battle.games(game_id), -- 親テーブル参照
  player_num    SMALLINT NOT NULL,              -- 人間が座っているスロット番号 (1 or 2)
  player_id     UUID NOT NULL,                  -- プレイヤー ID (cross-schema reference to account.players; app-level integrity, not enforced by FK)
  exp_awarded   BOOLEAN NOT NULL DEFAULT FALSE, -- 経験値付与済みフラグ（二重付与防止）
  PRIMARY KEY (game_id, player_num)
);

CREATE INDEX idx_game_players_player_id ON battle.game_players(player_id);

-- 4.2 Game State (child of games, 1:1)

CREATE TABLE battle.game_states (
  game_id              VARCHAR(26) PRIMARY KEY REFERENCES battle.games(game_id) ON DELETE CASCADE, -- 親テーブル参照
  initial_state        JSONB NOT NULL DEFAULT '{}',  -- ゲーム開始時の初期状態スナップショット（作成後は上書きされない）
  version              BIGINT NOT NULL,              -- 楽観的ロック用バージョン
  current_turn         BIGINT NOT NULL,              -- 現在ターン数
  current_phase        VARCHAR(20) NOT NULL,         -- 'draw' / 'main' / 'battle' / 'end'
  active_player        BIGINT NOT NULL,              -- 現在のターンプレイヤー (1 or 2)
  player1_budget       BIGINT NOT NULL,              -- Player 1 Budget
  player1_insight_pool BIGINT NOT NULL,              -- Player 1 Insight Pool
  player1_field        JSONB NOT NULL,               -- Player 1 フィールド上のカード
  player1_hand         JSONB NOT NULL,               -- Player 1 手札
  player1_repository   JSONB NOT NULL,               -- Player 1 リポジトリ（山札）
  player1_trash        JSONB NOT NULL,               -- Player 1 トラッシュ
  player1_time_bank    BIGINT NOT NULL,              -- Player 1 残り時間
  player2_budget       BIGINT NOT NULL,              -- Player 2 Budget
  player2_insight_pool BIGINT NOT NULL,              -- Player 2 Insight Pool
  player2_field        JSONB NOT NULL,               -- Player 2 フィールド上のカード
  player2_hand         JSONB NOT NULL,               -- Player 2 手札
  player2_repository   JSONB NOT NULL,               -- Player 2 リポジトリ（山札）
  player2_trash        JSONB NOT NULL,               -- Player 2 トラッシュ
  player2_time_bank    BIGINT NOT NULL,              -- Player 2 残り時間
  chain_stack          JSONB,                        -- 現在積まれているチェーンスタック
  current_action_timer BIGINT,                       -- アクションタイマー
  next_instance_seq    BIGINT NOT NULL DEFAULT 0,    -- インスタンスID発番用シーケンス
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now() -- 更新日時
);
CREATE TRIGGER trg_game_states_updated_at BEFORE UPDATE ON battle.game_states FOR EACH ROW EXECUTE FUNCTION shared.update_updated_at();

-- Game Actions (child of games, append-only action log)

CREATE TABLE battle.game_actions (
  game_id     VARCHAR(26) NOT NULL REFERENCES battle.games(game_id) ON DELETE CASCADE, -- 親テーブル参照
  seq         INT NOT NULL,                          -- アクション連番
  player_num  SMALLINT NOT NULL,                     -- アクション実行プレイヤー番号 (1 or 2)
  action_type TEXT NOT NULL,                         -- アクション種別（play_card, attack, scale_up 等）
  action_data JSONB NOT NULL,                        -- アクションの入力データ
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),    -- 記録日時
  PRIMARY KEY (game_id, seq)
);

-- 4.3 Game Events (child of games)

CREATE TABLE battle.game_events (
  game_id         VARCHAR(26) NOT NULL REFERENCES battle.games(game_id) ON DELETE CASCADE, -- 親テーブル参照
  sequence_number BIGINT NOT NULL,                   -- イベント連番
  event_type      VARCHAR(50) NOT NULL,              -- イベント種別
  player_num      SMALLINT,                          -- NULL=system event, 1 or 2=プレイヤーイベント
  event_data      JSONB NOT NULL,                    -- イベント詳細データ
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(), -- 発生日時
  PRIMARY KEY (game_id, sequence_number)
);

-- =============================================================================
-- 4.4 Player Management (schema: account)
-- =============================================================================

CREATE TABLE account.players (
  player_id          UUID NOT NULL DEFAULT gen_random_uuid(), -- UUID
  firebase_uid       VARCHAR(128) NOT NULL,          -- Firebase Auth UID (Unique)
  username           VARCHAR(50) NOT NULL,           -- 表示名
  level              BIGINT NOT NULL DEFAULT 1,      -- レベル (Default: 1)
  exp                BIGINT NOT NULL DEFAULT 0,      -- 経験値 (Default: 0)
  is_premium         BOOLEAN NOT NULL,               -- 課金ステータス
  equipped_icon_no   BIGINT,                         -- 装備中アイコン番号（NULL: デフォルト）
  selected_faction   VARCHAR(20),                    -- 選択済みファクション
  premium_expires_at TIMESTAMPTZ,                    -- サブスク有効期限
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(), -- 作成日時
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(), -- 更新日時
  PRIMARY KEY (player_id)
);

CREATE UNIQUE INDEX idx_players_firebase_uid ON account.players(firebase_uid);
CREATE TRIGGER trg_players_updated_at BEFORE UPDATE ON account.players FOR EACH ROW EXECUTE FUNCTION shared.update_updated_at();

-- player_daily_battle (child of players, 1:1)

CREATE TABLE account.player_daily_battle (
  player_id          UUID PRIMARY KEY REFERENCES account.players(player_id) ON DELETE CASCADE, -- 親テーブル参照
  daily_battle_count BIGINT NOT NULL,                -- 本日のバトル回数
  last_reset_date    DATE NOT NULL                   -- 最終リセット日
);

ALTER TABLE account.players
  ADD CONSTRAINT chk_players_selected_faction
    CHECK (selected_faction IS NULL OR selected_faction IN ('SHE', 'Tenki', 'Sugar', 'Tuners', 'Neutral'));

-- =============================================================================
-- 4.5 Player Factions (陣営所持の中間テーブル, schema: account)
-- =============================================================================

CREATE TABLE account.player_factions (
  player_id   UUID NOT NULL REFERENCES account.players(player_id) ON DELETE CASCADE, -- 親テーブル参照
  faction     VARCHAR(20) NOT NULL CHECK (faction IN ('SHE', 'Tenki', 'Sugar', 'Tuners', 'Neutral')), -- 陣営名 (SHE / Tenki / Sugar / Tuners / Neutral)
  source      VARCHAR(20) NOT NULL CHECK (source IN ('initial_selection', 'shop_purchase')), -- 取得経路 (initial_selection / shop_purchase)
  acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),    -- 取得日時
  PRIMARY KEY (player_id, faction)
);

-- =============================================================================
-- 4.6 User Settings (schema: account)
-- =============================================================================

CREATE TABLE account.user_settings (
  player_id    UUID PRIMARY KEY REFERENCES account.players(player_id) ON DELETE CASCADE, -- ユーザーID
  language     VARCHAR(10) NOT NULL,                 -- 言語設定
  bgm_volume   BIGINT NOT NULL,                      -- BGM音量 (0-100)
  se_volume    BIGINT NOT NULL,                      -- SE音量 (0-100)
  push_enabled BOOLEAN NOT NULL,                     -- 通知許可
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()    -- 更新日時
);
CREATE TRIGGER trg_user_settings_updated_at BEFORE UPDATE ON account.user_settings FOR EACH ROW EXECUTE FUNCTION shared.update_updated_at();

-- =============================================================================
-- 4.7 Card Definitions (schema: card)
-- =============================================================================

CREATE TABLE card.card_definitions (
  card_id        VARCHAR(10) NOT NULL,               -- カード識別子（例: SH-0001）
  card_name      VARCHAR(100) NOT NULL,              -- カード名
  resource_label VARCHAR(30) NOT NULL DEFAULT '',     -- リソースラベル
  faction        VARCHAR(20) NOT NULL CHECK (faction IN ('SHE', 'Tenki', 'Sugar', 'Tuners', 'Neutral')), -- 陣営（SHE / Tenki / Sugar / Tuners / Neutral）
  card_type      VARCHAR(30) NOT NULL,               -- カードタイプ（Resource / Support）
  resizable      BOOLEAN NOT NULL DEFAULT false,     -- Resizable 属性
  elastic        BOOLEAN NOT NULL DEFAULT false,     -- Elastic 属性
  stats          JSONB NOT NULL,                     -- ステータス定義
  effect_text    VARCHAR(500),                       -- 効果テキスト（表示用）
  effects        JSONB,                              -- 効果定義（JSON 配列）
  restriction    VARCHAR(20) NOT NULL,               -- 制限区分（unlimited / semi_limited / limited / forbidden）
  is_active      BOOLEAN NOT NULL,                   -- 有効フラグ
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(), -- 作成日時
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(), -- 更新日時
  PRIMARY KEY (card_id)
);

CREATE INDEX idx_cards_faction ON card.card_definitions(faction, card_type);
CREATE INDEX idx_cards_type ON card.card_definitions(card_type);
CREATE TRIGGER trg_card_definitions_updated_at BEFORE UPDATE ON card.card_definitions FOR EACH ROW EXECUTE FUNCTION shared.update_updated_at();

-- =============================================================================
-- 4.8 Card & Deck Management (schema: card, children of players)
-- =============================================================================

CREATE TABLE card.player_cards (
  player_id  UUID NOT NULL, -- 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK)
  card_id    VARCHAR(10) NOT NULL,                   -- カード識別子
  art_no     BIGINT NOT NULL DEFAULT 0,              -- アート番号 (Default: 0)
  count      INT NOT NULL DEFAULT 1,                 -- 所持枚数 (Default: 1)
  PRIMARY KEY (player_id, card_id, art_no)
);

CREATE TABLE card.decks (
  player_id   UUID NOT NULL, -- 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK)
  deck_id     BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY, -- デッキID（自動採番）
  deck_name   VARCHAR(50) NOT NULL,                  -- デッキ名
  playmat_no  BIGINT,                                -- プレイマット番号（NULL: デフォルト）
  sleeve_no   BIGINT,                                -- スリーブ番号（NULL: デフォルト）
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),    -- 作成日時
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),    -- 更新日時
  PRIMARY KEY (player_id, deck_id)
);

CREATE INDEX idx_decks_player ON card.decks(player_id, updated_at DESC);
CREATE TRIGGER trg_decks_updated_at BEFORE UPDATE ON card.decks FOR EACH ROW EXECUTE FUNCTION shared.update_updated_at();

CREATE TABLE card.deck_cards (
  player_id  UUID NOT NULL,                          -- ルート親参照
  deck_id    BIGINT NOT NULL,                        -- 親テーブル参照
  card_id    VARCHAR(10) NOT NULL,                   -- カード識別子
  art_no     BIGINT NOT NULL DEFAULT 0,              -- アート番号 (Default: 0)
  count      INT NOT NULL DEFAULT 1,                 -- 枚数 (Default: 1)
  PRIMARY KEY (player_id, deck_id, card_id, art_no),
  FOREIGN KEY (player_id, deck_id) REFERENCES card.decks(player_id, deck_id) ON DELETE CASCADE
);

-- =============================================================================
-- 4.9 Shop (schema: shop)
-- =============================================================================

CREATE TABLE shop.products (
  product_id          VARCHAR(50) NOT NULL,                  -- 商品ID
  name                VARCHAR(100) NOT NULL,                 -- 商品名
  type                VARCHAR(20) NOT NULL,                  -- 商品タイプ (faction_set / cosmetic / subscription)
  price               BIGINT NOT NULL,                       -- 価格 (JPY)
  content             JSONB NOT NULL,                        -- 商品内容
  faction_id          VARCHAR(20) CHECK (faction_id IS NULL OR faction_id IN ('SHE', 'Tenki', 'Sugar', 'Tuners', 'Neutral')), -- 陣営（faction_set 商品のみ、それ以外は NULL）
  requires_product_id VARCHAR(50),                           -- 購入前提の商品ID（拡張セット用、NULL: なし）
  description         VARCHAR(500),                          -- 商品説明
  image_url           VARCHAR(200),                          -- 画像URL
  is_active           BOOLEAN NOT NULL,                      -- 販売中フラグ
  PRIMARY KEY (product_id),
  FOREIGN KEY (requires_product_id) REFERENCES shop.products(product_id)
);

CREATE TABLE shop.subscriptions (
  player_id            UUID NOT NULL, -- 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK)
  subscription_id      BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY, -- 自動採番
  product_id           VARCHAR(50) NOT NULL,          -- 商品ID
  platform             VARCHAR(10) NOT NULL,          -- apple / google
  purchase_token       VARCHAR(256) NOT NULL,         -- 購入トークン（Apple: originalTransactionId / Google: purchaseToken）
  status               VARCHAR(20) NOT NULL,          -- active / grace_period / expired / refunded
  current_period_start TIMESTAMPTZ NOT NULL,          -- 課金期間開始日時
  current_period_end   TIMESTAMPTZ NOT NULL,          -- 課金期間終了日時
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(), -- 初回購入日時
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(), -- 更新日時
  PRIMARY KEY (player_id, subscription_id)
);
CREATE TRIGGER trg_subscriptions_updated_at BEFORE UPDATE ON shop.subscriptions FOR EACH ROW EXECUTE FUNCTION shared.update_updated_at();

CREATE TABLE shop.one_time_purchases (
  player_id      UUID NOT NULL, -- 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK)
  purchase_id    BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY, -- 自動採番
  product_id     VARCHAR(50) NOT NULL,               -- 商品ID
  platform       VARCHAR(10) NOT NULL,               -- apple / google
  purchase_token VARCHAR(256) NOT NULL,              -- 購入トークン（Apple: originalTransactionId / Google: purchaseToken）
  purchased_at   TIMESTAMPTZ NOT NULL DEFAULT now(), -- 購入日時
  PRIMARY KEY (player_id, purchase_id)
);

-- =============================================================================
-- 4.10 Cosmetics (schema: shop)
-- =============================================================================

CREATE TABLE shop.cosmetic_items (
  item_type      VARCHAR(20) NOT NULL,               -- アイテム種別（playmat / sleeve / icon / stamp）
  item_no        BIGINT NOT NULL,                    -- アイテム番号
  item_name      VARCHAR(100) NOT NULL,              -- アイテム名
  description    VARCHAR(500),                       -- 説明文
  is_purchasable BOOLEAN NOT NULL,                   -- 購入可能フラグ
  is_active      BOOLEAN NOT NULL,                   -- 有効フラグ
  PRIMARY KEY (item_type, item_no)
);

CREATE TABLE shop.player_items (
  player_id   UUID NOT NULL, -- 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK)
  item_type   VARCHAR(20) NOT NULL,                  -- アイテム種別
  item_no     BIGINT NOT NULL,                       -- アイテム番号
  acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),    -- 獲得日時
  PRIMARY KEY (player_id, item_type, item_no)
);

-- =============================================================================
-- 4.11 Game Configuration (schema: shared, server-side KV store, read-only for all services)
-- =============================================================================

CREATE TABLE shared.game_config (
  key        VARCHAR(100) PRIMARY KEY,               -- 設定キー
  value      JSONB NOT NULL,                         -- 設定値
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()      -- 更新日時
);
CREATE TRIGGER trg_game_config_updated_at BEFORE UPDATE ON shared.game_config FOR EACH ROW EXECUTE FUNCTION shared.update_updated_at();

-- =============================================================================
-- 4.12 News Feed (schema: newsfeed)
-- =============================================================================

CREATE TABLE newsfeed.news_articles (
  article_id   VARCHAR(26) NOT NULL,                 -- ULID
  source       VARCHAR(20) NOT NULL,                 -- ニュースソース (aws / google-cloud / azure / oci / other)
  source_url   TEXT NOT NULL,                        -- 元記事URL
  title        TEXT NOT NULL,                        -- 記事タイトル
  summary      TEXT,                                 -- AI要約（NULL: 未完了、次回リトライ対象）
  tags         TEXT[] NOT NULL DEFAULT '{}',          -- タグ
  raw_gcs_path TEXT,                                 -- GCSパス
  published_at TIMESTAMPTZ,                          -- 記事公開日時
  fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),   -- 取得日時
  PRIMARY KEY (article_id)
);

CREATE UNIQUE INDEX idx_news_articles_source_url ON newsfeed.news_articles(source_url);
CREATE INDEX idx_news_articles_published ON newsfeed.news_articles(published_at DESC);
CREATE INDEX idx_news_articles_source ON newsfeed.news_articles(source, published_at DESC);

-- =============================================================================
-- 4.13 Story Scenarios (schema: scenario)
-- =============================================================================

CREATE TABLE scenario.scenario_episodes (
  episode_id        VARCHAR(50) NOT NULL,            -- エピソードID（例: she_ep1, final）
  category          VARCHAR(20) NOT NULL DEFAULT 'main' CHECK (category IN ('main', 'side', 'event')), -- エピソード種別 (main / side / event)
  faction           VARCHAR(20) CHECK (faction IS NULL OR faction IN ('SHE', 'Tenki', 'Sugar', 'Tuners', 'Neutral')), -- 所属陣営（NULL: 全陣営共通）
  episode_number    BIGINT NOT NULL,                 -- 陣営内の章番号
  title_ja          VARCHAR(200) NOT NULL,           -- 日本語タイトル
  title_en          VARCHAR(200) NOT NULL,           -- 英語タイトル
  required_level    BIGINT NOT NULL DEFAULT 1,       -- アンロックに必要なレベル (Default: 1)
  required_episodes TEXT[] NOT NULL DEFAULT '{}',    -- アンロックに必要な完了済みエピソード
  script_path       VARCHAR(500) NOT NULL,           -- スクリプトパステンプレート（{lang} を言語コードに置換）
  thumbnail_path    VARCHAR(500),                    -- サムネイル画像パス
  sort_order        BIGINT NOT NULL,                 -- 表示順
  is_active         BOOLEAN NOT NULL DEFAULT true,   -- 公開フラグ (Default: true)
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(), -- 作成日時
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(), -- 更新日時
  PRIMARY KEY (episode_id)
);

CREATE INDEX idx_scenario_episodes_sort ON scenario.scenario_episodes(sort_order);
CREATE TRIGGER trg_scenario_episodes_updated_at BEFORE UPDATE ON scenario.scenario_episodes FOR EACH ROW EXECUTE FUNCTION shared.update_updated_at();

CREATE TABLE scenario.episode_required_factions (
  episode_id  VARCHAR(50) NOT NULL REFERENCES scenario.scenario_episodes(episode_id) ON DELETE CASCADE, -- エピソード参照
  faction_id  VARCHAR(20) NOT NULL CHECK (faction_id IN ('SHE', 'Tenki', 'Sugar', 'Tuners', 'Neutral')), -- 必要陣営
  PRIMARY KEY (episode_id, faction_id)
);

CREATE TABLE scenario.player_story_progress (
  player_id    UUID NOT NULL, -- 所有プレイヤー (cross-schema reference to account.players; app-level integrity, not enforced by FK)
  episode_id   VARCHAR(50) NOT NULL REFERENCES scenario.scenario_episodes(episode_id) ON DELETE RESTRICT, -- 完了したエピソードID
  completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),   -- 完了日時
  PRIMARY KEY (player_id, episode_id)
);
