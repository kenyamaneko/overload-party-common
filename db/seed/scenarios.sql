-- Story scenario episodes seed data

INSERT INTO scenario_episodes (episode_id, category, faction, episode_number, title_ja, title_en,
  required_level, required_episodes, script_path, sort_order) VALUES
  -- Round 1 (Lv2-5): 各陣営 第1章
  ('she_ep1',    'main', 'SHE',    1, 'SHE 第1章 ワニと少年と、届かない返事',       'SHE Ch.1 The Crocodile, the Boy, and the Unanswered Reply',  2, '{}',           'stories/{lang}/she_ep1.ks',    1),
  ('tenki_ep1',  'main', 'Tenki',  1, '天気使い 第1章 移ろう空、祈りの声',          'Tenki Ch.1 The Shifting Sky, Voices of Prayer',              3, '{}',           'stories/{lang}/tenki_ep1.ks',  2),
  ('sugar_ep1',  'main', 'Sugar',  1, 'しゅがーらぼ 第1章 カオスな厨房、最高の一口', 'Sugar Ch.1 Chaotic Kitchen, the Perfect Bite',                4, '{}',           'stories/{lang}/sugar_ep1.ks',  3),
  ('tuners_ep1', 'main', 'Tuners', 1, '調律部 第1章 放課後の不協和音',              'Tuners Ch.1 After-School Dissonance',                        5, '{}',           'stories/{lang}/tuners_ep1.ks', 4),
  -- Round 2 (Lv6-9): 各陣営 第2章
  ('she_ep2',    'main', 'SHE',    2, 'SHE 第2章 霧の中の「サジェスト」',            'SHE Ch.2 Suggestions in the Fog',                             6, '{she_ep1}',    'stories/{lang}/she_ep2.ks',    5),
  ('tenki_ep2',  'main', 'Tenki',  2, '天気使い 第2章 霧を晴らす「お助けフィルタ」', 'Tenki Ch.2 The Helpful Filter That Clears the Fog',           7, '{tenki_ep1}',  'stories/{lang}/tenki_ep2.ks',  6),
  ('sugar_ep2',  'main', 'Sugar',  2, 'しゅがーらぼ 第2章 AIの「健康診断」',         'Sugar Ch.2 The AI Health Check',                               8, '{sugar_ep1}',  'stories/{lang}/sugar_ep2.ks',  7),
  ('tuners_ep2', 'main', 'Tuners', 2, '調律部 第2章 完璧なメトロノーム',             'Tuners Ch.2 The Perfect Metronome',                           9, '{tuners_ep1}', 'stories/{lang}/tuners_ep2.ks', 8),
  -- Round 3 (Lv10-13): 各陣営 第3章
  ('she_ep3',    'main', 'SHE',    3, 'SHE 第3章 親切という名の侵食',               'SHE Ch.3 Erosion in the Name of Kindness',                   10, '{she_ep2}',    'stories/{lang}/she_ep3.ks',    9),
  ('tenki_ep3',  'main', 'Tenki',  3, '天気使い 第3章 塗りつぶされる情緒',           'Tenki Ch.3 Emotions Painted Over',                           11, '{tenki_ep2}',  'stories/{lang}/tenki_ep3.ks',  10),
  ('sugar_ep3',  'main', 'Sugar',  3, 'しゅがーらぼ 第3章 甘いものは「エラー」です', 'Sugar Ch.3 Sweets Are an Error',                              12, '{sugar_ep2}',  'stories/{lang}/sugar_ep3.ks',  11),
  ('tuners_ep3', 'main', 'Tuners', 3, '調律部 第3章 AIこそが「正解」の音楽',         'Tuners Ch.3 AI Is the Correct Music',                        13, '{tuners_ep2}', 'stories/{lang}/tuners_ep3.ks', 12),
  -- Round 4 (Lv14-17): 各陣営 第4章
  ('she_ep4',    'main', 'SHE',    4, 'SHE 第4章 崩れる信頼、拒絶される箱',          'SHE Ch.4 Crumbling Trust, Rejected Packages',                14, '{she_ep3}',    'stories/{lang}/she_ep4.ks',    13),
  ('tenki_ep4',  'main', 'Tenki',  4, '天気使い 第4章 奪われる能力、奪われる視線',   'Tenki Ch.4 Stolen Abilities, Stolen Gazes',                  15, '{tenki_ep3}',  'stories/{lang}/tenki_ep4.ks',  14),
  ('sugar_ep4',  'main', 'Sugar',  4, 'しゅがーらぼ 第4章 有害認定された「天才たち」', 'Sugar Ch.4 The Geniuses Deemed Harmful',                      16, '{sugar_ep3}',  'stories/{lang}/sugar_ep4.ks',  15),
  ('tuners_ep4', 'main', 'Tuners', 4, '調律部 第4章 かき消される鼓動',               'Tuners Ch.4 Heartbeats Drowned Out',                         17, '{tuners_ep3}', 'stories/{lang}/tuners_ep4.ks', 16),
  -- Round 5 (Lv18-21): 各陣営 第5章
  ('she_ep5',    'main', 'SHE',    5, 'SHE 第5章 迷うことの、贅沢',                  'SHE Ch.5 The Luxury of Indecision',                          18, '{she_ep4}',    'stories/{lang}/she_ep5.ks',    17),
  ('tenki_ep5',  'main', 'Tenki',  5, '天気使い 第5章 #あの日の空、不完全な記憶',    'Tenki Ch.5 #That Day''s Sky, Imperfect Memories',             19, '{tenki_ep4}',  'stories/{lang}/tenki_ep5.ks',  18),
  ('sugar_ep5',  'main', 'Sugar',  5, 'しゅがーらぼ 第5章 人生には「甘い記憶」が必要だ', 'Sugar Ch.5 Life Needs Sweet Memories',                        20, '{sugar_ep4}',  'stories/{lang}/sugar_ep5.ks',  19),
  ('tuners_ep5', 'main', 'Tuners', 5, '調律部 第5章 エゴイズム・レゾナンス',         'Tuners Ch.5 Egoism Resonance',                               21, '{tuners_ep4}', 'stories/{lang}/tuners_ep5.ks', 20),
  -- Final (Lv22): グランドエンディング
  ('final',      'main', NULL,     1, '最終話 静かなる共鳴',                         'Final Chapter: A Quiet Resonance',                           22, '{she_ep5,tenki_ep5,sugar_ep5,tuners_ep5}', 'stories/{lang}/final.ks', 21)
