# CLAUDE.md - overload-party-common (overload-party 開発拠点)

このリポは overload-party 配下の全リポを横断する開発拠点である。primary 作業ディレクトリは
本リポ、編集対象の他リポは additional working directory として参照する。

@rules/principles.md

## ファイル編集前のルール適用手順

ファイル編集 (Edit / Write) の前に必ず以下を実行する:

1. 編集対象ファイルのパスから対象リポを判定する
   - パスが `./` 起点または `rules/`, `data/`, `db/`, `packages/`, `scripts/`, `docs/` 配下 → `overload-party-common`
   - `../overload-party-<name>/` パターン → 該当リポ
2. [rules/repos.yaml](rules/repos.yaml) で対象リポの `lang` / `flow` を引く
3. 以下のルールを Read して以降の判断に適用する:
   - lang: `rules/lang/<lang>.md` (`lang: none` ならスキップ)
   - flow: `rules/flow/<flow>.md` (`flow: none` ならスキップ)
4. リポ固有のルールが必要な場合は対象リポの `docs/` 配下を Read する

`rules/principles.md` は本ファイルから @import 済みなので全リポに共通適用される。

## [common] SSoT と生成コード

- `data/game_design_constants.yaml` または `data/factions.yaml` を変更したら `python3 scripts/generate_constants.py` を実行する
- `db/schema_postgres.sql` を変更したら `python3 scripts/generate_schema_doc.py` を実行する
- `packages/doc-tools/` を変更したら `cd packages/doc-tools && pip install -e . && python -m pytest tests/ -v` でテストを実行する
