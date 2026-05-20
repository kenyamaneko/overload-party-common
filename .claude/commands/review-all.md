---
description: 指定リポジトリの現在のブランチ HEAD 全体を Subagent で並列レビューし、docs/review/all/{repo}/{実行日時}.md に書き出す。複数リポを引数指定可能
allowed-tools: Bash, Agent, Read, Write
argument-hint: "<repo> [repo ...]"
---

# /review-all

指定リポジトリの現在のブランチ HEAD 全体を `auto-review/review_criteria.yaml` の観点でレビューする。`/review-diff` が差分レビューなのに対し、`/review-all` は**リポ全体スキャン**を担う。

## 引数

`$ARGUMENTS` にスペース区切りで対象リポ名を渡す (必須)。`overload-party-` プレフィックスは省略可能。

例:

```
/review-all gateway                       # overload-party-gateway 全体
/review-all gateway battle                # 2 リポ並列
/review-all overload-party-gateway        # フルネームでも可
```

引数が空なら、フォールバックせずユーザーに使い方を返して終了する (`/review-diff` と異なり全リポ対象モードは持たない。リポ全体スキャンを 17 リポで並列走らせるとコスト・時間が過大になるため)。

## 全体方針

- このコマンド (親) は **オーケストレーション専任**。レビュー本体は Subagent が実行する
- 対象リポと観点は @auto-review/repos.yaml と @auto-review/review_criteria.yaml を SSoT とする
- 引数で指定されたリポ数ぶんの `general-purpose` Subagent を **すべて並列で** 投げる (1 メッセージ内で複数 Agent 呼び出し)
- Subagent は各自で `gh repo clone` してリポ全体を Read/Grep/Glob で参照し、観点に沿ってレビューする
- 結果は `docs/review/all/{repo}/{実行日時}.md` (common リポ配下、gitignored) に書き出す
- Issue 起票はしない (全体スキャンは指摘量が多くなり Issue を埋もれさせるため、ファイル出力とチャットサマリのみ)
- 全 Subagent 完了後、親が結果を集計しチャットにサマリを返す (集約 index ファイルは生成しない)

## 重要度の定義

各指摘には下記いずれかの重要度を必ず付ける。silent に省略しないこと。

| 重要度 | 適用基準 |
|---|---|
| `critical` | 本番影響リスクあり (バグ・セキュリティ脆弱性・データ破損・認証認可の穴) |
| `high` | 設計違反・主要機能の不整合・dead code・エラー握りつぶし・テスト不足で再発リスクあり |
| `medium` | 構成乱れ・docs と実装の乖離・命名の一貫性欠如・責務分離の改善余地 |
| `low` | 軽微なコメント・スタイル・将来的な改善提案 |

判断に迷う場合は **高い方** を選ぶ (見落としを防ぐため)。

## 手順

### 0. 実行コンテキストのガード

このコマンドは overload-party-common リポジトリ専用 (対象が overload-party 配下のリポに固定されているため)。誤って他リポで実行された場合は即座に中断する。

```bash
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$REPO_ROOT" ] || [ ! -f "$REPO_ROOT/auto-review/repos.yaml" ] || [ ! -f "$REPO_ROOT/auto-review/review_criteria.yaml" ]; then
  echo "ERROR: /review-all は overload-party-common リポジトリ配下でのみ実行可能です (auto-review/ 配下の設定ファイルが見つかりません)。" >&2
  exit 1
fi
```

設定ファイルが見つからない場合はフォールバックせず、上記エラーをユーザーに報告して終了する。

### 1. 引数と設定ファイルの読み込み

- `$ARGUMENTS` を空白で split して対象リポ名リストを得る
  - 空なら使い方メッセージを返して終了 (フォールバックしない)
  - 非空なら下記の正規化を適用してから repos.yaml と突合する:
    - 引数が `overload-party-` で始まらない場合、`overload-party-` を前置する (例: `gateway` → `overload-party-gateway`)
    - 既に `overload-party-` で始まる場合はそのまま使う
  - 正規化後の名前が repos.yaml に存在しない場合は、フォールバックせず該当不明リポ名 (正規化後) と利用可能なリポ一覧をユーザーに報告して終了する (typo の silent skip 防止)
- @auto-review/repos.yaml を Read して各リポの `branch` を取得
- @auto-review/review_criteria.yaml を Read して観点を取得し、Subagent プロンプトに差し込む Markdown を組み立てる
  - フォーマット: 各カテゴリを `## {name}` セクション、items を箇条書きにする
  - YAML 構造に異常 (categories キー欠落 / items が空) があれば、フォールバックせずユーザーに報告して終了する

### 2. 出力ディレクトリ作成

JST で「実行日時」を計算する。同じ日に複数回走らせても上書きしないよう分単位まで含める。

```bash
RUN_AT=$(TZ=Asia/Tokyo date +%Y-%m-%d-%H%M)
REVIEW_ROOT="$REPO_ROOT/docs/review/all"
for repo in <対象リポ群>; do
  mkdir -p "$REVIEW_ROOT/$repo"
done
```

