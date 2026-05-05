# CLAUDE.md - overload-party-common

@presets/claude/base/CLAUDE.md
@presets/claude/flow/githubflow/CLAUDE.md
@presets/claude/lang/python/CLAUDE.md

## [common] SSoT と生成コード

- `data/game_design_constants.yaml` または `data/factions.yaml` を変更したら `python3 scripts/generate_constants.py` を実行する
- `db/schema_postgres.sql` を変更したら `python3 scripts/generate_schema_doc.py` を実行する
- `packages/doc-tools/` を変更したら `cd packages/doc-tools && pip install -e . && python -m pytest tests/ -v` でテストを実行する
