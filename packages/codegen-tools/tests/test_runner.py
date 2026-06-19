"""CodegenRunner 統合テスト."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from codegen_tools import CodegenRunner, GoStyle, GoTarget


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_runner_single_target(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {
                    "name": "user",
                    "target": "wire",
                    "types": [
                        {
                            "name": "User",
                            "fields": [{"name": "ID", "type": "string", "json": "id"}],
                        }
                    ],
                }
            ]
        },
    )

    out_dir = tmp_path / "out"
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(out_dir, "apifoo", emit_tags=("json",))},
        style=GoStyle(),
    )
    rc = runner.run()
    assert rc == 0
    out_file = out_dir / "user_gen.go"
    assert out_file.exists()
    content = out_file.read_text()
    assert "package apifoo" in content
    assert 'json:"id"' in content


def test_runner_multi_target_via_targets_list(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {
                    "name": "evt",
                    "targets": ["wire", "domain"],
                    "types": [
                        {
                            "name": "E",
                            "fields": [{"name": "ID", "type": "string", "json": "id"}],
                        }
                    ],
                }
            ]
        },
    )

    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={
            "wire": GoTarget(tmp_path / "wire", "apifoo", emit_tags=("json",)),
            "domain": GoTarget(tmp_path / "dom", "domain", emit_tags=("json",)),
        },
    )
    assert runner.run() == 0
    assert (tmp_path / "wire" / "evt_gen.go").exists()
    assert (tmp_path / "dom" / "evt_gen.go").exists()


def test_runner_all_targets_keyword(tmp_path: Path) -> None:
    """account の "both" のように、単一 target で全 target に出すケース."""
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {
                    "name": "u",
                    "target": "both",
                    "types": [
                        {
                            "name": "U",
                            "fields": [
                                {"name": "ID", "type": "string", "json": "id", "db": "id"}
                            ],
                        }
                    ],
                }
            ]
        },
    )

    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={
            "api": GoTarget(tmp_path / "api", "apiu", emit_tags=("json",)),
            "domain": GoTarget(tmp_path / "dom", "domain", emit_tags=("db",)),
        },
        all_targets_keyword="both",
    )
    assert runner.run() == 0
    api_text = (tmp_path / "api" / "u_gen.go").read_text()
    dom_text = (tmp_path / "dom" / "u_gen.go").read_text()
    assert 'json:"id"' in api_text and "db:" not in api_text
    assert 'db:"id"' in dom_text and "json:" not in dom_text


def test_runner_target_and_targets_both_set_is_error(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {
                    "name": "x",
                    "target": "wire",
                    "targets": ["wire"],
                    "types": [],
                }
            ]
        },
    )
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
    )
    with pytest.raises(ValueError, match="both"):
        runner.run()


def test_runner_unknown_target_is_error(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {"files": [{"name": "x", "target": "nope", "types": []}]},
    )
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
    )
    with pytest.raises(ValueError, match="unknown target"):
        runner.run()


def test_runner_no_target_field_is_error(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(yaml_path, {"files": [{"name": "x", "types": []}]})
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
    )
    with pytest.raises(ValueError, match="has no `target`"):
        runner.run()


def test_runner_default_target_when_not_specified(tmp_path: Path) -> None:
    """scenario/card のように target を YAML に持たないリポ向けのデフォルト."""
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {
                    "name": "x",
                    "types": [
                        {
                            "name": "X",
                            "fields": [{"name": "F", "type": "string", "json": "f"}],
                        }
                    ],
                }
            ]
        },
    )
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"default": GoTarget(tmp_path / "out", "p", emit_tags=("json",))},
        default_target_key="default",
    )
    assert runner.run() == 0
    assert (tmp_path / "out" / "x_gen.go").exists()


def test_runner_constants_block(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {
                    "name": "enum",
                    "target": "wire",
                    "constants": [
                        {
                            "type": "string",
                            "values": [{"name": "A", "value": "alpha"}],
                        }
                    ],
                    "types": [],
                }
            ]
        },
    )
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
    )
    runner.style.const_style.should_quote_string_only = True  # shop-style
    assert runner.run() == 0
    text = (tmp_path / "out" / "enum_gen.go").read_text()
    assert 'A = "alpha"' in text


def test_runner_missing_section_name_field_returns_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """section_name_field 欠落時は _generate_one() の KeyError ではなく run() 入口で
    明示メッセージ + return 1 を返す (どの section が壊れているかユーザに伝える)."""
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {"name": "ok", "target": "wire", "types": []},
                {"target": "wire", "types": []},  # name 欠落
            ]
        },
    )
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
    )
    rc = runner.run()
    assert rc == 1
    err = capsys.readouterr().err
    assert "models.yaml" in err
    assert "section #2" in err
    assert "`name`" in err
    # fail-fast: 出力ファイルは 1 件も書かれない
    assert not (tmp_path / "out").exists()


def test_runner_emits_type_aliases_to_output_file(tmp_path: Path) -> None:
    """section の type_aliases が生成 Go ファイルに `type X = Y` として書かれることを固定する.

    emitter 単体テスト (test_go_emitter.test_render_type_aliases) は関数レベルでカバー
    済みだが、models.yaml → runner → 実ファイル の統合パスは未カバーだった。
    """
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {
                    "name": "ids",
                    "target": "wire",
                    "type_aliases": [
                        {"name": "PlayerID", "base": "string"},
                        {"name": "DeckID", "base": "int64"},
                    ],
                    "types": [],
                }
            ]
        },
    )
    out_dir = tmp_path / "out"
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(out_dir, "apifoo")},
    )
    assert runner.run() == 0
    content = (out_dir / "ids_gen.go").read_text()
    assert "type PlayerID = string" in content
    assert "type DeckID = int64" in content


# ─── pre_render_hook ──────────────────────────────────────


def _two_section_yaml(yaml_path: Path) -> None:
    """pre_render_hook テスト用の 2 section fixture を書き出す."""
    _write_yaml(
        yaml_path,
        {
            "files": [
                {"name": "a", "target": "wire", "types": []},
                {"name": "b", "target": "wire", "types": []},
            ]
        },
    )


def test_pre_render_hook_called_once_per_section_target_pair(tmp_path: Path) -> None:
    """hook は (section, target) ごとに 1 回ずつ呼ばれる. multi-target なら同 section に対し複数回."""
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {"name": "x", "targets": ["wire", "domain"], "types": []},
            ]
        },
    )
    calls: list[tuple[str, str]] = []

    def hook(section: dict, target_key: str) -> dict:
        calls.append((section["name"], target_key))
        return section

    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={
            "wire": GoTarget(tmp_path / "out/wire", "w"),
            "domain": GoTarget(tmp_path / "out/domain", "d"),
        },
        pre_render_hook=hook,
    )
    assert runner.run() == 0
    assert calls == [("x", "wire"), ("x", "domain")]


def test_pre_render_hook_mutation_reflected_in_output(tmp_path: Path) -> None:
    """hook 返り値が render パイプラインに反映される: types を注入したら生成 Go に出る."""
    yaml_path = tmp_path / "models.yaml"
    _two_section_yaml(yaml_path)

    def inject_types(section: dict, _target_key: str) -> dict:
        section = dict(section)
        section["types"] = [
            {"name": f"Injected{section['name'].upper()}", "fields": [
                {"name": "ID", "type": "string", "json": "id"},
            ]},
        ]
        return section

    out_dir = tmp_path / "out"
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(out_dir, "p")},
        pre_render_hook=inject_types,
    )
    assert runner.run() == 0
    assert "type InjectedA struct" in (out_dir / "a_gen.go").read_text()
    assert "type InjectedB struct" in (out_dir / "b_gen.go").read_text()


def test_pre_render_hook_returning_none_raises_typed_error(tmp_path: Path) -> None:
    """hook が None を返したら不透明な AttributeError ではなく TypeError + どの section の hook が
    壊れているかを示すメッセージで止める."""
    yaml_path = tmp_path / "models.yaml"
    _two_section_yaml(yaml_path)
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
        pre_render_hook=lambda _section, _target: None,  # type: ignore[return-value, arg-type]
    )
    with pytest.raises(TypeError, match=r"pre_render_hook for section 'a'.*returned NoneType"):
        runner.run()


def test_pre_render_hook_exception_propagates(tmp_path: Path) -> None:
    """hook 内例外は呼び出し側に伝搬する (silent skip しない)."""
    yaml_path = tmp_path / "models.yaml"
    _two_section_yaml(yaml_path)

    class HookError(Exception):
        pass

    def hook(_section: dict, _target_key: str) -> dict:
        raise HookError("boom")

    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
        pre_render_hook=hook,
    )
    with pytest.raises(HookError, match="boom"):
        runner.run()
