#!/usr/bin/env python3
"""Generate cards.json, cardno_gen.go, constants Go/TS, and CARDS.md from YAML card definitions.

This script lives in overload-party-common and generates outputs for:
  - common: docs/CARDS.md
  - server: internal/cache/cards_gen.json, internal/cardno/cardno_gen.go, internal/model/constants_gen.go
  - client: src/generated/constants.ts

Usage:
    python3 scripts/generate_from_yaml.py [--server-dir PATH] [--client-dir PATH]

Environment variables (alternative to flags):
    SERVER_DIR  Path to overload-party-server root
    CLIENT_DIR  Path to overload-party-client root
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# ─── Paths ──────────────────────────────────────────────
COMMON_ROOT = Path(__file__).resolve().parent.parent
YAML_DIR = COMMON_ROOT / "data" / "cards"
CONSTANTS_JSON = COMMON_ROOT / "data" / "constants.json"

# Common outputs
MD_OUT = COMMON_ROOT / "docs" / "CARDS.md"

# ─── Constants ──────────────────────────────────────────
COMPUTE_TYPES = {"Compute", "Container", "Orchestrator", "Serverless", "AI/ML"}
DATA_TYPES = {"Database", "NoSQL", "ObjectStorage", "CacheDB", "Datawarehouse"}
SUPPORT_TYPES = {"Platform", "Attachment", "Strategy", "Reactive", "Incident"}
ALL_CARD_TYPES = COMPUTE_TYPES | DATA_TYPES | SUPPORT_TYPES

VALID_SCALABILITY = {"R", "E", "RE", "none"}
VALID_RESTRICTION = {"unlimited", "limited", "semi_limited"}
VALID_FACTIONS = {"SWS", "Aozora", "Guruguru", "Miracle", "Neutral"}

COMPUTE_STAT_KEYS = {"throughput", "availability", "maintenance_cost", "deploy_cost", "sla_penalty"}
DATA_STAT_KEYS = {"dv_gen", "availability", "maintenance_cost", "deploy_cost", "sla_penalty"}
SUPPORT_STAT_KEYS = {"deploy_cost"}

# Faction file order
FACTION_ORDER = ["SWS", "Aozora", "Guruguru", "Miracle", "Neutral"]

# Card category display order within each faction for CARDS.md
CATEGORY_ORDER = [
    ("コンピュート系リソース", {"Compute", "Container", "Orchestrator", "Serverless"}),
    ("AI/ML系リソース", {"AI/ML"}),
    ("DB系リソース", {"Database", "NoSQL", "CacheDB", "Datawarehouse"}),
    ("オブジェクトストレージ", {"ObjectStorage"}),
    ("プラットフォーム", {"Platform"}),
    ("アタッチメント", {"Attachment"}),
    ("ストラテジー", {"Strategy"}),
    ("インシデント", {"Incident"}),
    ("リアクティブ", {"Reactive"}),
]


# ─── Load ───────────────────────────────────────────────
def load_all_cards():
    """Load all YAML files and return (all_cards, faction_data)."""
    all_cards = []
    faction_data = {}  # faction -> {display_name, cards}

    for faction in FACTION_ORDER:
        filename = f"{faction.lower()}.yaml"
        filepath = YAML_DIR / filename
        if not filepath.exists():
            print(f"WARNING: {filepath} not found, skipping", file=sys.stderr)
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        faction_name = data.get("faction", faction)
        display_name = data.get("display_name", faction_name)
        cards = data.get("cards", [])

        # Set faction on each card from file-level faction
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

    for card in cards:
        card_no = card.get("card_no")
        card_name = card.get("card_name", "???")
        label = f"#{card_no} {card_name}"

        # Required fields
        for field in ["card_no", "card_name", "const_name", "card_type", "scalability", "restriction", "is_active", "stats"]:
            if field not in card:
                errors.append(f"{label}: missing required field '{field}'")

        if card_no is None:
            continue

        # Duplicate card_no
        if card_no in seen_nos:
            errors.append(f"{label}: duplicate card_no (also used by {seen_nos[card_no]})")
        else:
            seen_nos[card_no] = card_name

        # Duplicate const_name
        const_name = card.get("const_name", "")
        if const_name:
            if const_name in seen_consts:
                errors.append(f"{label}: duplicate const_name '{const_name}' (also used by #{seen_consts[const_name]})")
            else:
                seen_consts[const_name] = card_no

            # Valid Go identifier
            if not re.match(r"^[A-Z][a-zA-Z0-9]*$", const_name):
                errors.append(f"{label}: const_name '{const_name}' is not a valid Go identifier (must be ASCII PascalCase)")

        # Card type
        card_type = card.get("card_type", "")
        if card_type and card_type not in ALL_CARD_TYPES:
            errors.append(f"{label}: invalid card_type '{card_type}'")

        # Scalability
        scalability = card.get("scalability", "")
        if scalability and scalability not in VALID_SCALABILITY:
            errors.append(f"{label}: invalid scalability '{scalability}'")

        # Restriction
        restriction = card.get("restriction", "")
        if restriction and restriction not in VALID_RESTRICTION:
            errors.append(f"{label}: invalid restriction '{restriction}'")

        # Stats validation
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
            elif card_type in SUPPORT_TYPES:
                missing = SUPPORT_STAT_KEYS - set(stats.keys())
                if missing:
                    errors.append(f"{label}: support card missing stats: {missing}")

    return errors


# ─── Generate JSON ─────────────────────────────────────
def generate_json(cards, server_dir):
    """Generate internal/cache/cards_gen.json in server."""
    json_out = server_dir / "internal" / "cache" / "cards_gen.json"
    output = []
    for card in sorted(cards, key=lambda c: c["card_no"]):
        entry = {
            "card_no": card["card_no"],
            "card_name": card["card_name"],
            "faction": card["faction"],
            "card_type": card["card_type"],
            "scalability": card["scalability"],
            "stats": card["stats"],
            "restriction": card["restriction"],
            "is_active": card["is_active"],
        }
        if card.get("effect_text"):
            entry["effect_text"] = card["effect_text"]
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


# ─── Generate Go (cardno) ─────────────────────────────
def generate_go_cardno(cards, faction_data, server_dir):
    """Generate internal/cardno/cardno_gen.go in server."""
    go_out = server_dir / "internal" / "cardno" / "cardno_gen.go"
    lines = [
        "// Code generated by generate_from_yaml.py; DO NOT EDIT.",
        "",
        "package cardno",
        "",
    ]

    # Group cards by faction
    for faction in FACTION_ORDER:
        if faction not in faction_data:
            continue
        faction_cards = sorted(faction_data[faction]["cards"], key=lambda c: c["card_no"])
        if not faction_cards:
            continue

        display = faction_data[faction]["display_name"]
        lines.append(f"// {display}")
        lines.append("const (")

        # Calculate alignment
        max_const_len = max(len(c["const_name"]) for c in faction_cards)

        for card in faction_cards:
            padding = " " * (max_const_len - len(card["const_name"]) + 1)
            lines.append(f"\t{card['const_name']}{padding}int64 = {card['card_no']:<4} // {card['card_name']}")

        lines.append(")")
        lines.append("")

    # CardNames map
    all_sorted = sorted(cards, key=lambda c: c["card_no"])
    lines.append("// CardNames maps card number to card name.")
    lines.append("var CardNames = map[int64]string{")
    for card in all_sorted:
        lines.append(f'\t{card["card_no"]}: "{card["card_name"]}",')
    lines.append("}")
    lines.append("")

    go_out.parent.mkdir(parents=True, exist_ok=True)
    with open(go_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return len(all_sorted)


# ─── Generate Go (constants) ──────────────────────────
def generate_go_constants(constants, server_dir):
    """Generate internal/model/constants_gen.go from constants.json."""
    go_out = server_dir / "internal" / "model" / "constants_gen.go"

    lines = [
        "// Code generated by generate_from_yaml.py from data/constants.json; DO NOT EDIT.",
        "",
        "package model",
        "",
    ]

    # Phases
    lines.append("// Phase constants.")
    lines.append("const (")
    phase_map = {"draw": "PhaseDraw", "dv_gen": "PhaseDVGen", "main": "PhaseMain", "battle": "PhaseBattle", "end": "PhaseEnd"}
    for phase in constants["phases"]:
        go_name = phase_map.get(phase, f"Phase{phase.title()}")
        lines.append(f'\t{go_name} = "{phase}"')
    lines.append(")")
    lines.append("")

    # Ranks
    lines.append("// Rank constants.")
    lines.append("const (")
    rank_map = {"small": "RankSmall", "medium": "RankMedium", "large": "RankLarge"}
    for rank in constants["ranks"]:
        go_name = rank_map.get(rank, f"Rank{rank.title()}")
        lines.append(f'\t{go_name} = "{rank}"')
    lines.append(")")
    lines.append("")

    # Instance Families
    lines.append("// Instance Family constants.")
    lines.append("const (")
    family_comments = {"M": "Balanced", "C": "Compute-optimized (TP×1.5, AV×0.75)", "R": "Reliability-optimized (TP×0.75, AV×1.5)"}
    for fam in constants["instance_families"]:
        comment = family_comments.get(fam, "")
        if comment:
            lines.append(f'\tFamily{fam} = "{fam}" // {comment}')
        else:
            lines.append(f'\tFamily{fam} = "{fam}"')
    lines.append(")")
    lines.append("")

    # Initial game values
    iv = constants["initial_values"]
    lines.append("// Initial game values.")
    lines.append("const (")
    lines.append(f"\tInitialBudget   = {iv['budget']}")
    lines.append(f"\tInitialDVPool   = {iv['dv_pool']}")
    lines.append(f"\tInitialHand     = {iv['hand_size']}")
    lines.append(f"\tHandLimit       = {iv['hand_limit']}")
    lines.append(f"\tInitialTimeBank = {iv['time_bank']} // seconds ({iv['time_bank'] // 60} minutes)")
    lines.append(f"\tDeckSize        = {iv['deck_size']}")
    lines.append(f"\tMaxAttachments  = {iv['max_attachments']}   // max attachment slots per resource")
    lines.append(f"\tPerTurnBudget   = {iv['per_turn_budget']} // budget added automatically at the start of each turn")
    lines.append(f"\tSlotsPerZone    = {iv['slots_per_zone']}   // number of slots per zone")
    lines.append(")")
    lines.append("")

    # Game status
    lines.append("// Game status constants.")
    lines.append("const (")
    status_map = {
        "waiting": ("GameStatusWaiting", "Waiting for starting resource selection"),
        "selecting": ("GameStatusSelecting", "Both players selecting starting resources"),
        "playing": ("GameStatusPlaying", "Game in progress"),
        "finished": ("GameStatusFinished", "Game ended"),
    }
    for status in constants["game_status"]:
        go_name, comment = status_map.get(status, (f"GameStatus{status.title()}", ""))
        lines.append(f'\t{go_name} = "{status}" // {comment}')
    lines.append(")")
    lines.append("")

    # Win reasons
    lines.append("// Win reason constants.")
    lines.append("const (")
    wr_map = {
        "budget_zero": "WinReasonBudgetZero",
        "system_down": "WinReasonSystemDown",
        "repository_out": "WinReasonRepositoryOut",
        "timeout": "WinReasonTimeout",
        "disconnect": "WinReasonDisconnect",
        "turn_limit": "WinReasonTurnLimit",
        "draw": "WinReasonDraw",
    }
    for wr in constants["win_reasons"]:
        go_name = wr_map.get(wr, f"WinReason{''.join(w.title() for w in wr.split('_'))}")
        lines.append(f'\t{go_name} = "{wr}"')
    lines.append(")")
    lines.append("")

    # Factions
    lines.append("// Faction constants.")
    lines.append("const (")
    for faction in constants["factions"]:
        lines.append(f'\tFaction{faction} = "{faction}"')
    lines.append(")")
    lines.append("")

    # ValidFactions
    lines.append("// ValidFactions is the set of selectable factions (excludes Neutral).")
    lines.append("var ValidFactions = map[string]bool{")
    for faction in constants["selectable_factions"]:
        lines.append(f"\tFaction{faction}: true,")
    lines.append("}")
    lines.append("")

    go_out.parent.mkdir(parents=True, exist_ok=True)
    with open(go_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(go_out.relative_to(server_dir))


# ─── Generate TypeScript (constants) ──────────────────
def generate_ts_constants(constants, client_dir):
    """Generate src/generated/constants.ts from constants.json."""
    ts_out = client_dir / "src" / "generated" / "constants.ts"

    lines = [
        "// Code generated by generate_from_yaml.py from data/constants.json; DO NOT EDIT.",
        "",
    ]

    # Phases
    phases = constants["phases"]
    lines.append(f"export const PHASES = {json.dumps(phases)} as const;")
    lines.append(f"export type GamePhase = (typeof PHASES)[number] | 'selecting';")
    lines.append("")

    # Zones
    zones = constants["zones"]
    lines.append(f"export const ZONES = {json.dumps(zones)} as const;")
    lines.append(f"export type Zone = (typeof ZONES)[number];")
    lines.append("")

    # Ranks
    ranks = constants["ranks"]
    lines.append(f"export const RANKS = {json.dumps(ranks)} as const;")
    lines.append(f"export type Rank = (typeof RANKS)[number];")
    lines.append("")

    # Instance families
    families = constants["instance_families"]
    lines.append(f"export const INSTANCE_FAMILIES = {json.dumps(families)} as const;")
    lines.append(f"export type InstanceFamily = (typeof INSTANCE_FAMILIES)[number] | '';")
    lines.append("")

    # Factions
    factions = [f.lower() for f in constants["selectable_factions"]]
    lines.append(f"export const FACTIONS = {json.dumps(constants['factions'])} as const;")
    lines.append(f"export const SELECTABLE_FACTIONS = {json.dumps(factions)} as const;")
    lines.append(f"export type FactionId = (typeof SELECTABLE_FACTIONS)[number];")
    lines.append("")

    # Game status
    lines.append(f"export const GAME_STATUS = {json.dumps(constants['game_status'])} as const;")
    lines.append(f"export type GameStatus = (typeof GAME_STATUS)[number];")
    lines.append("")

    # Win reasons
    lines.append(f"export const WIN_REASONS = {json.dumps(constants['win_reasons'])} as const;")
    lines.append(f"export type WinReason = (typeof WIN_REASONS)[number];")
    lines.append("")

    # Action types
    lines.append(f"export const ACTION_TYPES = {json.dumps(constants['action_types'])} as const;")
    lines.append(f"export type GameActionType = (typeof ACTION_TYPES)[number];")
    lines.append("")

    # Effect durations
    lines.append(f"export const EFFECT_DURATIONS = {json.dumps(constants['effect_durations'])} as const;")
    lines.append(f"export type EffectDuration = (typeof EFFECT_DURATIONS)[number];")
    lines.append("")

    # Restriction values
    lines.append(f"export const RESTRICTION_VALUES = {json.dumps(constants['restriction_values'])} as const;")
    lines.append(f"export type Restriction = (typeof RESTRICTION_VALUES)[number];")
    lines.append("")

    # Initial values
    iv = constants["initial_values"]
    lines.append("export const INITIAL_VALUES = {")
    for key, val in iv.items():
        # camelCase conversion: hand_size → handSize
        camel = re.sub(r'_([a-z])', lambda m: m.group(1).upper(), key)
        lines.append(f"  {camel}: {val},")
    lines.append("} as const;")
    lines.append("")

    # Level system
    lv = constants["level"]
    lines.append("export const LEVEL = {")
    lines.append(f"  expFormula: '{lv['exp_formula']}',")
    lines.append(f"  expWin: {lv['exp_win']},")
    lines.append(f"  expLoss: {lv['exp_loss']},")
    lines.append(f"  expDraw: {lv['exp_draw']},")
    lines.append("} as const;")
    lines.append("")

    ts_out.parent.mkdir(parents=True, exist_ok=True)
    with open(ts_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(ts_out.relative_to(client_dir))


# ─── Generate CARDS.md ─────────────────────────────────
def _scalability_display(card):
    """Return card_type with scalability suffix for display."""
    s = card["scalability"]
    ct = card["card_type"]
    # Map internal types to display types
    display_type = {
        "ObjectStorage": "Object Storage",
        "CacheDB": "Cache DB",
    }.get(ct, ct)
    if s == "R":
        return f"{display_type} (R)"
    elif s == "E":
        return f"{display_type} (E)"
    elif s == "RE":
        return f"{display_type} (R+E)"
    return display_type


def _tp_display(card):
    """Format throughput with optional max."""
    tp = card["stats"].get("throughput", 0)
    tp_max = card.get("tp_max")
    if tp_max:
        return f"{tp}→{tp_max}"
    return str(tp)


def _dv_display(card):
    """Format DV with optional max."""
    dv = card["stats"].get("dv_gen", 0)
    dv_max = card.get("dv_max")
    if dv_max:
        return f"{dv}→{dv_max}"
    return str(dv)


def _effect_display(card):
    """Format effect text for markdown table."""
    text = card.get("effect_text", "")
    if not text:
        return "—"
    # Replace newlines with <br> for markdown table cells
    return text.replace("\n", "<br>")


def generate_md(cards, faction_data):
    """Generate docs/CARDS.md."""
    total = len(cards)
    lines = []

    # Header
    lines.append("<!-- This file is auto-generated by scripts/generate_from_yaml.py. DO NOT EDIT. -->")
    lines.append("")
    lines.append(f"# Overload Party v1.6 — Card List")
    lines.append("")
    lines.append(f"**全 {total} 枚**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Restriction cards
    limited = [(c, fd) for f in FACTION_ORDER if f in faction_data
               for fd in [faction_data[f]] for c in fd["cards"]
               if c.get("restriction") == "limited"]
    semi_limited = [(c, fd) for f in FACTION_ORDER if f in faction_data
                    for fd in [faction_data[f]] for c in fd["cards"]
                    if c.get("restriction") == "semi_limited"]

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

    # Per-faction sections
    summary = {}  # faction -> {category_name -> count}

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
                key=lambda c: c["card_no"]
            )
            if not cat_cards:
                summary[faction][cat_name] = 0
                continue

            summary[faction][cat_name] = len(cat_cards)

            lines.append(f"### {cat_name}（{len(cat_cards)}枚）")
            lines.append("")

            # Determine table format based on category
            is_compute = cat_types & COMPUTE_TYPES
            is_data = cat_types & DATA_TYPES
            is_support = cat_types & SUPPORT_TYPES

            if is_compute:
                lines.append("| # | カード名 | タイプ | スループット | 可用性 | 維持コスト | 開発コスト | SLAペナルティ | 効果 | 元ネタ |")
                lines.append("|---|---------|-------|-----|-----|-----|-----|-----|------|----------|")
                for c in cat_cards:
                    origin = c.get("origin", "")
                    lines.append(
                        f"| {c['card_no']} | {c['card_name']} | {_scalability_display(c)} "
                        f"| {_tp_display(c)} | {c['stats']['availability']} "
                        f"| {c['stats']['maintenance_cost']} | {c['stats']['deploy_cost']} "
                        f"| {c['stats']['sla_penalty']} | {_effect_display(c)} | {origin} |"
                    )
            elif is_data:
                lines.append("| # | カード名 | タイプ | DV | 可用性 | 維持コスト | 開発コスト | SLAペナルティ | 効果 | 元ネタ |")
                lines.append("|---|---------|-------|-----|-----|-----|-----|-----|------|----------|")
                for c in cat_cards:
                    origin = c.get("origin", "")
                    lines.append(
                        f"| {c['card_no']} | {c['card_name']} | {_scalability_display(c)} "
                        f"| {_dv_display(c)} | {c['stats']['availability']} "
                        f"| {c['stats']['maintenance_cost']} | {c['stats']['deploy_cost']} "
                        f"| {c['stats']['sla_penalty']} | {_effect_display(c)} | {origin} |"
                    )
            elif is_support:
                lines.append("| # | カード名 | 効果 | 元ネタ |")
                lines.append("|---|---------|------|----------|")
                for c in cat_cards:
                    origin = c.get("origin", "")
                    lines.append(f"| {c['card_no']} | {c['card_name']} | {_effect_display(c)} | {origin} |")

            lines.append("")

        lines.append("---")
        lines.append("")

    # Summary table
    lines.append("## カード総数サマリ")
    lines.append("")
    lines.append("| カテゴリ | SWS | Aozora | Guruguru | Miracle | Neutral | 合計 |")
    lines.append("|---------|-----|--------|--------|-----|---------|------|")

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

    # Grand total row
    row = "| **合計** "
    all_total = 0
    for faction in FACTION_ORDER:
        row += f"| **{grand_total[faction]}** "
        all_total += grand_total[faction]
    row += f"| **{all_total}** |"
    lines.append(row)
    lines.append("")

    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return total


# ─── Main ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate card data and constants")
    parser.add_argument("--server-dir", type=Path,
                        default=os.environ.get("SERVER_DIR"),
                        help="Path to overload-party-server root")
    parser.add_argument("--client-dir", type=Path,
                        default=os.environ.get("CLIENT_DIR"),
                        help="Path to overload-party-client root")
    args = parser.parse_args()

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

    # Load shared constants
    with open(CONSTANTS_JSON, "r", encoding="utf-8") as f:
        constants = json.load(f)

    # Always generate common outputs
    md_count = generate_md(cards, faction_data)
    print(f"Generated {md_count} cards → {MD_OUT.relative_to(COMMON_ROOT)}", file=sys.stderr)

    # Server outputs
    server_dir = Path(args.server_dir) if args.server_dir else None
    if server_dir and server_dir.exists():
        json_count = generate_json(cards, server_dir)
        go_count = generate_go_cardno(cards, faction_data, server_dir)
        go_const_path = generate_go_constants(constants, server_dir)
        print(f"Generated {json_count} cards → {server_dir.name}/internal/cache/cards_gen.json", file=sys.stderr)
        print(f"Generated {go_count} constants → {server_dir.name}/internal/cardno/cardno_gen.go", file=sys.stderr)
        print(f"Generated constants → {server_dir.name}/{go_const_path}", file=sys.stderr)
    else:
        print("SKIP: server outputs (--server-dir not set or not found)", file=sys.stderr)

    # Client outputs
    client_dir = Path(args.client_dir) if args.client_dir else None
    if client_dir and client_dir.exists():
        ts_path = generate_ts_constants(constants, client_dir)
        print(f"Generated constants → {client_dir.name}/{ts_path}", file=sys.stderr)
    else:
        print("SKIP: client outputs (--client-dir not set or not found)", file=sys.stderr)


if __name__ == "__main__":
    main()
