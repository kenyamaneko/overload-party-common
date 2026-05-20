# Auto Review

各リポジトリのコードを Claude Code のスラッシュコマンドで並列レビューする自動コードレビューシステム。GitHub Issue 起票時のラベル名 (`auto-review`) と命名を揃えている。

提供コマンド:

| コマンド | 範囲 | 用途 |
|---|---|---|
| `/review-diff` | 前日 03:00 JST 以降の差分 | 毎朝の前日分レビュー |
| `/review-all` | ブランチ HEAD の全体 | 任意タイミングでのリポ全体スキャン |

`/review-diff` の起点を厳密な「前日 00:00」ではなく「前日 03:00 JST」に固定しているのは、深夜 1〜2 時台に日付を跨いで作業することがあるため。前日朝 3:00 を起点にすることで、その日の作業セッション全体 (前日朝〜実行直前) を取り逃さない。

## 使い方

Claude Code を **overload-party-common リポジトリ配下で** 起動し、`/review-diff` または `/review-all` を実行する。対象が overload-party 配下のリポに固定されているため、他リポでの実行はコマンド冒頭の Step 0 ガード (auto-review/ 配下の設定ファイル存在チェック) でブロックされる。

引数でリポを絞り込めば一部リポのみ対象にできる (`overload-party-` プレフィックスは省略可)。

```
/review-diff                  # 全リポ (前日差分)
/review-diff gateway          # overload-party-gateway のみ
/review-all gateway battle    # 2 リポ並列で全体スキャン
```

実行時の動作:

1. 当該日の `docs/review/diff/{前日日付}/` (`/review-diff`) または `docs/review/all/{実行日時}/` (`/review-all`) ディレクトリを common リポ配下に作成 (`.gitignore` で除外済)
2. 対象リポ (引数指定なら指定分、`/review-diff` で空なら [repos.yaml](repos.yaml) 全 17 リポ) に対して `general-purpose` Subagent を **並列**でディスパッチ
3. 各 Subagent が以下を担当:
   - `gh repo clone` でローカルにチェックアウト
   - `/review-diff` は前日 03:00 JST 以降の commit / 差分を `gh api` で取得 / `/review-all` は HEAD 全体を Read
   - リポ全体を Read/Grep/Glob で参照しながら [review_criteria.yaml](review_criteria.yaml) の観点で評価
   - 各指摘に重要度 (`critical` / `high` / `medium` / `low`) を付与
   - 結果を出力ディレクトリ配下の `{repo}.md` に書き出し
   - `/review-diff` で指摘ありなら各リポに GitHub Issue を起票 (`auto-review` ラベル、同タイトル既存ならスキップ)。`/review-all` は Issue 起票なし (指摘量が多くなり Issue を埋もれさせるため)
4. 親エージェントが出力ディレクトリ配下に `index.md` を集約生成 (重要度の高い順にソート)
5. チャットにサマリ (重要度別件数を含む) と Issue URL 一覧を返す

## 重要度

| 重要度 | 適用基準 |
|---|---|
| `critical` | 本番影響リスクあり (バグ・セキュリティ脆弱性・データ破損・認証認可の穴) |
| `high` | 設計違反・主要機能の不整合・dead code・エラー握りつぶし・テスト不足で再発リスクあり |
| `medium` | 構成乱れ・docs と実装の乖離・命名の一貫性欠如・責務分離の改善余地 |
| `low` | 軽微なコメント・スタイル・将来的な改善提案 |

判断に迷う場合は **高い方** を選ぶ運用 (見落とし防止)。

## 設定ファイル

### [repos.yaml](repos.yaml)

レビュー対象リポジトリと対象ブランチの SSoT。リポジトリを増減させたい場合はこのファイルだけ編集する。

### [review_criteria.yaml](review_criteria.yaml)

Subagent に渡すレビュー観点の SSoT。カテゴリと items を YAML で管理し、スラッシュコマンドが読み込んで Subagent プロンプトに展開する。

## スラッシュコマンドの実体

`.claude/commands/review-diff.md` および `.claude/commands/review-all.md` がオーケストレーション本体。Markdown 本文がそのまま Claude Code のプロンプトとして注入され、本ディレクトリの YAML を Read してから Subagent をディスパッチする。

スラッシュコマンドは Claude Code の規約上 `.claude/commands/` 配下にしか配置できないため、本ディレクトリと分離されている。
