"""parse_spec の中間 dict 出力が AsyncAPI 仕様の意味論と一致することを検証する."""

from __future__ import annotations

import pytest

from asyncapi_codegen_tools.parser import (
    parse_spec,
    strip_event_suffix,
    to_go_name,
    to_go_type,
)


class TestToGoName:
    """snake_case → CamelCase 変換は既知 acronym のみ大文字化し、それ以外は通常 capitalize."""

    def test_simple_word_capitalizes_first(self):
        assert to_go_name("timestamp") == "Timestamp"

    def test_multi_word_camel_cases_each_token(self):
        assert to_go_name("event_type") == "EventType"

    def test_acronym_token_uppercases_fully(self):
        assert to_go_name("event_id") == "EventID"
        assert to_go_name("card_pack_id") == "CardPackID"
        assert to_go_name("image_url") == "ImageURL"

    def test_empty_string_returns_empty(self):
        assert to_go_name("") == ""


class TestStripEventSuffix:
    def test_strips_event_when_suffix_present(self):
        assert strip_event_suffix("CardPackPurchasedEvent") == "CardPackPurchased"

    def test_returns_unchanged_when_no_event_suffix(self):
        assert strip_event_suffix("Foo") == "Foo"


class TestToGoType:
    """JSON Schema → Go 型. required は値型, optional は pointer."""

    def test_required_string_is_value_type(self):
        assert to_go_type({"type": "string"}, required=True) == "string"

    def test_optional_string_is_pointer(self):
        assert to_go_type({"type": "string"}, required=False) == "*string"

    def test_date_time_format_maps_to_time_time(self):
        assert to_go_type({"type": "string", "format": "date-time"}, required=True) == "time.Time"

    def test_optional_date_time_is_pointer_time(self):
        assert to_go_type({"type": "string", "format": "date-time"}, required=False) == "*time.Time"

    def test_integer_int64_default(self):
        assert to_go_type({"type": "integer"}, required=True) == "int64"

    def test_integer_int32_explicit(self):
        assert to_go_type({"type": "integer", "format": "int32"}, required=True) == "int"

    def test_boolean(self):
        assert to_go_type({"type": "boolean"}, required=True) == "bool"

    def test_array_of_string(self):
        assert to_go_type({"type": "array", "items": {"type": "string"}}, required=True) == "[]string"

    def test_object_falls_back_to_map(self):
        assert to_go_type({"type": "object"}, required=True) == "map[string]interface{}"

    def test_required_local_ref_resolves_to_schema_name(self):
        assert (
            to_go_type({"$ref": "#/components/schemas/EventTranslation"}, required=True)
            == "EventTranslation"
        )

    def test_optional_local_ref_is_pointer(self):
        assert (
            to_go_type({"$ref": "#/components/schemas/EventTranslation"}, required=False)
            == "*EventTranslation"
        )

    def test_array_of_ref_emits_slice_of_schema(self):
        prop = {
            "type": "array",
            "items": {"$ref": "#/components/schemas/EventTranslation"},
        }
        assert to_go_type(prop, required=True) == "[]EventTranslation"

    def test_external_ref_raises_value_error(self):
        with pytest.raises(ValueError):
            to_go_type({"$ref": "external.yaml#/Foo"}, required=True)

    def test_empty_local_ref_raises_value_error(self):
        with pytest.raises(ValueError):
            to_go_type({"$ref": "#/components/schemas/"}, required=True)


