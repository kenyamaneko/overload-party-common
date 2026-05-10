# overload-party-common

Overload Party の **横断的な共有リソース** を管理するリポジトリ。

所有するもの:

- **ゲームデザイン定数** (faction / card_type / restriction / zone 等。全リポ共通)
- **アーキテクチャ / ゲームデザイン / ビジネスドキュメント**
- **共通設定プリセット** (Claude 用ルール集、各リポへ配布)

## 構成

```
data/
  game_design_constants.yaml  # ゲームデザイン定数 SSoT
  factions.yaml               # ファクションマスター SSoT
packages/
  game-design-constants/          # Go module
  game-design-constants-dotnet/   # NuGet csproj
  game-design-constants-npm/      # npm package
presets/
  claude/                         # Claude Code 用ルール集 (各リポに自動配布)
    base/, flow/, lang/, skills/
    .consumers.yaml               # 配布先リスト
scripts/
  generate_constants.py           # game-design constants 生成 (Go + C# + npm)
.github/
  scripts/publish/                # CI publish 用スクリプト
  scripts/claude-presets/         # Claude presets 同期用スクリプト
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

## Claude プリセットの配信

main への push で [.github/workflows/claude-presets-sync.yaml](.github/workflows/claude-presets-sync.yaml) が走り、[rules/](rules/) 配下を `.consumers.yaml` で宣言された各 consumer リポに同期 PR を作成する。レイヤ構成・onboarding 手順・規約は [rules/README.md](rules/README.md) を参照。
