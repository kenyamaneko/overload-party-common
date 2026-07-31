"""リポジトリのテスト実行結果から、テスト観点カタログを生成する。

テストの命名規約 (keyandnotes-rules testing.md「テストの命名」) に従ったテスト名を、
グループ (テスト対象の要素) とケース (シナリオ) の階層に復元し、Markdown または HTML で
標準出力に書き出す。overload-party は多言語・多リポのため、テスト結果の形式ごとに専用の
パーサを持ち、共通の BehaviorCase 列に正規化してから描画する。

対応する結果形式:

- ``go-json``: ``go test -json`` の JSON Lines
- ``pytest-junit``: pytest の JUnit XML
- ``vitest-json``: vitest ``--reporter=json`` の JSON
- ``csharp-json``: battle が抽出した ``{target, case, skipped, source}`` の JSON 配列
  (対象要素を表す ``[Trait("対象", ...)]`` が TRX にも JUnit XML にも出力されないため、
  battle 側で抽出した中間形式を読む)

Usage::

    python -m doc_tools.generate_test_catalog \\
        --section '外から見た振る舞い:shop:go-json:results/shop.json:github.com/kenyamaneko/overload-party-shop/internal/handler' \\
        --section '内部の挙動:shop:go-json:results/shop.json:github.com/kenyamaneko/overload-party-shop/internal/repository' \\
        --format html --title "shop テスト観点カタログ" --commit "$SHA"
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# Go の testcase 名を階層に区切る文字。``t.Run`` のネストが ``/`` で連結される
GO_NAME_SEPARATOR = "/"

# pytest のクラス名は module のドット連結にテストクラス名を続ける。テストクラスは Test で始まる
PYTEST_CLASS_PREFIX = "Test"

# pytest のテストメソッド名は test_ で始まる
PYTEST_METHOD_PREFIX = "test_"

# vitest ``--reporter=json`` が skip 扱いとする status 値
VITEST_SKIPPED_STATUSES = frozenset({"skipped", "pending", "todo"})

# skip されたテストは実行されておらず「テスト済み」と言えないため、注記を付けて区別する
SKIPPED_NOTE = "（skip 中のため未検証）"

# テストの無い仕様はカタログに現れないため、「載っていない = 仕様がない」という誤読を防ぐ
DISCLAIMER = (
    "本カタログはこのリポジトリの自動テストのテスト名から生成した「テスト済みの観点」の一覧であり、"
    "仕様の全量ではない。テストの無い仕様はここに現れない。"
)

MARKDOWN_INDENT = "  "


@dataclass(frozen=True)
class BehaviorCase:
    """1 件のテストケースが表す振る舞い。

    Args:
        group_chain: テスト対象の要素を表すグループ名の連鎖。
        case_name: シナリオを表すケース名。
        is_skipped: skip されて実行されていないケースかどうか。
        source_file: 由来を表す文字列 (パッケージパス・モジュール・ファイル・名前空間)。
    """

    group_chain: tuple[str, ...]
    case_name: str
    is_skipped: bool
    source_file: str


@dataclass
class GroupNode:
    """グループ 1 階層分の入れ物。

    Args:
        subgroups: グループ名をキーとする下位グループ。
        cases: このグループ直下のケース。
    """

    subgroups: "dict[str, GroupNode]" = field(default_factory=dict)
    cases: list[BehaviorCase] = field(default_factory=list)


@dataclass(frozen=True)
class SectionSpec:
    """--section 引数 1 件分の指定。

    Args:
        category: セクションの上位カテゴリ名 (「外から見た振る舞い」「内部の挙動」等)。
        label: セクション名 (リポ名など)。
        fmt: テスト結果の形式 (PARSERS のキー)。
        path: テスト結果ファイルのパス。
        prefixes: このセクションに含める由来のプレフィクス群。None なら結果全体を含める。
    """

    category: str
    label: str
    fmt: str
    path: Path
    prefixes: "tuple[str, ...] | None"


def parse_go_test_json(path: Path) -> list[BehaviorCase]:
    """``go test -json`` の JSON Lines を BehaviorCase の列に変換する。

    先頭セグメント (テスト関数名 ``Test...``) は英語の器なので除き、``t.Run`` のネストを
    グループ連鎖、最下段をケース名とする。他のテストの接頭辞になっているテスト (親) は除き、
    末端のケースだけを残す。Go は subtest 名の空白を ``_`` に置換するため復元しない。

    Args:
        path: ``go test -json`` の出力ファイル。

    Returns:
        終了アクション出現順の BehaviorCase のリスト。

    Raises:
        ValueError: JSON として読めない行があるとき。
    """
    statuses: dict[tuple[str, str], str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number} は JSON として読めません: {exc}") from exc
        test = event.get("Test")
        action = event.get("Action")
        if test is None or action not in ("pass", "fail", "skip"):
            continue
        statuses[(event["Package"], test)] = action

    test_names_by_package: dict[str, set[str]] = {}
    for package, test in statuses:
        test_names_by_package.setdefault(package, set()).add(test)

    cases = []
    for (package, test), action in statuses.items():
        prefix = test + GO_NAME_SEPARATOR
        is_leaf = not any(
            other.startswith(prefix) for other in test_names_by_package[package]
        )
        if not is_leaf:
            continue
        segments = test.split(GO_NAME_SEPARATOR)[1:]
        if not segments:
            group_chain: tuple[str, ...] = ()
            case_name = test
        else:
            group_chain = tuple(segments[:-1])
            case_name = segments[-1]
        cases.append(BehaviorCase(group_chain, case_name, action == "skip", package))
    return cases


def parse_pytest_junit(path: Path) -> list[BehaviorCase]:
    """pytest の JUnit XML を BehaviorCase の列に変換する。

    ``classname`` を module 部分とテストクラス連鎖に分ける。テストクラスは ``Test`` で始まる
    ため、最初に ``Test`` で始まるセグメント以降をグループ連鎖 (``Test`` 接頭辞を除く)、
    それより前を由来の module とする。ケース名は ``test_`` 接頭辞を除いたメソッド名。

    Args:
        path: pytest の JUnit XML ファイル。

    Returns:
        文書順の BehaviorCase のリスト。

    Raises:
        ValueError: testcase に name または classname 属性が無いとき。
    """
    root = ET.parse(path).getroot()
    cases = []
    for testcase in root.iter("testcase"):
        name = testcase.get("name")
        if name is None:
            raise ValueError(f"testcase に name 属性がありません: {path}")
        classname = testcase.get("classname")
        if classname is None:
            raise ValueError(f"testcase に classname 属性がありません: {path}")
        segments = classname.split(".")
        class_start = next(
            (i for i, seg in enumerate(segments) if seg.startswith(PYTEST_CLASS_PREFIX)),
            len(segments),
        )
        module = ".".join(segments[:class_start])
        group_chain = tuple(
            seg[len(PYTEST_CLASS_PREFIX):] for seg in segments[class_start:]
        )
        case_name = name
        if case_name.startswith(PYTEST_METHOD_PREFIX):
            case_name = case_name[len(PYTEST_METHOD_PREFIX):]
        is_skipped = testcase.find("skipped") is not None
        cases.append(BehaviorCase(group_chain, case_name, is_skipped, module))
    return cases


def make_relative_to_working_directory(path_text: str) -> str:
    """絶対パスを実行位置からの相対パスに直す。

    Args:
        path_text: 変換するパス。相対パスならそのまま返す。

    Returns:
        実行位置からの相対パス。

    Raises:
        ValueError: 絶対パスが実行位置の配下に無いとき。
    """
    path = Path(path_text)
    if not path.is_absolute():
        return path_text
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError as exc:
        raise ValueError(f"実行位置の配下に無いパスです: {path_text}") from exc


def parse_vitest_json(path: Path) -> list[BehaviorCase]:
    """vitest ``--reporter=json`` の JSON を BehaviorCase の列に変換する。

    ``ancestorTitles`` (``describe`` のネスト) をグループ連鎖、``title`` (``it`` 名) を
    ケース名、テストファイルのパスを由来とする。由来は絶対パスで出力されるため、
    振り分けのプレフィクスをリポジトリ内のパスで書けるよう実行位置からの相対パスに直す。

    Args:
        path: vitest ``--reporter=json`` の出力ファイル。

    Returns:
        文書順の BehaviorCase のリスト。

    Raises:
        ValueError: assertionResult に status / title / ancestorTitles が無いとき、
            または由来が実行位置の配下に無いとき。
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for test_result in document["testResults"]:
        source_file = make_relative_to_working_directory(test_result["name"])
        for assertion in test_result["assertionResults"]:
            if "title" not in assertion or "status" not in assertion:
                raise ValueError(f"assertionResult に title / status がありません: {path}")
            group_chain = tuple(assertion["ancestorTitles"])
            is_skipped = assertion["status"] in VITEST_SKIPPED_STATUSES
            cases.append(
                BehaviorCase(group_chain, assertion["title"], is_skipped, source_file)
            )
    return cases


