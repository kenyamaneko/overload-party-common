# overload-party-common

Overload Party の **横断的な共有リソース** を管理するリポジトリ。

所有するもの:

- **ゲームデザイン定数** (faction / card_type / restriction / zone 等。全リポ共通)
- **アーキテクチャ / ゲームデザイン / ビジネスドキュメント**
- **Claude Code 開発ルール** (coding / branch / 言語別ルール。全リポ共通)

## 構成

```
data/
  game_design_constants.yaml      # ゲームデザイン定数 SSoT
  factions.yaml                   # ファクションマスター SSoT
  game_config_defaults.yaml       # game_config の初期値 (Firestore 投入元)
packages/
  game-design-constants/          # Go module
  game-design-constants-dotnet/   # NuGet csproj
  game-design-constants-npm/      # npm package
  codegen-tools/                  # codegen 共通ライブラリ (Python)
  asyncapi-codegen-tools/         # AsyncAPI 用 codegen ツール (Python)
  doc-tools/                      # ドキュメント生成ツール (Python)
rules/
  principles.md                   # 全リポ共通の base ルール (CLAUDE.md から @import)
  lang/                            # 言語別ルール
  flow/                            # ブランチ運用別ルール
  repos.yaml                       # リポ・レジストリ (path / lang / flow)
scripts/
  generate_constants.py            # game-design constants 生成 (Go + C# + npm)
  test_generate_constants.py       # 上記のテスト
.claude/
  skills/                          # Claude Code 用 skill
.github/
  workflows/                       # validate / publish
  actions/                         # publish / Cloudsmith 認証用 composite action
  scripts/                         # 上記 action / workflow のスクリプト
docs/
  architecture/                    # システム設計ドキュメント
  game_design/                     # ゲームデザイン (ルール, カード, UI 等)
  business/                        # ビジネス・法務
  notes/                           # 補助メモ
  adr/                             # ADR (gitignore、手元専用)
```

## パッケージ

| パッケージ | 形式 | 利用リポ |
|-----------|------|---------|
| `packages/game-design-constants` | Go module | 全 Go サービス |
| `packages/game-design-constants-dotnet` (`OverloadParty.GameDesignConstants`) | NuGet | battle |
| `packages/game-design-constants-npm` (`@kenyamaneko/overload-party-game-design-constants`) | npm | client |

## コード生成

`game-design-constants` 系の 3 パッケージは `data/*.yaml` から自動生成する。

```
data/game_design_constants.yaml ┐
data/factions.yaml              ┼─► scripts/generate_constants.py ─► packages/game-design-constants{,-dotnet,-npm}/ の *_gen.* ファイル
```

YAML を編集したら `python3 scripts/generate_constants.py` を実行してコミットする。前提: Python 3.8+ と `pip install pyyaml`。

## 配信 (CI publish)

main への push で [.github/workflows/publish.yaml](.github/workflows/publish.yaml) が走り、変更のあったパッケージだけを publish する。

- **変更検知**: [.github/scripts/publish/detect-changes.sh](.github/scripts/publish/detect-changes.sh) が前回タグとの diff を見てどのパッケージを bump するか決める。デフォルトは patch。
- **バージョン bump**: 手動で minor/major にしたい場合は Actions から `workflow_dispatch` で `bump` と `target` を指定して実行。
- **タグ規約**: `packages/<name>/v<semver>` (例: `packages/game-design-constants/v1.2.3`)
- **レジストリ**: Go は git tag のみ (`go get` が解決)、NuGet / npm は GitHub Packages (`nuget.pkg.github.com` / `npm.pkg.github.com`)

## 定数を変更するとき

1. `data/game_design_constants.yaml` もしくは `data/factions.yaml` を編集
2. `python3 scripts/generate_constants.py` を実行
3. main に push → CI が自動で patch bump で publish
4. 各リポでパッケージを更新:
   - Go サービス: `go get github.com/kenyamaneko/overload-party-common/packages/game-design-constants@latest`
   - battle: `dotnet add package OverloadParty.GameDesignConstants`
   - client: `npm install @kenyamaneko/overload-party-game-design-constants@latest`

