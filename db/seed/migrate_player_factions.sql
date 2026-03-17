-- Backfill player_factions from existing data.
-- Run once after creating the player_factions table.

BEGIN;

-- 初期選択陣営のバックフィル
INSERT INTO player_factions (player_id, faction, source, acquired_at)
SELECT player_id, selected_faction, 'initial_selection', created_at
FROM players
WHERE selected_faction IS NOT NULL
ON CONFLICT DO NOTHING;

-- ショップ購入分のバックフィル
INSERT INTO player_factions (player_id, faction, source, acquired_at)
SELECT otp.player_id, p.content->>'faction', 'shop_purchase', otp.purchased_at
FROM one_time_purchases otp
JOIN products p ON p.product_id = otp.product_id
WHERE p.type = 'faction_set'
  AND p.content->>'faction' IS NOT NULL
ON CONFLICT DO NOTHING;

COMMIT;
