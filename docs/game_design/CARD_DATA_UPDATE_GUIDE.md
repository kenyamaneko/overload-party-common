# カードデータ更新ガイド

カードのパラメーター変更からゲームへの反映までの手順書。

---

## 全体の流れ

```
① YAML ファイルを編集（カードの数値や効果を変更）
② コード生成コマンドを実行（自動で各種ファイルが更新される）
③ 動作確認（CARDS.md で変更内容を目視チェック）
④ Git で push → PR を作成
⑤ パッケージを配信（手動トリガー）
⑥ 各リポジトリでパッケージを更新 → ビルド・テスト確認
⑦ レビュー → マージ
```

② のコマンドを実行すれば、あとはサーバーやクライアントのコードを直接触る必要はない。
⑤ の配信は手動トリガーで、feature ブランチからでも実行できる。

---

## ① カードデータを編集する

### 編集するファイル

カードデータは陣営ごとに YAML ファイルで管理されている。

| ファイル | 陣営 |
|----------|------|
| `data/cards/sd.yaml` | SHE（Smile Horizon Express） |
| `data/cards/tenki.yaml` | 天気使い |
| `data/cards/sugar.yaml` | しゅがーらぼ |
| `data/cards/tuners.yaml` | 調律部（チューナーズ） |
| `data/cards/neutral.yaml` | Neutral |

### カード1枚のデータ構造

```yaml
- card_no: 1                    # カード番号（全カードで一意、変更しない）
  card_id: "SH-0001"            # カード識別子（ファクション接頭辞 + 連番、変更しない）
  card_name: "えくぼ"            # カード名
  resource_label: "Compute"     # 画面に表示するリソース種別ラベル
  const_name: SHEComputeEkubo   # プログラム内部の識別子（変更しない）
  card_type: Compute            # カード種別（後述の一覧から選択）
  deploy_turns: 1               # デプロイに必要なターン数（0/1/2）
  resizable: true               # 手動スケール（Resizable）の可否
  elastic: false                # 自動スケール（Elastic）の可否
  origin: "EC2"                 # 元ネタのクラウドサービス名（画面には表示されない）
  restriction: unlimited        # デッキ投入制限
  is_active: true               # ゲームに登場するか（false で無効化）
  stats:                        # ステータス値
    throughput: 700             #   スループット（Compute系のみ）
    availability: 1400          #   アベイラビリティ
    sla_penalty: 400            #   SLA ペナルティ
    maintenance_cost: 150       #   維持コスト
  effect_text: "—"              # 効果テキスト（なければ "—"）
```

### よくある変更パターン

#### ステータスの数値を変更する

`stats:` 以下の数値を書き換える。

```yaml
stats:
  throughput: 700       # ← 例: 800 に変更
  availability: 1400
  sla_penalty: 400
  maintenance_cost: 150
```

- Compute 系カード: `throughput`, `availability`, `sla_penalty`, `maintenance_cost`
- Data 系カード: `yield`, `availability`, `sla_penalty`, `maintenance_cost`

#### デプロイターン数を変更する

```yaml
deploy_turns: 1   # 0 = 即座にデプロイ / 1 = 1ターン / 2 = 2ターン
```

#### Elastic（自動スケール）のパラメーターを変更する

```yaml
elastic: true
elastic_increment: 100     # 1リクエストあたりのスケール増加量
free_tier: 500             # 無料枠（この値まではコストなし）
cost_per_request: 10       # 1リクエストあたりのコスト
```

#### 効果テキストを変更する

```yaml
effect_text: "**えりり Trigger:** 自分のフィールドに「SHE Storage - えりり」がいる場合、このカードのスループットを +200 する"
```

テキスト内で `**太字**` が使える（Markdown 記法）。

#### カードの制限を変更する

```yaml
restriction: unlimited      # デッキに何枚でも入れられる
restriction: limited        # デッキに1枚まで
restriction: semi_limited   # デッキに2枚まで
restriction: forbidden      # 使用禁止
```

#### カードを無効化する

```yaml
is_active: false   # ゲームから除外される（データは残る）
```

### ゲーム定数を変更する

デッキサイズは `data/constants.yaml` で管理されている。

```yaml
initial_values:
  deck_size: 30          # デッキ枚数
```

> **Note:** その他のゲーム定数（budget, hand_limit, time_bank 等）は `game_config` データベーステーブルで管理されており、コードデプロイなしに更新できる。詳細は `db/seed/game_config.sql` を参照。

ゲーム定数を変更した場合は、カード生成ではなく定数生成コマンドを実行する（② を参照）。

### カード種別の一覧

| グループ | カード種別 |
|----------|-----------|
| Compute 系 | `Compute`, `Container`, `Orchestrator`, `Serverless`, `AI/ML` |
| Data 系 | `Database`, `ObjectStorage`, `CacheDB` |
| Support 系 | `Platform`, `Attachment`, `Strategy`, `Reactive`, `Incident` |
| Log 系 | `Log` |

---

## ② コード生成コマンドを実行する

### 前提条件

