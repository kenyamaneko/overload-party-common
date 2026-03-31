#!/usr/bin/env python3
"""Generate card data outputs from YAML card definitions.

Outputs:
  - packages/gamedata/cache/cards_gen.json  (Go embedded, local dev)
  - packages/dotnet/cache/cards_gen.json    (C# embedded, local dev)
  - docs/game_design/CARDS.md               (human-readable card list)
  - db/seed/cards_seed.sql                  (PostgreSQL UPSERT seed)

Usage:
    python3 scripts/generate_cards.py
"""

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# ─── Paths ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
YAML_DIR = ROOT / "data" / "cards"
MD_OUT = ROOT / "docs" / "game_design" / "CARDS.md"
SEED_OUT = ROOT / "db" / "seed" / "cards_seed.sql"
GO_JSON_OUT = ROOT / "packages" / "gamedata" / "cache" / "cards_gen.json"
DOTNET_JSON_OUT = ROOT / "packages" / "dotnet" / "cache" / "cards_gen.json"

# ─── Constants ──────────────────────────────────────────
COMPUTE_TYPES = {"Compute", "Container", "Orchestrator", "Serverless", "AI/ML"}
DATA_TYPES = {"Database", "ObjectStorage", "CacheDB"}
SUPPORT_TYPES = {"Platform", "Attachment", "Strategy", "Reactive", "Incident"}
LOG_TYPES = {"Log"}
ALL_CARD_TYPES = COMPUTE_TYPES | DATA_TYPES | SUPPORT_TYPES | LOG_TYPES

VALID_RESTRICTION = {"unlimited", "limited", "semi_limited", "forbidden"}
VALID_FACTIONS = {"SHE", "Tenki", "Sugar", "Tuners", "Neutral"}

COMPUTE_STAT_KEYS = {"throughput", "availability", "maintenance_cost", "sla_penalty"}
DATA_STAT_KEYS = {"yield", "availability", "maintenance_cost", "sla_penalty"}

FACTION_ORDER = ["SHE", "Tenki", "Sugar", "Tuners", "Neutral"]
FACTION_FILE_MAP = {"SHE": "sd"}

CATEGORY_ORDER = [
    ("コンピュート系リソース", {"Compute", "Container", "Orchestrator", "Serverless"}),
    ("AI/ML系リソース", {"AI/ML"}),
    ("DB系リソース", {"Database", "CacheDB"}),
    ("オブジェクトストレージ", {"ObjectStorage"}),
    ("プラットフォーム", {"Platform"}),
    ("アタッチメント", {"Attachment"}),
    ("ストラテジー", {"Strategy"}),
    ("インシデント", {"Incident"}),
    ("リアクティブ", {"Reactive"}),
    ("ログ", {"Log"}),
]


# ─── Load ───────────────────────────────────────────────
def load_all_cards():
    """Load all YAML files and return (all_cards, faction_data)."""
    all_cards = []
    faction_data = {}

    for faction in FACTION_ORDER:
        file_stem = FACTION_FILE_MAP.get(faction, faction.lower())
        filepath = YAML_DIR / f"{file_stem}.yaml"
        if not filepath.exists():
            print(f"WARNING: {filepath} not found, skipping", file=sys.stderr)
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        faction_name = data.get("faction", faction)
        display_name = data.get("display_name", faction_name)
        cards = data.get("cards", [])

        for card in cards:
            card.setdefault("faction", faction_name)

        faction_data[faction_name] = {
            "display_name": display_name,
            "cards": cards,
            "restriction_cards": data.get("restriction_cards", []),
        }
        all_cards.extend(cards)

    return all_cards, faction_data


