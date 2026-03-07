#!/usr/bin/env python3
"""Generate cards.json, cardno_gen.go, constants Go/TS/C#, and CARDS.md from YAML card definitions.

This script lives in overload-party-common and generates outputs for:
  - common: docs/CARDS.md, cardno/cardno_gen.go
  - gateway: internal/cache/cards_gen.json, internal/model/*_gen.go, internal/constants/constants_gen.go
  - battle:  src/OverloadParty.Battle.Models/GameConstants_gen.cs, EventData_gen.cs
  - client:  src/generated/constants.ts, eventData.ts

Usage:
    python3 scripts/generate_from_yaml.py [--gateway-dir PATH] [--battle-dir PATH] [--client-dir PATH]

Environment variables (alternative to flags):
    GATEWAY_DIR  Path to overload-party-gateway root
    BATTLE_DIR   Path to overload-party-battle root
    CLIENT_DIR   Path to overload-party-client root
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
EVENT_SCHEMAS_JSON = COMMON_ROOT / "data" / "event_schemas.json"
MODELS_YAML = COMMON_ROOT / "data" / "models.yaml"

# Common outputs
MD_OUT = COMMON_ROOT / "docs" / "CARDS.md"

# ─── Constants ──────────────────────────────────────────
COMPUTE_TYPES = {"Compute", "Container", "Orchestrator", "Serverless", "AI/ML"}
DATA_TYPES = {"Database", "ObjectStorage", "CacheDB", "Datawarehouse"}
SUPPORT_TYPES = {"Platform", "Attachment", "Strategy", "Reactive", "Incident"}
ALL_CARD_TYPES = COMPUTE_TYPES | DATA_TYPES | SUPPORT_TYPES


VALID_RESTRICTION = {"unlimited", "limited", "semi_limited"}
VALID_FACTIONS = {"SD", "Tenki", "Sugar", "Tuners", "Neutral"}

COMPUTE_STAT_KEYS = {"throughput", "availability", "maintenance_cost", "sla_penalty"}
DATA_STAT_KEYS = {"yield", "availability", "maintenance_cost", "sla_penalty"}

# Faction file order
FACTION_ORDER = ["SD", "Tenki", "Sugar", "Tuners", "Neutral"]

# Card category display order within each faction for CARDS.md
CATEGORY_ORDER = [
    ("コンピュート系リソース", {"Compute", "Container", "Orchestrator", "Serverless"}),
    ("AI/ML系リソース", {"AI/ML"}),
    ("DB系リソース", {"Database", "CacheDB", "Datawarehouse"}),
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
        for field in ["card_no", "card_name", "const_name", "card_type", "resizable", "elastic", "restriction", "is_active", "stats"]:
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

        # Resizable / Elastic
        for bf in ("resizable", "elastic"):
            val = card.get(bf)
            if val is not None and not isinstance(val, bool):
                errors.append(f"{label}: '{bf}' must be a boolean, got {type(val).__name__}")

        # Restriction
        restriction = card.get("restriction", "")
        if restriction and restriction not in VALID_RESTRICTION:
            errors.append(f"{label}: invalid restriction '{restriction}'")

        # Elastic card validation: require free_tier and cost_per_request
        if card.get("elastic"):
            for ef in ("free_tier", "cost_per_request"):
                if ef not in card:
                    errors.append(f"{label}: elastic card missing required field '{ef}'")

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

    return errors


# ─── Generate JSON ─────────────────────────────────────
def generate_json(cards, repo_dir):
    """Generate internal/cache/cards_gen.json in given repo."""
    json_out = repo_dir / "internal" / "cache" / "cards_gen.json"
    output = []
    for card in sorted(cards, key=lambda c: c["card_no"]):
        # Strip deploy_cost from stats (deprecated)
        stats = {k: v for k, v in card["stats"].items() if k != "deploy_cost"} if card.get("stats") else {}
        deploy_turns = card.get("deploy_turns", 0)
        entry = {
            "card_no": card["card_no"],
            "card_name": card["card_name"],
            "resource_label": card.get("resource_label", ""),
            "faction": card["faction"],
            "card_type": card["card_type"],
            "deploy_turns": deploy_turns,
            "resizable": card["resizable"],
            "elastic": card["elastic"],
            "elastic_increment": card.get("elastic_increment", 0),
            "free_tier": card.get("free_tier", 0),
            "cost_per_request": card.get("cost_per_request", 0),
            "stats": stats,
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
def generate_go_cardno(cards, faction_data):
    """Generate cardno/cardno_gen.go in common."""
    go_out = COMMON_ROOT / "cardno" / "cardno_gen.go"
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


# ─── Generate Go models from models.yaml ──────────────
def _go_type_needs_import(type_str):
    """Detect imports required by a Go type string."""
    imports = set()
    if "time.Time" in type_str or "time." in type_str:
        imports.add("time")
    if "json.RawMessage" in type_str:
        imports.add("encoding/json")
    if "civil.Date" in type_str or "civil." in type_str:
        imports.add("cloud.google.com/go/civil")
    return imports


def generate_go_models(repo_dir, target):
    """Generate internal/model/*_gen.go from models.yaml.

    Args:
        repo_dir: Path to the repo root (gateway or battle).
        target: "gateway" or "battle".
    """
    with open(MODELS_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    generated = []
    for file_def in data["files"]:
        file_target = file_def.get("target", "both")
        # "both" matches all; otherwise must match exactly
        if file_target != "both" and file_target != target:
            continue

        name = file_def["name"]
        out_path = repo_dir / "internal" / "model" / f"{name}_gen.go"

        lines = [
            "// Code generated by generate_from_yaml.py from data/models.yaml; DO NOT EDIT.",
            "",
            "package model",
            "",
        ]

        # Collect imports from explicit list + field types
        declared_imports = set(file_def.get("imports", []))
        for td in file_def.get("types", []):
            for field in td.get("fields", []):
                declared_imports |= _go_type_needs_import(str(field["type"]))

        # Build import block
        if declared_imports:
            std_imports = sorted(i for i in declared_imports if "/" not in i)
            ext_imports = sorted(i for i in declared_imports if "/" in i)
            lines.append("import (")
            for imp in std_imports:
                lines.append(f'\t"{imp}"')
            if std_imports and ext_imports:
                lines.append("")
            for imp in ext_imports:
                lines.append(f'\t"{imp}"')
            lines.append(")")
            lines.append("")

        # Type aliases
        for ta in file_def.get("type_aliases", []):
            lines.append(f"type {ta['name']} {ta['base']}")
        if file_def.get("type_aliases"):
            lines.append("")

        # Constants
        for cgroup in file_def.get("constants", []):
            ctype = cgroup["type"]
            lines.append("const (")
            for cv in cgroup["values"]:
                lines.append(f'\t{cv["name"]} {ctype} = "{cv["value"]}"')
            lines.append(")")
            lines.append("")

        # Structs
        for td in file_def.get("types", []):
            if td.get("comment"):
                lines.append(f"// {td['comment']}")
            lines.append(f"type {td['name']} struct {{")

            # Calculate field name alignment
            fields = td.get("fields", [])
            if fields:
                max_name_len = max(len(f["name"]) for f in fields)
                max_type_len = max(len(str(f["type"])) for f in fields)

            for field in fields:
                fname = field["name"]
                ftype = str(field["type"])
                # Build struct tag
                tags = []
                if "json" in field:
                    tags.append(f'json:"{field["json"]}"')
                if "db" in field:
                    tags.append(f'db:"{field["db"]}"')
                tag_str = " ".join(tags)

                name_pad = " " * (max_name_len - len(fname) + 1)
                type_pad = " " * (max_type_len - len(ftype) + 1)

                if tag_str:
                    line = f"\t{fname}{name_pad}{ftype}{type_pad}`{tag_str}`"
                else:
                    line = f"\t{fname}{name_pad}{ftype}"

                if field.get("comment"):
                    line += f" // {field['comment']}"
                lines.append(line)

            lines.append("}")
            lines.append("")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        generated.append(name)

    return generated


# ─── Generate Go (constants per repo) ─────────────────

# Target mapping for constant groups.
# "both" = gateway + battle, "battle" = battle only, "gateway" = gateway only.
CONST_TARGETS = {
    "phases": "battle",
    "ranks": "battle",
    "instance_families": "battle",
    "initial_values_battle": "battle",
    "initial_values_gateway": "gateway",
    "game_status": "battle",
    "win_reasons": "battle",
    "factions": "both",
    "zones": "battle",
    "action_types": "battle",
    "event_types": "battle",
    "ws_message_types": "battle",
}


def _target_matches(group_target, repo_target):
    """Returns True if a group should be included in the given repo."""
    if group_target == "both":
        return True
    return group_target == repo_target


def generate_repo_constants(constants, repo_dir, target):
    """Generate internal/constants/constants_gen.go for a specific repo.

    Args:
        constants: parsed constants.json dict.
        repo_dir: Path to the repo root.
        target: "gateway" or "battle".
    """
    go_out = repo_dir / "internal" / "constants" / "constants_gen.go"

    lines = [
        "// Code generated by generate_from_yaml.py from data/constants.json; DO NOT EDIT.",
        "",
        "package constants",
        "",
    ]

    # Phases (battle only)
    if _target_matches("battle", target):
        phase_map = {"draw": "PhaseDraw", "yield": "PhaseYield", "main": "PhaseMain", "battle": "PhaseBattle", "end": "PhaseEnd"}
        lines.append("// Phase constants.")
        lines.append("const (")
        for phase in constants["phases"]:
            go_name = phase_map.get(phase, f"Phase{phase.title()}")
            lines.append(f'\t{go_name} = "{phase}"')
        lines.append(")")
        lines.append("")

    # Ranks (battle only)
    if _target_matches("battle", target):
        rank_map = {"small": "RankSmall", "medium": "RankMedium", "large": "RankLarge"}
        lines.append("// Rank constants.")
        lines.append("const (")
        for rank in constants["ranks"]:
            go_name = rank_map.get(rank, f"Rank{rank.title()}")
            lines.append(f'\t{go_name} = "{rank}"')
        lines.append(")")
        lines.append("")

    # Instance Families (battle only)
    if _target_matches("battle", target):
        family_comments = {"M": "Balanced", "C": "Compute-optimized (TP×1.5, AV×0.75)", "R": "Reliability-optimized (TP×0.75, AV×1.5)"}
        lines.append("// Instance Family constants.")
        lines.append("const (")
        for fam in constants["instance_families"]:
            comment = family_comments.get(fam, "")
            if comment:
                lines.append(f'\tFamily{fam} = "{fam}" // {comment}')
            else:
                lines.append(f'\tFamily{fam} = "{fam}"')
        lines.append(")")
        lines.append("")

    # Initial game values — split by target
    iv = constants["initial_values"]
    if _target_matches("battle", target):
        lines.append("// Initial game values.")
        lines.append("const (")
        lines.append(f"\tInitialBudget   = {iv['budget']}")
        lines.append(f"\tInitialInsightPool = {iv['insight_pool']}")
        lines.append(f"\tInitialHand     = {iv['hand_size']}")
        lines.append(f"\tHandLimit       = {iv['hand_limit']}")
        lines.append(f"\tInitialTimeBank = {iv['time_bank']} // seconds ({iv['time_bank'] // 60} minutes)")
        lines.append(f"\tMaxAttachments  = {iv['max_attachments']}   // max attachment slots per resource")
        lines.append(f"\tPerTurnBudget   = {iv['per_turn_budget']} // budget added automatically at the start of each turn")
        lines.append(f"\tSlotsPerZone    = {iv['slots_per_zone']}   // number of slots per zone")
        lines.append(")")
        lines.append("")

    # DeckSize (both)
    lines.append("// Deck size.")
    lines.append("const (")
    lines.append(f"\tDeckSize = {iv['deck_size']}")
    lines.append(")")
    lines.append("")

    # Game status (battle only)
    if _target_matches("battle", target):
        status_map = {
            "waiting": ("GameStatusWaiting", "Waiting for starting resource selection"),
            "playing": ("GameStatusPlaying", "Game in progress"),
            "finished": ("GameStatusFinished", "Game ended"),
        }
        lines.append("// Game status constants.")
        lines.append("const (")
        for status in constants["game_status"]:
            go_name, comment = status_map.get(status, (f"GameStatus{status.title()}", ""))
            lines.append(f'\t{go_name} = "{status}" // {comment}')
        lines.append(")")
        lines.append("")

    # Win reasons (battle only)
    if _target_matches("battle", target):
        wr_map = {
            "budget_zero": "WinReasonBudgetZero",
            "system_down": "WinReasonSystemDown",
            "repository_out": "WinReasonRepositoryOut",
            "timeout": "WinReasonTimeout",
            "disconnect": "WinReasonDisconnect",
            "turn_limit": "WinReasonTurnLimit",
            "draw": "WinReasonDraw",
            "launch_failure": "WinReasonLaunchFailure",
        }
        lines.append("// Win reason constants.")
        lines.append("const (")
        for wr in constants["win_reasons"]:
            go_name = wr_map.get(wr, f"WinReason{''.join(w.title() for w in wr.split('_'))}")
            lines.append(f'\t{go_name} = "{wr}"')
        lines.append(")")
        lines.append("")

    # Factions (both)
    if _target_matches("both", target):
        lines.append("// Faction constants.")
        lines.append("const (")
        for faction in constants["factions"]:
            lines.append(f'\tFaction{faction} = "{faction}"')
        lines.append(")")
        lines.append("")

    # Zones (battle only)
    if _target_matches("battle", target):
        lines.append("// Zone constants.")
        lines.append("const (")
        for zone in constants["zones"]:
            go_name = f"Zone{''.join(w.title() for w in zone.split('_'))}"
            lines.append(f'\t{go_name} = "{zone}"')
        lines.append(")")
        lines.append("")

    # Action types (battle only)
    if _target_matches("battle", target):
        lines.append("// Action type constants.")
        lines.append("const (")
        for action in constants["action_types"]:
            go_name = f"Action{''.join(w.title() for w in action.split('_'))}"
            lines.append(f'\t{go_name} = "{action}"')
        lines.append(")")
        lines.append("")

    # Event types (battle only)
    if _target_matches("battle", target):
        lines.append("// Event type constants.")
        lines.append("const (")
        for evt in constants["event_types"]:
            go_name = f"Event{''.join(w.title() for w in evt.split('_'))}"
            lines.append(f'\t{go_name} = "{evt}"')
        lines.append(")")
        lines.append("")

    # WS message types (battle only)
    if _target_matches("battle", target):
        ws_types = constants["ws_message_types"]
        lines.append("// WS message type constants (server → client).")
        lines.append("const (")
        for msg in ws_types["server"]:
            go_name = f"WSMsg{''.join(w.title() for w in msg.split('_'))}"
            lines.append(f'\t{go_name} = "{msg}"')
        lines.append(")")
        lines.append("")
        lines.append("// WS message type constants (client → server).")
        lines.append("const (")
        for msg in ws_types["client"]:
            go_name = f"WSMsg{''.join(w.title() for w in msg.split('_'))}"
            lines.append(f'\t{go_name} = "{msg}"')
        lines.append(")")
        lines.append("")

    go_out.parent.mkdir(parents=True, exist_ok=True)
    with open(go_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(go_out.relative_to(repo_dir))



    return str(go_out.relative_to(COMMON_ROOT))


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
    lines.append(f"export const FACTIONS = {json.dumps(constants['factions'])} as const;")
    lines.append(f"export const SELECTABLE_FACTIONS = {json.dumps(constants['selectable_factions'])} as const;")
    lines.append(f"export type FactionId = (typeof SELECTABLE_FACTIONS)[number];")
    # Display names: canonical → display
    display_names = constants.get("faction_display_names", {})
    display_entries = ", ".join(f'"{f}": "{display_names.get(f, f)}"' for f in constants["factions"])
    lines.append(f"export const FACTION_DISPLAY_NAMES: Record<string, string> = {{ {display_entries} }};")
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

    # Event types
    lines.append(f"export const EVENT_TYPES = {json.dumps(constants['event_types'])} as const;")
    lines.append(f"export type EventType = (typeof EVENT_TYPES)[number];")
    lines.append("")

    # Card types
    ct = constants["card_types"]
    all_card_types = ct["compute"] + ct["data"] + ct["support"]
    lines.append(f"export const CARD_TYPES = {json.dumps(all_card_types)} as const;")
    lines.append(f"export type CardType = (typeof CARD_TYPES)[number];")
    lines.append("")

    compute_set = json.dumps(ct["compute"])
    data_set = json.dumps(ct["data"])
    support_types = [t for t in ct["support"] if t not in ("Attachment",)]
    lines.append(f"const COMPUTE_TYPES: ReadonlySet<string> = new Set({compute_set});")
    lines.append(f"const DATA_TYPES: ReadonlySet<string> = new Set({data_set});")
    lines.append("")

    lines.append("/** Returns true if the card type is a deployable resource (compute, AI/ML, or data). */")
    lines.append("export function isResourceType(cardType: string): boolean {")
    lines.append("  return COMPUTE_TYPES.has(cardType) || DATA_TYPES.has(cardType);")
    lines.append("}")
    lines.append("")

    lines.append("/** Returns true if the card can be placed in the frontend zone. */")
    lines.append("export function isFrontendEligible(cardType: string): boolean {")
    lines.append("  return COMPUTE_TYPES.has(cardType) || cardType === 'ObjectStorage';")
    lines.append("}")
    lines.append("")

    lines.append("/** Returns true if the card can be placed in the backend zone. */")
    lines.append("export function isBackendEligible(cardType: string): boolean {")
    lines.append("  return DATA_TYPES.has(cardType) || COMPUTE_TYPES.has(cardType);")
    lines.append("}")
    lines.append("")

    lines.append("/** Returns true if the card goes in the support zone (Platform, Strategy, Incident, Reactive). */")
    lines.append("export function isSupportType(cardType: string): boolean {")
    support_cases = " || ".join(f"cardType === '{t}'" for t in support_types)
    lines.append(f"  return {support_cases};")
    lines.append("}")
    lines.append("")

    lines.append("/** Returns true if the card is an Attachment (attaches to resources, not support zone). */")
    lines.append("export function isAttachmentType(cardType: string): boolean {")
    lines.append("  return cardType === 'Attachment';")
    lines.append("}")
    lines.append("")

    # WS message types
    ws_types = constants["ws_message_types"]
    lines.append(f"export const WS_SERVER_MSG_TYPES = {json.dumps(ws_types['server'])} as const;")
    lines.append(f"export type WSServerMsgType = (typeof WS_SERVER_MSG_TYPES)[number];")
    lines.append(f"export const WS_CLIENT_MSG_TYPES = {json.dumps(ws_types['client'])} as const;")
    lines.append(f"export type WSClientMsgType = (typeof WS_CLIENT_MSG_TYPES)[number];")
    lines.append("")

    # Effect durations
    lines.append(f"export const EFFECT_DURATIONS = {json.dumps(constants['effect_durations'])} as const;")
    lines.append(f"export type EffectDuration = (typeof EFFECT_DURATIONS)[number];")
    lines.append("")

    # Restriction values
    lines.append(f"export const RESTRICTION_VALUES = {json.dumps(constants['restriction_values'])} as const;")
    lines.append(f"export type Restriction = (typeof RESTRICTION_VALUES)[number];")
    lines.append("")

    # Restriction copy count utility
    lines.append("/** Returns the maximum number of copies allowed in a deck for a given restriction. */")
    lines.append("export function restrictionCopyCount(restriction: Restriction): number {")
    lines.append("  switch (restriction) {")
    lines.append("    case 'limited': return 1;")
    lines.append("    case 'semi_limited': return 2;")
    lines.append("    case 'unlimited': return 3;")
    lines.append("    default: return 3;")
    lines.append("  }")
    lines.append("}")
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


