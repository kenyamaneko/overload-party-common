"""Unit tests for generate_constants.py helper functions."""

from generate_constants import (
    _snake_to_pascal,
    _camel_to_pascal,
    _go_type_needs_import,
    _go_to_cs_type,
    _go_to_ts_model_field,
)


# ── PascalCase conversion ──────────────────────────────


class TestSnakeToPascal:
    def test_single(self):
        assert _snake_to_pascal("turn") == "Turn"

    def test_two_words(self):
        assert _snake_to_pascal("is_active") == "IsActive"

    def test_three_words(self):
        assert _snake_to_pascal("is_my_turn") == "IsMyTurn"


class TestCamelToPascal:
    def test_lower(self):
        assert _camel_to_pascal("zone") == "Zone"

    def test_camel(self):
        assert _camel_to_pascal("cardId") == "CardId"

    def test_already_pascal(self):
        assert _camel_to_pascal("CardId") == "CardId"


class TestEventDataFieldDispatch:
    """camelCase / snake_case の分岐ロジック（generate_csharp_event_data と同じ）"""

    @staticmethod
    def to_cs_prop(key: str) -> str:
        return _snake_to_pascal(key) if "_" in key else _camel_to_pascal(key)

    def test_camel(self):
        assert self.to_cs_prop("cardId") == "CardId"

    def test_snake(self):
        assert self.to_cs_prop("match_type") == "MatchType"

    def test_single(self):
        assert self.to_cs_prop("zone") == "Zone"


# ── Go → C# type mapping ──────────────────────────────


class TestGoToCsType:
    def test_primitive(self):
        assert _go_to_cs_type("string") == "string"
        assert _go_to_cs_type("int64") == "long"
        assert _go_to_cs_type("bool") == "bool"

    def test_pointer(self):
        assert _go_to_cs_type("*string") == "string?"
        assert _go_to_cs_type("*int64") == "long?"

    def test_slice(self):
        assert _go_to_cs_type("[]string") == "string[]"
        assert _go_to_cs_type("[]int64") == "long[]"

    def test_pointer_slice(self):
        assert _go_to_cs_type("[]*string") == "string?[]"

    def test_custom_type(self):
        assert _go_to_cs_type("MyStruct") == "MyStruct"
        assert _go_to_cs_type("*MyStruct") == "MyStruct?"


# ── Go → TS type mapping ──────────────────────────────


class TestGoToTsModelField:
    def test_simple(self):
        key, ts, opt = _go_to_ts_model_field("string", "name")
        assert (key, ts, opt) == ("name", "string", False)

    def test_omitempty(self):
        key, ts, opt = _go_to_ts_model_field("string", "name,omitempty")
        assert (key, ts, opt) == ("name", "string", True)

    def test_pointer_without_omitempty(self):
        key, ts, opt = _go_to_ts_model_field("*string", "id")
        assert (key, ts, opt) == ("id", "string | null", False)

    def test_pointer_with_omitempty(self):
        key, ts, opt = _go_to_ts_model_field("*string", "id,omitempty")
        assert (key, ts, opt) == ("id", "string", True)

    def test_slice(self):
        key, ts, opt = _go_to_ts_model_field("[]int64", "ids")
        assert ts == "number[]"

    def test_pointer_slice(self):
        key, ts, opt = _go_to_ts_model_field("[]*User", "users")
        assert ts == "(User | null)[]"


# ── Go import detection ────────────────────────────────


class TestGoTypeNeedsImport:
    def test_no_import(self):
        assert _go_type_needs_import("string") == set()

    def test_time(self):
        assert "time" in _go_type_needs_import("time.Time")

    def test_json(self):
        assert "encoding/json" in _go_type_needs_import("json.RawMessage")
