"""utils モジュールのテスト."""

from __future__ import annotations

from pathlib import Path

import pytest

from doc_tools.utils import update_markers


class Testマーカー間コンテンツの更新:
    def test_マーカー間のコンテンツを差し替える(self, tmp_path: Path):
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

    def test_コンテンツが同一なら書き換えない(self, tmp_path: Path):
        doc = tmp_path / "doc.md"
        doc.write_text(
            "<!-- BEGIN GENERATED: foo -->\n"
            "same\n"
            "<!-- END GENERATED: foo -->\n",
            encoding="utf-8",
        )

        changed = update_markers(doc, {"foo": "same"})
        assert changed is False

    def test_生成元に無い名前のマーカーがあるときエラーで停止し文書を残す(self, tmp_path: Path):
        doc = tmp_path / "doc.md"
        original = (
            "<!-- BEGIN GENERATED: unknown -->\n"
            "content\n"
            "<!-- END GENERATED: unknown -->\n"
        )
        doc.write_text(original, encoding="utf-8")

        with pytest.raises(SystemExit, match="'unknown' not found in models.yaml"):
            update_markers(doc, {}, source_label="models.yaml")

        assert doc.read_text(encoding="utf-8") == original

    def test_複数マーカーを同時に更新する(self, tmp_path: Path):
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