以降のテンプレート中の `{OUTPUT_PATH}` は `$REVIEW_ROOT/{repo}/{RUN_AT}.md` を指す (common リポ配下、`.gitignore` で除外済)。リポごとに 1 ディレクトリ・1 ファイルを持つ構造で、cross-repo の集約ファイルは生成しない。

### 3. Subagent への指示テンプレート

対象リポの各エントリ `(name, branch)` ごとに `general-purpose` Subagent を起動する。テンプレート中の `{...}` は親が埋める。`{REVIEW_CRITERIA_MD}` は Step 1 で組み立てた Markdown。

---

```
あなたは {repo} (ブランチ: {branch}) の自動コードレビュアです。
ブランチ HEAD のリポ全体をレビューしてください (差分ではなく現時点の全コード)。

## 出力ファイル
{OUTPUT_PATH}  (= docs/review/all/{repo}/{RUN_AT}.md)

## 手順

### Step 1: リポの取得

```bash
WORKDIR=/tmp/review-all-{repo}-{RUN_AT}
if [ -d "$WORKDIR" ]; then
  git -C "$WORKDIR" fetch --quiet origin {branch}
  git -C "$WORKDIR" reset --hard --quiet "origin/{branch}"
else
  gh repo clone kenyamaneko/{repo} "$WORKDIR" -- --branch {branch}
fi
git -C "$WORKDIR" rev-parse HEAD > "$WORKDIR/.review-head.txt"
```

### Step 2: コンテキスト構築

- リポルートを Read / Glob で把握し、ディレクトリ構成・README・主要ドキュメントを最初に読む
- 設計ドキュメント (ARCHITECTURE / docs/ / ADR 等) があれば必ず読む。実装が設計通りかを判定する根拠になる
- 主要ソースファイルを Read で全文読む。差分レビューではないので全体を把握する必要がある
- 必要に応じて Grep / Glob で参照関係を追跡し、責務分離・重複・dead code を確認する

リポが大きい場合でも、コード本体・テスト・設定・ドキュメントは網羅する。「サンプリングだけで終わらせない」「重要度判定の根拠を曖昧にしない」を守ること。

### Step 3: レビュー観点

下記すべての観点で評価する。1 つでも該当する指摘があれば Step 4 で Markdown に書き出す。すべて問題なければ "LGTM" とだけ書いて Step 5 へ。

{REVIEW_CRITERIA_MD}

### Step 4: 結果ファイルの書き出し

`{OUTPUT_PATH}` に Markdown で書く。各指摘には重要度 `critical` / `high` / `medium` / `low` のいずれかを必ず付ける (定義は親プロンプトの「重要度の定義」セクションに従う)。判断に迷う場合は高い方を選ぶ。

フォーマット:

```
# {repo} 全体レビュー (HEAD: {commit-hash}, {RUN_AT})

## 重要度別件数
- critical: N
- high: N
- medium: N
- low: N

## 指摘

### {観点カテゴリ名}
- **重要度**: critical
- **ファイル**: `path/to/file.go:123-145`
- **指摘**: ...
- **改善案**: ...

### {観点カテゴリ名}
- **重要度**: high
- ...
```

指摘がない場合の本文は `LGTM` の一行のみとする (LGTM 判定のため後続処理が文字列マッチする)。

### Step 5: 親への返答

次の JSON 形式で 1 行返す。それ以外の冗長な文章は不要。`severity_counts` は Step 4 で集計した重要度別件数を入れる。

- LGTM: `{"repo": "{repo}", "status": "lgtm"}`
- 指摘あり: `{"repo": "{repo}", "status": "issues", "severity_counts": {"critical": N, "high": N, "medium": N, "low": N}, "review_path": "{OUTPUT_PATH}"}`
- 失敗: `{"repo": "{repo}", "status": "error", "error": "<短い説明>"}`

エラーは silent に握りつぶさず、必ず "error" ステータスで親に返すこと。
```

---

### 4. 並列ディスパッチ

Step 1 で確定した対象リポすべての Subagent を **1 メッセージ内で並列に呼び出す** こと。1 リポでも 1 並列として扱う (実装パターンを統一するため)。

### 5. 集約

全 Subagent の返答 (JSON 1 行) を集計し、Step 6 のチャット返答用にデータを準備する。指摘ありリポは **重要度の高い順** (critical → high → medium → low) でソートする (リポ内の最高重要度をソートキーにする)。

cross-repo の集約ファイル (index.md 等) は生成しない。サマリはチャット返答のみで完結させる。

### 6. ユーザーへの返答

チャットには下記を返す:

1. 1 行サマリ: `指摘あり: N / LGTM: N / 失敗: N`
2. 重要度別の合計件数: `critical: N / high: N / medium: N / low: N`
3. 指摘ありリポと結果ファイルパス (`docs/review/all/{repo}/{RUN_AT}.md`) の箇条書き (重要度の高い順)
4. 失敗リポとエラー概要 (あれば)

冗長な進捗ログや内部状態は出力しない。

## 失敗時の方針

- 個別 Subagent が失敗しても他の Subagent は継続させる (1 リポの失敗で全体停止しない)
- 失敗リポはチャット返答に明示する。silent に欠落させない
- 親自身が失敗した場合 (引数解析・設定読み込み・日付計算・ディレクトリ作成等) は即座にユーザーへ報告する