def parse_csharp_catalog_json(path: Path) -> list[BehaviorCase]:
    """battle が抽出した中間 JSON を BehaviorCase の列に変換する。

    ``[Trait("対象", ...)]`` の値 (``target``) をグループ、``DisplayName`` (``case``) を
    ケース名とする。対象要素が TRX にも JUnit XML にも出力されないため、battle 側で
    ``[Theory]`` を各行に展開しつつ抽出した ``{target, case, skipped, source}`` を読む。

    Args:
        path: battle が出力した中間 JSON ファイル (レコードの配列)。

    Returns:
        配列順の BehaviorCase のリスト。

    Raises:
        ValueError: レコードに target / case / source が無いとき。
    """
    records = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for record in records:
        for key in ("target", "case", "source"):
            if key not in record:
                raise ValueError(f"レコードに {key} がありません: {path}: {record}")
        target = record["target"]
        group_chain = (target,) if target else ()
        cases.append(
            BehaviorCase(
                group_chain, record["case"], bool(record.get("skipped", False)), record["source"]
            )
        )
    return cases


PARSERS = {
    "go-json": parse_go_test_json,
    "pytest-junit": parse_pytest_junit,
    "vitest-json": parse_vitest_json,
    "csharp-json": parse_csharp_catalog_json,
}


