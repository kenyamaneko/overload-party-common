"""utils モジュールのテスト."""

from __future__ import annotations

from pathlib import Path

from doc_tools.utils import update_markers


def test_update_markers_replaces_content(tmp_path: Path):
    """マーカー間のコンテンツが差し替えられること。"""
    doc = tmp_path / "doc.md"
    doc.write_text(
        "header\n"
        "<!-- BEGIN GENERATED: foo -->\n"
        "old\n"
        "<!-- END GENERATED: foo -->\n"
        "footer\n",
        encoding="utf-8",
    )

    changed = update_markers(doc, {"foo": "new content"})
    assert changed is True

    result = doc.read_text(encoding="utf-8")
    assert "new content" in result
    assert "old" not in result
    assert "header" in result
    assert "footer" in result


def test_update_markers_no_change(tmp_path: Path):
    """コンテンツが同一なら書き換えが発生しないこと。"""
    doc = tmp_path / "doc.md"
    doc.write_text(
        "<!-- BEGIN GENERATED: foo -->\n"
        "same\n"
        "<!-- END GENERATED: foo -->\n",
        encoding="utf-8",
    )

    changed = update_markers(doc, {"foo": "same"})
    assert changed is False


def test_update_markers_missing_key(tmp_path: Path, capsys):
    """replacements に存在しないマーカーは WARNING を出してスキップすること。"""
    doc = tmp_path / "doc.md"
    doc.write_text(
        "<!-- BEGIN GENERATED: unknown -->\n"
        "content\n"
        "<!-- END GENERATED: unknown -->\n",
        encoding="utf-8",
    )

    changed = update_markers(doc, {})
    assert changed is False

    captured = capsys.readouterr()
    assert "WARNING" in captured.err


def test_update_markers_multiple(tmp_path: Path):
    """複数マーカーが同時に更新されること。"""
    doc = tmp_path / "doc.md"
    doc.write_text(
        "<!-- BEGIN GENERATED: a -->\n"
        "old_a\n"
        "<!-- END GENERATED: a -->\n"
        "middle\n"
        "<!-- BEGIN GENERATED: b -->\n"
        "old_b\n"
        "<!-- END GENERATED: b -->\n",
        encoding="utf-8",
    )

    changed = update_markers(doc, {"a": "new_a", "b": "new_b"})
    assert changed is True

    result = doc.read_text(encoding="utf-8")
    assert "new_a" in result
    assert "new_b" in result
    assert "old_a" not in result
    assert "old_b" not in result
    assert "middle" in result
