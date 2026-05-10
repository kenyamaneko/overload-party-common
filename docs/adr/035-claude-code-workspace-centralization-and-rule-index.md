# ADR-035: Claude Code 開発拠点を common に集約し、ルール参照を CLAUDE.md 索引型に移行する

- Status: Accepted
- Date: 2026-05-10
- Deciders: kenyamaneko
- Related: なし (Issue 起票後に追記)

## Context

overload-party 配下のリポ群 (約 15 リポ) は現状、ユーザが各リポを直接開いて Claude Code を起動する運用となっている。各リポの開発ルールは `overload-party-common/rules/` を SSoT とし、`claude-presets-sync` workflow が `base / flow/{gitflow,githubflow} / lang/{go,python,csharp,iac,typescript}` の 3 軸でレイヤ別にコピーを各リポへ同期する仕組みで成立している (ADR は不在だが [rules/README.md](../../rules/README.md) に詳細記載)。

### 現状の運用構造

| 要素 | 現状 |
|---|---|
| 開発拠点 | リポごとに Claude Code セッションを開く |
| ルール SSoT | `overload-party-common/rules/` |
| ルール配布 | `claude-presets-sync` workflow が consumer リポへ PR で同期 |
| consumer 宣言 | `rules/.consumers.yaml` (現状 shop のみ) |
| consumer 側のルール参照 | 各リポの `CLAUDE.md` から `@.claude/docs/{base,flow,lang}/CLAUDE.md` を `@import` |

### 構造的問題

1. **リポ切替コスト**: 横断的な作業 (例: 「全 Go リポの構造を確認したい」「shop のイベント仕様を見ながら gateway の subscriber を修正したい」) で都度リポを開き直す必要がある。Claude Code セッションも都度立ち上げ直しになり、コンテキスト構築 (リポ理解・関連ファイルの読み込み) を繰り返す。
2. **複数リポの同時編集が困難**: 1 セッション 1 リポ前提では、common の SSoT 変更と consumer 側の追従を同一セッションで行えない。常に複数ターミナルとセッションを跨ぐ必要がある。
3. **既存 sync 機構は配布のみで横断作業を解決していない**: `claude-presets-sync` はルールの**分散配布**を解決しているが、開発者が**横断的に複数リポを触る作業形態**には寄与していない。
4. **同期遅延**: common の `rules/` を更新しても、consumer 側に PR が届きマージされるまではルールが反映されない。

### Claude Code の機能的前提

Claude Code は primary 作業ディレクトリ + additional working directories を指定できる。primary の `CLAUDE.md` のみが自動ロードされる (additional working dirs の `CLAUDE.md` は自動ロードされない前提で本 ADR は設計する)。本 ADR の運用が成立するためには、**common の CLAUDE.md だけでクロスリポ作業に必要な索引が完結する**ことが要件となる。

## Decision

**Claude Code の開発拠点を `overload-party-common` に集約する。primary 作業ディレクトリを common 固定とし、編集対象の他リポは additional working directory として参照する。各リポへ適用すべきルールは common の `CLAUDE.md` に置く索引から、ファイルパス起点で解決する。**

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

**スキーマ (案)**:

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

**`flow` の値の意味**:

- `flow: gitflow` は develop ベース運用 + feature ブランチ + PR
- `flow: githubflow` は main ベース運用 + feature ブランチ + PR
- `flow: none` は main 直 push を許容するリポ (ops / infra 系および現状 shop 以外の Go 系リポ)

ブランチ運用に関わる派生情報 (target branch 等) はこの `flow` から導出する。

`lang` の値は `rules/lang/` 配下のディレクトリ名 (`go` / `python` / `csharp` / `iac` / `typescript`) と 1:1 対応させる。

### common の CLAUDE.md の構造

CLAUDE.md は**索引と分岐ロジックのみ**を保持する。詳細ルールは `rules/` 配下を維持し、CLAUDE.md からは参照のみ行う。

**必須セクション**:

