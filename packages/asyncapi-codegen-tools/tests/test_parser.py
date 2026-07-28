"""parse_spec の中間 dict 出力が AsyncAPI 仕様の意味論と一致することを検証する."""

from __future__ import annotations

import pytest

from asyncapi_codegen_tools.parser import (
    parse_spec,
    strip_event_suffix,
    convert_to_go_name,
    convert_to_go_type,
)


class TestGo名への変換:
    def test_単語1つは先頭を大文字にする(self):
        assert convert_to_go_name("timestamp") == "Timestamp"

    def test_複数単語は各トークンをCamelCaseにする(self):
        assert convert_to_go_name("event_type") == "EventType"

    def test_acronymトークンは全て大文字にする(self):
        assert convert_to_go_name("event_id") == "EventID"
        assert convert_to_go_name("card_pack_id") == "CardPackID"
        assert convert_to_go_name("image_url") == "ImageURL"

    def test_空文字は空文字を返す(self):
        assert convert_to_go_name("") == ""


class TestEventサフィックスの除去:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            pytest.param(
                "CardPackPurchasedEvent",
                "CardPackPurchased",
                id="末尾が Event のとき Event を除去する",
            ),
            pytest.param("Foo", "Foo", id="末尾が Event でないときそのまま返す"),
        ],
    )
    def test_Eventサフィックスを除去する(self, name, expected):
        assert strip_event_suffix(name) == expected


class TestGo型への変換:
    @pytest.mark.parametrize(
        ("prop", "required", "expected"),
        [
            pytest.param(
                {"type": "string"}, True, "string",
                id="required な string は値型 string になる",
            ),
            pytest.param(
                {"type": "string"}, False, "*string",
                id="optional な string はポインタ *string になる",
            ),
            pytest.param(
                {"type": "string", "format": "date-time"}, True, "time.Time",
                id="date-time 形式は time.Time になる",
            ),
            pytest.param(
                {"type": "string", "format": "date-time"}, False, "*time.Time",
                id="optional な date-time はポインタ *time.Time になる",
            ),
            pytest.param(
                {"type": "integer"}, True, "int64",
                id="integer は既定で int64 になる",
            ),
            pytest.param(
                {"type": "integer", "format": "int32"}, True, "int",
                id="format int32 の integer は int になる",
            ),
            pytest.param(
                {"type": "boolean"}, True, "bool",
                id="boolean は bool になる",
            ),
            pytest.param(
                {"type": "number"}, True, "float64",
                id="必須の number 型は float64 になる",
            ),
            pytest.param(
                {"type": "number"}, False, "*float64",
                id="optional の number 型はポインタの float64 になる",
            ),
            pytest.param(
                {"type": "array", "items": {"type": "string"}}, True, "[]string",
                id="string の array は []string になる",
            ),
            pytest.param(
                {"type": "object"}, True, "map[string]interface{}",
                id="object は map[string]interface{} にフォールバックする",
            ),
            pytest.param(
                {"$ref": "#/components/schemas/EventTranslation"}, True, "EventTranslation",
                id="required な local ref はスキーマ名に解決される",
            ),
            pytest.param(
                {"$ref": "#/components/schemas/EventTranslation"}, False, "*EventTranslation",
                id="optional な local ref はポインタになる",
            ),
            pytest.param(
                {"type": "array", "items": {"$ref": "#/components/schemas/EventTranslation"}},
                True, "[]EventTranslation",
                id="ref の array は []EventTranslation になる",
            ),
        ],
    )
    def test_JSONスキーマをGo型に変換する(self, prop, required, expected):
        assert convert_to_go_type(prop, required=required) == expected

    @pytest.mark.parametrize(
        "prop",
        [
            pytest.param(
                {"$ref": "external.yaml#/Foo"},
                id="外部ファイル参照の ref は ValueError になる",
            ),
            pytest.param(
                {"$ref": "#/components/schemas/"},
                id="空の local ref は ValueError になる",
            ),
        ],
    )
    def test_不正なrefはValueErrorになる(self, prop):
        with pytest.raises(ValueError):
            convert_to_go_type(prop, required=True)


class TestAsyncAPIスペックのパース:
    def test_objectスキーマをフィールド付きの型にする(self):
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

    def test_型名で始まるdescriptionはそのまま使う(self):
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

    def test_descriptionが無いとき型名だけをコメントにする(self):
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

    def test_constフィールドはstructフィールドとトップレベル定数を生成する(self):
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

    def test_単一値enumは名前付き定数を生成する(self):
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

    def test_x_go_nameは既定のフィールド命名を上書きする(self):
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

    def test_object以外のスキーマはスキップする(self):
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

    def test_optionalなdate_timeはポインタかつomitemptyになる(self):
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

    def test_2値以上のenumを持つプロパティはフィールドにはなるが定数は生成されない(self):
        spec = {
            "components": {
                "schemas": {
                    "FooEvent": {
                        "type": "object",
                        "required": ["status"],
                        "properties": {
                            "status": {"type": "string", "enum": ["a", "b"]},
                        },
                    }
                }
            }
        }
        out = parse_spec(spec)
        assert out["types"][0]["fields"] == [
            {"name": "Status", "type": "string", "json": "status"},
        ]
        assert out["constants"] == []

    @pytest.mark.parametrize(
        "spec",
        [
            pytest.param({}, id="componentsが無いとき"),
            pytest.param({"components": {}}, id="schemasが無いときも同様"),
        ],
    )
    def test_componentsまたはschemasが無いとき型も定数も生成されない(self, spec):
        out = parse_spec(spec)
        assert out["types"] == []
        assert out["constants"] == []

    def test_propertiesの無いobjectスキーマはフィールドの無い型になる(self):
        spec = {
            "components": {
                "schemas": {
                    "FooEvent": {"type": "object"},
                }
            }
        }
        out = parse_spec(spec)
        assert out["types"] == [
            {"name": "FooEvent", "comment": "FooEvent", "fields": []},
        ]

    def test_requiredの無いスキーマは全フィールドがomitempty付きのoptionalになる(self):
        spec = {
            "components": {
                "schemas": {
                    "FooEvent": {
                        "type": "object",
                        "properties": {
                            "bar": {"type": "string"},
                        },
                    }
                }
            }
        }
        out = parse_spec(spec)
        assert out["types"][0]["fields"] == [
            {"name": "Bar", "type": "*string", "json": "bar,omitempty"},
        ]

    def test_プロパティ定義がmappingでないときそのプロパティはフィールドにならない(self):
        spec = {
            "components": {
                "schemas": {
                    "FooEvent": {
                        "type": "object",
                        "required": ["bar"],
                        "properties": {
                            "bar": "not-a-mapping",
                        },
                    }
                }
            }
        }
        out = parse_spec(spec)
        assert out["types"][0]["fields"] == []

    def test_constと単一値enumが併存するとき両方の定数が生成される(self):
        spec = {
            "components": {
                "schemas": {
                    "FooEvent": {
                        "type": "object",
                        "required": ["event_type"],
                        "properties": {
                            "event_type": {"type": "string", "const": "foo_happened"},
                            "source": {"type": "string", "enum": ["shop"]},
                        },
                    }
                }
            }
        }
        out = parse_spec(spec)
        names_and_values = {
            (v["name"], v["value"])
            for block in out["constants"]
            for v in block["values"]
        }
        assert ("EventTypeFoo", "foo_happened") in names_and_values
        assert ("FooSourceShop", "shop") in names_and_values
