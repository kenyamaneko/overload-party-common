"""AsyncAPI 3.0 spec から Go 型を生成する共通 codegen ライブラリ."""

from .parser import parse_spec
from .runner import generate, cli

__all__ = ["parse_spec", "generate", "cli"]
