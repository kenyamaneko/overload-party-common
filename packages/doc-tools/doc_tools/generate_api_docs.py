"""endpoints.yaml + models.yaml から API_REFERENCE.md の型テーブルを自動生成する。

API_REFERENCE.md の ``<!-- BEGIN/END GENERATED: TypeName -->`` マーカー間に
型定義テーブルを自動生成・更新する。エンドポイント説明は手書き。

Usage::

    python -m doc_tools.generate_api_docs --models data/models.yaml --doc docs/API_REFERENCE.md
    python -m doc_tools.generate_api_docs --models data/models.yaml --doc docs/API_REFERENCE.md --add-markers
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

from .utils import add_markers_generic, load_yaml, update_markers


@dataclass
class FieldDef:
    """型フィールド定義。"""

    name: str
    go_type: str
    json_key: str
    doc: str


@dataclass
class TypeDef:
    """型定義。"""

    name: str
    fields: list[FieldDef] = field(default_factory=list)


def parse_types(models_data: dict) -> dict[str, TypeDef]:
    """models.yaml の files セクションから型定義を抽出する。"""
    types: dict[str, TypeDef] = {}
    for file_def in models_data.get("files", []):
        for td in file_def.get("types", []):
            type_name = td["name"]
            fields: list[FieldDef] = []
            for f in td.get("fields", []):
                json_raw = f.get("json", "")
                json_key = json_raw.split(",")[0]
                doc = f.get("doc", f.get("comment", ""))
                fields.append(FieldDef(
                    name=f["name"],
                    go_type=str(f["type"]),
                    json_key=json_key,
                    doc=doc,
                ))
            types[type_name] = TypeDef(name=type_name, fields=fields)
    return types


def generate_type_table(type_def: TypeDef) -> str:
    """型定義から Markdown テーブルを生成する。"""
    rows = [
        "| フィールド | 型 | JSON | 説明 |",
        "|---|---|---|---|",
    ]
    for f in type_def.fields:
        fname = f"`{f.name}`"
        ftype = f"`{f.go_type}`"
        fjson = f"`{f.json_key}`" if f.json_key else ""
        doc = f.doc.replace("|", "\\|")
        rows.append(f"| {fname} | {ftype} | {fjson} | {doc} |")
    return "\n".join(rows)


def _find_type_name(
    lines: list[str], table_header_idx: int, name_set: set[str]
) -> str | None:
    """テーブルヘッダーの上方向にバッククォートで囲まれた型名を探す。"""
    backtick_re = re.compile(r"`(\w+)`")
    for j in range(table_header_idx - 1, max(table_header_idx - 10, -1), -1):
        for m in backtick_re.finditer(lines[j]):
            candidate = m.group(1)
            if candidate in name_set:
                return candidate
    return None


def add_markers(doc_path: Path, types: dict[str, TypeDef]) -> None:
    """初回セットアップ: 既存の型テーブルにマーカーを追加する。"""
    add_markers_generic(
        doc_path,
        set(types.keys()),
        "| フィールド | 型 | JSON | 説明 |",
        _find_type_name,
    )


def run(
    models_path: Path,
    doc_path: Path,
    *,
    endpoints_path: Path | None = None,
    do_add_markers: bool = False,
) -> None:
    """API ドキュメント生成のメインロジック。"""
    models_data = load_yaml(models_path)

    types = parse_types(models_data)
    print(f"Parsed {len(types)} types from {models_path.name}")
    for name in sorted(types):
        print(f"  {name}: {len(types[name].fields)} fields")

    if do_add_markers:
        add_markers(doc_path, types)

    replacements = {name: generate_type_table(td) for name, td in types.items()}
    update_markers(doc_path, replacements, source_label="models.yaml")


def main() -> None:
    """CLI エントリーポイント。"""
    ap = argparse.ArgumentParser(
        description="endpoints.yaml + models.yaml → API_REFERENCE.md マーカー差し込み"
    )
    ap.add_argument("--endpoints", type=Path, help="data/endpoints.yaml のパス（将来拡張用）")
    ap.add_argument("--models", required=True, type=Path, help="data/models.yaml のパス")
    ap.add_argument("--doc", required=True, type=Path, help="docs/API_REFERENCE.md のパス")
    ap.add_argument(
        "--add-markers",
        action="store_true",
        help="初回セットアップ: マーカー挿入",
    )
    args = ap.parse_args()
    run(
        args.models,
        args.doc,
        endpoints_path=args.endpoints,
        do_add_markers=args.add_markers,
    )


if __name__ == "__main__":
    main()
