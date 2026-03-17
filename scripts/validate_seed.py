#!/usr/bin/env python3
"""Validate referential integrity of seed SQL files.

Checks:
  - required_episodes in scenario_episodes reference valid episode_id values
  - required_factions contain only known faction names

Usage:
  python3 scripts/validate_seed.py
"""

import re
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "db" / "seed"
VALID_FACTIONS = {"SHE", "Tenki", "Sugar", "Tuners"}

# PostgreSQL string literal: handles escaped single quotes ('')
_PG_STR = r"'(?:[^']|'')*'"

# Regex to extract individual rows from the scenarios.sql INSERT statement.
ROW_RE = re.compile(
    r"\(\s*'([^']+)'"                  # episode_id (no escapes expected)
    r"\s*,\s*" + _PG_STR +            # category
    r"\s*,\s*(?:'([^']+)'|NULL)"       # faction (nullable)
    r"\s*,\s*\d+"                      # episode_number
    r"\s*,\s*" + _PG_STR +            # title_ja (may contain '')
    r"\s*,\s*" + _PG_STR +            # title_en (may contain '')
    r"\s*,\s*\d+"                      # required_level
    r"\s*,\s*'\{([^}]*)\}'"            # required_factions
    r"\s*,\s*'\{([^}]*)\}'"            # required_episodes
    r"\s*,\s*" + _PG_STR +            # script_path
    r"\s*,\s*\d+"                      # sort_order
    r"\s*\)",
)


def parse_array(raw: str) -> list[str]:
    """Parse a PostgreSQL text array literal (without braces) into a list."""
    if not raw.strip():
        return []
    return [s.strip() for s in raw.split(",")]


def validate_scenarios() -> list[str]:
    path = SEED_DIR / "scenarios.sql"
    if not path.exists():
        return [f"{path} not found"]

    content = path.read_text()
    rows = ROW_RE.findall(content)
    if not rows:
        return [f"No rows parsed from {path}"]

    episode_ids = {row[0] for row in rows}
    errors: list[str] = []

    for episode_id, _faction, factions_raw, episodes_raw in rows:
        for f in parse_array(factions_raw):
            if f not in VALID_FACTIONS:
                errors.append(
                    f"  {episode_id}: required_factions contains unknown faction '{f}'"
                )

        for ep in parse_array(episodes_raw):
            if ep not in episode_ids:
                errors.append(
                    f"  {episode_id}: required_episodes references unknown episode_id '{ep}'"
                )

    return errors


def main() -> int:
    errors = validate_scenarios()

    if errors:
        print("Seed data validation FAILED:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        return 1

    print("Seed data validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
