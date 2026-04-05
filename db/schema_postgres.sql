-- Overload Party - PostgreSQL DDL
-- All tables with foreign keys and indexes

-- =============================================================================
-- Shared: updated_at auto-update trigger function
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 4.1 Game Management
-- =============================================================================

CREATE TABLE games (
  game_id            VARCHAR(26) NOT NULL,           -- ULID
  player1_id         UUID NOT NULL,                  -- プレイヤー1 ID
  player2_id         UUID NOT NULL,                  -- プレイヤー2 ID
  player1_deck_snapshot JSONB NOT NULL,              -- 使用デッキのスナップショット（カードIDリスト）
  player2_deck_snapshot JSONB NOT NULL,              -- 使用デッキのスナップショット（カードIDリスト）
  status             VARCHAR(20) NOT NULL,           -- 'waiting' / 'playing' / 'finished'
  engine_version     TEXT NOT NULL DEFAULT '',        -- バトルエンジンバージョン（ゲーム作成時に記録）
  card_data_version  TEXT NOT NULL DEFAULT '',        -- カードデータバージョン（ゲーム作成時に記録）
  winner_id          UUID,                           -- 勝者 ID
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(), -- 作成日時
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(), -- 更新日時
  finished_at        TIMESTAMPTZ,                    -- 終了日時
  PRIMARY KEY (game_id)
);

CREATE INDEX idx_games_status ON games(status, created_at DESC);
CREATE TRIGGER trg_games_updated_at BEFORE UPDATE ON games FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 4.2 Game State (child of games, 1:1)

CREATE TABLE game_states (
  game_id              VARCHAR(26) PRIMARY KEY REFERENCES games(game_id) ON DELETE CASCADE, -- 親テーブル参照
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
CREATE TRIGGER trg_game_states_updated_at BEFORE UPDATE ON game_states FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Game Actions (child of games, append-only action log)

CREATE TABLE game_actions (
  game_id     VARCHAR(26) NOT NULL REFERENCES games(game_id) ON DELETE CASCADE, -- 親テーブル参照
  seq         INT NOT NULL,                          -- アクション連番
  player_id   UUID NOT NULL,                         -- アクション実行プレイヤー
  action_type TEXT NOT NULL,                         -- アクション種別（play_card, attack, scale_up 等）
  action_data JSONB NOT NULL,                        -- アクションの入力データ
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),    -- 記録日時
  PRIMARY KEY (game_id, seq)
);

-- 4.3 Game Events (child of games)

CREATE TABLE game_events (
  game_id         VARCHAR(26) NOT NULL REFERENCES games(game_id) ON DELETE CASCADE, -- 親テーブル参照
  sequence_number BIGINT NOT NULL,                   -- イベント連番
  event_type      VARCHAR(50) NOT NULL,              -- イベント種別
  player_id       UUID,                              -- 行動プレイヤー
  event_data      JSONB NOT NULL,                    -- イベント詳細データ
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(), -- 発生日時
  PRIMARY KEY (game_id, sequence_number)
);

-- =============================================================================
-- 4.4 Player Management
-- =============================================================================

CREATE TABLE players (
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

CREATE UNIQUE INDEX idx_players_firebase_uid ON players(firebase_uid);
CREATE TRIGGER trg_players_updated_at BEFORE UPDATE ON players FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- player_daily_battle (child of players, 1:1)

CREATE TABLE player_daily_battle (
  player_id          UUID PRIMARY KEY REFERENCES players(player_id) ON DELETE CASCADE, -- 親テーブル参照
  daily_battle_count BIGINT NOT NULL,                -- 本日のバトル回数
  last_reset_date    DATE NOT NULL                   -- 最終リセット日
);

-- =============================================================================
-- 4.6 Card Definitions
-- =============================================================================

CREATE TABLE card_definitions (
  card_id        VARCHAR(10) NOT NULL,               -- カード識別子（例: SH-0001）
  card_name      VARCHAR(100) NOT NULL,              -- カード名
  resource_label VARCHAR(30) NOT NULL DEFAULT '',     -- リソースラベル
  faction        VARCHAR(20) NOT NULL,               -- 陣営
  card_type      VARCHAR(30) NOT NULL,               -- カードタイプ
  resizable      BOOLEAN NOT NULL DEFAULT false,     -- Resizable 属性
  elastic        BOOLEAN NOT NULL DEFAULT false,     -- Elastic 属性
  stats          JSONB NOT NULL,                     -- ステータス定義
  effect_text    VARCHAR(500),                       -- 効果テキスト（表示用）
  effects        JSONB,                              -- 効果定義（JSON 配列）
  restriction    VARCHAR(20) NOT NULL,               -- 制限区分
  is_active      BOOLEAN NOT NULL,                   -- 有効フラグ
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(), -- 作成日時
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(), -- 更新日時
  PRIMARY KEY (card_id)
);

CREATE INDEX idx_cards_faction ON card_definitions(faction, card_type);
CREATE INDEX idx_cards_type ON card_definitions(card_type);
CREATE TRIGGER trg_card_definitions_updated_at BEFORE UPDATE ON card_definitions FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- 4.7 Card & Deck Management (children of players)
-- =============================================================================

CREATE TABLE player_cards (
  player_id  UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE, -- 親テーブル参照
  card_id    VARCHAR(10) NOT NULL,                   -- カード識別子
  art_no     BIGINT NOT NULL DEFAULT 0,              -- アート番号 (Default: 0)
  count      INT NOT NULL DEFAULT 1,                 -- 所持枚数 (Default: 1)
  PRIMARY KEY (player_id, card_id, art_no)
);

CREATE TABLE decks (
  player_id   UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE, -- 親テーブル参照
  deck_id     BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY, -- デッキID（自動採番）
  deck_name   VARCHAR(50) NOT NULL,                  -- デッキ名
  playmat_no  BIGINT,                                -- プレイマット番号（NULL: デフォルト）
  sleeve_no   BIGINT,                                -- スリーブ番号（NULL: デフォルト）
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),    -- 作成日時
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),    -- 更新日時
  PRIMARY KEY (player_id, deck_id)
);

