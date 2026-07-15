# ADR-055: 全リポのテスト名を集約したテスト観点カタログを Pages に公開する

## ステータス

Proposed (2026-07-15)

## 結論

テストを読めば仕様が把握できる状態を保つため、テストを実行する全 13 リポのテスト名を common が 1 枚の**テスト観点カタログ**に集約し、common の GitHub Pages に公開する。テストの命名規約 (keyandnotes-rules testing.md「テストの命名」) がテスト名を仕様の一文として書くことを求めており、命名規約の適用は全リポで完了しているため、テスト名の集約がそのまま横断仕様のドキュメントになる。

- 各リポの CI は main でのテスト実行時に、自リポのテスト結果ファイルを artifact 化し、common へ `repository_dispatch` する。
- common の集約 workflow が dispatch を受け、全リポの最新のテスト結果 artifact を集め、言語別のパーサで共通モデルに正規化し、HTML を Pages に公開する。テスト名の階層の作り方が言語ごとに異なるため、パーサは言語ごとに新規実装する。
- カタログは「外から見た振る舞い」「内部の挙動」の 2 カテゴリに分けて示す。

これにより、全リポのテスト名を 1 枚のページで俯瞰でき、どの振る舞いがテストで担保されているかをリポを渡り歩かずに確認できる。

## 背景・課題

テストの命名規約により各ケース名は「〜のとき、〜すると、〜になる」の仕様の一文として書かれている。しかし各ケース名はテストコードに散在し、仕様の全体像を掴むには全リポのテストファイルを渡り歩く必要がある。単一リポの pokelingual では main への push (テスト実行) に紐づけてカタログを Pages へ公開しているが、overload-party は多リポ・多言語のため同じ配線を直に使えず、集約を common に集中させる。

ADR-052 で各リポの CI テストレポート出力は標準化済みで、各言語のテスト結果 (JSON・TRX・JUnit XML) を整形して `$GITHUB_STEP_SUMMARY` に出している。ただし ADR-052 は「結果ファイルは artifact として保持しない…傾向分析が必要になった時点で別途検討する」として結果の集約を先送りした。横断カタログはこの集約を必要とするため、本 ADR で対象リポの結果ファイルの artifact 保持を有効化する (ADR-052 に Amendment を追記する)。

考慮した制約は次の通り。

- private リポでも Pages サイト自体は誰でも閲覧できる。カタログの中身はテスト名 (振る舞いの記述) のみで、秘匿情報を含まない。
- CI コスト方針 (timeout-minutes・concurrency・paths) に従い、各リポに足す artifact と dispatch、および common の集約 workflow は軽量に保つ。

## 不採用案

- **pokelingual の generator を流用する**: Vitest と Playwright の JUnit 区切り専用で、`go test -json`・TRX・vitest JSON を扱えない。テスト名の階層の慣習が言語ごとに違うため、言語別パーサを新規に作る。
- **各リポが自分の Pages にカタログを公開する (リポ別)**: ADR-052 の artifact 判断に手を付けず配線も軽いが、全仕様を 1 枚で俯瞰する狙いが得られない。
- **各リポで共通中間形式に正規化してから artifact 化する**: 正規化ロジックが各リポ CI に分散する。パーサを common に集約すれば、言語追加時も common だけを触れば済む。
- **nightly schedule で集約する**: 配線は最も軽いが、カタログが最大 24 時間古くなる。main マージの `repository_dispatch` で即時に再公開する。

## Amendment: 2026-07-15 C# だけは中間形式を経由する

C# (battle) は対象要素を `[Trait("対象", "…")]` に、ケース名を `[Fact/Theory(DisplayName = "…")]` に持つ。しかしこの `対象` trait はどの標準の .NET テスト結果ファイルにも出力されない。TRX は DisplayName を testName に含むが trait を落とし、`JUnitXml.TestLogger` は trait も DisplayName も出さず英語のメソッド名を出す。そのため「テスト結果ファイルを言語別パーサで正規化する」という本文の方式は C# では成立せず、グループ階層を作れない。

そこで C# に限り、パーサの入力を標準のテスト結果ファイルではなく battle が抽出した中間 JSON にする。battle は抽出ステップ (テスト DLL のリフレクション、または `.cs` ソースの走査) で `[Theory]` を各行に展開しつつ `{target, case, skipped, source}` の平坦なレコードを出力し、common の `csharp-json` パーサがそれを共通モデルに正規化する。パーサと正規化は本文どおり common に残るため、これは不採用案「各リポで共通中間形式に正規化してから artifact 化する」(正規化を各リポ CI に分散させる案) とは異なる。他の 3 言語 (Go の `go test -json`・Python の JUnit XML・TS の vitest JSON) は本文どおり結果ファイルを直接パースする。
