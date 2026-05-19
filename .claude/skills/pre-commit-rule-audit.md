---
name: pre-commit-rule-audit
description: コミット直前に変更を rules/principles.md と該当リポの rules/lang/<lang>.md に照らして audit する。違反があれば file:line で列挙し commit を保留する。「audit して」「ルール check して」「commit 前に見直して」と依頼されたとき、また実装後 commit の直前に必ず実行する。
---

# コミット前のルール audit

`git diff` (staged + unstaged) を common の rules に照らして違反を列挙する skill。違反があれば commit を保留し、修正してから再 audit に進む。

## mental shortcut の禁止 (最重要)

この skill の各 step を「頭の中で済ませた」ことにしてはならない。step 1〜7 はすべて tool 呼び出し (Read / Bash) の実体を伴って実行する。次の行為は audit の**未実施**とみなす:

- commit メッセージや `echo` に「audit 済み」「違反 0」とだけ書く宣言
- step 3 のルールファイルを Read tool で読み直さず、記憶・会話文脈で代用すること (過去に読んでいても必ず再 Read する)
- step 5 の逐次照合を、diff を grep / 目視せずに「問題なし」と結論すること

「違反は無い」と仮定して始めない。違反を 1 つ以上見つける前提で探し、各ルール項目について diff の該当箇所を確認した結果としてのみ「違反 0」と報告する。

## 手順

1. **変更ファイル取得**: `git status --short` と `git diff --stat` で変更ファイル一覧を出す
2. **対象リポ判定**: 各変更ファイルのパスから対象リポを判定 (`./` 起点 / `../<repo>/`)
3. **適用ルール Read** (対象リポごとに resolve する):
   - 常に: common の `rules/principles.md`
   - 各リポ: common の `rules/repos.yaml` で対象リポの `lang` / `flow` を引いて `rules/lang/<lang>.md` / `rules/flow/<flow>.md` を Read (`none` はスキップ)
   - リポ固有: 対象リポの `docs/` 配下に追加ルールがあれば Read
4. **既存スタイル参照**: 編集ファイルが test なら同パッケージの既存 test を 1 本 Read してケース命名スタイル等の前例を把握
5. **逐次照合**: 上記で Read したルールの**各項目**に対し変更を audit する
6. **結果報告**: 違反 0 なら ✅ + commit OK / 違反 1 以上ならファイル単位で `path:line` 形式で列挙、commit 保留を明示
7. **修正後は再 audit**: 違反 0 まで繰り返し、その後初めて `git add` / `git commit` に進む

## 注意

- audit のみ。自動修正はしない (修正方針は別途確認)
- 対象は staged + unstaged 両方
- ルールは実行のたびに必ず Read (キャッシュ禁止)