def route_cases_to_specs(
    specs: list[SectionSpec], cases: list[BehaviorCase]
) -> dict[SectionSpec, list[BehaviorCase]]:
    """1 つの結果ファイルから読んだケース群を、由来のプレフィクスでセクションへ振り分ける。

    Args:
        specs: 同じ結果ファイルを参照する SectionSpec のリスト。
        cases: その結果ファイルから読んだ BehaviorCase のリスト。

    Returns:
        SectionSpec ごとに振り分けられた BehaviorCase のリスト。

    Raises:
        ValueError: どのセクションにも、または複数セクションに振り分けられるケースがあるとき。
    """
    if len(specs) == 1 and specs[0].prefixes is None:
        return {specs[0]: cases}

    assigned: dict[SectionSpec, list[BehaviorCase]] = {spec: [] for spec in specs}
    for case in cases:
        matches = [
            spec
            for spec in specs
            if spec.prefixes is not None
            and any(case.source_file.startswith(prefix) for prefix in spec.prefixes)
        ]
        if not matches:
            raise ValueError(f"どのセクションにも振り分けられない由来です: {case.source_file}")
        if len(matches) > 1:
            raise ValueError(f"複数のセクションに振り分けられる由来です: {case.source_file}")
        assigned[matches[0]].append(case)
    return assigned


def build_sections(specs: list[SectionSpec]) -> list[tuple[str, str, GroupNode]]:
    """--section 引数群から (カテゴリ, セクション名, グループ木) のリストを組み立てる。

    同じ結果ファイルを参照する SectionSpec は由来のプレフィクスで振り分ける。出力は
    --section の指定順によらず、カテゴリの初出順にまとめる。

    Args:
        specs: コマンドラインで指定された SectionSpec のリスト。

    Returns:
        カテゴリごとにまとめた (カテゴリ, セクション名, グループ木) のリスト。

    Raises:
        ValueError: 同じ結果ファイルに異なる形式が指定されたとき。
    """
    specs_by_path: dict[Path, list[SectionSpec]] = {}
    for spec in specs:
        specs_by_path.setdefault(spec.path, []).append(spec)

    assigned: dict[SectionSpec, list[BehaviorCase]] = {}
    for path, path_specs in specs_by_path.items():
        formats = {spec.fmt for spec in path_specs}
        if len(formats) > 1:
            raise ValueError(f"同じ結果ファイルに複数の形式が指定されています: {path}: {formats}")
        cases = PARSERS[path_specs[0].fmt](path)
        assigned.update(route_cases_to_specs(path_specs, cases))

    specs_by_category: dict[str, list[SectionSpec]] = {}
    for spec in specs:
        specs_by_category.setdefault(spec.category, []).append(spec)

    return [
        (spec.category, spec.label, build_group_tree(assigned[spec]))
        for category_specs in specs_by_category.values()
        for spec in category_specs
    ]


