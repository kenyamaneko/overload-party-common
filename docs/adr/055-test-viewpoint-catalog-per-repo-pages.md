# ADR-055: テスト観点カタログを各リポの GitHub Pages に公開する

## ステータス

Proposed (2026-07-15)

## 結論

テストを読めば仕様が把握できる状態を保つため、テストを実行する各リポが自リポのテスト名から**テスト観点カタログ**を生成し、自リポの GitHub Pages に公開する。生成ロジック (言語別パーサ・レンダラ) は common の `packages/doc-tools` に SSoT として実装し、各リポはこれを `pip install` して利用する。テストの命名規約 (keyandnotes-rules testing.md「テストの命名」) がテスト名を仕様の一文として書くことを求めており、命名規約の適用は全リポで完了しているため、テスト名がそのまま各リポの仕様ドキュメントになる。

- 各リポの CI は main でのテスト実行時に、自リポのテスト結果ファイルから `doc-tools` でカタログを生成し、自リポの GitHub Pages に公開する。common への artifact 送信・dispatch・cross-repo 集約は行わない。
- カタログは「外から見た振る舞い」「内部の挙動」の 2 カテゴリに分けて示す。テスト名の階層の作り方が言語ごとに異なるため、パーサは言語ごとに `doc-tools` へ実装する。
- common は各リポの Pages URL への静的なリンク一覧 (インデックスページ) を自身の Pages に公開し、全リポを横断する入口を提供する。

これにより、各リポが自分のテスト観点カタログを自分の CI だけで完結して公開でき、他リポへの書き込み権限・cross-repo の artifact 取得・集約 workflow の同時実行制御が一切不要になる。common のインデックスページから、全リポのカタログへ辿り着ける。

## 背景・課題

テストの命名規約により各ケース名は「〜のとき、〜すると、〜になる」の仕様の一文として書かれている。しかし各ケース名はテストコードに散在し、仕様の全体像を掴むには全リポのテストファイルを渡り歩く必要がある。単一リポの pokelingual では main への push (テスト実行) に紐づけてカタログを Pages へ公開しており (ADR-014)、この配線はリポ内で完結する。

overload-party は 13 リポにまたがるため、当初は common に集約する設計を検討した。各リポの CI が結果を artifact 化し common へ `repository_dispatch` し、common の集約 workflow が cross-repo でこれを取得して 1 枚の Pages に統合する案である。しかし実装検証で次のコストが判明した。

- common への書き込み (`repository_dispatch`) には Contents:Write 権限を持つ GitHub App が要り、対象 13 リポ全てに App の secret を新規配布する必要がある
- common 側が全リポの artifact を横断取得するには cross-repo の Read 権限を持つ App が要り、「コード変更のない main push は artifact が無いため最新 run では取りこぼす」問題への対処も要る
- 単一 Pages 環境への同時 deploy を、複数リポの同時マージに対して concurrency で直列化する必要がある
- Go 9 リポは重複した `ci.yaml` を持ち、common の reusable workflow (ADR-054) への集約が前提になるが、これは実装検証時点で 0/9 リポで未完了であり、caller 化には required status check の再設定 (branch ruleset 更新) が付随する

これらは、各サービスが自身の CI/CD を独立に完結させるという境界 (各サービスが自身の master data の唯一の SSoT であるという原則の CI 版) と相性が悪い。各リポが自分の Pages に公開する方式なら、上記のコストは発生しない。

ADR-052 で各リポの CI テストレポート出力は標準化済みで、各言語のテスト結果 (JSON・TRX・JUnit XML) を整形して `$GITHUB_STEP_SUMMARY` に出している。カタログ生成はこの結果ファイルをその場で読むだけで完結するため、ADR-052 で先送りした artifact 保持の有効化は不要になる (ADR-052 の該当 Amendment を取り消す)。

考慮した制約は次の通り。

- private リポでも Pages サイト自体は誰でも閲覧できる。カタログの中身はテスト名 (振る舞いの記述) のみで、秘匿情報を含まない。
- CI コスト方針 (timeout-minutes・concurrency・paths) に従い、各リポに足す生成・公開 step は軽量に保つ。

## 不採用案

- **common に集約し 1 枚の Pages に公開する**: 全仕様を 1 枚で俯瞰できる利点はあるが、上記「背景・課題」のコストが大きく、各サービスの CI/CD 独立性を壊す。common のインデックスページ (リンク一覧) で「入口の一本化」だけを軽量に代替する
- **pokelingual の generator を流用する**: Vitest と Playwright の JUnit 区切り専用で、`go test -json`・TRX・vitest JSON を扱えない。テスト名の階層の慣習が言語ごとに違うため、言語別パーサを新規に作る
- **各リポで生成ロジックも個別実装する**: 言語追加・パーサ修正のたびに全リポへの横展開が要る。生成ロジックは common の `packages/doc-tools` に集約し、各リポは pip install するだけにする

## Amendment: 2026-07-15 C# だけは中間形式を経由する

C# (battle) は対象要素を `[Trait("対象", "…")]` に、ケース名を `[Fact/Theory(DisplayName = "…")]` に持つ。しかしこの `対象` trait はどの標準の .NET テスト結果ファイルにも出力されない。TRX は DisplayName を testName に含むが trait を落とし、`JUnitXml.TestLogger` は trait も DisplayName も出さず英語のメソッド名を出す。そのため「テスト結果ファイルを言語別パーサで正規化する」という本文の方式は C# では成立せず、グループ階層を作れない。

そこで C# に限り、パーサの入力を標準のテスト結果ファイルではなく battle が抽出した中間 JSON にする。battle は抽出ステップ (テスト DLL のリフレクション、または `.cs` ソースの走査) で `[Theory]` を各行に展開しつつ `{target, case, skipped, source}` の平坦なレコードを出力し、common の `csharp-json` パーサがそれを共通モデルに正規化する。パーサと正規化は本文どおり common に残るため、これは不採用案「各リポで生成ロジックも個別実装する」とは異なる。他の 3 言語 (Go の `go test -json`・Python の JUnit XML・TS の vitest JSON) は本文どおり結果ファイルを直接パースする。

## Amendment: 2026-07-31 生成ロジックの届け方を composite action にする

本文は「各リポはこれを `pip install` して利用する」としていたが、各リポへの届け方を common の composite action に改める。common は private なので、各リポから直接取得するには cross-repo の資格情報が要る。この資格情報を持たないリポがあり、揃えるには新たな配布が要る。composite action は common の Actions アクセス設定だけで全リポから参照でき、追加の資格情報を要さない。ADR-052 のテストレポート整形も同じ形で配っているため、経路が一つにまとまる。

生成ロジックを common に SSoT として置き各リポがそれを利用するという結論は変わらない。action が参照するのも common の生成ロジックであり、不採用案「各リポで生成ロジックも個別実装する」の棄却理由も変わらない。

カテゴリの振り分けは、どのセクションにも入らない由来があればカタログの生成を失敗させる。既定のカテゴリへ落とすと分類されないまま紛れ込むため、テストを持つパッケージが増えたときに振り分け設定の更新を強制する。
