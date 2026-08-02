"""DDL から DATA_DESIGN.md のカラムテーブルを自動生成する。

schema.sql のインラインコメントを SSoT として、
DATA_DESIGN.md の ``<!-- BEGIN/END GENERATED: table_name -->`` マーカー間の
カラムテーブルを自動生成・更新する。

Usage::

    python -m doc_tools.generate_schema_doc --sql db/schema.sql --doc docs/DATA_DESIGN.md
    python -m doc_tools.generate_schema_doc --sql db/schema.sql --doc docs/DATA_DESIGN.md --add-markers
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

from .utils import add_markers_generic, update_markers


@dataclass
class Column:
    """テーブルカラム定義。"""

    name: str
    col_type: str
    is_nullable: bool
    doc: str


@dataclass
class Table:
    """テーブル定義。"""

    name: str
    columns: list[Column] = field(default_factory=list)


_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?((?:\w+\.)?\w+)\s*\((.*?)\);",
    re.DOTALL | re.IGNORECASE,
)

_CREATE_TABLE_KEYWORD_RE = re.compile(r"CREATE\s+TABLE\b", re.IGNORECASE)

_LINE_COMMENT_RE = re.compile(r"--[^\n]*")

_TYPE_STOP = frozenset(
    {"NOT", "DEFAULT", "GENERATED", "REFERENCES", "CHECK", "PRIMARY", "UNIQUE", "CONSTRAINT"}
)


def parse_schema(sql_text: str) -> dict[str, Table]:
    """CREATE TABLE 文をパースしてテーブル定義を返す。

    Raises:
        ValueError: カラムを 1 つも抽出できない CREATE TABLE があるとき、
            DDL 中の CREATE TABLE の数と抽出できたテーブルの数が食い違うとき。
    """
    tables: dict[str, Table] = {}

    for m in _CREATE_TABLE_RE.finditer(sql_text):
        qualified = m.group(1)
        table_name = qualified.split(".", 1)[1] if "." in qualified else qualified
        body = m.group(2)
        columns: list[Column] = []

        for raw_line in body.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            doc = ""
            if "--" in line:
                idx = line.index("--")
                doc = line[idx + 2 :].strip()
                line = line[:idx].strip()

            line = line.rstrip(",").strip()
            if not line:
                continue

            upper = line.upper().lstrip()
            if upper.startswith(
                ("PRIMARY KEY", "FOREIGN KEY", "CHECK (", "CONSTRAINT", "UNIQUE")
            ):
                continue

            tokens = line.split()
            if len(tokens) < 2:
                continue

            col_name = tokens[0]
            if col_name.upper() in (
                "CREATE", "TABLE", "INDEX", "TRIGGER", "ON", "FOR", "EXECUTE",
            ):
                continue

            is_nullable = "NOT NULL" not in line.upper()
            if "PRIMARY KEY" in line.upper():
                is_nullable = False

            is_identity = "GENERATED ALWAYS AS IDENTITY" in line.upper()

            type_tokens: list[str] = []
            for t in tokens[1:]:
                if t.upper() in _TYPE_STOP:
                    break
                type_tokens.append(t)
            col_type = " ".join(type_tokens)

            if is_identity:
                col_type += " (IDENTITY)"

            columns.append(Column(col_name, col_type, is_nullable, doc))

        if not columns:
            raise ValueError(
                f"no column found in CREATE TABLE {qualified}. "
                f"The DDL for {qualified} cannot be parsed."
            )
        tables[table_name] = Table(table_name, columns)

    declared = len(_CREATE_TABLE_KEYWORD_RE.findall(_LINE_COMMENT_RE.sub("", sql_text)))
    if declared != len(tables):
        raise ValueError(
            f"the DDL declares {declared} tables but {len(tables)} were parsed "
            f"({sorted(tables)}). Either a CREATE TABLE statement cannot be parsed, "
            f"or two of them share one unqualified table name."
        )

    return tables


def generate_table_md(table: Table) -> str:
    """テーブル定義から Markdown テーブルを生成する。"""
    rows = [
        "| カラム名 | 型 | Nullable | 説明 |",
        "|---|---|---|---|",
    ]
    for c in table.columns:
        nb = "Yes" if c.is_nullable else "No"
        doc = c.doc.replace("|", "\\|")
        rows.append(f"| `{c.name}` | {c.col_type} | {nb} | {doc} |")
    return "\n".join(rows)


def convert_snake_to_pascal(name: str) -> str:
    """snake_case を PascalCase に変換する。

    Args:
        name: 変換元の snake_case 文字列。

    Returns:
        各語頭を大文字化して連結した PascalCase 文字列。
    """
    return "".join(w.capitalize() for w in name.split("_"))


def add_markers(doc_path: Path, tables: dict[str, Table]) -> None:
    """DATA_DESIGN.md 内の既存 Markdown テーブルを検出しマーカーで囲む。"""
    display_map: dict[str, str] = {}
    for sql_name in tables:
        pascal = convert_snake_to_pascal(sql_name)
        display_map[pascal] = sql_name
        display_map[sql_name] = sql_name

    def _find_name(
        lines: list[str], idx: int, _name_set: set[str]
    ) -> str | None:
        bold_re = re.compile(r"\*\*(\w+)\*\*\s*\(")
        for j in range(idx - 1, max(idx - 15, -1), -1):
            bm = bold_re.search(lines[j])
            if bm:
                display_name = bm.group(1)
                return display_map.get(display_name)
        return None

    add_markers_generic(
        doc_path,
        set(display_map.keys()),
        "| カラム名 | 型 | Nullable | 説明 |",
        _find_name,
    )


def run(sql_path: Path, doc_path: Path, *, do_add_markers: bool = False) -> None:
    """スキーマドキュメント生成のメインロジック。"""
    if not sql_path.exists():
        raise SystemExit(
            f"ERROR: schema file not found: {sql_path}. "
            f"{sql_path.name} must exist before running this generator."
        )
    sql_text = sql_path.read_text(encoding="utf-8")
    tables = parse_schema(sql_text)
    print(f"Parsed {len(tables)} tables from {sql_path.name}")
    for name in sorted(tables):
        print(f"  {name}: {len(tables[name].columns)} columns")

    if do_add_markers:
        add_markers(doc_path, tables)

    replacements = {name: generate_table_md(tbl) for name, tbl in tables.items()}
    update_markers(doc_path, replacements, source_label="DDL")


def main() -> None:
    """CLI エントリーポイント。"""
    ap = argparse.ArgumentParser(description="DDL → DATA_DESIGN.md マーカー差し込み")
    ap.add_argument("--sql", required=True, type=Path, help="db/schema.sql のパス")
    ap.add_argument("--doc", required=True, type=Path, help="docs/DATA_DESIGN.md のパス")
    ap.add_argument(
        "--add-markers",
        action="store_true",
        help="初回セットアップ: マーカー挿入",
    )
    args = ap.parse_args()
    run(args.sql, args.doc, do_add_markers=args.add_markers)


if __name__ == "__main__":
    main()
