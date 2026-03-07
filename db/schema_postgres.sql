-- Overload Party - PostgreSQL DDL
-- All tables with foreign keys and indexes

-- =============================================================================
-- 4.1 Game Management
-- =============================================================================

CREATE TABLE games (
  game_id            VARCHAR(26) NOT NULL,
  player1_id         UUID NOT NULL,
  player2_id         UUID NOT NULL,
  player1_deck_snapshot JSONB NOT NULL,
  player2_deck_snapshot JSONB NOT NULL,
  status             VARCHAR(20) NOT NULL,
  winner_id          UUID,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at        TIMESTAMPTZ,
  PRIMARY KEY (game_id)
);

CREATE INDEX idx_games_status ON games(status, created_at DESC);

-- 4.2 Game State (child of games, 1:1)

CREATE TABLE game_states (
  game_id              VARCHAR(26) PRIMARY KEY REFERENCES games(game_id) ON DELETE CASCADE,
  version              BIGINT NOT NULL,
  current_turn         BIGINT NOT NULL,
  current_phase        VARCHAR(20) NOT NULL,
  active_player        BIGINT NOT NULL,
  player1_budget       BIGINT NOT NULL,
  player1_insight_pool BIGINT NOT NULL,
  player1_field        JSONB NOT NULL,
  player1_hand         JSONB NOT NULL,
  player1_repository   JSONB NOT NULL,
  player1_trash        JSONB NOT NULL,
  player1_time_bank    BIGINT NOT NULL,
  player2_budget       BIGINT NOT NULL,
  player2_insight_pool BIGINT NOT NULL,
  player2_field        JSONB NOT NULL,
  player2_hand         JSONB NOT NULL,
  player2_repository   JSONB NOT NULL,
  player2_trash        JSONB NOT NULL,
  player2_time_bank    BIGINT NOT NULL,
  chain_stack          JSONB,
  current_action_timer BIGINT,
  next_instance_seq    BIGINT NOT NULL DEFAULT 0,
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4.3 Game Events (child of games)

CREATE TABLE game_events (
  game_id         VARCHAR(26) NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
  sequence_number BIGINT NOT NULL,
  event_type      VARCHAR(50) NOT NULL,
  player_id       UUID,
  event_data      JSONB NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (game_id, sequence_number)
);

-- =============================================================================
-- 4.4 Match History
-- =============================================================================

CREATE TABLE matches (
  match_id              BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY,
  game_id               VARCHAR(26) NOT NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (match_id)
);

CREATE INDEX idx_matches_game_id ON matches(game_id);

-- =============================================================================
-- 4.5 Player Management
-- =============================================================================

CREATE TABLE players (
  player_id          UUID NOT NULL DEFAULT gen_random_uuid(),
  firebase_uid       VARCHAR(128) NOT NULL,
  username           VARCHAR(50) NOT NULL,
  level              BIGINT NOT NULL DEFAULT 1,
  exp                BIGINT NOT NULL DEFAULT 0,
  wins               BIGINT,
  losses             BIGINT,
  is_premium         BOOLEAN NOT NULL,
  equipped_icon_no   BIGINT,
  selected_faction   VARCHAR(20),
  premium_expires_at TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id)
);

CREATE UNIQUE INDEX idx_players_firebase_uid ON players(firebase_uid);

-- player_daily_battle (child of players, 1:1)

CREATE TABLE player_daily_battle (
  player_id          UUID PRIMARY KEY REFERENCES players(player_id) ON DELETE CASCADE,
  daily_battle_count BIGINT NOT NULL,
  last_reset_date    DATE NOT NULL
);

-- =============================================================================
-- 4.6 Card Definitions
-- =============================================================================

CREATE TABLE card_definitions (
  card_no        BIGINT NOT NULL,
  card_name      VARCHAR(100) NOT NULL,
  resource_label VARCHAR(30) NOT NULL DEFAULT '',
  faction        VARCHAR(20) NOT NULL,
  card_type      VARCHAR(30) NOT NULL,
  resizable      BOOLEAN NOT NULL DEFAULT false,
  elastic        BOOLEAN NOT NULL DEFAULT false,
  stats          JSONB NOT NULL,
  effect_text    VARCHAR(500),
  effects        JSONB,
  restriction    VARCHAR(20) NOT NULL,
  is_active      BOOLEAN NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (card_no)
);

CREATE INDEX idx_cards_faction ON card_definitions(faction, card_type);
CREATE INDEX idx_cards_type ON card_definitions(card_type);

