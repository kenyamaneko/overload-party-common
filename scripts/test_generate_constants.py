"""Unit tests for generate_constants.py helper functions."""

import re
from pathlib import Path

from generate_constants import (
    _snake_to_pascal,
    _camel_to_pascal,
    _go_type_needs_import,
    _go_to_cs_type,
    _go_to_ts_model_field,
    generate_csharp_event_data,
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


# ── generate_csharp_event_data ─────────────────────────


class TestGenerateCsharpEventData:
    """Regression tests for the generator — protects the IEventData contract."""

    SCHEMAS = {
        "play_card": {
            "cardId": "string",
            "zone": "string",
            "index": "int",
            "cancelled?": "bool",
        },
        "turn_start": {
            "turn": "long",
            "is_my_turn": "bool",
        },
        "select_slot": {
            "cardId": "string",
            "instanceId": "string",
            "zone": "string",
            "index": "int",
        },
    }

    def _generate(self, tmp_path: Path) -> str:
        out = tmp_path / "EventData_gen.cs"
        generate_csharp_event_data(self.SCHEMAS, out_path=out)
        return out.read_text(encoding="utf-8")

    def test_marker_interface_declared_once(self, tmp_path):
        content = self._generate(tmp_path)
        matches = re.findall(r"public interface IEventData \{ \}", content)
        assert len(matches) == 1, f"expected exactly 1 IEventData interface declaration, got {len(matches)}"

    def test_every_class_implements_marker(self, tmp_path):
        content = self._generate(tmp_path)
        class_decls = re.findall(r"public class (\w+EventData)(?: : (\w+))?", content)
        assert class_decls, "no EventData classes were generated"
        for class_name, base in class_decls:
            assert base == "IEventData", f"{class_name} does not implement IEventData (got base={base!r})"

    def test_no_to_dictionary_method(self, tmp_path):
        content = self._generate(tmp_path)
        assert "ToDictionary" not in content, "ToDictionary helper should no longer be generated"

    def test_select_slot_class_shape(self, tmp_path):
        content = self._generate(tmp_path)
        assert "public class SelectSlotEventData : IEventData" in content
        assert "public required string CardId { get; init; }" in content
        assert "public required string InstanceId { get; init; }" in content
        assert "public required string Zone { get; init; }" in content
        assert "public required int Index { get; init; }" in content

    def test_optional_field_rendered(self, tmp_path):
        content = self._generate(tmp_path)
        assert "public bool? Cancelled { get; init; }" in content
