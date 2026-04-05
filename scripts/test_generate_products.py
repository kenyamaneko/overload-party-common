"""Unit tests for generate_products.py logic functions."""

from generate_products import validate, _sql_escape


# ── SQL escape ─────────────────────────────────────────


class TestSqlEscape:
    def test_none(self):
        assert _sql_escape(None) == "NULL"

    def test_plain(self):
        assert _sql_escape("hello") == "'hello'"

    def test_single_quote(self):
        assert _sql_escape("50% off") == "'50% off'"


# ── Product validation ────────────────────────────────


class TestValidate:
    VALID_PRODUCT = {
        "product_id": "prod_001",
        "name": "Starter Pack",
        "type": "faction_set",
        "price": 500,
        "content": {"faction": "SHE"},
        "is_active": True,
    }

    def test_valid_no_errors(self):
        assert validate([self.VALID_PRODUCT]) == []

    def test_missing_field(self):
        product = {k: v for k, v in self.VALID_PRODUCT.items() if k != "name"}
        errors = validate([product])
        assert any("name" in e for e in errors)

    def test_duplicate_id(self):
        errors = validate([self.VALID_PRODUCT, self.VALID_PRODUCT])
        assert any("duplicate" in e for e in errors)

    def test_invalid_type(self):
        product = {**self.VALID_PRODUCT, "type": "bogus"}
        errors = validate([product])
        assert any("invalid type" in e for e in errors)

    def test_negative_price(self):
        product = {**self.VALID_PRODUCT, "price": -100}
        errors = validate([product])
        assert any("price" in e for e in errors)
