#!/usr/bin/env python3
"""Golden test for generate_cards.py.

Generates all outputs to a temp directory and compares them against
the golden snapshots in tests/golden/. If any diff is found, the test
fails and prints the first difference.

Usage:
    python3 -m pytest tests/test_generate_cards_golden.py -v
    python3 tests/test_generate_cards_golden.py          # standalone
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "tests" / "golden"

# (golden file, generated file relative to ROOT)
TARGETS = [
    ("cards_gen.json", "packages/gamedata/cache/cards_gen.json"),
    ("CARDS.md", "docs/game_design/CARDS.md"),
    ("cards_seed.sql", "db/seed/cards_seed.sql"),
]


def _run_generate():
    """Run generate_cards.py and return (returncode, stderr)."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_cards.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    return result.returncode, result.stderr


def test_golden_match():
    """All generated outputs must exactly match the golden snapshots."""
    rc, stderr = _run_generate()
    assert rc == 0, f"generate_cards.py failed:\n{stderr}"

    failures = []
    for golden_name, gen_rel_path in TARGETS:
        golden = (GOLDEN_DIR / golden_name).read_text(encoding="utf-8")
        actual = (ROOT / gen_rel_path).read_text(encoding="utf-8")
        if golden != actual:
            # Find first differing line for a useful error message.
            golden_lines = golden.splitlines(keepends=True)
            actual_lines = actual.splitlines(keepends=True)
            for i, (g, a) in enumerate(zip(golden_lines, actual_lines), 1):
                if g != a:
                    failures.append(
                        f"{golden_name}: first diff at line {i}\n"
                        f"  expected: {g.rstrip()}\n"
                        f"  actual:   {a.rstrip()}"
                    )
                    break
            else:
                longer = "golden" if len(golden_lines) > len(actual_lines) else "actual"
                failures.append(
                    f"{golden_name}: files differ in length "
                    f"(golden={len(golden_lines)}, actual={len(actual_lines)}, "
                    f"{longer} is longer)"
                )

    assert not failures, "Golden test failures:\n" + "\n\n".join(failures)


if __name__ == "__main__":
    test_golden_match()
    print("All golden tests passed.")