CREATE INDEX idx_decks_player ON decks(player_id, updated_at DESC);
CREATE TRIGGER trg_decks_updated_at BEFORE UPDATE ON decks FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE deck_cards (
  player_id  UUID NOT NULL,                          -- ルート親参照
  deck_id    BIGINT NOT NULL,                        -- 親テーブル参照
  card_id    VARCHAR(10) NOT NULL,                   -- カード識別子
  art_no     BIGINT NOT NULL DEFAULT 0,              -- アート番号 (Default: 0)
  count      INT NOT NULL DEFAULT 1,                 -- 枚数 (Default: 1)
  PRIMARY KEY (player_id, deck_id, card_id, art_no),
  FOREIGN KEY (player_id, deck_id) REFERENCES decks(player_id, deck_id) ON DELETE CASCADE
);

-- =============================================================================
-- 4.8 Shop & Settings
-- =============================================================================

CREATE TABLE products (
  product_id  VARCHAR(50) NOT NULL,                  -- 商品ID
  name        VARCHAR(100) NOT NULL,                 -- 商品名
  type        VARCHAR(20) NOT NULL,                  -- 商品タイプ (card_pack / subscription)
  price       BIGINT NOT NULL,                       -- 価格 (JPY)
  content     JSONB NOT NULL,                        -- 商品内容
  description VARCHAR(500),                          -- 商品説明
  image_url   VARCHAR(200),                          -- 画像URL
  is_active   BOOLEAN NOT NULL,                      -- 販売中フラグ
  PRIMARY KEY (product_id)
);

CREATE TABLE subscriptions (
  player_id            UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE, -- 親テーブル参照
  subscription_id      BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY, -- 自動採番
  product_id           VARCHAR(50) NOT NULL,          -- 商品ID
  platform             VARCHAR(10) NOT NULL,          -- apple / google
  purchase_token       VARCHAR(256) NOT NULL,         -- 購入トークン
  status               VARCHAR(20) NOT NULL,          -- active / grace_period / expired / refunded
  current_period_start TIMESTAMPTZ NOT NULL,          -- 課金期間開始日時
  current_period_end   TIMESTAMPTZ NOT NULL,          -- 課金期間終了日時
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(), -- 初回購入日時
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(), -- 更新日時
  PRIMARY KEY (player_id, subscription_id)
);
CREATE TRIGGER trg_subscriptions_updated_at BEFORE UPDATE ON subscriptions FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE one_time_purchases (
  player_id      UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE, -- 親テーブル参照
  purchase_id    BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY, -- 自動採番
  product_id     VARCHAR(50) NOT NULL,               -- 商品ID
  platform       VARCHAR(10) NOT NULL,               -- apple / google
  purchase_token VARCHAR(256) NOT NULL,              -- 購入トークン
  purchased_at   TIMESTAMPTZ NOT NULL DEFAULT now(), -- 購入日時
  PRIMARY KEY (player_id, purchase_id)
);

CREATE TABLE user_settings (
  player_id    UUID PRIMARY KEY REFERENCES players(player_id) ON DELETE CASCADE, -- ユーザーID
  language     VARCHAR(10) NOT NULL,                 -- 言語設定
  bgm_volume   BIGINT NOT NULL,                      -- BGM音量 (0-100)
  se_volume    BIGINT NOT NULL,                      -- SE音量 (0-100)
  push_enabled BOOLEAN NOT NULL,                     -- 通知許可
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()    -- 更新日時
);
CREATE TRIGGER trg_user_settings_updated_at BEFORE UPDATE ON user_settings FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- 4.9 Cosmetics
-- =============================================================================