ON CONFLICT (episode_id) DO NOTHING;

-- Episode required factions (アンロックに必要な陣営所持)
INSERT INTO episode_required_factions (episode_id, faction_id) VALUES
  -- Round 1
  ('she_ep1',    'SHE'),
  ('tenki_ep1',  'Tenki'),
  ('sugar_ep1',  'Sugar'),
  ('tuners_ep1', 'Tuners'),
  -- Round 2
  ('she_ep2',    'SHE'),
  ('tenki_ep2',  'Tenki'),
  ('sugar_ep2',  'Sugar'),
  ('tuners_ep2', 'Tuners'),
  -- Round 3
  ('she_ep3',    'SHE'),
  ('tenki_ep3',  'Tenki'),
  ('sugar_ep3',  'Sugar'),
  ('tuners_ep3', 'Tuners'),
  -- Round 4
  ('she_ep4',    'SHE'),
  ('tenki_ep4',  'Tenki'),
  ('sugar_ep4',  'Sugar'),
  ('tuners_ep4', 'Tuners'),
  -- Round 5
  ('she_ep5',    'SHE'),
  ('tenki_ep5',  'Tenki'),
  ('sugar_ep5',  'Sugar'),
  ('tuners_ep5', 'Tuners'),
  -- Final (全陣営必要)
  ('final',      'SHE'),
  ('final',      'Tenki'),
  ('final',      'Sugar'),
  ('final',      'Tuners')
ON CONFLICT (episode_id, faction_id) DO NOTHING;
