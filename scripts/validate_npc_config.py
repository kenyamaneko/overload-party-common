#!/usr/bin/env python3
"""Validate NPC AI config YAML files against card definitions.

Checks:
  - Structural completeness (required sections, fields)
  - Deck card IDs exist in card definitions
  - attachments / reactive: covers all typed cards in deck
  - deploy.choices: covers all choice-bearing cards in deck
  - deploy.priorities / zone_preferences: valid values
  - effect_priorities / immediate_cards: valid effect categories
  - target_selection / scale_up / monetize: valid order_by and selector values
  - No phantom references (config references cards not in deck)
  - Numeric ranges (budget, monetize, scale_up)

Usage:
    python3 scripts/validate_npc_config.py [--battle-dir PATH]

Exit codes:
    0  All configs valid
    1  Validation errors found
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# ─── Paths ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "data" / "cards"
CONSTANTS_YAML = ROOT / "data" / "constants.yaml"
DEFAULT_BATTLE_DIR = ROOT.parent / "overload-party-battle"
NPC_DATA_REL = Path("src") / "OverloadParty.Battle.Npc" / "Data"

VALID_ORDER_BY = {"tp_desc", "tp_asc", "av_desc", "av_asc", "damage_desc", "damage_asc"}
VALID_SELECTOR_OWNERS = {"self", "opponent"}


def _to_snake(name: str) -> str:
    """CamelCase to snake_case. 'ObjectStorage' -> 'object_storage', 'AI/ML' -> 'ai_ml'."""
    name = name.replace("/", "_")
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


# ─── Constants loader ──────────────────────────────────
def load_constants() -> dict:
    """Load valid values from data/constants.yaml (SSoT)."""
    with open(CONSTANTS_YAML, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    card_type_groups: dict[str, list[str]] = raw.get("card_types", {})
    all_card_types: set[str] = set()
    for types in card_type_groups.values():
        all_card_types.update(types)

    # NpcAi.MatchesCardType のグループキー ("compute", "data") + 個別カードタイプ
    deploy_card_type_keys = set(card_type_groups.keys()) | all_card_types
    # config では小文字で書かれることがある
    deploy_card_type_keys |= {t.lower() for t in all_card_types}

    # zone_preferences のキーは NpcAi.PickDeployZone のマッピングに由来
    # グループキー ("compute", "data") + 個別タイプの snake_case
    zone_type_keys = set(card_type_groups.keys()) | {
        _to_snake(t) for t in all_card_types
    }

    return {
        "factions": set(raw.get("selectable_factions", [])),
        "zones": set(raw.get("zones", [])),
        "instance_families": set(raw.get("instance_families", [])),
        "effect_categories": set(raw.get("effect_categories", [])),
        "all_card_types": all_card_types,
        "deploy_card_type_keys": deploy_card_type_keys,
        "zone_type_keys": zone_type_keys,
    }


# ─── Data loaders ──────────────────────────────────────
def load_card_definitions() -> dict:
    """Load all card definitions from data/cards/*.yaml."""
    cards: dict = {}
    for yaml_file in sorted(CARDS_DIR.glob("*.yaml")):
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data or "cards" not in data:
            continue
        for card in data["cards"]:
            cid = card.get("card_id", "")
            if cid:
                cards[cid] = card
    return cards


def load_npc_configs(npc_data_dir: Path) -> list[tuple[str, dict | None]]:
    """Load all NPC config YAMLs. Returns list of (name, config_dict)."""
    results = []
    for f in sorted(npc_data_dir.glob("*.yaml")):
        with open(f, encoding="utf-8") as fh:
            results.append((f.stem, yaml.safe_load(fh)))
    return results


# ─── Helpers ───────────────────────────────────────────
def _deck_ids(config: dict) -> set[str]:
    return {e.get("card_id", "") for e in config.get("deck", [])
            if e.get("card_id")}


def _deck_ids_of_type(deck_ids: set[str], card_defs: dict,
                      card_type: str) -> set[str]:
    return {cid for cid in deck_ids
            if cid in card_defs and card_defs[cid].get("card_type") == card_type}


def _choice_cards(deck_ids: set[str], card_defs: dict) -> set[str]:
    return {cid for cid in deck_ids
            if cid in card_defs and card_defs[cid].get("choice_options")}


# ─── Validation result ─────────────────────────────────
@dataclass
class Issue:
    config_name: str
    section: str
    message: str
    severity: str = "error"

    def __str__(self) -> str:
        tag = "ERROR" if self.severity == "error" else "WARN"
        return f"  [{tag}] {self.config_name} > {self.section}: {self.message}"


@dataclass
class ValidationContext:
    config_name: str
    config: dict
    card_defs: dict
    consts: dict
    deck_ids: set[str] = field(default_factory=set)
    issues: list[Issue] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.deck_ids = _deck_ids(self.config)

    def err(self, section: str, msg: str, severity: str = "error") -> None:
        self.issues.append(Issue(self.config_name, section, msg, severity))


# ─── Validation functions ──────────────────────────────
def check_required_sections(ctx: ValidationContext) -> None:
    for section in ("model", "faction", "deck", "budget", "deploy",
                    "immediate_cards", "effect_priorities",
                    "target_selection", "scale_up", "monetize"):
        if section not in ctx.config or ctx.config[section] is None:
            ctx.err("structure", f"Required section '{section}' is missing")


def check_model_and_faction(ctx: ValidationContext) -> None:
    if not ctx.config.get("model"):
        ctx.err("model", "model is empty")
    faction = ctx.config.get("faction", "")
    if faction not in ctx.consts["factions"]:
        ctx.err("faction",
                f"Invalid faction '{faction}', "
                f"expected one of {sorted(ctx.consts['factions'])}")


def check_deck(ctx: ValidationContext) -> None:
    deck = ctx.config.get("deck", [])
    if not deck:
        ctx.err("deck", "Deck is empty")
    for entry in deck:
        cid = entry.get("card_id", "")
        if cid and cid not in ctx.card_defs:
            ctx.err("deck", f"Card '{cid}' not found in card definitions")
        copies = entry.get("copies", 1)
        if not isinstance(copies, int) or copies < 1:
            ctx.err("deck", f"Invalid copies '{copies}' for card '{cid}'")


def check_budget(ctx: ValidationContext) -> None:
    budget = ctx.config.get("budget") or {}
    lt = budget.get("low_threshold")
    if lt is not None and (not isinstance(lt, (int, float)) or lt <= 0):
        ctx.err("budget", f"low_threshold should be > 0, got {lt}")
    mlr = budget.get("maintenance_limit_ratio")
    if mlr is not None and (not isinstance(mlr, (int, float))
                            or mlr <= 0 or mlr > 1):
        ctx.err("budget",
                f"maintenance_limit_ratio should be in (0, 1], got {mlr}")


def check_attachments(ctx: ValidationContext) -> None:
    deck_attach = _deck_ids_of_type(ctx.deck_ids, ctx.card_defs, "Attachment")
    cfg = ctx.config.get("attachments") or {}

    if deck_attach and not cfg:
        ctx.err("attachments",
                f"Deck contains {len(deck_attach)} Attachment card(s) "
                f"but 'attachments' section is missing")

    for cid in deck_attach:
        if cid not in cfg:
            ctx.err("attachments",
                    f"Attachment card '{cid}' in deck has no config entry")

    for cid, entry in cfg.items():
        if cid not in ctx.deck_ids:
            ctx.err("attachments", f"Config entry '{cid}' is not in deck")
        elif (cid in ctx.card_defs
              and ctx.card_defs[cid].get("card_type") != "Attachment"):
            actual = ctx.card_defs[cid].get("card_type", "?")
            ctx.err("attachments",
                    f"Config entry '{cid}' has card_type '{actual}', "
                    f"not Attachment")
        if isinstance(entry, dict) and "target" in entry:
            _check_target_spec(ctx, "attachments", f"{cid}.target",
                               entry["target"])


def check_reactive(ctx: ValidationContext) -> None:
    deck_react = _deck_ids_of_type(ctx.deck_ids, ctx.card_defs, "Reactive")
    cfg = ctx.config.get("reactive") or {}
    priorities = cfg.get("priorities", {}) if cfg else {}

    if deck_react and not cfg:
        ctx.err("reactive",
                f"Deck contains {len(deck_react)} Reactive card(s) "
                f"but 'reactive' section is missing")

    for cid in deck_react:
        if cid not in priorities:
            ctx.err("reactive",
                    f"Reactive card '{cid}' in deck has no "
                    f"reactive.priorities entry")

    for cid in priorities:
        if cid not in ctx.deck_ids:
            ctx.err("reactive",
                    f"reactive.priorities entry '{cid}' is not in deck")
        elif (cid in ctx.card_defs
              and ctx.card_defs[cid].get("card_type") != "Reactive"):
            actual = ctx.card_defs[cid].get("card_type", "?")
            ctx.err("reactive",
                    f"reactive.priorities entry '{cid}' has card_type "
                    f"'{actual}', not Reactive")

    if cfg and not deck_react:
        ctx.err("reactive",
                "reactive section exists but deck has no Reactive cards",
                severity="warning")

    if cfg and "max_slots" in cfg:
        ms = cfg["max_slots"]
        if not isinstance(ms, int) or ms <= 0:
            ctx.err("reactive", f"max_slots should be > 0, got {ms}")


def check_deploy(ctx: ValidationContext) -> None:
    deploy = ctx.config.get("deploy") or {}
    consts = ctx.consts

    # choices
    choices_cfg = deploy.get("choices") or {}
    for cid in _choice_cards(ctx.deck_ids, ctx.card_defs):
        if cid not in choices_cfg:
            ctx.err("deploy.choices",
                    f"Card '{cid}' has choice_options but no "
                    f"deploy.choices entry")
    for cid in choices_cfg:
        if cid not in ctx.deck_ids:
            ctx.err("deploy.choices",
                    f"deploy.choices entry '{cid}' is not in deck",
                    severity="warning")

    # priorities
    for entry in deploy.get("priorities", []):
        ct = entry.get("card_type")
        if ct and ct not in consts["deploy_card_type_keys"]:
            ctx.err("deploy.priorities", f"Unknown card_type '{ct}'")
        cid = entry.get("card_id")
        if cid and cid not in ctx.deck_ids:
            ctx.err("deploy.priorities",
                    f"card_id '{cid}' is not in deck", severity="warning")

    # conditional_priorities
    for entry in deploy.get("conditional_priorities") or []:
        cid = entry.get("card_id", "")
        if cid and cid not in ctx.deck_ids:
            ctx.err("deploy.conditional_priorities",
                    f"card_id '{cid}' is not in deck")

    # zone_preferences
    zones = consts["zones"]
    for key, vals in (deploy.get("zone_preferences") or {}).items():
        if key not in consts["zone_type_keys"]:
            ctx.err("deploy.zone_preferences",
                    f"Unknown zone type key '{key}'")
        if isinstance(vals, list):
            for z in vals:
                if z not in zones:
                    ctx.err("deploy.zone_preferences",
                            f"Unknown zone '{z}' in [{key}]")


def check_effect_priorities(ctx: ValidationContext) -> None:
    cats = ctx.consts["effect_categories"]
    for key in ctx.config.get("effect_priorities") or {}:
        if key not in cats:
            ctx.err("effect_priorities", f"Unknown effect category '{key}'")


def check_immediate_cards(ctx: ValidationContext) -> None:
    cats = ctx.consts["effect_categories"]
    imm = ctx.config.get("immediate_cards") or {}
    for val in imm.get("always_use") or []:
        if val not in cats:
            ctx.err("immediate_cards", f"Unknown always_use value '{val}'")


def _check_target_spec(ctx: ValidationContext, section: str,
                       name: str, spec: object) -> None:
    """Validate a single target spec entry (selector + order_by)."""
    if not isinstance(spec, dict):
        ctx.err(section, f"'{name}' should be a dict, got {type(spec).__name__}")
        return
    selector = spec.get("selector")
    if selector is not None:
        if not isinstance(selector, dict):
            ctx.err(section,
                    f"'{name}.selector' should be a dict, "
                    f"got {type(selector).__name__}")
        else:
            owner = selector.get("owner")
            if owner is not None and owner not in VALID_SELECTOR_OWNERS:
                ctx.err(section,
                        f"'{name}.selector.owner' is '{owner}', "
                        f"expected one of {sorted(VALID_SELECTOR_OWNERS)}")
    order_by = spec.get("order_by")
    if order_by is not None and order_by not in VALID_ORDER_BY:
        ctx.err(section,
                f"'{name}.order_by' is '{order_by}', "
                f"expected one of {sorted(VALID_ORDER_BY)}")


def check_target_selection(ctx: ValidationContext) -> None:
    ts = ctx.config.get("target_selection") or {}
    for field_name in ("attack", "single_damage", "debuff", "buff", "heal"):
        val = ts.get(field_name)
        if val is not None:
            _check_target_spec(ctx, "target_selection", field_name, val)


def check_scale_up(ctx: ValidationContext) -> None:
    su = ctx.config.get("scale_up") or {}
    families = ctx.consts["instance_families"]
    ob = su.get("order_by", "")
    if ob and ob not in VALID_ORDER_BY:
        ctx.err("scale_up",
                f"Unknown order_by '{ob}', "
                f"expected one of {sorted(VALID_ORDER_BY)}")
    fam = su.get("instance_family", "")
    if fam and fam not in families:
        ctx.err("scale_up", f"Unknown instance_family '{fam}'")
    mmr = su.get("max_maintenance_ratio")
    if mmr is not None and (not isinstance(mmr, (int, float))
                            or mmr <= 0 or mmr > 1):
        ctx.err("scale_up",
                f"max_maintenance_ratio should be in (0, 1], got {mmr}")
    for cf in su.get("conditional_family") or []:
        f = cf.get("family", "")
        if f and f not in families:
            ctx.err("scale_up", f"Unknown conditional_family '{f}'")


def check_monetize(ctx: ValidationContext) -> None:
    mon = ctx.config.get("monetize") or {}
    ob = mon.get("order_by", "")
    if ob and ob not in VALID_ORDER_BY:
        ctx.err("monetize",
                f"Unknown order_by '{ob}', "
                f"expected one of {sorted(VALID_ORDER_BY)}")
    rr = mon.get("reserve_ratio")
    if rr is not None and (not isinstance(rr, (int, float))
                           or rr < 0 or rr > 1):
        ctx.err("monetize", f"reserve_ratio should be in [0, 1], got {rr}")


def check_game_phases(ctx: ValidationContext) -> None:
    gp = ctx.config.get("game_phases")
    if not gp:
        return
    late = gp.get("late") or {}
    cats = ctx.consts["effect_categories"]
    late_ts = late.get("target_selection") or {}
    for field_name in ("attack", "single_damage", "debuff", "buff", "heal"):
        val = late_ts.get(field_name)
        if val is not None:
            _check_target_spec(ctx, "game_phases.late.target_selection",
                               field_name, val)
    for key in late.get("effect_priorities") or {}:
        if key not in cats:
            ctx.err("game_phases.late.effect_priorities",
                    f"Unknown effect category '{key}'")


ALL_CHECKS = [
    check_required_sections,
    check_model_and_faction,
    check_deck,
    check_budget,
    check_attachments,
    check_reactive,
    check_deploy,
    check_effect_priorities,
    check_immediate_cards,
    check_target_selection,
    check_scale_up,
    check_monetize,
    check_game_phases,
]


def validate_config(config: dict, config_name: str,
                    card_defs: dict, consts: dict) -> list[Issue]:
    ctx = ValidationContext(config_name, config, card_defs, consts)
    for check in ALL_CHECKS:
        check(ctx)
    return ctx.issues


# ─── Main ──────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate NPC AI config YAML files")
    parser.add_argument(
        "--battle-dir", type=Path, default=DEFAULT_BATTLE_DIR,
        help="Path to overload-party-battle repository root")
    args = parser.parse_args()

    npc_data_dir = args.battle_dir / NPC_DATA_REL
    if not npc_data_dir.is_dir():
        print(f"ERROR: NPC config directory not found: {npc_data_dir}",
              file=sys.stderr)
        return 1

    consts = load_constants()
    card_defs = load_card_definitions()
    if not card_defs:
        print(f"ERROR: No card definitions loaded from {CARDS_DIR}",
              file=sys.stderr)
        return 1

    configs = load_npc_configs(npc_data_dir)
    if not configs:
        print(f"ERROR: No YAML files found in {npc_data_dir}", file=sys.stderr)
        return 1

    print(f"Loaded {len(card_defs)} card definitions, "
          f"{len(configs)} NPC config(s)")

    all_issues: list[Issue] = []
    for name, config in configs:
        if not config:
            all_issues.append(Issue(name, "file", "Empty or invalid"))
            continue
        issues = validate_config(config, name, card_defs, consts)
        all_issues.extend(issues)
        errs = sum(1 for i in issues if i.severity == "error")
        warns = sum(1 for i in issues if i.severity == "warning")
        status = "OK" if errs == 0 else "FAIL"
        detail = ""
        if errs or warns:
            parts = []
            if errs:
                parts.append(f"{errs} error(s)")
            if warns:
                parts.append(f"{warns} warning(s)")
            detail = f" — {', '.join(parts)}"
        print(f"  {status}: {name}{detail}")

    if all_issues:
        print()
        current = ""
        for i in all_issues:
            if i.config_name != current:
                current = i.config_name
                print(f"── {current} ──")
            print(i)
        print()

    total = len(configs)
    error_count = sum(1 for i in all_issues if i.severity == "error")
    warn_count = sum(1 for i in all_issues if i.severity == "warning")
    failed = len({i.config_name for i in all_issues if i.severity == "error"})
    print(f"Validated {total} config(s): "
          f"{total - failed} passed, {failed} failed "
          f"({error_count} error(s), {warn_count} warning(s))")

    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