- Python 3 がインストールされていること
- `pyyaml` ライブラリがインストールされていること（未導入なら `pip install pyyaml`）

### コマンド

プロジェクトのルートディレクトリで、変更した内容に応じて以下を実行する:

**カードデータ（`data/cards/*.yaml`）を変更した場合:**

```bash
python3 scripts/generate_cards.py
```

**ゲーム定数・イベントスキーマ・モデル定義（`data/constants.yaml`, `data/event_schemas.yaml`, `data/models.yaml`）を変更した場合:**

```bash
python3 scripts/generate_constants.py
```

### 何が起こるか

**これらの生成ファイルは直接編集してはいけない。**

#### generate_cards.py の生成物

| 生成ファイル | 用途 |
|-------------|------|
| `docs/game_design/CARDS.md` | カード一覧ドキュメント（目視確認用） |
| `packages/devdata/cache/cards_gen.json` | Gateway サーバー用カードデータ（ローカル開発用） |
| `packages/dotnet/cache/cards_gen.json` | Battle サーバー用カードデータ（ローカル開発用） |
| `db/seed/cards_seed.sql` | PostgreSQL カード定義 seed（UPSERT） |

#### generate_products.py の生成物

| 生成ファイル | 用途 |
|-------------|------|
| `packages/devdata/cache/products_gen.json` | Gateway サーバー用商品データ（ローカル開発用） |
| `db/seed/products.sql` | PostgreSQL 商品定義 seed（UPSERT） |

#### generate_constants.py の生成物

| 生成ファイル | 用途 |
|-------------|------|
| `packages/gamedata/constants/constants_gen.go` | Gateway サーバー用定数 |
| `packages/gamedata/model/*_gen.go` | Gateway サーバー用 Go 型定義 |
| `packages/dotnet/GameConstants_gen.cs` | Battle サーバー用定数 |
| `packages/dotnet/EventData_gen.cs` | Battle サーバー用イベント型 |
| `packages/npm/src/constants.ts` | クライアント用定数 |
| `packages/npm/src/eventData.ts` | クライアント用イベント型 |
| `packages/npm/src/wsMessages.ts` | クライアント用 WS メッセージ型 |

---

## ③ 変更内容を確認する

`docs/game_design/CARDS.md` を開いて、変更が正しく反映されているか目視で確認する。
このファイルにはすべてのカードのステータスが一覧で表示される。

---

## ④ PR を作成する

1. 変更を Git にコミットして push する
2. Pull Request（PR）を作成する
3. PR を作成すると **Codegen Sync Check** という自動チェックが走る
   - YAML のバリデーション（必須フィールド、値の範囲、型チェック等）
   - YAML の変更と生成ファイルの整合性を検証する
   - ② のコマンドを実行し忘れていた場合、ここでエラーになる
   - エラーが出たら ② を実行してコミットし直せば OK

---

## ⑤ パッケージを配信する（手動トリガー）

PR の自動チェックが通ったら、パッケージを配信する。
**この配信は自動ではなく、手動で実行する。** feature ブランチからでも実行できる。

### 実行方法

**Slack から（推奨）:**

```
/publish-gamedata-pkg <ブランチ名>
```

ブランチ名を省略すると main ブランチから実行される。

**GitHub CLI から:**

```bash
gh workflow run "Publish GameData Packages" --ref <ブランチ名>
```

**GitHub Web UI から:** Actions → Publish GameData Packages → Run workflow → ブランチを選択 → Run

### 配信されるパッケージ

| パッケージ | 参照元 |
|-----------|--------|
| Go モジュール（`packages/gamedata/vX.Y.Z` タグ） | Gateway サーバー |
| NuGet `OverloadParty.GameData` | Battle サーバー |
| npm `@overload-party/generated` | クライアント |

---

## ⑥ 各リポジトリでビルド・テスト確認

パッケージが公開されたら、各リポジトリで最新バージョンに更新してビルドとテストを確認する:

```bash
# Gateway（Go）
go get github.com/kenyamaneko/overload-party-common/packages/gamedata@latest

# Battle（.NET） - NuGet の最新バージョンを指定
dotnet add package OverloadParty.GameData

# Client（npm）
npm install @overload-party/generated@latest
```

---

## ⑦ レビュー → マージ

ビルド・テストが通ることを確認できたら、PR のレビューを受けてマージする。

---

## 注意事項

- `card_id`、`const_name` はプログラム内部で使われる識別子なので変更しない。`card_no` は YAML の開発参照用で、生成コードやDBには出力されない
- `card_id` はファクション接頭辞（SH/TK/SL/TN/NT）+ ハイフン + 4桁連番（例: `SH-0001`）。新規カード追加時は各ファクション内の最大番号の次を振る
- `origin` フィールドは開発者向けの参考情報で、ゲーム画面には表示されない
- `CARDS.md` は自動生成なので直接編集しない（YAML を編集してコマンドを実行する）
- YAML の書式エラー（インデントずれ、コロン抜け等）があるとコマンドが失敗する。エラーメッセージを確認して修正する