-- =============================================================================
-- 4.7 Card & Deck Management (children of players)
-- =============================================================================

CREATE TABLE player_cards (
  player_id  UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  card_no    BIGINT NOT NULL,
  art_no     BIGINT NOT NULL DEFAULT 0,
  count      INT NOT NULL DEFAULT 1,
  PRIMARY KEY (player_id, card_no, art_no)
);

CREATE TABLE decks (
  player_id   UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  deck_id     BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY,
  deck_name   VARCHAR(50) NOT NULL,
  is_valid    BOOLEAN NOT NULL,
  playmat_no  BIGINT,
  sleeve_no   BIGINT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, deck_id)
);

CREATE INDEX idx_decks_player ON decks(player_id, updated_at DESC);

CREATE TABLE deck_cards (
  player_id  UUID NOT NULL,
  deck_id    BIGINT NOT NULL,
  card_no    BIGINT NOT NULL,
  art_no     BIGINT NOT NULL DEFAULT 0,
  count      INT NOT NULL DEFAULT 1,
  PRIMARY KEY (player_id, deck_id, card_no, art_no),
  FOREIGN KEY (player_id, deck_id) REFERENCES decks(player_id, deck_id) ON DELETE CASCADE
);

-- =============================================================================
-- 4.8 Shop & Settings
-- =============================================================================

CREATE TABLE products (
  product_id VARCHAR(50) NOT NULL,
  name       VARCHAR(100) NOT NULL,
  type       VARCHAR(20) NOT NULL,
  price      BIGINT NOT NULL,
  content    JSONB NOT NULL,
  is_active  BOOLEAN NOT NULL,
  PRIMARY KEY (product_id)
);

CREATE TABLE subscriptions (
  player_id            UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  subscription_id      BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY,
  product_id           VARCHAR(50) NOT NULL,
  platform             VARCHAR(10) NOT NULL,
  purchase_token       VARCHAR(256) NOT NULL,
  status               VARCHAR(20) NOT NULL,
  current_period_start TIMESTAMPTZ NOT NULL,
  current_period_end   TIMESTAMPTZ NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, subscription_id)
);

CREATE TABLE one_time_purchases (
  player_id      UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  purchase_id    BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY,
  product_id     VARCHAR(50) NOT NULL,
  platform       VARCHAR(10) NOT NULL,
  purchase_token VARCHAR(256) NOT NULL,
  purchased_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, purchase_id)
);

CREATE TABLE user_settings (
  player_id    UUID PRIMARY KEY REFERENCES players(player_id) ON DELETE CASCADE,
  language     VARCHAR(10) NOT NULL,
  bgm_volume   BIGINT NOT NULL,
  se_volume    BIGINT NOT NULL,
  push_enabled BOOLEAN NOT NULL,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 4.9 Cosmetics
-- =============================================================================

CREATE TABLE cosmetic_items (
  item_type      VARCHAR(20) NOT NULL,
  item_no        BIGINT NOT NULL,
  item_name      VARCHAR(100) NOT NULL,
  description    VARCHAR(500),
  is_purchasable BOOLEAN NOT NULL,
  is_active      BOOLEAN NOT NULL,
  PRIMARY KEY (item_type, item_no)
);

CREATE TABLE player_items (
  player_id   UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
  item_type   VARCHAR(20) NOT NULL,
  item_no     BIGINT NOT NULL,
  acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, item_type, item_no)
);

-- =============================================================================
-- 4.10 Game Configuration (server-side KV store)
-- =============================================================================

CREATE TABLE game_config (
  key        VARCHAR(100) PRIMARY KEY,
  value      JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 4.11 News Feed
-- =============================================================================

CREATE TABLE news_articles (
  article_id   VARCHAR(26) NOT NULL,              -- ULID
  source       VARCHAR(20) NOT NULL,              -- 'aws' | 'azure' | 'gcp' | 'oci'
  source_url   TEXT NOT NULL,
  title        TEXT NOT NULL,
  summary      TEXT,                              -- NULL = AI要約未完了（次回リトライ対象）
  tags         TEXT[] NOT NULL DEFAULT '{}',
  raw_gcs_path TEXT,                              -- gs://...-newsfeed/raw/{source}/{date}/{article_id}.json
  published_at TIMESTAMPTZ,
  fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (article_id)
);

CREATE UNIQUE INDEX idx_news_articles_source_url ON news_articles(source_url);
CREATE INDEX idx_news_articles_published ON news_articles(published_at DESC);
CREATE INDEX idx_news_articles_source ON news_articles(source, published_at DESC);
