"""Unit tests for validate_seed.py logic functions."""

from validate_seed import parse_array


class TestParseArray:
    def test_empty(self):
        assert parse_array("") == []
        assert parse_array("  ") == []

    def test_single(self):
        assert parse_array("SHE") == ["SHE"]

    def test_multiple(self):
        assert parse_array("SHE,Tenki,Sugar") == ["SHE", "Tenki", "Sugar"]

    def test_whitespace(self):
        assert parse_array(" SHE , Tenki ") == ["SHE", "Tenki"]
