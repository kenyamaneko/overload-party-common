-- Factions master seed data

INSERT INTO factions (faction_id, short_name_ja, short_name_en, full_name_ja, full_name_en, is_collectible, sort_order) VALUES
  ('Neutral', 'ニュートラル', 'Neutral',    'ニュートラル',               'Neutral',                      false, 0),
  ('SHE',     'SHE',         'SHE',        'SHE（Smile Horizon Express）','SHE (Smile Horizon Express)',  true,  1),
  ('Tenki',   '天気使い',     'Weatherers', '天気使い',                   'Weatherers',                    true,  2),
  ('Sugar',   'しゅがーらぼ', 'Sugar Lab',  'しゅがーらぼ',               'Sugar Lab',                     true,  3),
  ('Tuners',  '調律部',       'The Tuners', '調律部（チューナーズ）',      'The Tuners',                    true,  4)
ON CONFLICT (faction_id) DO UPDATE SET
  short_name_ja  = EXCLUDED.short_name_ja,
  short_name_en  = EXCLUDED.short_name_en,
  full_name_ja   = EXCLUDED.full_name_ja,
  full_name_en   = EXCLUDED.full_name_en,
  is_collectible = EXCLUDED.is_collectible,
  sort_order     = EXCLUDED.sort_order;