CREATE TABLE cosmetic_items (
  item_type      VARCHAR(20) NOT NULL,               -- アイテム種別（playmat / sleeve / icon / stamp）
  item_no        BIGINT NOT NULL,                    -- アイテム番号
  item_name      VARCHAR(100) NOT NULL,              -- アイテム名
  description    VARCHAR(500),                       -- 説明文
  is_purchasable BOOLEAN NOT NULL,                   -- 購入可能フラグ
  is_active      BOOLEAN NOT NULL,                   -- 有効フラグ
  PRIMARY KEY (item_type, item_no)
);

CREATE TABLE player_items (
  player_id   UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE, -- 親テーブル参照
  item_type   VARCHAR(20) NOT NULL,                  -- アイテム種別
  item_no     BIGINT NOT NULL,                       -- アイテム番号
  acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),    -- 獲得日時
  PRIMARY KEY (player_id, item_type, item_no)
);

-- =============================================================================
-- 4.10 Game Configuration (server-side KV store)
-- =============================================================================

CREATE TABLE game_config (
  key        VARCHAR(100) PRIMARY KEY,               -- 設定キー
  value      JSONB NOT NULL,                         -- 設定値
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()      -- 更新日時
);
CREATE TRIGGER trg_game_config_updated_at BEFORE UPDATE ON game_config FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- 4.11 News Feed
-- =============================================================================

CREATE TABLE news_articles (
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

CREATE UNIQUE INDEX idx_news_articles_source_url ON news_articles(source_url);
CREATE INDEX idx_news_articles_published ON news_articles(published_at DESC);
CREATE INDEX idx_news_articles_source ON news_articles(source, published_at DESC);

-- =============================================================================
-- 4.12 Player Factions (陣営所持の中間テーブル)
-- =============================================================================

CREATE TABLE player_factions (
  player_id   UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE, -- 親テーブル参照
  faction     VARCHAR(20) NOT NULL CHECK (faction IN ('SHE', 'Tenki', 'Sugar', 'Tuners')), -- 陣営名 (SHE / Tenki / Sugar / Tuners)
  source      VARCHAR(20) NOT NULL CHECK (source IN ('initial_selection', 'shop_purchase')), -- 取得経路 (initial_selection / shop_purchase)
  acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),    -- 取得日時
  PRIMARY KEY (player_id, faction)
);

-- =============================================================================
-- 4.13 Story Scenarios
-- =============================================================================

CREATE TABLE scenario_episodes (
  episode_id        VARCHAR(50) NOT NULL,            -- エピソードID（例: she_ep1, final）
  category          VARCHAR(20) NOT NULL DEFAULT 'main' CHECK (category IN ('main', 'side', 'event')), -- エピソード種別 (main / side / event)
  faction           VARCHAR(20) CHECK (faction IS NULL OR faction IN ('SHE', 'Tenki', 'Sugar', 'Tuners')), -- 所属陣営（NULL: 全陣営共通）
  episode_number    BIGINT NOT NULL,                 -- 陣営内の章番号
  title_ja          VARCHAR(200) NOT NULL,           -- 日本語タイトル
  title_en          VARCHAR(200) NOT NULL,           -- 英語タイトル
  required_level    BIGINT NOT NULL DEFAULT 1,       -- アンロックに必要なレベル (Default: 1)
  required_factions TEXT[] NOT NULL DEFAULT '{}' CHECK (required_factions <@ ARRAY['SHE','Tenki','Sugar','Tuners']::TEXT[]), -- アンロックに必要な陣営所持
  required_episodes TEXT[] NOT NULL DEFAULT '{}',    -- アンロックに必要な完了済みエピソード
  script_path       VARCHAR(500) NOT NULL,           -- スクリプトパステンプレート
  thumbnail_path    VARCHAR(500),                    -- サムネイル画像パス
  sort_order        BIGINT NOT NULL,                 -- 表示順
  is_active         BOOLEAN NOT NULL DEFAULT true,   -- 公開フラグ (Default: true)
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(), -- 作成日時
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(), -- 更新日時
  PRIMARY KEY (episode_id)
);

CREATE INDEX idx_scenario_episodes_sort ON scenario_episodes(sort_order);
CREATE TRIGGER trg_scenario_episodes_updated_at BEFORE UPDATE ON scenario_episodes FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TABLE player_story_progress (
  player_id    UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE, -- 親テーブル参照
  episode_id   VARCHAR(50) NOT NULL REFERENCES scenario_episodes(episode_id) ON DELETE RESTRICT, -- 完了したエピソードID
  completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),   -- 完了日時
  PRIMARY KEY (player_id, episode_id)
);
