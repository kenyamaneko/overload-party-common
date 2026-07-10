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

## 詳細

### 開発拠点の構造

| 項目 | 設定 |
|---|---|
| primary 作業ディレクトリ | `overload-party-common` |
| additional working directories | overload-party 配下の編集対象リポ全て |
| 自動ロードされる CLAUDE.md | common の `CLAUDE.md` のみ |
| 各リポの CLAUDE.md | common への動線のみを残した最小内容に置換 (詳細は後述) |

### リポ・レジストリ

各リポの属性 (path / lang / flow) を機械可読に列挙したレジストリを common 配下に新設する。

**配置**: `rules/repos.yaml` (旧 `.consumers.yaml` は本 ADR の sync 撤廃と同時に削除する)。

スキーマ:

```yaml
repos:
  - name: overload-party-shop
    path: ../overload-party-shop
    lang: go
    flow: gitflow

  - name: overload-party-gateway
    path: ../overload-party-gateway
    lang: go
    flow: none

  - name: overload-party-battle
    path: ../overload-party-battle
    lang: csharp
    flow: none
```

`flow` の値の意味:

- `flow: gitflow` は develop ベース運用 + feature ブランチ + PR
- `flow: githubflow` は main ベース運用 + feature ブランチ + PR
- `flow: none` は main 直 push を許容するリポ (ops / infra 系および現状 shop 以外の Go 系リポ)

ブランチ運用に関わる派生情報 (target branch 等) はこの `flow` から導出する。

`lang` の値は `rules/lang/` 配下のファイル名 (`go.md` / `python.md` / `csharp.md` / `iac.md` / `typescript.md`) と 1:1 対応させる。

### common の CLAUDE.md の構造

CLAUDE.md は**索引と分岐ロジックのみ**を保持する。詳細ルールは `rules/` 配下を維持し、CLAUDE.md からは参照のみ行う。

必須セクション:

1. common 自身に適用するルール (`@rules/principles.md` の @import)
2. **クロスリポ作業時の解決手順**: 「編集対象ファイルパスからリポを判別 → レジストリで属性を引く → 該当 preset を適用」を明示
3. レジストリへのポインタ (`rules/repos.yaml`)
4. ルールの場所一覧 (`rules/principles.md` / `rules/lang/{go,python,csharp,iac,typescript}.md` / `rules/flow/{gitflow,githubflow}.md`)
5. リポ固有ルールへのフォールバック手順 (各リポの `docs/` 配下を読む)

詳細ルールを CLAUDE.md に書くか `.claude/` 配下に書くかの方針:

- CLAUDE.md は毎セッション全文ロードされる (コンテキスト消費が大きい) ため、**索引と分岐ロジック以外は書かない**
- 詳細ルールは `rules/principles.md` / `rules/lang/<lang>.md` / `rules/flow/<flow>.md` を継続使用する
- common 自身用の詳細補助ドキュメントが必要な場合のみ、既存の `.claude/docs/` を活用する (新規ディレクトリは作らない)

### 各リポの CLAUDE.md

各リポのルート `CLAUDE.md` は **common への動線のみを残した最小内容に置換する**。ルール本体は common 側の SSoT を参照させ、各リポにコピーは置かない。

```markdown
> **重要**: このリポジトリで作業を始める前に、必ず `../overload-party-common/CLAUDE.md` を読むこと。
```

これにより:

- リポ単体で Claude Code を開いた場合でも、ユーザのローカルに common が clone されていれば動線が機能する
- common 経由運用 (本 ADR の主運用) では各リポの CLAUDE.md は自動ロード対象外なのでこのファイルは触れられないが、人間がリポを直接見たときの参照ポインタとして残る

各リポで合わせて削除する対象:

- `.claude/docs.yaml` (sync の layer 宣言)
- `.claude/docs/` (sync で展開された rule layer のコピー)
- `.claude/skills/` のうち sync で展開されたもの (リポ独自の skill がある場合は峻別する)
- `.gitignore` の `.claude/` 例外指定 (上記が消えれば不要)

### リポ固有ルールの取り扱い

各リポ固有のルール (CI/CD・リリース手順・リポ独自の運用) は**各リポの `docs/` 配下に残置する**。common 集約の対象は「複数リポに共通する横断的ルール」のみであり、リポ固有運用は本 ADR の対象外とする。

common の CLAUDE.md には「リポ固有ルールが必要な場合は `<repo>/docs/` を参照」というフォールバック指示のみ記載する。

### sync workflow の撤廃

`claude-presets-sync` workflow を**撤廃する**。common 経由運用に一本化することで配布対象 (各リポの CLAUDE.md / `.claude/docs/`) が消えるため、配布機構自体が不要になる。

撤廃対象:

- `claude-presets-sync` workflow 本体 (`.github/workflows/` 配下)
- `rules/.consumers.yaml`
- `CLAUDE_SYNC_TOKEN` GitHub Secret (他用途がなければ削除)
- 各 consumer リポの `.claude/docs.yaml`、同期されていた `.claude/docs/` および `.claude/skills/`

`rules/` の preset 本体は引き続き SSoT として存続する (sync で配布されなくなるだけで、common 経由運用で参照される)。

### 限界事項 / scope 外

- **CLAUDE.md ロード挙動の検証**: additional working dir の `CLAUDE.md` がどのように扱われるかは実機検証する。本 ADR は「common の CLAUDE.md のみが自動ロードされる」前提で設計しているが、Claude Code のバージョンや設定により挙動が異なる場合は再設計が必要
- **モデルが索引を毎ターン参照するかの保証**: CLAUDE.md は session 開始時にロードされるが、以降のターンで「ファイル編集前にレジストリを引く」手順をモデルが確実に踏むかは運用上の規約に依存する。異なる lang / flow のリポで典型作業を試行して検証し、期待挙動から外れる場合は CLAUDE.md の索引・分岐記述を調整する

### トレードオフ

- **リポ単体運用が common 依存になる**: 各リポを単独で Claude Code に開いた場合、自動ロードされるのはルート `CLAUDE.md` の動線指示のみとなり、ルール本体を得るにはユーザのローカルに common が clone されている必要がある。common が無い環境 (一部の CI 自動実行など) では別途設計が必要
- **レジストリ整備コスト**: 全 ~15 リポの属性を初回列挙する必要がある (一過性)
- **索引参照の運用依存**: モデルが「編集前にレジストリを引いて適切な preset を当てる」手順を踏まなかった場合、誤ったルールが適用されるリスクがある。CLAUDE.md の指示が明確でなければ漏れる
- **CLAUDE.md のサイズ増加**: common の CLAUDE.md に索引と分岐ロジックが追加されるため、毎セッションのコンテキスト消費が増加する (規模感は数十行〜100 行程度を想定)
- **移行時の cleanup 範囲**: 全 consumer リポで CLAUDE.md を最小内容に置換し、`.claude/docs/` / `.claude/docs.yaml` 等を削除する作業が一斉に発生する

なお `rules/` のレイヤ構造 (base / flow / lang) とリポ固有ルール (`<repo>/docs/`) の所在は本 ADR では変えない。

## Amendment: 2026-07-04 ルール SSoT を keyandnotes-rules に移設

ルール SSoT を `overload-party-common/rules/` から `keyandnotes-rules` リポに移設し、common は `@import` で参照する構成に変更した。common の `rules/` には overload-party 固有の overlay と `repos.yaml` のみが残る。
