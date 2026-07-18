"""yaml_loader のテスト."""

from __future__ import annotations

from pathlib import Path

import pytest

from codegen_tools.yaml_loader import load_yaml


def _write_yaml_text(path: Path, text: str) -> Path:
    """YAML テキストをファイルに書き出す.

    Args:
        path: 書き出し先のパス。
        text: 書き出す YAML テキスト。

    Returns:
        書き出したファイルのパス。
    """
    path.write_text(text, encoding="utf-8")
    return path


class TestYAML定義の読み込み:
    def test_空のYAMLファイルは空の定義として読み込まれる(self, tmp_path: Path):
        path = _write_yaml_text(tmp_path / "empty.yaml", "")
        assert load_yaml(path) == {}

    @pytest.mark.parametrize(
        ("text", "type_name"),
        [
            pytest.param(
                "- a\n", "list",
                id="トップレベルがリストのときmappingを要求するValueErrorになる",
            ),
            pytest.param(
                "plain text\n", "str",
                id="トップレベルがスカラのときも同じValueErrorになる",
            ),
        ],
    )
    def test_トップレベルがmapping以外のときValueErrorになる(self, tmp_path, text, type_name):
        path = _write_yaml_text(tmp_path / "invalid.yaml", text)
        with pytest.raises(ValueError, match=f"must be a mapping, got {type_name}"):
            load_yaml(path)
