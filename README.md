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
packages/                # 9 Go module + 4 NuGet csproj + 8 npm package (ADR-015 Phase 3/4/5)
  game-design-constants/       # Go module
  game-logic-constants/        # Go module
  ws-constants/                # Go module
  shop-constants/              # Go module
  newsfeed-constants/          # Go module
  card-types/                  # Go module
  api-client/                  # Go module
  api-battle-rpc/              # Go module
  devdata/                     # Go module (開発用 JSON 埋め込み)
  game-design-constants-dotnet/  # NuGet csproj
  game-logic-constants-dotnet/   # NuGet csproj
  game-state-dotnet/             # NuGet csproj (cards_gen.json を同梱)
  api-battle-rpc-dotnet/         # NuGet csproj
  game-design-constants-npm/     # npm package
  game-logic-constants-npm/      # npm package
  ws-constants-npm/              # npm package
  shop-constants-npm/            # npm package
  newsfeed-constants-npm/        # npm package
  card-types-npm/                # npm package
  game-state-npm/                # npm package
  api-client-npm/                # npm package
go.work                   # local dev 用 Go workspace (9 Go module を束ねる)
scripts/
  generate_cards.py       # カード生成
  generate_products.py    # 商品生成
  generate_constants.py   # 定数/モデル/型生成 (21 package に振り分け)
  generate_schema_doc.py  # DATA_DESIGN.md 更新
docs/                     # 全ドキュメント
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
| Go module `game-design-constants` | Faction / Zone / CardType / Restriction 等のゲームデザイン定数 | 全 Go サービス + future card / shop |
| Go module `game-logic-constants` | Phase / WinReason / TriggerType / EffectOp 等のバトル状態機械 enum | future battle (現状 gateway も) |
| Go module `ws-constants` | WSServerMsg / WSClientMsg 種別 | future gateway |
| Go module `shop-constants` | ProductType 等 | future shop |
| Go module `newsfeed-constants` | CloudNewsSource 等 | future newsfeed |
| Go module `card-types` | CardDefinition / CardStats / PassiveEffect / NpcModel | gateway / future card |
| Go module `api-client` | client ↔ gateway REST + WS 契約 | future gateway |
| Go module `api-battle-rpc` | gateway ↔ battle 内部 RPC 契約 | future battle |
| Go module `devdata` | カード・商品 JSON（ローカルモック用） | Go サービス 開発用 |
| NuGet `OverloadParty.GameDesignConstants` (`packages/game-design-constants-dotnet/`) | Faction / Zone / CardType / Restriction / DeckSize 等のゲームデザイン定数 | battle |
| NuGet `OverloadParty.GameLogicConstants` (`packages/game-logic-constants-dotnet/`) | Phase / WinReason / TriggerType / EffectOp 等のゲームロジック enum | battle |
| NuGet `OverloadParty.GameState` (`packages/game-state-dotnet/`) | ClientGameState / PlayerView / Field / EventData / VariantTypes + cards_gen.json を EmbeddedResource で同梱 | battle |
| NuGet `OverloadParty.ApiBattleRpc` (`packages/api-battle-rpc-dotnet/`) | gateway ↔ battle 内部 RPC 契約 (NpcBattleRequest / ActionEvent / ActionResult 等) | battle |
| npm `@kenyamaneko/overload-party-game-design-constants` (`packages/game-design-constants-npm/`) | Faction / Zone / CardType / Restriction / DeckSize 等のゲームデザイン定数 (Layer 1) | client |
| npm `@kenyamaneko/overload-party-game-logic-constants` (`packages/game-logic-constants-npm/`) | Phase / WinReason / TriggerType / EffectOp 等のゲームロジック enum (Layer 1) | client |
| npm `@kenyamaneko/overload-party-ws-constants` (`packages/ws-constants-npm/`) | WSServerMsg / WSClientMsg 種別 (Layer 1) | client |
| npm `@kenyamaneko/overload-party-shop-constants` (`packages/shop-constants-npm/`) | ProductType 等 (Layer 1) | client |
| npm `@kenyamaneko/overload-party-newsfeed-constants` (`packages/newsfeed-constants-npm/`) | CloudNewsSource 等 (Layer 1) | client |
| npm `@kenyamaneko/overload-party-card-types` (`packages/card-types-npm/`) | CardDefinition / CardStats / PassiveEffect / NpcModel (Layer 2) | client |
| npm `@kenyamaneko/overload-party-game-state` (`packages/game-state-npm/`) | ClientGameState / PlayerView / Field / EventData / AvailableAction (Layer 2) | client |
| npm `@kenyamaneko/overload-party-api-client` (`packages/api-client-npm/`) | client ↔ gateway REST + WS + Deck 型 (Layer 3) | client |

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
   - Go サービス: 必要な module を個別に `go get` (例: `go get github.com/kenyamaneko/overload-party-common/packages/game-design-constants@latest` など 9 module から選択)
   - battle: `dotnet restore`
   - client: 必要な npm package を個別に install (`npm install @kenyamaneko/overload-party-game-design-constants` など 8 package から選択)
