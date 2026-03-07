# overload-party-common

Overload Party の **共有データ・定義** を管理するリポジトリ。

server / client リポジトリから **シンボリックリンク** または **コード生成** で参照されます。

## 構成

```
data/
  cards/          # カード定義 YAML (Single Source of Truth)
  constants.json  # ゲーム共通定数 (Phase, Zone, Rank, 初期値 等)
db/
  schema_postgres.sql   # PostgreSQL DDL (Single Source of Truth)
  grant_iam.sql         # IAM 認証用権限付与 (psqldef 対象外、手動実行)
  seed/                 # 初期データ (dev/stg 環境向け)
docs/             # 全ドキュメント
scripts/
  generate_from_yaml.py   # コード生成スクリプト
```

## DB スキーマ管理

`db/schema_postgres.sql` が全テーブルの Single Source of Truth。

```bash
# スキーマ適用（psqldef 使用）
psqldef -U postgres overload_party < db/schema_postgres.sql

# IAM 権限付与（スキーマ適用後に手動実行）
psql -U postgres overload_party < db/grant_iam.sql

# シードデータ投入（dev/stg のみ）
psql -U postgres overload_party < db/seed/game_config.sql
psql -U postgres overload_party < db/seed/products.sql
psql -U postgres overload_party < db/seed/stamps.sql
```

## コード生成

`generate_from_yaml.py` は以下のファイルを生成します：

| 入力 | 出力 | 出力先 |
|------|------|--------|
| `data/cards/*.yaml` | `docs/CARDS.md` | common |
| `data/cards/*.yaml` | `internal/cache/cards_gen.json` | gateway |
| `data/cards/*.yaml` | `internal/cardno/cardno_gen.go` | gateway |
| `data/constants.json` | `internal/constants/constants_gen.go` | gateway |
| `data/constants.json` | `src/generated/constants.ts` | client |

### 実行方法

```bash
# 直接実行
python3 scripts/generate_from_yaml.py \
  --gateway-dir /path/to/overload-party-gateway \
  --client-dir /path/to/overload-party-client
```

### 前提条件

- Python 3.8+
- `pip install pyyaml`

## セットアップ

各リポジトリから common を参照するためのシンボリックリンクを作成：

```bash
# gateway
cd overload-party-gateway
ln -s /path/to/overload-party-common/data  data
ln -s /path/to/overload-party-common/docs  docs

# client は symlink 不要（generate で直接出力）
```

## 定数を変更するとき

1. `data/constants.json` を編集
2. `python3 scripts/generate_from_yaml.py --gateway-dir ...` を実行
3. 生成された `constants_gen.go` と `constants.ts` をそれぞれコミット
