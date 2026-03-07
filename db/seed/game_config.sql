-- Game configuration seed data
INSERT INTO game_config (key, value) VALUES
  ('free_daily_battle_limit', '10'),
  ('premium_daily_battle_limit', '30')
ON CONFLICT (key) DO NOTHING;
