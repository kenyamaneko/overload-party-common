-- Stamp (emote) definitions seed data
-- item_type = 'stamp', is_purchasable = false → 無料配布スタンプ

INSERT INTO shop.cosmetic_items (item_type, item_no, item_name, description, is_purchasable, is_active) VALUES
  ('stamp', 1, 'よろしくお願いします！', 'Greeting / 対戦開始時',                                   false, true),
  ('stamp', 2, 'ヨシ！',               'Confirmation / 完璧な盤面を作った時など',                  false, true),
  ('stamp', 3, '仕様です',             'Working as Intended / 痛いところを突かれた時の言い訳や、カウンター時', false, true),
  ('stamp', 4, 'LGTM',                'Looks Good To Me / 相手の良いプレイへの称賛',              false, true),
  ('stamp', 5, '進捗ダメです',         'Bad Status / 劣勢時・リソース枯渇時のSOS',                 false, true),
  ('stamp', 6, '完全に理解した',       'Understood / とりあえず強いカードを出した時・分かってない時', false, true),
  ('stamp', 7, '何もわからない',       'Clueless / パニック時・相手の長考や複雑なコンボを見た時',   false, true)
ON CONFLICT (item_type, item_no) DO NOTHING;

-- 課金スタンプ（陣営別セット）— キャラクターデザインは今後追加予定
-- item_no 100番台: SHE, 200番台: Tenki, 300番台: Sugar, 400番台: Tuners
-- 現時点ではプレースホルダーのみ（is_active = false で非公開）
INSERT INTO shop.cosmetic_items (item_type, item_no, item_name, description, is_purchasable, is_active) VALUES
  ('stamp', 101, 'SHEスタンプ（準備中）',         'SHE陣営キャラクタースタンプ', true, false),
  ('stamp', 201, '天気使いスタンプ（準備中）',    '天気使い陣営キャラクタースタンプ', true, false),
  ('stamp', 301, 'しゅがーらぼスタンプ（準備中）', 'しゅがーらぼ陣営キャラクタースタンプ', true, false),
  ('stamp', 401, '調律部スタンプ（準備中）',      '調律部陣営キャラクタースタンプ', true, false)
ON CONFLICT (item_type, item_no) DO NOTHING;
