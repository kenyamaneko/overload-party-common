#!/usr/bin/env python3
"""Validate that every shop product card_pack_id refers to an existing card pack_id.

ADR-031 §5 / ADR-032 §5 で「shop seed の card_pack_id ⊂ card seed の pack_id」を
CI で検証する責務を overload-party-common に置くと決定したのを実装する。
shop / card 両方の seed が見えるのは共通基盤のみ。

Usage:
    python3 scripts/validate_card_pack_refs.py \
        --shop-yaml /path/to/overload-party-shop/data/products.yaml \
        --card-yaml /path/to/overload-party-card/data/card_packs.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def load_shop_card_pack_refs(shop_yaml: Path) -> dict[str, str]:
    """shop products.yaml から product_id -> card_pack_id の dict を返す.

    card_pack_id を持つ product type (faction_set / card_pack) のみを抽出。
    cosmetic / subscription 等は card_pack 参照を持たないのでスキップ。
    """
    data = yaml.safe_load(shop_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "products" not in data:
        raise ValueError(f"{shop_yaml}: top-level 'products' key is required")
    refs: dict[str, str] = {}
    for p in data["products"] or []:
        if "card_pack_id" in p:
            refs[p["product_id"]] = p["card_pack_id"]
    return refs


def load_card_pack_ids(card_yaml: Path) -> set[str]:
    """card card_packs.yaml から pack_id 集合を返す."""
    data = yaml.safe_load(card_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "packs" not in data:
        raise ValueError(f"{card_yaml}: top-level 'packs' key is required")
    return {p["pack_id"] for p in data["packs"] or []}


def validate(shop_refs: dict[str, str], card_pack_ids: set[str]) -> list[tuple[str, str]]:
    """shop の card_pack_id 参照のうち card 側に存在しないものを (product_id, card_pack_id) で返す."""
    return sorted(
        (product_id, pack_id)
        for product_id, pack_id in shop_refs.items()
        if pack_id not in card_pack_ids
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shop-yaml", type=Path, required=True, help="overload-party-shop/data/products.yaml")
    parser.add_argument("--card-yaml", type=Path, required=True, help="overload-party-card/data/card_packs.yaml")
    args = parser.parse_args()

    shop_refs = load_shop_card_pack_refs(args.shop_yaml)
    card_pack_ids = load_card_pack_ids(args.card_yaml)
    missing = validate(shop_refs, card_pack_ids)

    if missing:
        sys.stderr.write(
            f"error: {len(missing)} shop product(s) reference unknown card_pack_id "
            f"(not in {args.card_yaml.name}):\n"
        )
        for product_id, pack_id in missing:
            sys.stderr.write(f"  - shop product {product_id!r} → card_pack_id {pack_id!r}\n")
        return 1

    print(
        f"OK: {len(shop_refs)} shop product(s) all reference valid card_pack_id "
        f"(card defines {len(card_pack_ids)} pack(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
