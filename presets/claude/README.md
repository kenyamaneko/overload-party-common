# Claude Common Config

各リポの `CLAUDE.md` / `.claude/skills/` を共通化するためのレイヤ別設定。
このディレクトリの内容は `claude-presets-sync` workflow が消費リポに自動同期する。

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

---

## 使い方

### 新規 consumer を onboard する

#### 1. common 側に登録

[`presets/claude/.consumers.yaml`](.consumers.yaml) に追記する。

```yaml
consumers:
  - repo: kenyamaneko/overload-party-{name}
    target_branch: develop
```

#### 2. consumer リポにレイヤ宣言を置く

リポに `.claude/docs.yaml` を配置する。

```yaml
layers:
  - base
  - flow/gitflow
  - lang/go
```

#### 3. ルート `CLAUDE.md` を @import 構成にする

```markdown
# {repo-name}

@.claude/docs/base/CLAUDE.md
@.claude/docs/flow/CLAUDE.md
@.claude/docs/lang/CLAUDE.md

# このリポ固有

## [{repo}] SSoT と生成コード
- ...
```

#### 4. consumer の `.gitignore` を調整

`.claude/` 全体を ignore しているリポでは、同期対象を negation で例外指定する。

```gitignore
.claude/
!.claude/docs.yaml
!.claude/docs/
!.claude/docs/**
!.claude/skills/
!.claude/skills/**
```

### 共通設定を変更する

- このディレクトリの変更は main に直接 commit する (本リポのブランチ運用方針)
- main への push を契機に `claude-presets-sync` workflow が消費リポへ同期 PR を作成する

---

## 規約

### セクション命名

各レイヤの CLAUDE.md 内のセクション見出しは `## [{layer}] {セクション名}` プレフィックスを付ける。出自が明示され grep しやすくなる。

例:
- `## [base] 設計思想`
- `## [flow/gitflow] ブランチ・Issue 運用`
- `## [lang/go] テスト方針`
- `## [shop] SSoT と生成コード` (consumer 固有セクション)

### @import の順序と衝突解決

- 順序: general → specific (`base` → `flow` → `lang` → consumer 固有)
- 矛盾時は **後ろが優先** (consumer 固有 > lang > flow > base)
- `@import` はテキストインクルード (構造的マージしない)。consumer 固有の方針はファイル末尾に書くことで common より優先させられる
- セクション名重複は許容 (プレフィックスで出自が分かるため)

---

## 仕組み

### 同期動作

`claude-presets-sync` workflow が main push を契機に各 consumer に PR を作成する。

- `.claude/docs.yaml` で宣言されたレイヤの top-level `*.md` を `.claude/docs/<bucket>/` に展開
  - bucket = `base` / `flow` / `lang`
  - `flow/<variant>` と `lang/<variant>` のレイヤ名は consumer 側で variant を落として `.claude/docs/flow/` と `.claude/docs/lang/` にフラット展開される (1 リポにつき 1 variant 前提)
- 各レイヤの `skills/*.md` を `.claude/skills/` に展開
- consumer の作業ツリーに変更が出たときのみ PR を作成 (差分なしならスキップ)

### 必要な GitHub Secret

`claude-presets-sync` workflow が消費リポに push / PR を作成するために必要。

- Secret 名: `CLAUDE_SYNC_TOKEN`
- 必要な権限: 消費リポの `Contents: write` + `Pull requests: write`
- 推奨: fine-grained PAT を消費リポ群に対して発行
