"""Overload Party サービス系リポ向けコード生成共通ライブラリ."""

from .go_emitter import (
    GoConstStyle,
    GoStyle,
    render_const_block,
    render_go_file,
    render_import_block,
    render_struct,
    resolve_auto_imports,
)
from .go_format import format_go_source

__version__ = "1.0.0"

__all__ = [
    "GoConstStyle",
    "GoStyle",
    "format_go_source",
    "render_const_block",
    "render_go_file",
    "render_import_block",
    "render_struct",
    "resolve_auto_imports",
]
