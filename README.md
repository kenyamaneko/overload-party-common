# overload-party-common

Overload Party の **共有データ・定義** を管理するリポジトリ。

server / client リポジトリから **シンボリックリンク** または **コード生成** で参照されます。

## 構成

```
data/
  cards/          # カード定義 YAML (Single Source of Truth)
  cards.json      # 生成: カードの JSON データ (126 枚)
  constants.json  # ゲーム共通定数 (Phase, Zone, Rank, 初期値 等)
docs/             # 全ドキュメント
scripts/
  generate_from_yaml.py   # コード生成スクリプト
```

## コード生成

`generate_from_yaml.py` は以下のファイルを生成します：

| 入力 | 出力 | 出力先 |
|------|------|--------|
| `data/cards/*.yaml` | `data/cards.json` | common |
| `data/cards/*.yaml` | `docs/CARDS.md` | common |
| `data/cards/*.yaml` | `internal/cardno/cardno_gen.go` | server |
| `data/constants.json` | `internal/model/constants_gen.go` | server |
| `data/constants.json` | `src/generated/constants.ts` | client |

### 実行方法

```bash
# server の Makefile 経由（推奨）
cd overload-party-server
make generate

# 直接実行
python3 scripts/generate_from_yaml.py \
  --server-dir /path/to/overload-party-server \
  --client-dir /path/to/overload-party-client
```

### 前提条件

- Python 3.8+
- `pip install pyyaml`

## セットアップ

各リポジトリから common を参照するためのシンボリックリンクを作成：

```bash
# server
cd overload-party-server
ln -s /path/to/overload-party-common/data  data
ln -s /path/to/overload-party-common/docs  docs

# client は symlink 不要（generate で直接出力）
```

## 定数を変更するとき

1. `data/constants.json` を編集
2. `make generate` を実行（server 側）
3. 生成された `constants_gen.go` と `constants.ts` をそれぞれコミット
