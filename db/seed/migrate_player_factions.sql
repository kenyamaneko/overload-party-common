-- Backfill player_factions from existing data.
-- Run once after creating the player_factions table.

BEGIN;

-- 初期選択陣営のバックフィル
INSERT INTO account.player_factions (player_id, faction, source, acquired_at)
SELECT player_id, selected_faction, 'initial_selection', created_at
FROM account.players
WHERE selected_faction IS NOT NULL
ON CONFLICT DO NOTHING;

-- ショップ購入分のバックフィル
-- NOTE: 越境 JOIN (account.player_factions ← shop.one_time_purchases + shop.products)
-- は一回限りのバックフィルに使う管理ユーザー前提で実行する（通常の IAM ユーザーには shop と account を同時に読む権限はない）。
INSERT INTO account.player_factions (player_id, faction, source, acquired_at)
SELECT otp.player_id, p.content->>'faction', 'shop_purchase', otp.purchased_at
FROM shop.one_time_purchases otp
JOIN shop.products p ON p.product_id = otp.product_id
WHERE p.type = 'faction_set'
  AND p.content->>'faction' IS NOT NULL
ON CONFLICT DO NOTHING;

COMMIT;
