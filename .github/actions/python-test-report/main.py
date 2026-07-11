"""python-test-report の CLI エントリポイント。"""

import os
import sys

from report_builder import build_annotations, build_summary, parse


def main() -> int:
    """JUnit XML を読み、$GITHUB_STEP_SUMMARY への書き出しと ::error:: の出力を行う。

    Returns:
        プロセスの終了コード。
    """
    if len(sys.argv) < 3:
        print("usage: python-test-report <xml-path> <title>", file=sys.stderr)
        return 1

    xml_path = sys.argv[1]
    title = sys.argv[2]
    workspace = os.environ.get("GITHUB_WORKSPACE", "")

    with open(xml_path, encoding="utf-8") as f:
        xml_text = f.read()

    result = parse(xml_text, workspace)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(build_summary(title, result))

    for line in build_annotations(result):
        print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
