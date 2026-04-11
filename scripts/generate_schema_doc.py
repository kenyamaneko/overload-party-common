#!/usr/bin/env python3
"""DDL → DATA_DESIGN.md テーブル自動生成.

schema_postgres.sql のインラインコメントを SSoT として、
DATA_DESIGN.md の <!-- BEGIN/END GENERATED: table_name --> マーカー間の
カラムテーブルを自動生成する。

Usage:
    python3 scripts/generate_schema_doc.py                # マーカー間のテーブルを更新
    python3 scripts/generate_schema_doc.py --add-markers  # 初回: マーカーを挿入してから更新
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_PATH = ROOT / "db" / "schema_postgres.sql"
DOC_PATH = ROOT / "docs" / "architecture" / "DATA_DESIGN.md"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Column:
    name: str
    col_type: str
    nullable: bool
    doc: str


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DDL parser
# ---------------------------------------------------------------------------

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+((?:\w+\.)?\w+)\s*\((.*?)\);", re.DOTALL | re.IGNORECASE
)

_TYPE_STOP = frozenset(
    {"NOT", "DEFAULT", "GENERATED", "REFERENCES", "CHECK", "PRIMARY", "UNIQUE", "CONSTRAINT"}
)


def parse_schema(sql_text: str) -> dict[str, Table]:
    """CREATE TABLE 文をパースしてテーブル定義を返す."""
    tables: dict[str, Table] = {}

    for m in _CREATE_TABLE_RE.finditer(sql_text):
        qualified = m.group(1)
        # schema-qualified な場合は unqualified 部分のみ保持（DATA_DESIGN.md マーカーは unqualified）
        table_name = qualified.split(".", 1)[1] if "." in qualified else qualified
        body = m.group(2)
        columns: list[Column] = []

        for raw_line in body.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            # インラインコメントを抽出
            doc = ""
            if "--" in line:
                idx = line.index("--")
                doc = line[idx + 2 :].strip()
                line = line[:idx].strip()

            line = line.rstrip(",").strip()
            if not line:
                continue

            # 制約行はスキップ
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

            # Nullable 判定
            nullable = "NOT NULL" not in line.upper()
            if "PRIMARY KEY" in line.upper():
                nullable = False

            # IDENTITY 判定
            is_identity = "GENERATED ALWAYS AS IDENTITY" in line.upper()

            # 型トークンを抽出（制約キーワードで打ち切り）
            type_tokens: list[str] = []
            for t in tokens[1:]:
                if t.upper() in _TYPE_STOP:
                    break
                type_tokens.append(t)
            col_type = " ".join(type_tokens)

            if is_identity:
                col_type += " (IDENTITY)"

            columns.append(Column(col_name, col_type, nullable, doc))

        if columns:
            tables[table_name] = Table(table_name, columns)

    return tables


# ---------------------------------------------------------------------------
# Markdown table generator
# ---------------------------------------------------------------------------


def generate_table_md(table: Table) -> str:
    """テーブル定義から Markdown テーブルを生成する."""
    rows = [
        "| カラム名 | 型 | Nullable | 説明 |",
        "|---|---|---|---|",
    ]
    for c in table.columns:
        nb = "Yes" if c.nullable else "No"
        doc = c.doc.replace("|", "\\|")
        rows.append(f"| `{c.name}` | {c.col_type} | {nb} | {doc} |")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Marker update (generate_constants.py と同じパターン)
# ---------------------------------------------------------------------------

_MARKER_RE = re.compile(
    r"(<!-- BEGIN GENERATED: (\w+) -->)\n(.*?)(<!-- END GENERATED: \2 -->)",
    re.DOTALL,
)


def update_markers(doc_path: Path, tables: dict[str, Table]) -> bool:
    """マーカー間のテーブルを DDL から再生成して差し替える."""
    text = doc_path.read_text(encoding="utf-8")
    changed = False

    def _replacer(match: re.Match) -> str:
        nonlocal changed
        begin_tag = match.group(1)
        tbl_name = match.group(2)
        end_tag = match.group(4)

        tbl = tables.get(tbl_name)
        if tbl is None:
            print(
                f"WARNING: table '{tbl_name}' not found in DDL, skipping",
                file=sys.stderr,
            )
            return match.group(0)

        md = generate_table_md(tbl)
        new_block = f"{begin_tag}\n{md}\n{end_tag}"
        if new_block != match.group(0):
            changed = True
        return new_block

    new_text = _MARKER_RE.sub(_replacer, text)

    if new_text != text:
        doc_path.write_text(new_text, encoding="utf-8")
        print(f"Updated {doc_path.name}")
    else:
        print(f"No changes in {doc_path.name}")
    return changed


# ---------------------------------------------------------------------------
# --add-markers: 既存テーブルにマーカーを自動挿入
# ---------------------------------------------------------------------------


def _snake_to_pascal(name: str) -> str:
    return "".join(w.capitalize() for w in name.split("_"))


def add_markers(doc_path: Path, tables: dict[str, Table]) -> None:
    """DATA_DESIGN.md 内の既存 Markdown テーブルを検出し、マーカーで囲む."""
    text = doc_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    # 表示名 → SQL テーブル名のマッピング
    display_map: dict[str, str] = {}
    for sql_name in tables:
        pascal = _snake_to_pascal(sql_name)
        display_map[pascal] = sql_name
        display_map[sql_name] = sql_name

    bold_re = re.compile(r"\*\*(\w+)\*\*\s*\(")

    # テーブル領域を検出: (begin_line, end_line, sql_name)
    regions: list[tuple[int, int, str]] = []

    for i, line in enumerate(lines):
        # 既存マーカーがあればスキップ
        if "<!-- BEGIN GENERATED:" in line:
            continue

        if line.strip() != "| カラム名 | 型 | Nullable | 説明 |":
            continue

        table_header_line = i

        # 上方向にボールドヘッダーを探す
        sql_name = None
        for j in range(i - 1, max(i - 15, -1), -1):
            bm = bold_re.search(lines[j])
            if bm:
                display_name = bm.group(1)
                sql_name = display_map.get(display_name)
                break

        if sql_name is None:
            continue

        # テーブル終端を探す
        end = table_header_line + 2  # ヘッダー + セパレーター
        while end < len(lines) and lines[end].strip().startswith("|"):
            end += 1
        end -= 1  # 最終データ行

        regions.append((table_header_line, end, sql_name))

    if not regions:
        print("No tables found to add markers to.", file=sys.stderr)
        return

    # 逆順で挿入（行番号がずれないように）
    for begin, end, sql_name in reversed(regions):
        lines.insert(end + 1, f"<!-- END GENERATED: {sql_name} -->")
        lines.insert(begin, f"<!-- BEGIN GENERATED: {sql_name} -->")

    doc_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Added {len(regions)} marker pairs to {doc_path.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="DDL → DATA_DESIGN.md table generator")
    ap.add_argument(
        "--add-markers",
        action="store_true",
        help="Insert markers around existing tables (first-time setup)",
    )
    args = ap.parse_args()

    sql_text = SQL_PATH.read_text(encoding="utf-8")
    tables = parse_schema(sql_text)
    print(f"Parsed {len(tables)} tables from {SQL_PATH.name}")
    for name in sorted(tables):
        print(f"  {name}: {len(tables[name].columns)} columns")

    if args.add_markers:
        add_markers(DOC_PATH, tables)

    update_markers(DOC_PATH, tables)


if __name__ == "__main__":
    main()
