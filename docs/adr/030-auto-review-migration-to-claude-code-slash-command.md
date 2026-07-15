# ADR-030: 全リポ自動レビューを Cloud Run Job + Anthropic API から Claude Code スラッシュコマンドに移管

## ステータス

Accepted (2026-05-03)

## 結論

コストとコンテキスト不足の課題を解消するため、夜間 Cloud Run Job + Anthropic API 直叩き構成を廃止し、**Claude Code のカスタムスラッシュコマンドを朝に手動実行する**構成に移管する。API コストは月 $30-40 から Max プラン込みで実質追加費用なしになり、入力は差分のみから「差分 + リポジトリ全体クローン (Read/Grep/Glob 可)」へ拡張されて propagation / scope の見落としを構造的に抑制する。実行は Subagent による全リポ並列となり、Cloud Run Job / 専用 SA / Secret / スケジュール等のインフラが丸ごと消え、対象リポ・観点の変更は YAML 編集のみで完結する。org rate limit 競合も 1 user の Max プラン枠を使うことで回避される。

## 背景・課題

`overload-party-ops/nightly-review/` (Python + Cloud Run Job) として運用してきた全リポ自動レビューに以下の課題があった。

1. **API コスト**: Anthropic API 直叩きで月額 $30-40。Nightly Review 1 用途に対して継続費用が大きい。
2. **入力範囲がコンテキスト不足**: 各リポの差分テキストと変更ファイル全文だけを Claude API に投げる構造。リポジトリ全体・呼び出し元・関連設計までは見せられない。
3. **Opus 4.7 の propagation / scope 見落とし**: 上記コンテキスト不足が原因で、変更が呼び出し元に与える影響や設計範囲外への波及が拾えないケースが増えた。
4. **org rate limit 競合**: org 上限 30k input tokens/min に対して、17 リポの大きな差分を逐次投げるバッチ実行で 429 を頻発させていた (関連メモ: nightly-review 用 429 リトライ実装)。

夜間バッチに固定する積極的理由は薄く、「朝に手動トリガでも問題ない」運用上の許容があった。

## Amendment: 2026-05-20 配置を common に移行

スラッシュコマンドと機能ディレクトリの配置を `overload-party-ops` から `overload-party-common` に移行した。理由は「全リポの開発起点を common に集約する」運用方針 (`overload-party-common` を primary working directory として扱う)。同時にコマンド名を「差分 / 全体」の対称軸で揃え、全体スキャン用コマンドを新設した。

| 要素 | 旧配置 | 新配置 |
|---|---|---|
| 差分レビュー (旧 `/review-yesterday`) | `overload-party-ops/.claude/commands/review-yesterday.md` | `overload-party-common/.claude/commands/review-diff.md` |
| 全体スキャン (新設) | — | `overload-party-common/.claude/commands/review-all.md` |
| 機能ディレクトリ | `overload-party-ops/auto-review/` | `overload-party-common/auto-review/` |
| 結果出力先 | `~/workspace/key_and_notes/overload-party/review/...` | `overload-party-common/docs/review/{diff,all}/...` (gitignored) |

YAML / SSoT スキーマ・観点・Issue 起票挙動 (`/review-diff`) はすべて旧方式と同一。`/review-all` は Issue 起票せずファイル出力のみ。
