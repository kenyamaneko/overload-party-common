# overload-party-common

Overload Party の **共有データ・定義** を管理するリポジトリ。

各リポジトリは **パッケージ** としてインストールして参照します。

## 構成

```
data/
  cards/          # カード定義 YAML (Single Source of Truth)
  constants.json  # ゲーム共通定数 (Phase, Zone, Rank, 初期値 等)
  event_schemas.json  # イベントデータスキーマ
  models.yaml     # Go モデル定義
db/
  schema_postgres.sql   # PostgreSQL DDL (Single Source of Truth)
  grant_iam.sql         # IAM 認証用権限付与 (psqldef 対象外、手動実行)
  seed/                 # 初期データ (dev/stg 環境向け)
packages/
  generate_from_yaml.py  # コード生成スクリプト
  go/             # Go パッケージ (gateway 用)
  dotnet/         # NuGet パッケージ (battle 用)
  npm/            # npm パッケージ (client 用)
docs/             # 全ドキュメント
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

`generate_from_yaml.py` は以下のパッケージを `packages/` 以下に生成します：

| パッケージ | 内容 | 利用リポ |
|-----------|------|---------|
| Go module (`packages/go/`) | model, constants, cardno, cards_gen.json (embed) | gateway |
| NuGet `OverloadParty.Generated` (`packages/dotnet/`) | GameConstants, EventData, cards_gen.json | battle |
| npm `@overload-party/generated` (`packages/npm/`) | constants.ts, eventData.ts | client |

### 実行方法

```bash
# パッケージモード（推奨）
python3 packages/generate_from_yaml.py --gen-dir packages/
```

main への push 時に CI (`publish-packages.yaml`) が自動で生成・publish します。

### 前提条件

- Python 3.8+
- `pip install pyyaml`

## 定数を変更するとき

1. `data/constants.json` を編集
2. `python3 packages/generate_from_yaml.py --gen-dir packages/` を実行
3. main に push → CI が自動でパッケージ publish
4. 各リポでパッケージを更新:
   - gateway: `go get github.com/kenyamaneko/overload-party-common/packages/go@latest`
   - battle: `dotnet restore`
   - client: `npm install`