def build_group_tree(cases: list[BehaviorCase]) -> GroupNode:
    """ケース列をグループ連鎖に沿った木に組み上げる。

    Args:
        cases: 振る舞いのリスト。

    Returns:
        ルートの GroupNode。同名グループは 1 つのノードに統合される。
    """
    root = GroupNode()
    for case in cases:
        node = root
        for group_name in case.group_chain:
            node = node.subgroups.setdefault(group_name, GroupNode())
        node.cases.append(case)
    return root


def count_cases(node: GroupNode) -> int:
    """木に含まれるケースの総数を返す。

    Args:
        node: 数え上げの起点となる GroupNode。

    Returns:
        起点以下の全ケース数。
    """
    return len(node.cases) + sum(count_cases(sub) for sub in node.subgroups.values())


def escape_text(text: str) -> str:
    """テスト名を Markdown / HTML のどちらでもタグと誤解釈されない形にする。

    Args:
        text: テスト名などの表示テキスト。

    Returns:
        ``&`` ``<`` ``>`` を実体参照にしたテキスト。
    """
    return html.escape(text, quote=False)


def format_case_text(case: BehaviorCase) -> str:
    """ケース 1 件の表示テキストを組み立てる。

    Args:
        case: 表示する振る舞い。

    Returns:
        エスケープ済みケース名。skip 中なら未検証の注記付き。
    """
    text = escape_text(case.case_name)
    if case.is_skipped:
        text += SKIPPED_NOTE
    return text


def append_group_markdown(lines: list[str], node: GroupNode, depth: int) -> None:
    """グループ内のケースと下位グループを Markdown の入れ子リストとして追記する。

    Args:
        lines: 追記先の行リスト。
        node: 描画するグループ。
        depth: リストの入れ子の深さ (0 起点)。
    """
    indent = MARKDOWN_INDENT * depth
    for case in node.cases:
        lines.append(f"{indent}- {format_case_text(case)}")
    for group_name, subgroup in node.subgroups.items():
        lines.append(f"{indent}- **{escape_text(group_name)}**")
        append_group_markdown(lines, subgroup, depth + 1)


def render_markdown(
    sections: list[tuple[str, str, GroupNode]], commit: str | None, title: str
) -> str:
    """テスト観点カタログを Markdown で描画する。

    Args:
        sections: (カテゴリ, セクション名, グループ木) のリスト。
        commit: 生成元 commit の SHA。None なら記載しない。
        title: ページの表題。

    Returns:
        Markdown 文書全体。
    """
    lines = [f"# {escape_text(title)}", "", f"> {DISCLAIMER}", ""]
    if commit is not None:
        lines += [f"生成元 commit: `{commit}`", ""]
    current_category = None
    for category, label, root in sections:
        if category != current_category:
            lines += [f"## {escape_text(category)}", ""]
            current_category = category
        lines += [f"### {escape_text(label)}（全 {count_cases(root)} ケース）", ""]
        for case in root.cases:
            lines.append(f"- {format_case_text(case)}")
        if root.cases:
            lines.append("")
        for group_name in sorted(root.subgroups):
            lines += [f"#### {escape_text(group_name)}", ""]
            append_group_markdown(lines, root.subgroups[group_name], 0)
            lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def append_group_html(parts: list[str], node: GroupNode) -> None:
    """グループ内のケースと下位グループを HTML として追記する。

    ケースは ``<ul><li>`` で列挙し、下位グループは ``<details>`` としてケース数の注記付きで
    追記する。

    Args:
        parts: 追記先の HTML 断片リスト。
        node: 描画するグループ。
    """
    if node.cases:
        parts.append("<ul>")
        for case in node.cases:
            css_class = ' class="skipped"' if case.is_skipped else ""
            parts.append(f"<li{css_class}>{format_case_text(case)}</li>")
        parts.append("</ul>")
    for group_name in sorted(node.subgroups):
        subgroup = node.subgroups[group_name]
        parts.append(
            f"<details><summary>{escape_text(group_name)}"
            f"（全 {count_cases(subgroup)} ケース）</summary>"
        )
        append_group_html(parts, subgroup)
        parts.append("</details>")