1. common 自身に適用するルール (`@rules/base/CLAUDE.md` 等の現行 import)
2. **クロスリポ作業時の解決手順**: 「編集対象ファイルパスからリポを判別 → レジストリで属性を引く → 該当 preset を適用」を明示
3. レジストリへのポインタ (`rules/repos.yaml`)
4. preset の場所一覧 (`rules/{base, flow/{gitflow,githubflow}, lang/{go,python,csharp,iac,typescript}}`)
5. リポ固有ルールへのフォールバック手順 (各リポの `docs/` 配下を読む)

**詳細ルールを CLAUDE.md に書くか `.claude/` 配下に書くかの方針**:

- CLAUDE.md は毎セッション全文ロードされる (コンテキスト消費が大きい) ため、**索引と分岐ロジック以外は書かない**
- 詳細ルールは既存の `rules/{base,flow,lang}/CLAUDE.md` を継続使用する
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
- 各 consumer リポの `.claude/docs.yaml`、同期されていた `.claude/docs/` および `.claude/skills/` (前項「各リポの CLAUDE.md」の置換と一括で実施)

`rules/{base, flow, lang}/` の preset 本体は引き続き SSoT として存続する (sync で配布されなくなるだけで、common 経由運用で参照される)。

### 限界事項 / scope 外

- **CLAUDE.md ロード挙動の検証**: additional working dir の `CLAUDE.md` がどのように扱われるかは Phase 8 で実機検証する。本 ADR は「common の CLAUDE.md のみが自動ロードされる」前提で設計しているが、Claude Code のバージョンや設定により挙動が異なる場合は再設計が必要
- **モデルが索引を毎ターン参照するかの保証**: CLAUDE.md は session 開始時にロードされるが、以降のターンで「ファイル編集前にレジストリを引く」手順をモデルが確実に踏むかは運用上の規約に依存する。Phase 8 で典型作業ケースを試行して検証する

## Consequences

### Positive

- **リポ切替コスト削減**: 横断的な作業 (common の SSoT 変更 + consumer 追従、複数リポを跨ぐ調査) が単一セッションで完結する
- **ルール変更のリードタイム短縮**: common の `rules/` を更新した時点で、sync PR を待たずに即座に反映される
- **複数リポ横断の調査効率向上**: 「全 Go リポで X を確認」「shop の event 仕様を gateway 側で参照」等の作業が 1 セッションで可能になる
- **配布機構の撤廃**: `claude-presets-sync` workflow / `CLAUDE_SYNC_TOKEN` PAT / consumer 側の `.claude/docs/` コピー / 同期 PR のレビュー負担が一掃される
- **SSoT への一本化**: ルールが common の `rules/` 一箇所のみに存在する状態になり、コピーが各リポに残ることによる drift 余地がなくなる
- **レジストリの副次効用**: リポ属性 (lang / flow) が機械可読に列挙されることで、将来 CI / 運用スクリプトからも参照可能になる (例: 「全 Go リポで lint を実行」「全 gitflow リポで release ブランチを作成」等)
- **メモリ依存の解消**: ユーザのメモリに残していた「shop は Git flow、他は main 直 push」のようなリポ属性情報がコード化され、メモリから移管できる

### Negative

- **リポ単体運用が common 依存になる**: 各リポを単独で Claude Code に開いた場合、自動ロードされるのはルート `CLAUDE.md` の動線指示のみとなり、ルール本体を得るにはユーザのローカルに common が clone されている必要がある。common が無い環境 (一部の CI 自動実行など) では別途設計が必要
- **レジストリ整備コスト**: 全 ~15 リポの属性を初回列挙する必要がある (一過性)
- **索引参照の運用依存**: モデルが「編集前にレジストリを引いて適切な preset を当てる」手順を踏まなかった場合、誤ったルールが適用されるリスクがある。CLAUDE.md の指示が明確でなければ漏れる
- **CLAUDE.md のサイズ増加**: common の CLAUDE.md に索引と分岐ロジックが追加されるため、毎セッションのコンテキスト消費が増加する (規模感は数十行〜100 行程度を想定)
- **移行時の cleanup 範囲**: 全 consumer リポで CLAUDE.md を最小内容に置換し、`.claude/docs/` / `.claude/docs.yaml` 等を削除する作業が一斉に発生する

### Neutral

