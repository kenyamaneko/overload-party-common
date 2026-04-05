#!/usr/bin/env python3
"""Generate mock news data from YAML for local development.

Outputs:
  - packages/devdata/cache/news.json

Usage:
    python3 scripts/generate_news_mock.py
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "data" / "mock" / "news.yaml"
JSON_OUT = ROOT / "packages" / "devdata" / "cache" / "news.json"

VALID_SOURCES = {"aws", "google-cloud", "azure", "oci", "other"}


def main():
    if not YAML_PATH.exists():
        print(f"ERROR: {YAML_PATH} not found", file=sys.stderr)
        sys.exit(1)

    with open(YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    articles = data.get("articles", [])
    if not articles:
        print("ERROR: No articles found", file=sys.stderr)
        sys.exit(1)

    errors = []
    seen_ids = set()
    for a in articles:
        aid = a.get("article_id", "")
        if not aid:
            errors.append("article missing article_id")
        if aid in seen_ids:
            errors.append(f"duplicate article_id '{aid}'")
        seen_ids.add(aid)
        source = a.get("source", "")
        if source not in VALID_SOURCES:
            errors.append(f"{aid}: invalid source '{source}'")

    if errors:
        print(f"Validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Generated {len(articles)} articles → {JSON_OUT.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