def render_html(
    sections: list[tuple[str, str, GroupNode]], commit: str | None, title: str
) -> str:
    """テスト観点カタログを単一ファイルの HTML ページとして描画する。

    Args:
        sections: (カテゴリ, セクション名, グループ木) のリスト。
        commit: 生成元 commit の SHA。None なら記載しない。
        title: ページの表題。

    Returns:
        HTML 文書全体。
    """
    parts = [
        "<!doctype html>",
        '<html lang="ja">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape_text(title)}</title>",
        "<style>",
        "body { font-family: sans-serif; max-width: 60rem; margin: 0 auto; padding: 1rem 1.5rem; line-height: 1.7; }",
        "blockquote { border-left: 4px solid #c9c9c9; margin: 1rem 0; padding: 0.25rem 1rem; background: #f6f6f6; }",
        "h2 { border-bottom: 2px solid #ddd; padding-bottom: 0.25rem; margin-top: 2.5rem; }",
        "h3 { margin-top: 1.75rem; }",
        "details { margin: 0.25rem 0 0.25rem 1rem; }",
        "summary { cursor: pointer; font-weight: bold; }",
        "summary:hover { color: #1a5fb4; }",
        "li.skipped { color: #888; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{escape_text(title)}</h1>",
        f"<blockquote>{DISCLAIMER}</blockquote>",
    ]
    if commit is not None:
        parts.append(f"<p>生成元 commit: <code>{escape_text(commit)}</code></p>")
    current_category = None
    for category, label, root in sections:
        if category != current_category:
            parts.append(f"<h2>{escape_text(category)}</h2>")
            current_category = category
        parts.append(f"<h3>{escape_text(label)}（全 {count_cases(root)} ケース）</h3>")
        append_group_html(parts, root)
    parts += ["</body>", "</html>"]
    return "\n".join(parts) + "\n"


def parse_section_arg(value: str) -> SectionSpec:
    """--section の「カテゴリ:ラベル:形式:パス[:プレフィクス]」形式を分解する。

    Args:
        value: コマンドラインで渡された値。

    Returns:
        分解済みの SectionSpec。

    Raises:
        argparse.ArgumentTypeError: 形式が不正、または未対応の形式を指定したとき。
    """
    parts = value.split(":", 4)
    if len(parts) < 4 or not all(parts[:4]):
        raise argparse.ArgumentTypeError(
            f"「カテゴリ:ラベル:形式:パス」または「…:プレフィクス」の形式で指定してください: {value!r}"
        )
    category, label, fmt, path = parts[0], parts[1], parts[2], parts[3]
    if fmt not in PARSERS:
        raise argparse.ArgumentTypeError(
            f"未対応の形式です: {fmt!r} (対応: {', '.join(sorted(PARSERS))})"
        )
    prefixes = None
    if len(parts) == 5:
        prefixes = tuple(prefix for prefix in parts[4].split(",") if prefix)
        if not prefixes:
            raise argparse.ArgumentTypeError(f"プレフィクスが空です: {value!r}")
    return SectionSpec(category, label, fmt, Path(path), prefixes)


def main(argv: list[str] | None = None) -> None:
    """コマンドライン引数を解釈し、カタログを標準出力へ書き出す。

    Args:
        argv: コマンドライン引数。None なら sys.argv を使う。
    """
    parser = argparse.ArgumentParser(description="テスト結果からテスト観点カタログを生成する")
    parser.add_argument(
        "--section",
        action="append",
        required=True,
        type=parse_section_arg,
        metavar="CATEGORY:LABEL:FORMAT:PATH[:PREFIXES]",
        help="カテゴリ名・セクション名・形式・結果ファイルのパス・振り分けプレフィクス (複数指定可)",
    )
    parser.add_argument("--format", choices=("markdown", "html"), required=True, help="出力形式")
    parser.add_argument("--title", required=True, help="ページの表題")
    parser.add_argument("--commit", default=None, help="生成元 commit の SHA (省略可)")
    args = parser.parse_args(argv)

    sections = build_sections(args.section)
    renderer = render_markdown if args.format == "markdown" else render_html
    sys.stdout.write(renderer(sections, args.commit, args.title))


if __name__ == "__main__":
    main()
