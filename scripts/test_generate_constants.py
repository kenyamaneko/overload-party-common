"""generate_constants.py のユニットテスト。"""

from generate_constants import _to_pascal


class TestToPascal:
    def test_lowercase_word(self):
        assert _to_pascal("zone") == "Zone"

    def test_snake_case(self):
        assert _to_pascal("semi_limited") == "SemiLimited"

    def test_kebab_case(self):
        assert _to_pascal("semi-limited") == "SemiLimited"

    def test_already_pascal(self):
        assert _to_pascal("Compute") == "Compute"

    def test_slash_removed(self):
        assert _to_pascal("AI/ML") == "AIML"

    def test_empty(self):
        assert _to_pascal("") == ""
