# overload-party-common

Overload Party の **横断的な共有リソース** を管理するリポジトリ。

所有するもの:

- **ゲームデザイン定数** (faction / card_type / restriction / zone 等。全リポ共通)
- **アーキテクチャ / ゲームデザイン / ビジネスドキュメント**

> 旧 `shared` スキーマ DDL は Cloud Firestore へ移管予定。`db/schema_postgres.sql` および `db/seed/game_config.sql` は移管完了後に削除する。

## 構成

```
data/
  game_design_constants.yaml  # ゲームデザイン定数 SSoT
  factions.yaml               # ファクションマスター SSoT
db/
  schema_postgres.sql         # shared スキーマ DDL のみ
  grant_iam.sql               # IAM 認証用権限付与 (ops リポから実行)
packages/
  game-design-constants/          # Go module
  game-design-constants-dotnet/   # NuGet csproj
  game-design-constants-npm/      # npm package
scripts/
  generate_constants.py           # game-design constants 生成 (Go + C# + npm)
  generate_schema_doc.py          # DATA_DESIGN.md のカラム表生成
  ci/detect-changes.sh            # CI publish 対象検知
docs/
  architecture/                   # システム設計 (ARCHITECTURE, CI_CD, DATA_DESIGN, I18N)
  game_design/                    # ゲームデザイン (ルール, カード, UI 等)
  business/                       # ビジネス・法務
  adr/                            # ADR (gitignore、手元専用)
```

## パッケージ

| パッケージ | 形式 | 利用リポ |
|-----------|------|---------|
| `packages/game-design-constants` | Go module | 全 Go サービス |
| `packages/game-design-constants-dotnet` (`OverloadParty.GameDesignConstants`) | NuGet | battle |
| `packages/game-design-constants-npm` (`@kenyamaneko/overload-party-game-design-constants`) | npm | client |

## コード生成

```bash
python3 scripts/generate_constants.py   # game-design constants を Go/C#/npm に生成
python3 scripts/generate_schema_doc.py  # DATA_DESIGN.md のカラム表を更新
```

main への push 時に CI (`.github/workflows/publish.yaml`) が自動で publish する。

### 前提条件

- Python 3.8+
- `pip install pyyaml`

## 定数を変更するとき

1. `data/game_design_constants.yaml` もしくは `data/factions.yaml` を編集
2. `python3 scripts/generate_constants.py` を実行
3. main に push → CI が自動で patch bump で publish
4. 各リポでパッケージを更新:
   - Go サービス: `go get github.com/kenyamaneko/overload-party-common/packages/game-design-constants@latest`
   - battle: `dotnet add package OverloadParty.GameDesignConstants`
   - client: `npm install @kenyamaneko/overload-party-game-design-constants@latest`

## DB スキーマ管理

common は現状 `shared` スキーマ（`shared.game_config` + `shared.update_updated_at()`）のみ所有するが、`shared.game_config` は Cloud Firestore へ移管予定。`update_updated_at()` は各サービススキーマ内に再定義し、`shared` スキーマごと廃止する。移管完了後、本セクションは削除する。

```bash
psqldef -U postgres overload_party < db/schema_postgres.sql
psql -U postgres overload_party < db/grant_iam.sql
```

per-service スキーマは以下を参照:
- `overload-party-account/db/schema.sql` (account)
- `overload-party-card/db/schema.sql` (card)
- `overload-party-shop/db/schema.sql` (shop)
- `overload-party-scenario/db/schema.sql` (scenario)
- `overload-party-battle/db/schema.sql` (battle)
- `overload-party-newsfeed/db/schema.sql` (newsfeed)
