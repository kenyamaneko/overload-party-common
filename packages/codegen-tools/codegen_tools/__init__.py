"""Overload Party サービス系リポ向けコード生成共通ライブラリ."""

from .go_emitter import (
    GoConstStyle,
    GoStyle,
    render_const_block,
    render_go_file,
    render_import_block,
    render_struct,
    render_type_aliases,
    resolve_auto_imports,
)
from .go_format import format_go_source
from .runner import CodegenRunner, GoTarget
from .yaml_loader import load_yaml

__version__ = "0.2.0"

__all__ = [
    "CodegenRunner",
    "GoConstStyle",
    "GoStyle",
    "GoTarget",
    "format_go_source",
    "load_yaml",
    "render_const_block",
    "render_go_file",
    "render_import_block",
    "render_struct",
    "render_type_aliases",
    "resolve_auto_imports",
]
