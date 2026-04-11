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
| Go module (`packages/gamedata/`) | model, constants サブパッケージ (game_design / game_logic / ws / shop / newsfeed) | Go サービス各種（gateway / account / matchmaking / shop / scenario / card） |
| Go module (`packages/api/`) | REST / WS / battle-gateway RPC 契約モデル | Go サービス各種 |
| Go module (`packages/devdata/`) | カード・商品 JSON（ローカルモック用） | Go サービス 開発用 |
| NuGet `OverloadParty.GameData` (`packages/gamedata-dotnet/`) | GameDesign / GameLogic / Ws / Shop / Newsfeed namespace + EventData + GameStateView + VariantTypes + BattleGatewayRpc | battle |
| npm `@kenyamaneko/overload-party-gamedata` (`packages/gamedata-npm/`) | game-design / game-logic / ws / shop / newsfeed / eventData / variantTypes / models サブエントリポイント | client |
| npm `@kenyamaneko/overload-party-api` (`packages/api-npm/`) | REST / WS メッセージモデル | client |

### 実行方法

```bash
python3 scripts/generate_cards.py       # カードデータ
python3 scripts/generate_products.py    # 商品データ
python3 scripts/generate_constants.py   # 定数・モデル・イベントスキーマ
python3 scripts/generate_schema_doc.py  # DATA_DESIGN.md のスキーマドキュメント
```

main への push 時に CI (`publish.yaml`) が自動で publish します。

### 前提条件

- Python 3.8+
- `pip install pyyaml`

## 定数を変更するとき

1. 対象の yaml を編集:
   - ゲームデザイン: `data/game_design_constants.yaml`
   - ゲームロジック: `data/game_logic_constants.yaml`
   - WS メッセージタイプ: `data/gateway_ws_constants.yaml`
   - ショップ: `data/shop_constants.yaml`
   - ニュースフィード: `data/newsfeed_constants.yaml`
   - ファクション: `data/factions.yaml`
2. `python3 scripts/generate_constants.py` を実行
3. main に push → CI が自動でパッケージ publish
4. 各リポでパッケージを更新:
   - Go サービス（gateway / account / matchmaking / shop / scenario / card）: `go get github.com/kenyamaneko/overload-party-common/packages/gamedata@latest`
   - battle: `dotnet restore`
   - client: `npm install`