# ─── Validate ──────────────────────────────────────────
def validate(cards):
    """Run all validation checks. Returns list of error strings."""
    errors = []
    seen_nos = {}
    seen_consts = {}
    seen_card_ids = {}

    for card in cards:
        card_no = card.get("card_no")
        card_name = card.get("card_name", "???")
        label = f"#{card_no} {card_name}"

        is_log = card.get("card_type") in LOG_TYPES
        if is_log:
            required = ["card_no", "card_id", "card_name", "const_name", "card_type", "restriction", "is_active"]
        else:
            required = ["card_no", "card_id", "card_name", "const_name", "card_type", "resizable", "elastic", "restriction", "is_active", "stats"]
        for field in required:
            if field not in card:
                errors.append(f"{label}: missing required field '{field}'")

        if card_no is None:
            continue

        if card_no in seen_nos:
            errors.append(f"{label}: duplicate card_no (also used by {seen_nos[card_no]})")
        else:
            seen_nos[card_no] = card_name

        card_id = card.get("card_id", "")
        if card_id:
            if not re.match(r"^(SH|TK|SL|TN|NT)-\d{4}$", card_id):
                errors.append(f"{label}: card_id '{card_id}' must match XX-NNNN format (SH/TK/SL/TN/NT)")
            if card_id in seen_card_ids:
                errors.append(f"{label}: duplicate card_id '{card_id}' (also used by #{seen_card_ids[card_id]})")
            else:
                seen_card_ids[card_id] = card_no

        const_name = card.get("const_name", "")
        if const_name:
            if const_name in seen_consts:
                errors.append(f"{label}: duplicate const_name '{const_name}' (also used by #{seen_consts[const_name]})")
            else:
                seen_consts[const_name] = card_no
            if not re.match(r"^[A-Z][a-zA-Z0-9]*$", const_name):
                errors.append(f"{label}: const_name '{const_name}' is not a valid Go identifier (must be ASCII PascalCase)")

        card_type = card.get("card_type", "")
        if card_type and card_type not in ALL_CARD_TYPES:
            errors.append(f"{label}: invalid card_type '{card_type}'")

        for bf in ("resizable", "elastic"):
            val = card.get(bf)
            if val is not None and not isinstance(val, bool):
                errors.append(f"{label}: '{bf}' must be a boolean, got {type(val).__name__}")

        restriction = card.get("restriction", "")
        if restriction and restriction not in VALID_RESTRICTION:
            errors.append(f"{label}: invalid restriction '{restriction}'")

        if card.get("elastic"):
            for ef in ("free_tier", "cost_per_request"):
                if ef not in card:
                    errors.append(f"{label}: elastic card missing required field '{ef}'")

        stats = card.get("stats", {})
        if card_type and stats:
            if card_type in COMPUTE_TYPES:
                missing = COMPUTE_STAT_KEYS - set(stats.keys())
                if missing:
                    errors.append(f"{label}: compute card missing stats: {missing}")
            elif card_type in DATA_TYPES:
                missing = DATA_STAT_KEYS - set(stats.keys())
                if missing:
                    errors.append(f"{label}: data card missing stats: {missing}")
            for stat_key, stat_val in stats.items():
                if not isinstance(stat_val, (int, float)):
                    errors.append(f"{label}: stat '{stat_key}' must be a number, got {type(stat_val).__name__}")
                elif stat_val < 0:
                    errors.append(f"{label}: stat '{stat_key}' must be non-negative, got {stat_val}")

        deploy_turns = card.get("deploy_turns")
        if deploy_turns is not None:
            if not isinstance(deploy_turns, int) or deploy_turns not in (0, 1, 2):
                errors.append(f"{label}: deploy_turns must be 0, 1, or 2, got {deploy_turns}")

        if card.get("elastic"):
            for ef in ("elastic_increment", "free_tier", "cost_per_request"):
                val = card.get(ef)
                if val is not None and (not isinstance(val, (int, float)) or val < 0):
                    errors.append(f"{label}: '{ef}' must be a non-negative number, got {val}")

        faction = card.get("faction", "")
        if faction and faction not in VALID_FACTIONS:
            errors.append(f"{label}: invalid faction '{faction}'")

        is_active = card.get("is_active")
        if is_active is not None and not isinstance(is_active, bool):
            errors.append(f"{label}: 'is_active' must be a boolean, got {type(is_active).__name__}")

        if card_no is not None:
            if not isinstance(card_no, int) or card_no <= 0:
                errors.append(f"{label}: card_no must be a positive integer, got {card_no}")

    return errors


