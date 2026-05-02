# CLAUDE.md - overload-party-common

## 行動制約

- 不具合解消時はワークアラウンドではなく根本解決する。難しい場合はユーザーに相談
- コード修正時はドキュメント更新の必要性を検討する
- ドキュメント修正時はテストコードの作成・更新の必要性を検討する
- コメントは意図（なぜそうしたか）が読み取りづらい場合のみ記述する
- エラーは握りつぶさない
- git tag を手動で打たない（CI が自動作成する）
- `data/game_design_constants.yaml` または `data/factions.yaml` を変更したら `python3 scripts/generate_constants.py` を実行する
- `db/schema_postgres.sql` を変更したら `python3 scripts/generate_schema_doc.py` を実行する
- `packages/doc-tools/` を変更したら `cd packages/doc-tools && pip install -e . && python -m pytest tests/ -v` でテストを実行する