# ─── Generate C# (constants for battle) ───────────────
def generate_csharp_constants(constants, battle_dir):
    """Generate src/OverloadParty.Battle.Models/GameConstants_gen.cs from constants.json."""
    cs_out = battle_dir / "src" / "OverloadParty.Battle.Models" / "GameConstants_gen.cs"

    lines = [
        "// Code generated by generate_from_yaml.py from data/constants.json; DO NOT EDIT.",
        "",
        "namespace OverloadParty.Battle.Models;",
        "",
        "public static partial class GameConstants",
        "{",
    ]

    # Initial values
    iv = constants["initial_values"]
    iv_map = {
        "budget": ("long", "InitialBudget"),
        "insight_pool": ("long", "InitialInsightPool"),
        "hand_size": ("int", "InitialHandSize"),
        "hand_limit": ("int", "HandLimit"),
        "time_bank": ("long", "InitialTimeBank"),
        "deck_size": ("int", "DeckSize"),
        "max_attachments": ("int", "MaxAttachments"),
        "slots_per_zone": ("int", "SlotsPerZone"),
    }
    lines.append("    // Initial values")
    for json_key, (cs_type, cs_name) in iv_map.items():
        val = iv[json_key]
        lines.append(f"    public const {cs_type} {cs_name} = {val};")
    lines.append("")

    # Factions
    lines.append("    // Factions")
    for faction in constants["factions"]:
        lines.append(f'    public const string Faction{faction} = "{faction}";')
    lines.append("")

    # Zones
    lines.append("    // Zones (wire format)")
    for zone in constants["zones"]:
        cs_name = f"Zone{''.join(w.title() for w in zone.split('_'))}"
        lines.append(f'    public const string {cs_name} = "{zone}";')

    lines.append("}")
    lines.append("")

    cs_out.parent.mkdir(parents=True, exist_ok=True)
    with open(cs_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(cs_out.relative_to(battle_dir))


# ─── Generate C# (event data types for battle) ────────
_CS_TYPE_MAP = {
    "string": "string",
    "int": "int",
    "long": "long",
    "bool": "bool",
    "string[]": "List<string>",
}

_CS_NULLABLE_DEFAULTS = {
    "string": "string?",
    "int": "int?",
    "long": "long?",
    "bool": "bool?",
    "string[]": "List<string>?",
}


def _snake_to_pascal(s):
    """Convert snake_case to PascalCase."""
    return "".join(w.title() for w in s.split("_"))


def _camel_to_pascal(s):
    """Convert camelCase to PascalCase."""
    return s[0].upper() + s[1:]


def generate_csharp_event_data(schemas, battle_dir):
    """Generate src/OverloadParty.Battle.Models/EventData_gen.cs from event_schemas.json."""
    cs_out = battle_dir / "src" / "OverloadParty.Battle.Models" / "EventData_gen.cs"

    lines = [
        "// Code generated by generate_from_yaml.py from data/event_schemas.json; DO NOT EDIT.",
        "",
        "namespace OverloadParty.Battle.Models;",
        "",
    ]

    for event_type, fields in schemas.items():
        if event_type.startswith("_"):
            continue

        class_name = f"{_snake_to_pascal(event_type)}EventData"
        lines.append(f"public class {class_name}")
        lines.append("{")

        required_fields = []
        optional_fields = []

        for raw_key, raw_type in fields.items():
            optional = raw_key.endswith("?")
            key = raw_key.rstrip("?")
            cs_prop = _camel_to_pascal(key)

            if optional:
                cs_type = _CS_NULLABLE_DEFAULTS[raw_type]
                optional_fields.append((key, cs_prop, cs_type, raw_type))
            else:
                cs_type = _CS_TYPE_MAP[raw_type]
                init = ' = "";' if raw_type == "string" else " = [];" if raw_type == "string[]" else ""
                required_fields.append((key, cs_prop, cs_type, init))
                lines.append(f"    public required {cs_type} {cs_prop} {{ get; init; }}{init}")

        for key, cs_prop, cs_type, raw_type in optional_fields:
            lines.append(f"    public {cs_type} {cs_prop} {{ get; init; }}")

        # ToDictionary method
        lines.append("")
        lines.append("    public Dictionary<string, object> ToDictionary()")
        lines.append("    {")
        lines.append("        var d = new Dictionary<string, object>")
        lines.append("        {")
        for key, cs_prop, _, _ in required_fields:
            lines.append(f'            ["{key}"] = {cs_prop},')
        lines.append("        };")

        for key, cs_prop, _, _ in optional_fields:
            lines.append(f'        if ({cs_prop} is not null) d["{key}"] = {cs_prop};')

        lines.append("        return d;")
        lines.append("    }")
        lines.append("}")
        lines.append("")

    cs_out.parent.mkdir(parents=True, exist_ok=True)
    with open(cs_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(cs_out.relative_to(battle_dir))


# ─── Generate TypeScript (event data types) ───────────
_TS_TYPE_MAP = {
    "string": "string",
    "int": "number",
    "long": "number",
    "bool": "boolean",
    "string[]": "string[]",
}


def generate_ts_event_data(schemas, client_dir):
    """Generate src/generated/eventData.ts from event_schemas.json."""
    ts_out = client_dir / "src" / "generated" / "eventData.ts"

    lines = [
        "// Code generated by generate_from_yaml.py from data/event_schemas.json; DO NOT EDIT.",
        "",
    ]

    type_names = []

    for event_type, fields in schemas.items():
        if event_type.startswith("_"):
            continue

        type_name = f"{_snake_to_pascal(event_type)}EventData"
        type_names.append((event_type, type_name))

        lines.append(f"export interface {type_name} {{")
        for raw_key, raw_type in fields.items():
            optional = raw_key.endswith("?")
            key = raw_key.rstrip("?")
            ts_type = _TS_TYPE_MAP[raw_type]
            opt = "?" if optional else ""
            lines.append(f"  {key}{opt}: {ts_type};")
        lines.append("}")
        lines.append("")

    # EventDataMap type
    lines.append("export interface EventDataMap {")
    for event_type, type_name in type_names:
        lines.append(f'  {event_type}: {type_name};')
    lines.append("}")
    lines.append("")

    ts_out.parent.mkdir(parents=True, exist_ok=True)
    with open(ts_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(ts_out.relative_to(client_dir))


# ─── Generate CARDS.md ─────────────────────────────────
def _scalability_display(card):
    """Return card_type with scalability suffix for display."""
    ct = card["card_type"]
    display_type = {
        "ObjectStorage": "Object Storage",
        "CacheDB": "Cache DB",
    }.get(ct, ct)
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
    """Format throughput value."""
    tp = card["stats"].get("throughput", 0)
    return str(tp)


def _yield_display(card):
    """Format Yield value."""
    y = card["stats"].get("yield", 0)
    return str(y)


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
                lines.append("| # | カード名 | タイプ | スループット | 可用性 | 維持コスト | デプロイT | SLAペナルティ | 効果 | 元ネタ |")
                lines.append("|---|---------|-------|-----|-----|-----|-----|-----|------|----------|")
                for c in cat_cards:
                    origin = c.get("origin", "")
                    dt = c.get("deploy_turns", 0)
                    lines.append(
                        f"| {c['card_no']} | {c['card_name']} | {_scalability_display(c)} "
                        f"| {_tp_display(c)} | {c['stats']['availability']} "
                        f"| {c['stats']['maintenance_cost']} | {dt} "
                        f"| {c['stats']['sla_penalty']} | {_effect_display(c)} | {origin} |"
                    )
            elif is_data:
                lines.append("| # | カード名 | タイプ | Yield | 可用性 | 維持コスト | デプロイT | SLAペナルティ | 効果 | 元ネタ |")
                lines.append("|---|---------|-------|-----|-----|-----|-----|-----|------|----------|")
                for c in cat_cards:
                    origin = c.get("origin", "")
                    dt = c.get("deploy_turns", 0)
                    lines.append(
                        f"| {c['card_no']} | {c['card_name']} | {_scalability_display(c)} "
                        f"| {_yield_display(c)} | {c['stats']['availability']} "
                        f"| {c['stats']['maintenance_cost']} | {dt} "
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
    parser.add_argument("--gateway-dir", type=Path,
                        default=os.environ.get("GATEWAY_DIR"),
                        help="Path to overload-party-gateway root")
    parser.add_argument("--battle-dir", type=Path,
                        default=os.environ.get("BATTLE_DIR"),
                        help="Path to overload-party-battle root")
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

    # Load shared constants and event schemas
    with open(CONSTANTS_JSON, "r", encoding="utf-8") as f:
        constants = json.load(f)
    with open(EVENT_SCHEMAS_JSON, "r", encoding="utf-8") as f:
        event_schemas = json.load(f)

    # Always generate common outputs (CARDS.md, cardno)
    md_count = generate_md(cards, faction_data)
    go_count = generate_go_cardno(cards, faction_data)
    print(f"Generated {md_count} cards → {MD_OUT.relative_to(COMMON_ROOT)}", file=sys.stderr)
    print(f"Generated {go_count} constants → cardno/cardno_gen.go", file=sys.stderr)

    # Gateway outputs
    gateway_dir = Path(args.gateway_dir) if args.gateway_dir else None
    if gateway_dir and gateway_dir.exists():
        json_count = generate_json(cards, gateway_dir)
        model_names = generate_go_models(gateway_dir, "gateway")
        const_path = generate_repo_constants(constants, gateway_dir, "gateway")
        print(f"Generated {json_count} cards → {gateway_dir.name}/internal/cache/cards_gen.json", file=sys.stderr)
        print(f"Generated models → {gateway_dir.name}/internal/model/ [{', '.join(model_names)}]", file=sys.stderr)
        print(f"Generated constants → {gateway_dir.name}/{const_path}", file=sys.stderr)
    else:
        print("SKIP: gateway outputs (--gateway-dir not set or not found)", file=sys.stderr)

    # Battle outputs (C#)
    battle_dir = Path(args.battle_dir) if args.battle_dir else None
    if battle_dir and battle_dir.exists():
        cs_path = generate_csharp_constants(constants, battle_dir)
        cs_evt_path = generate_csharp_event_data(event_schemas, battle_dir)
        print(f"Generated constants → {battle_dir.name}/{cs_path}", file=sys.stderr)
        print(f"Generated event data → {battle_dir.name}/{cs_evt_path}", file=sys.stderr)
    else:
        print("SKIP: battle outputs (--battle-dir not set or not found)", file=sys.stderr)

    # Client outputs
    client_dir = Path(args.client_dir) if args.client_dir else None
    if client_dir and client_dir.exists():
        ts_path = generate_ts_constants(constants, client_dir)
        ts_evt_path = generate_ts_event_data(event_schemas, client_dir)
        print(f"Generated constants → {client_dir.name}/{ts_path}", file=sys.stderr)
        print(f"Generated event data → {client_dir.name}/{ts_evt_path}", file=sys.stderr)
    else:
        print("SKIP: client outputs (--client-dir not set or not found)", file=sys.stderr)


if __name__ == "__main__":
    main()
