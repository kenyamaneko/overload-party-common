"""YAML 入力ロード用の薄いラッパー."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    sys.stderr.write("error: PyYAML is required (pip install pyyaml)\n")
    raise


def load_yaml(path: Path) -> dict[str, Any]:
    """YAML ファイルをロードして dict として返す."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level must be a mapping, got {type(data).__name__}")
    return data
