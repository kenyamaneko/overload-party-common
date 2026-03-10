-- Shop products seed data

INSERT INTO products (product_id, name, type, price, content, is_active) VALUES
  ('faction_she',      'SHEカードセット',         'faction_set',   980, '{"faction":"SHE"}'::jsonb,      true),
  ('faction_tenki',    '天気使いカードセット',    'faction_set',   980, '{"faction":"Tenki"}'::jsonb,    true),
  ('faction_sugar',    'しゅがーらぼカードセット', 'faction_set',   980, '{"faction":"Sugar"}'::jsonb,    true),
  ('faction_tuners',   '調律部カードセット',      'faction_set',   980, '{"faction":"Tuners"}'::jsonb,   true),
  ('premium_monthly',  'プレミアムプラン（月額）', 'subscription', 480, '{"duration_days":30}'::jsonb,   true),
  -- スタンプセット（課金）— キャラクターデザイン完成後に is_active = true にする
  ('stamp_she',      'SHEスタンプセット',         'cosmetic', 480, '{"item_type":"stamp","item_no":101}'::jsonb, false),
  ('stamp_tenki',    '天気使いスタンプセット',    'cosmetic', 480, '{"item_type":"stamp","item_no":201}'::jsonb, false),
  ('stamp_sugar',    'しゅがーらぼスタンプセット', 'cosmetic', 480, '{"item_type":"stamp","item_no":301}'::jsonb, false),
  ('stamp_tuners',   '調律部スタンプセット',      'cosmetic', 480, '{"item_type":"stamp","item_no":401}'::jsonb, false)
ON CONFLICT (product_id) DO NOTHING;
