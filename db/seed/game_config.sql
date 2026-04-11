-- Game configuration seed data
INSERT INTO shared.game_config (key, value) VALUES
  ('free_daily_battle_limit', '10'),
  ('premium_daily_battle_limit', '30'),
  ('initial_time_bank', '480'),
  ('exp_win', '40'),
  ('exp_loss', '20'),
  ('exp_draw', '30'),
  ('exp_formula_coefficient', '60')
ON CONFLICT (key) DO NOTHING;
