# ADR-030: 全リポ自動レビューを Cloud Run Job + Anthropic API から Claude Code スラッシュコマンドに移管

- Status: Accepted
- Date: 2026-05-03
- Deciders: kenyamaneko
- Related: なし

## Context

`overload-party-ops/nightly-review/` (Python + Cloud Run Job) として運用してきた全リポ自動レビューに以下の課題があった。

1. **API コスト**: Anthropic API 直叩きで月額 $30-40。Nightly Review 1 用途に対して継続費用が大きい。
2. **入力範囲がコンテキスト不足**: 各リポの差分テキストと変更ファイル全文だけを Claude API に投げる構造。リポジトリ全体・呼び出し元・関連設計までは見せられない。
3. **Opus 4.7 の propagation / scope 見落とし**: 上記コンテキスト不足が原因で、変更が呼び出し元に与える影響や設計範囲外への波及が拾えないケースが増えた。
4. **org rate limit 競合**: org 上限 30k input tokens/min に対して、17 リポの大きな差分を逐次投げるバッチ実行で 429 を頻発させていた (関連メモ: nightly-review 用 429 リトライ実装)。

夜間バッチに固定する積極的理由は薄く、「朝に手動トリガでも問題ない」運用上の許容があった。

## Decision

夜間 Cloud Run Job + Anthropic API 直叩き構成を廃止し、**Claude Code のカスタムスラッシュコマンドを朝に手動実行する**構成に移管する。

### 構成

| 要素 | 配置 |
|---|---|
| スラッシュコマンド本体 | `overload-party-ops/.claude/commands/review-yesterday.md` |
| 機能ディレクトリ (設定・ドキュメント) | `overload-party-ops/auto-review/` |
| 対象リポ一覧 (SSoT) | `auto-review/repos.yaml` |
| レビュー観点 (SSoT) | `auto-review/review_criteria.yaml` |
| GitHub Issue ラベル | `auto-review` (旧 nightly-review 時代から継続) |
| ローカル出力 | `~/reviews/{前日日付}/{repo}.md` と `index.md` |

### 動作

1. ユーザが Claude Code 内で `/review-yesterday` を実行
2. 親エージェントが `repos.yaml` / `review_criteria.yaml` を Read
3. 対象リポすべてに対して `general-purpose` Subagent を **並列**ディスパッチ
4. 各 Subagent が `gh repo clone` でローカルにチェックアウトし、`gh api` で前日 00:00 JST 以降の差分を取得、リポ全体を Read/Grep/Glob しながら観点に沿ってレビュー
5. 結果を `~/reviews/{前日日付}/{repo}.md` に書き出し、指摘ありなら各リポに GitHub Issue を起票
6. 親が `index.md` に集約してチャットに 1 行サマリと Issue URL 一覧を返す

### 命名ルール

- スラッシュコマンドは動詞始まり: `/review-yesterday`
- 機能ディレクトリは名詞 (`___-review`): `auto-review/`
- GitHub Issue ラベルと出力語彙を `auto-review` / `~/reviews/` に統一

## Consequences

### Positive

- **API コスト削減**: 月 $30-40 → Max プラン込みで実質追加費用なし
- **入力コンテキスト拡大**: 差分のみから「差分 + リポジトリ全体クローン (Read/Grep/Glob 可)」へ拡張。Opus 4.7 の propagation/scope 見落としを構造的に抑制
- **並列度向上**: リポジトリ逐次から、Subagent による全リポ並列実行へ
- **インフラ削減**: Cloud Run Job / 専用 SA / Anthropic Secret / GitHub Actions schedule / Artifact Registry イメージ / 失敗通知 shell をすべて廃止
- **設定変更の容易化**: 対象リポ・観点の編集が YAML 編集のみで完結 (Python コード改変不要)
- **rate limit 緩和**: 1 user の Max プラン枠を使うため org rate limit 競合を回避

### Negative

- **手動トリガが必要**: 朝に Claude Code 内で `/review-yesterday` を 1 回叩く必要がある。蓋を開けない日はレビューがスキップされる
- **Mac の Claude Code に依存**: ヘッドレス環境 (CI / 出張中スマホ閲覧) からは実行不可
- **実行所要時間がフォアグラウンド**: 旧 Cloud Run Job 方式の「寝てる間に終わる」が消え、実行中はユーザのセッションを占有する (Subagent 並列で数分〜十数分想定)
- **Claude Code バージョン差分の影響を受ける**: スラッシュコマンドの仕様変更 (`@file` 参照・Subagent ツール仕様等) があれば本機能も追従が必要

### Neutral

- 出力先が GitHub Issue 単独からローカル `~/reviews/` + GitHub Issue の二重出力になる。Issue 起票挙動 (リポごと 1 Issue/日、LGTM はスキップ、同タイトル前方一致で dedup、`auto-review` ラベル) は旧方式と同一
- レビュー観点 YAML のスキーマも旧方式から継承

## Migration

- `overload-party-ops` の `nightly-review/` (Python 一式) と `.github/workflows/nightly-review*.yaml` を削除
- `overload-party-infra` の `providers/google-cloud/ops/modules/nightly-review/` を削除し `terraform apply` 実施 (Cloud Run Job / SA `nightly-reviewer` / Secret 2 件 / IAM 計 10 リソース destroy)
- Artifact Registry の `nightly-review` イメージを `gcloud artifacts docker images delete` で全削除
- GitHub Secret `ANTHROPIC_API_KEY` を削除 (他用途なし)
- 旧 `GH_PAT_NIGHTLY_REVIEW` Secret は drift-monitor が現役で利用していたため `INFRA_DRIFT_MONITOR_TOKEN` に改名し用途と一致させた

## Postscript (2026-05-20)

スラッシュコマンドと機能ディレクトリの配置を `overload-party-ops` から `overload-party-common` に移行した。理由は「全リポの開発起点を common に集約する」運用方針 (`overload-party-common` を primary working directory として扱う)。同時にコマンド名を「差分 / 全体」の対称軸で揃え、全体スキャン用コマンドを新設した。

| 要素 | 旧配置 | 新配置 |
|---|---|---|
| 差分レビュー (旧 `/review-yesterday`) | `overload-party-ops/.claude/commands/review-yesterday.md` | `overload-party-common/.claude/commands/review-diff.md` |
| 全体スキャン (新設) | — | `overload-party-common/.claude/commands/review-all.md` |
| 機能ディレクトリ | `overload-party-ops/auto-review/` | `overload-party-common/auto-review/` |
| 結果出力先 | `~/workspace/key_and_notes/overload-party/review/...` | `overload-party-common/docs/review/{diff,all}/...` (gitignored) |

YAML / SSoT スキーマ・観点・Issue 起票挙動 (`/review-diff`) はすべて旧方式と同一。`/review-all` は Issue 起票せずファイル出力のみ。