# ─── Generate JSON ─────────────────────────────────────
def generate_json(cards, *, out_path):
    """Generate cards_gen.json."""
    json_out = Path(out_path)
    output = []
    for card in sorted(cards, key=lambda c: c["card_id"]):
        stats = dict(card["stats"].items()) if card.get("stats") else {}
        deploy_turns = card.get("deploy_turns", 0)
        entry = {
            "card_id": card["card_id"],
            "card_name": card["card_name"],
            "resource_label": card.get("resource_label", ""),
            "faction": card["faction"],
            "card_type": card["card_type"],
            "deploy_turns": deploy_turns,
            "resizable": card.get("resizable", False),
            "elastic": card.get("elastic", False),
            "elastic_increment": card.get("elastic_increment", 0),
            "free_tier": card.get("free_tier", 0),
            "cost_per_request": card.get("cost_per_request", 0),
            "stats": stats,
            "restriction": card["restriction"],
            "is_active": card["is_active"],
        }
        if card.get("effect_text"):
            entry["effect_text"] = card["effect_text"]
        if card.get("effects"):
            entry["effects"] = card["effects"]
        if card.get("passive_effects"):
            entry["passive_effects"] = card["passive_effects"]
        if card.get("platform_effects"):
            entry["platform_effects"] = card["platform_effects"]
        if card.get("attachment_effects"):
            entry["attachment_effects"] = card["attachment_effects"]
        output.append(entry)

    json_out.parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return len(output)


