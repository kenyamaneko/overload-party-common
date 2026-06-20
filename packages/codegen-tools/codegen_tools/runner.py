"""高レベル Codegen 実行ランナー.

`CodegenRunner` は YAML ロード → セクション毎の target 解決 → ファイル書き出しまでを
一括で扱う標準パイプライン。account / shop / support / scenario / card のような
「単一 YAML から 1〜複数 target に Go ファイルを出す」ユースケースを想定。

matchmaking のような独自スキーマのリポは、`render_go_file` 等を直接呼ぶ
低レベルパスを使う想定 (このランナーには載せない)。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .go_emitter import GoStyle, render_go_file
from .yaml_loader import load_yaml


@dataclass
class GoTarget:
    """1 つの Go 出力先 (ディレクトリ + パッケージ名 + 付与タグ集合)."""

    out_dir: Path
    package: str
    emit_tags: tuple[str, ...] = ("json",)


@dataclass
class CodegenRunner:
    """標準ケース向け codegen パイプライン."""

    models_yaml: Path
    repo_root: Path
    targets: dict[str, GoTarget]
    style: GoStyle = field(default_factory=GoStyle)

    # ── target 解決 ──
    single_target_field: str | None = "target"
    """セクションで単一 target を指定するキー名. None で無効."""
    multi_target_field: str | None = "targets"
    """セクションで複数 target をリスト指定するキー名. None で無効."""
    all_targets_keyword: str | None = None
    """単一 target で全 target に出力する予約語 (例: account の "both"). None で無効."""
    default_target_key: str | None = None
    """セクションが target を持たない場合のデフォルト. 全リポで target を必ず指定するなら None."""

    # ── 出力パス ──
    section_name_field: str = "name"
    """セクションのファイル名解決に使うキー (`{name}_gen.go`)."""
    file_suffix: str = "_gen.go"

    # ── ファイル末尾 ──
    has_trailing_blank_line: bool = False
    """末尾に空行を残すか. 既存スクリプトに合わせて互換用."""

    # ── プラグイン ──
    pre_render_hook: Callable[[dict[str, Any], str], dict[str, Any]] | None = None
    """セクション dict と target_key を受け取り、セクションを書き換えて返すフック."""

    def _resolve_targets(self, section: dict[str, Any]) -> list[str]:
        """セクションの target/targets 指定を target キー名のリストに正規化する."""
        section_name = section.get(self.section_name_field, "<unnamed>")

        has_single = self.single_target_field is not None and self.single_target_field in section
        has_multi = self.multi_target_field is not None and self.multi_target_field in section

        if has_single and has_multi:
            raise ValueError(
                f"section {section_name!r} sets both "
                f"`{self.single_target_field}` and `{self.multi_target_field}`"
            )

        if has_multi:
            ts = section[self.multi_target_field]  # type: ignore[index]
            if not isinstance(ts, list) or not ts:
                raise ValueError(
                    f"section {section_name!r} `{self.multi_target_field}` "
                    "must be a non-empty list"
                )
            target_keys = list(ts)
        elif has_single:
            value = section[self.single_target_field]
            if self.all_targets_keyword is not None and value == self.all_targets_keyword:
                target_keys = list(self.targets.keys())
            else:
                target_keys = [value]
        elif self.default_target_key is not None:
            target_keys = [self.default_target_key]
        else:
            field_name = self.single_target_field or self.multi_target_field or "target"
            raise ValueError(
                f"section {section_name!r} has no `{field_name}` "
                f"(and no default_target_key configured)"
            )

        for tk in target_keys:
            if tk not in self.targets:
                raise ValueError(
                    f"section {section_name!r}: unknown target {tk!r} "
                    f"(known: {sorted(self.targets)})"
                )
        return target_keys

    def _generate_one(self, section: dict[str, Any], target_key: str) -> Path:
        target = self.targets[target_key]

        if self.pre_render_hook is not None:
            section_name = section.get(self.section_name_field, "<unnamed>")
            section = self.pre_render_hook(section, target_key)
            # None / 非 dict 返却は呼び出し側の bug。section.get() で AttributeError に
            # して読み手を混乱させず、原因が hook であることを明示する。
            if not isinstance(section, dict):
                raise TypeError(
                    f"pre_render_hook for section {section_name!r} "
                    f"(target {target_key!r}) returned {type(section).__name__}, "
                    "expected dict"
                )

        extra_imports = set(section.get("imports", []))
        constants = section.get("constants") or []
        type_aliases = section.get("type_aliases") or []
        types = section.get("types", [])

        body = render_go_file(
            package=target.package,
            types=types,
            style=self.style,
            constants=constants,
            type_aliases=type_aliases,
            extra_imports=extra_imports,
            emit_tags=target.emit_tags,
            has_trailing_blank_line=self.has_trailing_blank_line,
        )

        out_path = target.out_dir / f"{section[self.section_name_field]}{self.file_suffix}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
        return out_path

    def run(self) -> int:
        """models.yaml を読み、全セクションを target 別に出力する."""
        data = load_yaml(self.models_yaml)
        sections = data.get("files")
        if not sections:
            sys.stderr.write(
                f"error: {self.models_yaml.name} has no `files:` section\n"
            )
            return 1

        # 全 section をループ前にバリデーションして fail-fast。section_name_field
        # 欠落だと _generate_one() の出力パス組み立てで KeyError になり、どの section
        # が原因か追えないため事前に明示エラーで止める。
        for i, section in enumerate(sections):
            if self.section_name_field not in section:
                sys.stderr.write(
                    f"error: {self.models_yaml.name} section #{i + 1} missing "
                    f"required `{self.section_name_field}` field\n"
                )
                return 1

        for section in sections:
            for tk in self._resolve_targets(section):
                out = self._generate_one(section, tk)
                try:
                    rel = out.relative_to(self.repo_root)
                except ValueError:
                    rel = out
                print(f"wrote {rel}")
        return 0
