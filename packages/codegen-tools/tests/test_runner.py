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
    runner.style.const_style.quote_string_only = True  # shop-style
    assert runner.run() == 0
    text = (tmp_path / "out" / "enum_gen.go").read_text()
    assert 'A = "alpha"' in text


def test_runner_missing_section_name_is_error(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(yaml_path, {"files": [{"target": "wire", "types": []}]})
    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
    )
    with pytest.raises(ValueError, match="has no `name`"):
        runner.run()


def test_runner_type_aliases_block(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {
                    "name": "ids",
                    "target": "wire",
                    "type_aliases": [{"name": "ID", "base": "string"}],
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
    assert runner.run() == 0
    text = (tmp_path / "out" / "ids_gen.go").read_text()
    assert "type ID = string" in text


def test_runner_pre_render_hook_called_for_each_section(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(
        yaml_path,
        {
            "files": [
                {"name": "a", "target": "wire", "types": []},
                {"name": "b", "target": "wire", "types": []},
            ]
        },
    )
    seen: list[str] = []

    def hook(section: dict, target_key: str) -> dict:
        seen.append(section["name"])
        return section

    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
        pre_render_hook=hook,
    )
    assert runner.run() == 0
    assert seen == ["a", "b"]


def test_runner_pre_render_hook_return_value_is_rendered(tmp_path: Path) -> None:
    """フックの返り値 (元セクションではなく) が render パイプラインに渡る."""
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(yaml_path, {"files": [{"name": "x", "target": "wire", "types": []}]})

    def hook(section: dict, target_key: str) -> dict:
        return {**section, "type_aliases": [{"name": "Injected", "base": "int64"}]}

    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
        pre_render_hook=hook,
    )
    assert runner.run() == 0
    text = (tmp_path / "out" / "x_gen.go").read_text()
    assert "type Injected = int64" in text


def test_runner_pre_render_hook_exception_propagates(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(yaml_path, {"files": [{"name": "x", "target": "wire", "types": []}]})

    def hook(section: dict, target_key: str) -> dict:
        raise RuntimeError("hook boom")

    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
        pre_render_hook=hook,
    )
    with pytest.raises(RuntimeError, match="hook boom"):
        runner.run()


def test_runner_pre_render_hook_non_dict_return_is_error(tmp_path: Path) -> None:
    yaml_path = tmp_path / "models.yaml"
    _write_yaml(yaml_path, {"files": [{"name": "x", "target": "wire", "types": []}]})

    def hook(section: dict, target_key: str):
        return None

    runner = CodegenRunner(
        models_yaml=yaml_path,
        repo_root=tmp_path,
        targets={"wire": GoTarget(tmp_path / "out", "p")},
        pre_render_hook=hook,
    )
    with pytest.raises(ValueError, match="must return a dict"):
        runner.run()
