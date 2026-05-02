"""claude/ 配下の skill ファイルに必須 frontmatter キーが揃っているか検証する。"""

import os
import re
import sys

REQUIRED_KEYS = {"name", "description"}


def main() -> int:
    errors: list[str] = []
    for root, _, files in os.walk("claude"):
        if not root.endswith(os.sep + "skills"):
            continue
        for f in files:
            if not f.endswith(".md"):
                continue
            path = os.path.join(root, f)
            with open(path) as fp:
                content = fp.read()
            m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if not m:
                errors.append(f"{path}: missing frontmatter")
                continue
            keys = set(re.findall(r"^(\w+):", m.group(1), re.MULTILINE))
            missing = REQUIRED_KEYS - keys
            if missing:
                errors.append(f"{path}: missing frontmatter keys: {sorted(missing)}")
    if errors:
        for e in errors:
            print(f"::error::{e}")
        return 1
    print("All skill frontmatter OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
