"""asyncapi.yaml の components/schemas を codegen-tools 互換の中間 dict に変換する.

`go_emitter.render_go_file` が扱う以下の構造に正規化する:

- types: list[{name, comment, fields: [{name, type, json}]}]
- constants: list[{type: "string", values: [{name, value}]}]

const / 単一値 enum / 多値 enum のフィールド命名規則:

- const 値 (例: event_type の discriminator):
    定数名 = "{FieldGoName}{StripEventSuffix(SchemaName)}"
    例: CardPackPurchasedEvent.event_type=card_pack_purchased
        → EventTypeCardPackPurchased
- 単一値 enum:
    定数名 = "{StripEventSuffix(SchemaName)}{FieldGoName}{ValueGoName}"
    例: PremiumUpdatedEvent.source enum=[shop]
        → PremiumUpdatedSourceShop
- 多値 enum: 現状未対応 (将来対応)。
    呼び出し側で個別ハンドリングするか、x-go-name で明示指定する。

x-go-name 拡張で個別 field 名を上書き可能。
"""

from __future__ import annotations

from typing import Any

# Go 命名で全大文字にする略語。snake_case の単一トークンが一致した場合のみ適用。
DEFAULT_ACRONYMS: frozenset[str] = frozenset({"id", "url", "uri", "api", "http", "json", "ws"})


def convert_to_go_name(snake: str, acronyms: frozenset[str] = DEFAULT_ACRONYMS) -> str:
    """snake_case を CamelCase に変換し、acronyms に含まれるトークンは大文字化する.

    例: "card_pack_id" -> "CardPackID", "event_type" -> "EventType"

    Args:
        snake: 変換元の snake_case 文字列。
        acronyms: 全大文字化するトークンの集合。

    Returns:
        変換後の CamelCase 文字列。
    """
    if not snake:
        return ""
    parts = snake.split("_")
    rendered: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.lower() in acronyms:
            rendered.append(part.upper())
        else:
            rendered.append(part[:1].upper() + part[1:])
    return "".join(rendered)


def strip_event_suffix(name: str) -> str:
    """schema 名から末尾の "Event" を除去する (なければそのまま)."""
    if name.endswith("Event"):
        return name[: -len("Event")]
    return name


_LOCAL_REF_PREFIX = "#/components/schemas/"


def _resolve_local_ref(ref: str) -> str:
    """`#/components/schemas/X` を `X` に解決する. 外部 ref / 形式不正は例外."""
    if not isinstance(ref, str) or not ref.startswith(_LOCAL_REF_PREFIX):
        raise ValueError(
            f"only local component refs are supported, got {ref!r} "
            f"(expected prefix {_LOCAL_REF_PREFIX!r})"
        )
    name = ref[len(_LOCAL_REF_PREFIX):]
    if not name:
        raise ValueError(f"empty schema name in $ref: {ref!r}")
    return name


def convert_to_go_type(prop: dict[str, Any], required: bool) -> str:
    """JSON Schema の型情報から Go 型文字列に変換する.

    `$ref` はローカル component schema 名にのみ解決し、required に応じて値型 /
    ポインタ型 / 配列要素型を切り替える。

    Args:
        prop: JSON Schema のプロパティ定義。
        required: 必須フィールドなら True (ポインタ化しない)。

    Returns:
        対応する Go 型を表す文字列。

    Raises:
        ValueError: 外部 ref や形式不正の ref のとき、`type` が無いか対応外のとき、
            array に mapping の `items` が無いとき。
    """
    if "$ref" in prop:
        base = _resolve_local_ref(prop["$ref"])
        return base if required else f"*{base}"

    if "type" not in prop:
        raise ValueError(f"schema property must declare a type, got {prop!r}")
    json_type = prop["type"]

    if json_type == "string":
        if prop.get("format") == "date-time":
            base = "time.Time"
        else:
            base = "string"
    elif json_type == "integer":
        fmt = prop.get("format", "int64")
        base = "int64" if fmt == "int64" else "int"
    elif json_type == "number":
        base = "float64"
    elif json_type == "boolean":
        base = "bool"
    elif json_type == "array":
        items = prop.get("items")
        if not isinstance(items, dict):
            raise ValueError(
                f"array property must declare items as a mapping, got {prop!r}"
            )
        item_type = convert_to_go_type(items, required=True)
        return f"[]{item_type}"
    elif json_type == "object":
        base = "map[string]interface{}"
    else:
        raise ValueError(f"unsupported schema type {json_type!r} in {prop!r}")

    return base if required else f"*{base}"


def _build_type_comment(schema_name: str, description: str | None) -> str:
    """godoc 規約に合わせ、型名で始まる comment 文字列を返す.

    description が既に schema 名で始まっている場合はそのまま使用、
    それ以外は "{schema_name} は {description}" の形に整える。
    description が無ければ schema 名のみ。
    """
    desc = (description or "").strip()
    if not desc:
        return schema_name
    if desc.startswith(schema_name):
        return desc
    return f"{schema_name} は {desc}"


def parse_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """asyncapi spec dict を {types, constants} に変換する.

    components/schemas の各スキーマを type 定義として、各プロパティの const /
    単一値 enum を constants として抽出する。多値 enum は定数を生成しない。

    Raises:
        ValueError: components/schemas が mapping として無いとき、スキーマが
            type=object でないとき、プロパティが mapping でないとき。
    """
    components = spec.get("components")
    if not isinstance(components, dict):
        raise ValueError(f"spec must declare components as a mapping, got {components!r}")
    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        raise ValueError(
            f"spec must declare components.schemas as a mapping, got {schemas!r}"
        )

    types: list[dict[str, Any]] = []
    const_values: list[dict[str, str]] = []
    enum_values: list[dict[str, str]] = []

    for schema_name, schema in schemas.items():
        if not isinstance(schema, dict):
            raise ValueError(f"schema {schema_name!r} must be a mapping, got {schema!r}")
        if schema.get("type") != "object":
            raise ValueError(
                f"schema {schema_name!r} must have type 'object', "
                f"got {schema.get('type')!r}"
            )

        required = set(schema.get("required", []) or [])
        fields: list[dict[str, Any]] = []

        for prop_name, prop in (schema.get("properties") or {}).items():
            if not isinstance(prop, dict):
                raise ValueError(
                    f"property {schema_name}.{prop_name} must be a mapping, got {prop!r}"
                )

            go_name = prop.get("x-go-name") or convert_to_go_name(prop_name)
            is_required = prop_name in required
            go_type = convert_to_go_type(prop, required=is_required)
            json_tag = prop_name if is_required else f"{prop_name},omitempty"

            fields.append({
                "name": go_name,
                "type": go_type,
                "json": json_tag,
            })

            schema_short = strip_event_suffix(schema_name)

            if "const" in prop:
                const_name = f"{go_name}{schema_short}"
                const_values.append({
                    "name": const_name,
                    "value": str(prop["const"]),
                })
            elif "enum" in prop and isinstance(prop["enum"], list) and len(prop["enum"]) == 1:
                value = prop["enum"][0]
                const_name = f"{schema_short}{go_name}{convert_to_go_name(str(value))}"
                enum_values.append({
                    "name": const_name,
                    "value": str(value),
                })

        types.append({
            "name": schema_name,
            "comment": _build_type_comment(schema_name, schema.get("description")),
            "fields": fields,
        })

    constants: list[dict[str, Any]] = []
    if const_values:
        constants.append({"type": "string", "values": const_values})
    if enum_values:
        constants.append({"type": "string", "values": enum_values})

    return {
        "types": types,
        "constants": constants,
    }
