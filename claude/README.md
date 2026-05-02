# Claude Common Config

各リポの `CLAUDE.md` / `.claude/skills/` を共通化するためのレイヤ別設定。
このディレクトリの内容は `claude-config-sync` workflow が各消費リポに自動同期する。

## レイヤ構成

| レイヤ | 適用範囲 | 内容 |
|---|---|---|
| `base/` | 全リポ | 設計思想・コーディング方針・ログ方針・テスト方針・実装フロー・共通禁止事項、Issue 起票 skill |
| `flow-gitflow/` | Git flow 採用リポ | ブランチ・Issue 運用、BRANCHING.md、Issue 実装 skill |
| `flow-githubflow/` | GitHub Flow 採用リポ | (未実装 — Phase 3 で追加) |
| `lang-go/` | Go リポ | (未実装 — Phase 2 で追加) |
| `lang-csharp/` | C# リポ | (未実装) |
| `lang-python/` | Python リポ | (未実装) |
| `lang-iac/` | Terraform / k8s リポ | (未実装) |

## 消費リポ側の使い方

### 1. レイヤ宣言

リポルートに `.claude-common.yaml` を置き、適用するレイヤを宣言する:

```yaml
layers:
  - base
  - flow-gitflow
```

### 2. CLAUDE.md を薄く保ち @import で取り込む

```markdown
# {repo-name}

@.claude-common/base/CLAUDE.md
@.claude-common/flow-gitflow/CLAUDE.md

# このリポ固有

## [{repo}] 言語固有方針
- ...

## [{repo}] 禁止事項
- ...
```

`@import` はテキストインクルード (構造的マージしない)。**矛盾時は後ろが優先** されるため、リポ固有の方針はファイル末尾に書くことで common より優先させられる。

### 3. 自動同期

`overload-party-common` の main に変更が push されると、`claude-config-sync` workflow が:
- `.claude-common.yaml` で宣言されたレイヤの top-level `*.md` を `.claude-common/<layer>/` に
- 各レイヤの `skills/*.md` を `.claude/skills/` に
コピーした内容で消費リポに PR を作成する。

## セクション命名規約

各レイヤの CLAUDE.md 内のセクション見出しは `## [{layer}] {セクション名}` のプレフィックスを付ける。

例:
- `## [base] 設計思想`
- `## [flow-gitflow] ブランチ・Issue 運用`
- `## [shop] 言語固有方針` (リポ側)

これによりセクションの出自が明示され、grep しやすくなる。

## 消費リポの登録

`.github/claude-consumers.yaml` に登録された消費リポにのみ同期される。新リポを追加する場合はこのファイルに追記する。

## 必要な GitHub Secret

`claude-config-sync` workflow には消費リポへの push / PR 作成権限が必要。

- Secret 名: `CLAUDE_SYNC_TOKEN`
- 必要な権限: 消費リポの `Contents: write` + `Pull requests: write`
- 推奨: fine-grained PAT を消費リポ群に対して発行

## 変更フロー

- このディレクトリの変更は main に直接 commit (本リポのブランチ運用方針)
- 変更時は `claude-config-validate` workflow が以下を検証:
  - skill frontmatter の必須項目 (`name` / `description`)
  - `@import` パスの参照先存在
- 検証 pass 後、`claude-config-sync` workflow が消費リポへ自動 PR

## 衝突解決ルール

- `@import` の順序: general → specific (base → flow → lang → リポ固有)
- 矛盾時: 後ろが優先 (リポ固有 > lang > flow > base)
- セクション名重複は許容 (プレフィックスで出自が分かるため)
