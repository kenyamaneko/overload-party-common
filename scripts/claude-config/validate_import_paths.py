"""claude/ 配下の @import パスがすべて存在するファイルを指しているか検証する。"""

import os
import re
import sys


def main() -> int:
    errors: list[str] = []
    for root, _, files in os.walk("claude"):
        for f in files:
            if not f.endswith(".md"):
                continue
            path = os.path.join(root, f)
            with open(path) as fp:
                for i, line in enumerate(fp, 1):
                    if not line.startswith("@"):
                        continue
                    m = re.match(r"^@(\S+)", line)
                    if not m:
                        continue
                    imp = m.group(1)
                    base = os.path.dirname(path)
                    resolved = os.path.normpath(os.path.join(base, imp))
                    if not os.path.exists(resolved):
                        errors.append(f"{path}:{i}: @import target not found: {imp}")
    if errors:
        for e in errors:
            print(f"::error::{e}")
        return 1
    print("All @import paths resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
