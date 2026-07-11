"""pytest --junitxml が出力する JUnit XML を解析し、サマリと注釈を組み立てる。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree

_LOCATION_RE = re.compile(r"([A-Za-z0-9_./-]+\.py):(\d+):")


@dataclass(frozen=True)
class Failure:
    """失敗した (エラーを含む) テスト1件の集計結果を表す。"""

    name: str
    message: str
    file: str | None
    line: int | None


@dataclass(frozen=True)
class ReportResult:
    """JUnit XML の集計結果を表す。"""

    passed: int
    failed: int
    skipped: int
    failures: list[Failure] = field(default_factory=list)


def parse(xml_text: str, workspace: str) -> ReportResult:
    """JUnit XML の文字列からテスト結果一覧を集計する。

    Args:
        xml_text: pytest --junitxml が出力した JUnit XML の内容。
        workspace: リポジトリルートの絶対パス (失敗箇所の相対パス化に使う)。

    Returns:
        通過・失敗・スキップの件数と、失敗したテストの一覧。
    """
    root = ElementTree.fromstring(xml_text)

    passed = 0
    failed = 0
    skipped = 0
    failures: list[Failure] = []

    for testcase in root.iter("testcase"):
        name = f"{testcase.get('classname', '')}.{testcase.get('name', '')}"
        failure = testcase.find("failure")
        error = testcase.find("error")
        skip = testcase.find("skipped")

        if failure is not None or error is not None:
            failed += 1
            node = failure if failure is not None else error
            raw_message = node.get("message") or ""
            message = raw_message.splitlines()[0] if raw_message else ""
            file, line = extract_location(node.text or "", workspace)
            failures.append(Failure(name=name, message=message, file=file, line=line))
        elif skip is not None:
            skipped += 1
        else:
            passed += 1

    return ReportResult(passed=passed, failed=failed, skipped=skipped, failures=failures)


def extract_location(traceback_text: str, workspace: str) -> tuple[str | None, int | None]:
    """トレースバックから最初の file:line を抽出し、ワークスペース相対パスにする。

    Args:
        traceback_text: failure/error 要素の本文 (トレースバック)。
        workspace: リポジトリルートの絶対パス。

    Returns:
        相対ファイルパスと行番号のタプル。見つからなければ両方 None。
    """
    match = _LOCATION_RE.search(traceback_text)
    if not match:
        return None, None

    file = match.group(1)
    line = int(match.group(2))

    if workspace and file.startswith(workspace):
        file = file[len(workspace) :].lstrip("/")

    return file, line


def build_summary(title: str, result: ReportResult) -> str:
    """$GITHUB_STEP_SUMMARY に書き出す Markdown を組み立てる。

    Args:
        title: サマリ見出し。
        result: 集計結果。

    Returns:
        追記する Markdown 本文。
    """
    lines = [
        f"## {title}",
        "",
        "| 項目 | 件数 |",
        "|---|---|",
        f"| 通過 | {result.passed} |",
        f"| 失敗 | {result.failed} |",
        f"| スキップ | {result.skipped} |",
    ]
    if result.failed > 0:
        lines += ["", "失敗したテスト:", ""]
        lines += [f"- {f.name}" for f in result.failures]
    lines.append("")
    return "\n".join(lines)


def build_annotations(result: ReportResult) -> list[str]:
    """失敗テストの workflow コマンド (::error::) 一覧を組み立てる。

    Args:
        result: 集計結果。

    Returns:
        各要素が1件の ::error:: コマンド文字列になる一覧。
    """
    annotations = []
    for f in result.failures:
        message = escape_data(f"{f.name}: {f.message}")
        if f.file is not None and f.line is not None and f.line > 0:
            annotations.append(f"::error file={escape_property(f.file)},line={f.line}::{message}")
        else:
            annotations.append(f"::error::{message}")
    return annotations


def escape_data(s: str) -> str:
    """workflow コマンドのメッセージ本文をエスケープする。

    Args:
        s: エスケープ対象の文字列。

    Returns:
        エスケープ後の文字列。
    """
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(s: str) -> str:
    """workflow コマンドのプロパティ値をエスケープする。

    Args:
        s: エスケープ対象の文字列。

    Returns:
        エスケープ後の文字列。
    """
    return escape_data(s).replace(":", "%3A").replace(",", "%2C")
