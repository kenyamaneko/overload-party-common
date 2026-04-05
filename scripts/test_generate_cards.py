"""Unit tests for generate_cards.py logic functions."""

from generate_cards import validate, _sql_escape, _scalability_display


# ── SQL escape ─────────────────────────────────────────


class TestSqlEscape:
    def test_none(self):
        assert _sql_escape(None) == "NULL"

    def test_plain(self):
        assert _sql_escape("hello") == "'hello'"

    def test_single_quote(self):
        assert _sql_escape("it's") == "'it''s'"


# ── Scalability display ───────────────────────────────


class TestScalabilityDisplay:
    def test_neither(self):
        assert _scalability_display({"card_type": "Compute"}) == "Compute"

    def test_resizable(self):
        assert _scalability_display({"card_type": "Database", "resizable": True}) == "Database (R)"

    def test_elastic(self):
        assert _scalability_display({"card_type": "Serverless", "elastic": True}) == "Serverless (E)"

    def test_both(self):
        assert _scalability_display({"card_type": "Compute", "resizable": True, "elastic": True}) == "Compute (R+E)"

    def test_display_name_remap(self):
        assert _scalability_display({"card_type": "ObjectStorage"}) == "Object Storage"
        assert _scalability_display({"card_type": "CacheDB"}) == "Cache DB"


# ── Card validation ───────────────────────────────────


class TestValidate:
    VALID_CARD = {
        "card_no": 1,
        "card_id": "SH-0001",
        "card_name": "テスト",
        "const_name": "Test",
        "card_type": "Compute",
        "resizable": True,
        "elastic": False,
        "restriction": "unlimited",
        "is_active": True,
        "stats": {"throughput": 100, "availability": 200, "maintenance_cost": 50, "sla_penalty": 100},
    }

    def test_valid_card_no_errors(self):
        assert validate([self.VALID_CARD]) == []

    def test_missing_required_field(self):
        card = {k: v for k, v in self.VALID_CARD.items() if k != "card_name"}
        errors = validate([card])
        assert any("card_name" in e for e in errors)

    def test_duplicate_card_no(self):
        errors = validate([self.VALID_CARD, self.VALID_CARD])
        assert any("duplicate" in e for e in errors)

    def test_invalid_card_id_format(self):
        card = {**self.VALID_CARD, "card_id": "XX-0001"}
        errors = validate([card])
        assert any("card_id" in e and "format" in e for e in errors)

    def test_negative_stat(self):
        card = {**self.VALID_CARD, "stats": {**self.VALID_CARD["stats"], "throughput": -1}}
        errors = validate([card])
        assert any("non-negative" in e for e in errors)
