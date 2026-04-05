# ローカルシードデータの devdata パッケージ移行

## ステータス: common・gateway 対応済み

## 背景

`cmd/local/main.go` にハードコードされていたローカルモード用データを、common の devdata パッケージ（YAML → JSON 生成）に移行した。

## 完了した対応

### common

| YAML ソース | codegen スクリプト | 生成物 |
|---|---|---|
| `data/mock/starter_decks.yaml` | `generate_cards.py` | `devdata/cache/starter_decks_gen.json` |
| `data/mock/news.yaml` | `generate_news_mock.py` | `devdata/cache/news.json` |
| `data/mock/products.yaml` | `generate_products.py` | `devdata/cache/products_gen.json` |

- スターターデッキはカード ID バリデーション付き（`generate_cards.py` 内で `data/cards/*.yaml` と照合）
- ニュースモックは source バリデーション付き

### gateway

- `cmd/local/main.go` の3種のハードコードを devdata の embedded JSON 読み込みに置換済み
- ビルド・テスト通過済み

## gateway 側の残作業

### devdata パッケージの正式更新

現在 vendor は手動パッチ済み。devdata の新バージョンが publish されたら正式に同期する:

```
go get github.com/kenyamaneko/overload-party-common/packages/devdata@latest
go mod vendor
```

### ニュースモックの拡張時

`data/mock/news.yaml` のスキーマを拡張した場合（summary、published_at 等を追加）、
gateway 側の `model.NewsArticle` は既にこれらのフィールドを持っているので、
YAML に値を追加すれば JSON → Unmarshal でそのまま反映される。
`fetched_at` のみ gateway がリクエスト時に `time.Now()` で埋める設計。

### スターターデッキの変更時

`data/mock/starter_decks.yaml` を編集後、`python3 scripts/generate_cards.py` を実行すれば
カード ID の存在チェックが走り、`starter_decks_gen.json` が再生成される。
gateway 側のコード変更は不要（JSON 構造が変わらない限り）。
