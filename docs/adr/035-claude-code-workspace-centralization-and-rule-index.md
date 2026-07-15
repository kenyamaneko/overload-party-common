# ADR-035: Claude Code 開発拠点を common に集約し、ルール参照を CLAUDE.md 索引型に移行する

## ステータス

Accepted (2026-05-10)。末尾の Amendment (2026-07-04: ルール SSoT の keyandnotes-rules 移設) を含めて現行方針とする

## 結論

リポごとに Claude Code セッションを開く運用の切替コストとルール同期遅延を解消するため、**Claude Code の開発拠点を `overload-party-common` に集約する。primary 作業ディレクトリを common 固定とし、編集対象の他リポは additional working directory として参照する。各リポへ適用すべきルールは common の `CLAUDE.md` に置く索引から、ファイルパス起点で解決する。** 横断作業が単一セッションで完結し、ルール変更は sync PR を待たず即座に反映される。`claude-presets-sync` workflow / `CLAUDE_SYNC_TOKEN` / consumer 側コピーの配布機構は一掃され、ルールは common 一箇所の SSoT に閉じて drift 余地がなくなる。リポ属性 (lang / flow) はレジストリとして機械可読になり、将来 CI / 運用スクリプトからも参照できる。

## 背景・課題

overload-party 配下のリポ群 (約 15 リポ) は現状、ユーザが各リポを直接開いて Claude Code を起動する運用となっている。各リポの開発ルールは `overload-party-common/rules/` を SSoT とし、`claude-presets-sync` workflow が `base / flow/{gitflow,githubflow} / lang/{go,python,csharp,iac,typescript}` の 3 軸でレイヤ別にコピーを各リポへ同期する仕組みで成立している。

### 現状の運用構造

| 要素 | 現状 |
|---|---|
| 開発拠点 | リポごとに Claude Code セッションを開く |
| ルール SSoT | `overload-party-common/rules/` |
| ルール配布 | `claude-presets-sync` workflow が consumer リポへ PR で同期 |
| consumer 宣言 | `rules/.consumers.yaml` |
| consumer 側のルール参照 | 各リポの `CLAUDE.md` から `@.claude/docs/{base,flow,lang}/CLAUDE.md` を `@import` |

### 構造的問題

1. **リポ切替コスト**: 横断的な作業 (例: 「全 Go リポの構造を確認したい」「shop のイベント仕様を見ながら gateway の subscriber を修正したい」) で都度リポを開き直す必要がある。Claude Code セッションも都度立ち上げ直しになり、コンテキスト構築 (リポ理解・関連ファイルの読み込み) を繰り返す。
2. **複数リポの同時編集が困難**: 1 セッション 1 リポ前提では、common の SSoT 変更と consumer 側の追従を同一セッションで行えない。常に複数ターミナルとセッションを跨ぐ必要がある。
3. **既存 sync 機構は配布のみで横断作業を解決していない**: `claude-presets-sync` はルールの**分散配布**を解決しているが、開発者が**横断的に複数リポを触る作業形態**には寄与していない。
4. **同期遅延**: common の `rules/` を更新しても、consumer 側に PR が届きマージされるまではルールが反映されない。

### Claude Code の機能的前提

Claude Code は primary 作業ディレクトリ + additional working directories を指定できる。primary の `CLAUDE.md` のみが自動ロードされる (additional working dirs の `CLAUDE.md` は自動ロードされない前提で本 ADR は設計する)。本 ADR の運用が成立するためには、**common の CLAUDE.md だけでクロスリポ作業に必要な索引が完結する**ことが要件となる。

## Amendment: 2026-07-04 ルール SSoT を keyandnotes-rules に移設

ルール SSoT を `overload-party-common/rules/` から `keyandnotes-rules` リポに移設し、common は `@import` で参照する構成に変更した。common の `rules/` には overload-party 固有の overlay と `repos.yaml` のみが残る。
