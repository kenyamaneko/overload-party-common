-- Seed data: Card definitions for dev/testing
-- One card per faction + Neutral for basic testing

INSERT INTO card_definitions (card_no, card_id, card_name, faction, card_type, resizable, elastic, stats, effect_text, restriction, is_active, created_at, updated_at)
VALUES
(1, 'SH-0001', 'EC2 Instance', 'SD', 'Compute', true, true,
 '{"throughput": 500, "throughput_max": 800, "availability": 1200, "maintenance_cost": 300, "sla_penalty": 200}'::jsonb,
 'Deploy: +100 Budget to DV Pool', 'unlimited', true, now(), now()),

(2, 'TK-0001', 'Cloud Functions', 'Tenki', 'Serverless', false, true,
 '{"throughput": 300, "throughput_max": 600, "availability": 800, "maintenance_cost": 100, "sla_penalty": 100}'::jsonb,
 'Auto-scale: TP doubles when Budget < 2000', 'unlimited', true, now(), now()),

(3, 'TK-0002', 'Cloud SQL', 'Tenki', 'Database', true, false,
 '{"yield": 200, "yield_max": null, "availability": 1000, "maintenance_cost": 350, "sla_penalty": 150}'::jsonb,
 NULL, 'unlimited', true, now(), now()),

(4, 'SL-0001', 'GKE Pod', 'Sugar', 'Container', true, true,
 '{"throughput": 400, "throughput_max": 700, "availability": 1100, "maintenance_cost": 250, "sla_penalty": 180}'::jsonb,
 'Orchestrate: Adjacent containers gain +50 TP', 'semi_limited', true, now(), now()),

(5, 'TN-0001', 'Azure Cosmos DB', 'Tuners', 'Database', true, true,
 '{"yield": 250, "yield_max": 400, "availability": 900, "maintenance_cost": 300, "sla_penalty": 120}'::jsonb,
 'Multi-region: Cannot be targeted by single-target Incidents', 'limited', true, now(), now()),

(6, 'NT-0001', 'Load Balancer', 'Neutral', 'Platform', false, false,
 '{}'::jsonb,
 'Distribute: Split incoming attack damage between two frontend resources', 'unlimited', true, now(), now()),

(7, 'NT-0002', 'DDoS Attack', 'Neutral', 'Incident', false, false,
 '{}'::jsonb,
 'Deal 400 damage to all frontend resources', 'semi_limited', true, now(), now()),

(8, 'SH-0002', 'Auto-Scaling Policy', 'SD', 'Attachment', false, false,
 '{}'::jsonb,
 'Attach to Compute: +200 TP max, gain Elastic if not already', 'unlimited', true, now(), now())

ON CONFLICT (card_no) DO NOTHING;