- `rules/` のレイヤ構造 (base / flow / lang) は据え置き
- リポ固有ルール (`<repo>/docs/`) の所在も据え置き

## Migration

### Phase 1: 現状調査 (read-only)

- `rules/` 配下の preset 内容棚卸し
- 各リポ (~15) の `CLAUDE.md` および `.claude/` 配下棚卸し (sync 由来か、リポ独自の skill / 設定が混在しているか)
- 各リポの `docs/` 配下のリポ固有ドキュメント所在確認

### Phase 2: 設計確定

- レジストリスキーマの確定 (本 ADR 案ベース)
- common CLAUDE.md の構造確定 (索引・分岐ロジックの記述形式)
- 各リポで sync 由来でない `.claude/` 内資産があれば退避方針を確定

### Phase 3: common の索引整備

- `rules/repos.yaml` 作成 (全 ~15 リポを列挙)
- common の `CLAUDE.md` を索引型に書き換え

### Phase 4: lang preset の充実

現状 `lang/{python, csharp, typescript, iac}` は TODO スケルトンのみ。各リポの CLAUDE.md からリポ横断で適用すべきルールを吸い上げて充実させる。

- `lang/python/CLAUDE.md`: ops / newsfeed の Python ルールから抽出
- `lang/csharp/CLAUDE.md`: battle の C# 規約 (LINQ / switch 式 / `ICardCache.MustGet` / 上流契約の再検証禁止 等) から抽出
- `lang/typescript/CLAUDE.md`: client の方針から抽出
- `lang/iac/CLAUDE.md`: infra / k8s の Terraform 方針 (default 禁止 / output 抑制 / Secret Manager 経由) から抽出
- `lang/go/CLAUDE.md`: 既存内容に追加すべきもの (例: account の「リポジトリ層は API 契約の型を使わない」が既に取り込まれているか確認) を点検

各リポ固有として残すべきルール (例: gateway の「他サービスのデータをそのまま通過させる」、client の「Gateway port 9001 のみと通信」) は lang preset に上げず、各リポの `docs/` 配下に退避する。

### Phase 5: 各リポの cleanup

各 consumer リポで以下を実施:

- ルート `CLAUDE.md` を common への動線指示のみの最小内容に置換
- `.claude/docs.yaml` を削除 (shop のみ存在)
- `.claude/docs/` (sync で展開されたコピー) を削除 (shop のみ存在)
- `.claude/skills/` を削除 (shop / scenario / infra / account に存在するが、いずれも common 由来のため独自保持不要)
- `.gitignore` の `.claude/` 例外指定を削除 (上記が消えれば不要)
- リポ固有として残すルールがあれば `docs/` 配下のドキュメントへ退避 (Phase 4 で識別済)

リポ単位で PR を切り、common 経由運用で当該リポを編集できることを 1 リポで先行確認してから残リポへ展開する (Phase 8 の検証手順を 1 リポ分先行実施)。

### Phase 6: sync 機構の撤廃

- `.github/workflows/claude-presets-sync.yaml` (および関連 action / script) を削除
- `rules/.consumers.yaml` を削除
- `CLAUDE_SYNC_TOKEN` GitHub Secret を削除 (他用途がなければ)
- `rules/README.md` を新運用に合わせて書き換え (sync 手順の記述を削除し、common 経由運用の手順を記載)

### Phase 7: メモリ整理

- ユーザの auto-memory にある「リポごとのブランチ運用状況」エントリを削除 (レジストリに移管したため)

### Phase 8: 検証

- common を primary、各リポを additional working dir で開く構成で Claude Code を起動
- 異なる lang / flow のリポで典型作業を実行し、適切な preset が適用されるか確認
  - 例 1: shop (Go + gitflow) のファイル編集で「lang/go + flow/gitflow」が効くか
  - 例 2: gateway (Go + githubflow) のファイル編集で「lang/go + flow/githubflow」が効くか
  - 例 3: battle (C# + none) のファイル編集で「lang/csharp + flow/none」が効くか
- 期待挙動から外れる場合は CLAUDE.md の索引・分岐記述を調整

## 関連 issue

- 本 ADR の全体トラッカー Issue は ADR 採択後に起票し追記する
