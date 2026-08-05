"""生成した Go ソースを gofmt に通す."""

from __future__ import annotations

import subprocess


def format_go_source(source: str) -> str:
    """Go ソースを gofmt の整形結果に置き換える.

    Args:
        source: 整形前の Go ソース。

    Returns:
        gofmt が整形した Go ソース。

    Raises:
        FileNotFoundError: gofmt が PATH に無い場合。
        ValueError: gofmt が構文エラーなどで整形を拒んだ場合。
    """
    try:
        completed = subprocess.run(
            ["gofmt"],
            input=source,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        raise FileNotFoundError(
            "gofmt not found on PATH; Go toolchain is required to emit Go sources"
        ) from e

    if completed.returncode != 0:
        raise ValueError(f"gofmt rejected the generated source: {completed.stderr.strip()}")

    return completed.stdout