# ─── Generate Seed SQL ─────────────────────────────────
def _sql_escape(s):
    """Escape a string for PostgreSQL single-quoted literal."""
    if s is None:
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def generate_seed_sql(cards, *, out_path):
    """Generate db/seed/cards_seed.sql with UPSERT statements."""
    sql_out = Path(out_path)
    sorted_cards = sorted(cards, key=lambda c: c["card_id"])

    lines = []
    lines.append("-- Auto-generated by scripts/generate_cards.py. DO NOT EDIT.")
    lines.append("")
    lines.append("INSERT INTO card_definitions")
    lines.append("  (card_id, card_name, resource_label, faction, card_type,")
    lines.append("   resizable, elastic, stats, effect_text, effects, restriction, is_active)")
    lines.append("VALUES")

    value_rows = []
    for card in sorted_cards:
        card_id = _sql_escape(card["card_id"])
        card_name = _sql_escape(card["card_name"])
        resource_label = _sql_escape(card.get("resource_label", ""))
        faction = _sql_escape(card["faction"])
        card_type = _sql_escape(card["card_type"])
        resizable = "true" if card.get("resizable", False) else "false"
        elastic = "true" if card.get("elastic", False) else "false"

        stats = card.get("stats")
        stats_json = _sql_escape(json.dumps(stats, ensure_ascii=False)) + "::jsonb" if stats else "'{}'::jsonb"

        effect_text = _sql_escape(card.get("effect_text")) if card.get("effect_text") and card["effect_text"] != "—" else "NULL"

        effects = card.get("effects")
        effects_json = _sql_escape(json.dumps(effects, ensure_ascii=False)) + "::jsonb" if effects else "NULL"

        restriction = _sql_escape(card["restriction"])
        is_active = "true" if card["is_active"] else "false"

        row = (
            f"  ({card_id}, {card_name}, {resource_label}, {faction}, {card_type},\n"
            f"   {resizable}, {elastic}, {stats_json},\n"
            f"   {effect_text},\n"
            f"   {effects_json},\n"
            f"   {restriction}, {is_active})"
        )
        value_rows.append(row)

    lines.append(",\n\n".join(value_rows))
    lines.append("")
    lines.append("ON CONFLICT (card_id) DO UPDATE SET")
    lines.append("  card_name      = EXCLUDED.card_name,")
    lines.append("  resource_label = EXCLUDED.resource_label,")
    lines.append("  faction        = EXCLUDED.faction,")
    lines.append("  card_type      = EXCLUDED.card_type,")
    lines.append("  resizable      = EXCLUDED.resizable,")
    lines.append("  elastic        = EXCLUDED.elastic,")
    lines.append("  stats          = EXCLUDED.stats,")
    lines.append("  effect_text    = EXCLUDED.effect_text,")
    lines.append("  effects        = EXCLUDED.effects,")
    lines.append("  restriction    = EXCLUDED.restriction,")
    lines.append("  is_active      = EXCLUDED.is_active,")
    lines.append("  updated_at     = now();")
    lines.append("")

    sql_out.parent.mkdir(parents=True, exist_ok=True)
    with open(sql_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")

    return len(sorted_cards)


# ─── Generate CARDS.md ─────────────────────────────────
def _scalability_display(card):
    ct = card["card_type"]
    display_type = {"ObjectStorage": "Object Storage", "CacheDB": "Cache DB"}.get(ct, ct)
    r = card.get("resizable", False)
    e = card.get("elastic", False)
    if r and e:
        return f"{display_type} (R+E)"
    elif r:
        return f"{display_type} (R)"
    elif e:
        return f"{display_type} (E)"
    return display_type


def _tp_display(card):
    return str(card["stats"].get("throughput", 0))


def _yield_display(card):
    return str(card["stats"].get("yield", 0))


def _effect_display(card):
    text = card.get("effect_text", "")
    if not text:
        return "—"
    return text.replace("\n", "<br>")


def generate_md(cards, faction_data, *, out_path):
    """Generate docs/CARDS.md."""
    md_out = Path(out_path)
    total = len(cards)
    lines = []

    lines.append("<!-- This file is auto-generated by scripts/generate_cards.py. DO NOT EDIT. -->")
    lines.append("")
    lines.append("# Overload Party — Card List")
    lines.append("")
    lines.append(f"**全 {total} 枚**")
    lines.append("")
    lines.append("---")
    lines.append("")

    limited = []
    semi_limited = []
    for f in FACTION_ORDER:
        if f not in faction_data:
            continue
        fd = faction_data[f]
        for c in fd["cards"]:
            if c.get("restriction") == "limited":
                limited.append((c, fd))
            elif c.get("restriction") == "semi_limited":
                semi_limited.append((c, fd))

    if limited:
        lines.append("### 制限カード（1枚制限）")
        lines.append("")
        lines.append("| カード名 | 理由 |")
        lines.append("|---------|------|")
        for card, _ in limited:
            reason = card.get("restriction_reason", "")
            lines.append(f"| {card['card_name']} | {reason} |")
        lines.append("")

    if semi_limited:
        lines.append("### 準制限カード（2枚制限）")
        lines.append("")
        lines.append("| カード名 | 理由 |")
        lines.append("|---------|------|")
        for card, _ in semi_limited:
            reason = card.get("restriction_reason", "")
            lines.append(f"| {card['card_name']} | {reason} |")
        lines.append("")

    lines.append("**上記以外のカードはすべて 3枚まで投入可能。**")
    lines.append("")
    lines.append("---")
    lines.append("")

    summary = {}

    for faction in FACTION_ORDER:
        if faction not in faction_data:
            continue
        fd = faction_data[faction]
        faction_cards = fd["cards"]
        faction_total = len(faction_cards)
        display = fd["display_name"]

        lines.append(f"## {display}— {faction_total}枚")
        lines.append("")

        summary[faction] = {}

        for cat_name, cat_types in CATEGORY_ORDER:
            cat_cards = sorted(
                [c for c in faction_cards if c["card_type"] in cat_types],
                key=lambda c: c["card_id"]
            )
            if not cat_cards:
                summary[faction][cat_name] = 0
                continue

            summary[faction][cat_name] = len(cat_cards)

            lines.append(f"### {cat_name}（{len(cat_cards)}枚）")
            lines.append("")

            is_compute = cat_types & COMPUTE_TYPES
            is_data = cat_types & DATA_TYPES
            is_support = cat_types & SUPPORT_TYPES

            if is_compute:
                lines.append("| ID | カード名 | タイプ | スループット | 可用性 | 維持コスト | デプロイT | SLAペナルティ | 効果 |")
                lines.append("|------|---------|-------|-----|-----|-----|-----|-----|------|")
                for c in cat_cards:
                    dt = c.get("deploy_turns", 0)
                    lines.append(
                        f"| {c['card_id']} | {c['card_name']} | {_scalability_display(c)} "
                        f"| {_tp_display(c)} | {c['stats']['availability']} "
                        f"| {c['stats']['maintenance_cost']} | {dt} "
                        f"| {c['stats']['sla_penalty']} | {_effect_display(c)} |"
                    )
            elif is_data:
                lines.append("| ID | カード名 | タイプ | Yield | 可用性 | 維持コスト | デプロイT | SLAペナルティ | 効果 |")
                lines.append("|------|---------|-------|-----|-----|-----|-----|-----|------|")
                for c in cat_cards:
                    dt = c.get("deploy_turns", 0)
                    lines.append(
                        f"| {c['card_id']} | {c['card_name']} | {_scalability_display(c)} "
                        f"| {_yield_display(c)} | {c['stats']['availability']} "
                        f"| {c['stats']['maintenance_cost']} | {dt} "
                        f"| {c['stats']['sla_penalty']} | {_effect_display(c)} |"
                    )
            elif is_support or (cat_types & LOG_TYPES):
                lines.append("| ID | カード名 | 効果 |")
                lines.append("|------|---------|------|")
                for c in cat_cards:
                    lines.append(f"| {c['card_id']} | {c['card_name']} | {_effect_display(c)} |")

            lines.append("")

        lines.append("---")
        lines.append("")

    # Summary table
    lines.append("## カード総数サマリ")
    lines.append("")
    header_names = [faction_data[f]["display_name"] if f in faction_data else f for f in FACTION_ORDER]
    lines.append("| カテゴリ | " + " | ".join(header_names) + " | 合計 |")
    lines.append("|---------|" + "|".join(["------" for _ in FACTION_ORDER]) + "|------|")

    grand_total = {f: 0 for f in FACTION_ORDER}
    for cat_name, _ in CATEGORY_ORDER:
        row = f"| {cat_name} "
        cat_total = 0
        for faction in FACTION_ORDER:
            count = summary.get(faction, {}).get(cat_name, 0)
            grand_total[faction] += count
            cat_total += count
            row += f"| {count} "
        row += f"| {cat_total} |"
        lines.append(row)

    row = "| **合計** "
    all_total = 0
    for faction in FACTION_ORDER:
        row += f"| **{grand_total[faction]}** "
        all_total += grand_total[faction]
    row += f"| **{all_total}** |"
    lines.append(row)
    lines.append("")

    md_out.parent.mkdir(parents=True, exist_ok=True)
    with open(md_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")

    return total


# ─── Main ──────────────────────────────────────────────
def main():
    if not YAML_DIR.exists():
        print(f"ERROR: YAML directory not found: {YAML_DIR}", file=sys.stderr)
        sys.exit(1)

    cards, faction_data = load_all_cards()
    if not cards:
        print("ERROR: No cards loaded from YAML files", file=sys.stderr)
        sys.exit(1)

    errors = validate(cards)
    if errors:
        print(f"Validation failed with {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # cards_gen.json (Go + dotnet)
    go_count = generate_json(cards, out_path=GO_JSON_OUT)
    print(f"Generated {go_count} cards → {GO_JSON_OUT.relative_to(ROOT)}", file=sys.stderr)
    dotnet_count = generate_json(cards, out_path=DOTNET_JSON_OUT)
    print(f"Generated {dotnet_count} cards → {DOTNET_JSON_OUT.relative_to(ROOT)}", file=sys.stderr)

    # CARDS.md
    md_count = generate_md(cards, faction_data, out_path=MD_OUT)
    print(f"Generated {md_count} cards → {MD_OUT.relative_to(ROOT)}", file=sys.stderr)

    # Seed SQL
    seed_count = generate_seed_sql(cards, out_path=SEED_OUT)
    print(f"Generated {seed_count} cards → {SEED_OUT.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