class TestParseSpec:
    """AsyncAPI components/schemas を中間 dict にマップする."""

    def test_object_schema_becomes_type_with_fields(self):
        spec = {
            "components": {
                "schemas": {
                    "FooEvent": {
                        "type": "object",
                        "description": "Foo の説明",
                        "required": ["bar"],
                        "properties": {
                            "bar": {"type": "string"},
                            "baz": {"type": "integer"},
                        },
                    }
                }
            }
        }
        out = parse_spec(spec)

        assert len(out["types"]) == 1
        t = out["types"][0]
        assert t["name"] == "FooEvent"
        # godoc 規約に合わせて型名が先頭に付く
        assert t["comment"] == "FooEvent は Foo の説明"
        assert t["fields"] == [
            {"name": "Bar", "type": "string", "json": "bar"},
            {"name": "Baz", "type": "*int64", "json": "baz,omitempty"},
        ]

    def test_description_already_starting_with_type_name_is_kept_as_is(self):
        spec = {
            "components": {
                "schemas": {
                    "FooEvent": {
                        "type": "object",
                        "description": "FooEvent は何かをする",
                        "required": ["x"],
                        "properties": {"x": {"type": "string"}},
                    }
                }
            }
        }
        out = parse_spec(spec)
        assert out["types"][0]["comment"] == "FooEvent は何かをする"

    def test_no_description_falls_back_to_type_name_only(self):
        spec = {
            "components": {
                "schemas": {
                    "FooEvent": {
                        "type": "object",
                        "required": ["x"],
                        "properties": {"x": {"type": "string"}},
                    }
                }
            }
        }
        out = parse_spec(spec)
        assert out["types"][0]["comment"] == "FooEvent"

    def test_const_field_emits_struct_field_and_top_level_constant(self):
        spec = {
            "components": {
                "schemas": {
                    "CardPackPurchasedEvent": {
                        "type": "object",
                        "required": ["event_type"],
                        "properties": {
                            "event_type": {"type": "string", "const": "card_pack_purchased"},
                        },
                    }
                }
            }
        }
        out = parse_spec(spec)

        # struct field は普通の string として残る
        fields = out["types"][0]["fields"]
        assert fields[0] == {"name": "EventType", "type": "string", "json": "event_type"}

        # 定数として "EventType{StripEventSuffix(SchemaName)}" が出る
        assert out["constants"] == [
            {
                "type": "string",
                "values": [{"name": "EventTypeCardPackPurchased", "value": "card_pack_purchased"}],
            }
        ]

    def test_single_value_enum_emits_named_constant(self):
        spec = {
            "components": {
                "schemas": {
                    "PremiumUpdatedEvent": {
                        "type": "object",
                        "required": ["source"],
                        "properties": {
                            "source": {"type": "string", "enum": ["shop"]},
                        },
                    }
                }
            }
        }
        out = parse_spec(spec)
        # 定数名は "{SchemaShort}{FieldGoName}{ValueGoName}" で PremiumUpdatedSourceShop
        names = [v["name"] for v in out["constants"][0]["values"]]
        assert names == ["PremiumUpdatedSourceShop"]
        assert out["constants"][0]["values"][0]["value"] == "shop"

    def test_x_go_name_overrides_default_field_naming(self):
        spec = {
            "components": {
                "schemas": {
                    "FooEvent": {
                        "type": "object",
                        "required": ["weird_field"],
                        "properties": {
                            "weird_field": {"type": "string", "x-go-name": "CustomName"},
                        },
                    }
                }
            }
        }
        out = parse_spec(spec)
        assert out["types"][0]["fields"][0]["name"] == "CustomName"

    def test_non_object_schemas_are_skipped(self):
        spec = {
            "components": {
                "schemas": {
                    "JustAString": {"type": "string", "enum": ["a", "b"]},
                    "Real": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
                }
            }
        }
        out = parse_spec(spec)
        assert [t["name"] for t in out["types"]] == ["Real"]

    def test_optional_date_time_is_pointer_with_omitempty(self):
        spec = {
            "components": {
                "schemas": {
                    "FooEvent": {
                        "type": "object",
                        "required": [],
                        "properties": {
                            "expires_at": {"type": "string", "format": "date-time"},
                        },
                    }
                }
            }
        }
        out = parse_spec(spec)
        f = out["types"][0]["fields"][0]
        assert f == {"name": "ExpiresAt", "type": "*time.Time", "json": "expires_at,omitempty"}
