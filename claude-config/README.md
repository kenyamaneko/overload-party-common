# Claude Common Config

各リポの `CLAUDE.md` / `.claude/skills/` を共通化するためのレイヤ別設定。
このディレクトリの内容は `claude-config-sync` workflow が各消費リポに自動同期する。

## レイヤ構成

レイヤは `base` / `flow/{name}` / `lang/{name}` の 3 軸で直交分割する。

| レイヤ | 適用範囲 | 内容 |
|---|---|---|
| `base` | 全リポ | 設計思想・コーディング方針・ログ方針・テスト方針・実装フロー・共通禁止事項、Issue 起票 skill |
| `flow/gitflow` | Git flow 採用リポ | ブランチ・Issue 運用、BRANCHING.md、Issue 実装 skill |
| `flow/githubflow` | GitHub Flow 採用リポ (ops / infra 系) | (未実装 — Phase 3 で追加) |
| `lang/go` | Go リポ | テーブル駆動テスト等の Go 固有方針 |
| `lang/csharp` | C# (battle service) | スケルトンのみ。内容追加待ち |
| `lang/python` | Python (ジョブ系・ops 系) | スケルトンのみ。内容追加待ち。ジョブ系も ops 系も同じレイヤを使う (品質基準は共通) |
| `lang/iac` | Terraform / k8s リポ | スケルトンのみ。内容追加待ち |
| `lang/typescript` | TypeScript (client 等) | スケルトンのみ。内容追加待ち |

## 消費リポ側の使い方

### 1. レイヤ宣言

リポに `.claude/docs.yaml` を置き、適用するレイヤを宣言する:

```yaml
layers:
  - base
  - flow/gitflow
  - lang/go
```

### 2. CLAUDE.md を薄く保ち @import で取り込む

```markdown
# {repo-name}

@.claude/docs/base/CLAUDE.md
@.claude/docs/flow/CLAUDE.md
@.claude/docs/lang/CLAUDE.md

# このリポ固有

## [{repo}] SSoT と生成コード
- ...

## [{repo}] 禁止事項
- ...
```

`@import` はテキストインクルード (構造的マージしない)。**矛盾時は後ろが優先** されるため、リポ固有の方針はファイル末尾に書くことで common より優先させられる。

### 3. 自動同期

`overload-party-common` の main に変更が push されると、`claude-config-sync` workflow が:
- `.claude/docs.yaml` で宣言されたレイヤの top-level `*.md` を `.claude/docs/<bucket>/` に
  - bucket = `base` / `flow` / `lang` のいずれか
  - `flow/<variant>` と `lang/<variant>` レイヤは consumer 側で variant を落として `.claude/docs/flow/` と `.claude/docs/lang/` に展開される (1 リポにつき 1 variant 前提)
- 各レイヤの `skills/*.md` を `.claude/skills/` に
コピーした内容で消費リポに PR を作成する。

### 4. .gitignore の対応

`.claude/` 全体を ignore しているリポでは、同期対象を negation で例外指定する:

```gitignore
.claude/
!.claude/docs.yaml
!.claude/docs/
!.claude/docs/**
!.claude/skills/
!.claude/skills/**
```

## セクション命名規約

各レイヤの CLAUDE.md 内のセクション見出しは `## [{layer}] {セクション名}` のプレフィックスを付ける。

例:
- `## [base] 設計思想`
- `## [flow/gitflow] ブランチ・Issue 運用`
- `## [lang/go] テスト方針`
- `## [shop] SSoT と生成コード` (リポ側)

これによりセクションの出自が明示され、grep しやすくなる。

## 消費リポの登録

[`claude-config/.consumers.yaml`](.consumers.yaml) に登録された消費リポにのみ同期される。新リポを追加する場合はこのファイルに追記する。

## 必要な GitHub Secret

`claude-config-sync` workflow には消費リポへの push / PR 作成権限が必要。

- Secret 名: `CLAUDE_SYNC_TOKEN`
- 必要な権限: 消費リポの `Contents: write` + `Pull requests: write`
- 推奨: fine-grained PAT を消費リポ群に対して発行

## 変更フロー

- このディレクトリの変更は main に直接 commit (本リポのブランチ運用方針)
- main への push を契機に `claude-config-sync` workflow が消費リポへ自動 PR

## 衝突解決ルール

- `@import` の順序: general → specific (base → flow → lang → リポ固有)
- 矛盾時: 後ろが優先 (リポ固有 > lang > flow > base)
- セクション名重複は許容 (プレフィックスで出自が分かるため)
