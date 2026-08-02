"""マーカー更新・挿入のユーティリティ."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import yaml as _yaml

MARKER_RE = re.compile(
    r"(<!-- BEGIN GENERATED: (\w+) -->)\n(.*?)(<!-- END GENERATED: \2 -->)",
    re.DOTALL,
)


def load_yaml(path: Path) -> dict:
    """YAML ファイルを読み込む。ファイルが存在しなければ即座に終了する。"""
    if not path.exists():
        raise SystemExit(f"ERROR: file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return _yaml.safe_load(f)


def update_markers(
    doc_path: Path,
    replacements: dict[str, str],
    *,
    source_label: str = "source",
) -> bool:
    """マーカー間のコンテンツを replacements の値で差し替える。

    Args:
        doc_path: 対象 Markdown ファイル
        replacements: {マーカー名: 生成 Markdown} のマッピング
        source_label: エラーメッセージで表示するソース名

    Returns:
        差し替えが発生した場合 True

    Raises:
        SystemExit: ドキュメントが存在しないとき、ドキュメントのマーカーに対応する
            生成結果が replacements に無いとき。
    """
    if not doc_path.exists():
        raise SystemExit(
            f"ERROR: documentation file not found: {doc_path}. "
            f"{doc_path.name} must exist before running this generator."
        )
    text = doc_path.read_text(encoding="utf-8")
    has_changed = False

    def _replacer(match: re.Match) -> str:
        nonlocal has_changed
        begin_tag = match.group(1)
        key = match.group(2)
        end_tag = match.group(4)

        md = replacements.get(key)
        if md is None:
            raise SystemExit(
                f"ERROR: '{key}' not found in {source_label} "
                f"but {doc_path.name} has a marker for it. "
                f"Remove the marker or restore '{key}' in {source_label}."
            )

        new_block = f"{begin_tag}\n{md}\n{end_tag}"
        if new_block != match.group(0):
            has_changed = True
        return new_block

    new_text = MARKER_RE.sub(_replacer, text)

    if new_text != text:
        doc_path.write_text(new_text, encoding="utf-8")
        print(f"Updated {doc_path.name}")
    else:
        print(f"No changes in {doc_path.name}")
    return has_changed


def add_markers_generic(
    doc_path: Path,
    name_set: set[str],
    header_pattern: str,
    find_name: Callable[[list[str], int, set[str]], str | None],
) -> None:
    """ドキュメント内の既存テーブルにマーカーを挿入する汎用関数。

    Args:
        doc_path: 対象 Markdown ファイル
        name_set: マーカー名として許可される名前の集合
        header_pattern: テーブルヘッダー行の期待値（strip 後）
        find_name: (lines, table_header_index, name_set) → マーカー名 or None

    Raises:
        SystemExit: ドキュメントが存在しないとき、マーカーを 1 つも挿入できないとき。
    """
    if not doc_path.exists():
        raise SystemExit(
            f"ERROR: documentation file not found: {doc_path}. "
            f"{doc_path.name} must exist before running --add-markers."
        )
    text = doc_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    regions: list[tuple[int, int, str]] = []

    for i, line in enumerate(lines):
        if "<!-- BEGIN GENERATED:" in line:
            continue

        if line.strip() != header_pattern:
            continue

        table_header_line = i
        name = find_name(lines, i, name_set)
        if name is None:
            continue

        end = table_header_line + 2
        while end < len(lines) and lines[end].strip().startswith("|"):
            end += 1
        end -= 1

        regions.append((table_header_line, end, name))

    if not regions:
        raise SystemExit(
            f"ERROR: no table to add markers to in {doc_path.name}. "
            f"A target table must have the header '{header_pattern}' "
            f"and a name from the generation source above it."
        )

    for begin, end, name in reversed(regions):
        lines.insert(end + 1, f"<!-- END GENERATED: {name} -->")
        lines.insert(begin, f"<!-- BEGIN GENERATED: {name} -->")

    doc_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Added {len(regions)} marker pairs to {doc_path.name}")
