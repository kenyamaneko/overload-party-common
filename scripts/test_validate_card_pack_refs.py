"""validate_card_pack_refs.py のユニットテスト."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import validate_card_pack_refs as v


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


class TestLoadShopRefs:
    """shop products.yaml からの card_pack_id 抽出仕様."""

    def test_extracts_card_pack_id_from_faction_set_and_card_pack(self, tmp_path: Path):
        """faction_set と card_pack の両 type から card_pack_id を抽出する."""
        path = tmp_path / "products.yaml"
        _write_yaml(path, {
            "products": [
                {"product_id": "fs_she", "type": "faction_set", "card_pack_id": "faction_set_she"},
                {"product_id": "pack_x", "type": "card_pack", "card_pack_id": "limited_x"},
            ],
        })
        assert v.load_shop_card_pack_refs(path) == {
            "fs_she": "faction_set_she",
            "pack_x": "limited_x",
        }

    def test_skips_products_without_card_pack_id(self, tmp_path: Path):
        """card_pack_id を持たない product (cosmetic / subscription 想定) はスキップする.

        cross-repo 検証対象は card_pack_id を持つ product のみ。
        """
        path = tmp_path / "products.yaml"
        _write_yaml(path, {
            "products": [
                {"product_id": "fs_she", "type": "faction_set", "card_pack_id": "faction_set_she"},
                {"product_id": "stamp_a", "type": "cosmetic"},
                {"product_id": "premium_monthly", "type": "subscription"},
            ],
        })
        assert v.load_shop_card_pack_refs(path) == {"fs_she": "faction_set_she"}

    def test_missing_top_level_products_raises(self, tmp_path: Path):
        path = tmp_path / "products.yaml"
        _write_yaml(path, {"other_key": []})
        with pytest.raises(ValueError, match="top-level 'products' key is required"):
            v.load_shop_card_pack_refs(path)


class TestLoadCardPackIds:
    """card card_packs.yaml からの pack_id 集合抽出仕様."""

    def test_extracts_all_pack_ids(self, tmp_path: Path):
        path = tmp_path / "card_packs.yaml"
        _write_yaml(path, {
            "packs": [
                {"pack_id": "basic", "cards": []},
                {"pack_id": "faction_set_she", "cards": []},
            ],
        })
        assert v.load_card_pack_ids(path) == {"basic", "faction_set_she"}

    def test_missing_top_level_packs_raises(self, tmp_path: Path):
        path = tmp_path / "card_packs.yaml"
        _write_yaml(path, {"other_key": []})
        with pytest.raises(ValueError, match="top-level 'packs' key is required"):
            v.load_card_pack_ids(path)


class TestValidate:
    """整合性検証の core ロジック."""

    def test_all_refs_present_returns_empty_list(self):
        shop_refs = {"fs_she": "faction_set_she", "fs_tenki": "faction_set_tenki"}
        card_ids = {"basic", "faction_set_she", "faction_set_tenki"}
        assert v.validate(shop_refs, card_ids) == []

    def test_missing_pack_id_reported_with_product_id(self):
        """shop が card に存在しない card_pack_id を参照していたら (product_id, pack_id) で報告する."""
        shop_refs = {"fs_ghost": "faction_set_ghost"}
        card_ids = {"basic", "faction_set_she"}
        assert v.validate(shop_refs, card_ids) == [("fs_ghost", "faction_set_ghost")]

    def test_multiple_missing_reported_sorted(self):
        """複数の不整合は (product_id, pack_id) でソート済みリストとして返す (出力が安定する)."""
        shop_refs = {
            "z_product": "z_pack",
            "a_product": "a_pack",
            "ok_product": "basic",
        }
        card_ids = {"basic"}
        assert v.validate(shop_refs, card_ids) == [
            ("a_product", "a_pack"),
            ("z_product", "z_pack"),
        ]


class TestMainIntegration:
    """CLI 経由の終了コードと stderr メッセージ."""

    def _write_pair(self, tmp_path: Path, shop_products, card_packs):
        shop = tmp_path / "products.yaml"
        card = tmp_path / "card_packs.yaml"
        _write_yaml(shop, {"products": shop_products})
        _write_yaml(card, {"packs": card_packs})
        return shop, card

    def test_main_returns_zero_when_all_refs_valid(self, tmp_path: Path, capsys, monkeypatch):
        shop, card = self._write_pair(
            tmp_path,
            [{"product_id": "fs_she", "type": "faction_set", "card_pack_id": "faction_set_she"}],
            [{"pack_id": "faction_set_she", "cards": []}],
        )
        monkeypatch.setattr("sys.argv", ["v", "--shop-yaml", str(shop), "--card-yaml", str(card)])
        assert v.main() == 0
        out = capsys.readouterr().out
        assert "OK" in out
        assert "1 shop product" in out

    def test_main_returns_one_and_lists_missing(self, tmp_path: Path, capsys, monkeypatch):
        shop, card = self._write_pair(
            tmp_path,
            [{"product_id": "fs_ghost", "type": "faction_set", "card_pack_id": "faction_set_ghost"}],
            [{"pack_id": "basic", "cards": []}],
        )
        monkeypatch.setattr("sys.argv", ["v", "--shop-yaml", str(shop), "--card-yaml", str(card)])
        assert v.main() == 1
        err = capsys.readouterr().err
        assert "1 shop product(s) reference unknown card_pack_id" in err
        assert "'fs_ghost'" in err
        assert "'faction_set_ghost'" in err
