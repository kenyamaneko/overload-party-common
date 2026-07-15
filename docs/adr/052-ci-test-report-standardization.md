# ADR-052: CI テストレポート出力を標準化する

## ステータス

Accepted (2026-07-10)

## 結論

テストを実行する 13 リポの CI で、テストの成否と失敗したテスト名を人間が読める形で出力する。各言語のテストコマンドが出す結果 (JUnit XML / TRX / JSON) を自前スクリプトで表形式に整形し、`$GITHUB_STEP_SUMMARY` に書き出す。失敗したテストについては workflow コマンド (`::error::` など、GitHub Actions が実行ログから読み取って処理する特殊な文字列) を使い、PR の diff 上に行単位で指摘を表示する。外部の **Action**（`uses:` で step に組み込める、他者が公開している再利用可能な処理のかたまり。`dorny/test-reporter` などが該当する）は導入しない。結果ファイルは artifact として保持しない。単体テストと結合テストの両方を対象にする。

これにより、CI が落ちたときに Actions の生ログを目で追わなくても、どのテストが失敗したかを PR の diff 上と `$GITHUB_STEP_SUMMARY` から直接確認できるようになる。

## 背景・課題

overload-party 全リポの CI はテストを実行しているが、その結果を人間が読める形で外に出す配線がほぼ無い。落ちたテストの一覧やカバレッジの詳細は、GitHub Actions の生ログを目で追う以外に観測手段が無い。

2026-07-10 時点で各リポの `ci.yaml` を確認したところ、以下のとおりだった。

| リポ | 言語 | テスト実行 | 現状のレポート出力 |
|---|---|---|---|
| gateway | Go | 単体 + 結合 | カバレッジ合計 1 行のみ (`go tool cover -func \| tail -1 >> $GITHUB_STEP_SUMMARY`) |
| account / card / matchmaking / news / scenario / shop | Go | 単体 + 結合 | なし |
| support | Go | 単体 | なし |
| analytics | Go | 単体 | なし |
| battle | C#/.NET | `dotnet test` | なし (`--logger trx` もカバレッジ収集も無し) |
| client | TypeScript | `npm run test:run` | なし |
| newsfeed | Python | `pytest -v` | なし |
| common | Python | `pytest -v` (scripts / doc-tools / codegen-tools) | なし |

JUnit XML / TRX の出力、PR 上への指摘表示、結果 artifact のいずれかを行っているリポは 0 だった。gateway のカバレッジ出力もテスト個々の成否ではなく数値のメモに留まる。

## 制約

- 4 言語 (Go / C# / TypeScript / Python) でテストコマンドの出力形式が異なる (`go test -json`、`dotnet test` の TRX、vitest の JSON/JUnit、pytest の JUnit XML) ため、共通の 1 スクリプトでは賄えず言語ごとに整形スクリプトが要る。
- `$GITHUB_STEP_SUMMARY` には書き込みサイズの上限があるため、失敗テスト数が極端に多い場合は出力を切り詰める配慮が実装時に要る。
- 外部の Action (`dorny/test-reporter` など) は `checks:write` 権限を要求するものが多く、各リポの workflow 権限設定に手を入れる必要がある。

## 詳細

### 対象範囲

テストを実行している 13 リポ全てで、単体テストの step と結合テストの step の両方を対象にする: account / analytics / battle / card / client / common / gateway / matchmaking / news / newsfeed / scenario / shop / support。

### 配置場所

整形処理は言語ごとに 1 本、`overload-party-common` の `.github/actions/<lang>-test-report/` に composite action として実装する: `go-test-report` / `csharp-test-report` / `ts-test-report` / `python-test-report`。各リポの workflow は `uses: kenyamaneko/overload-party-common/.github/actions/<lang>-test-report@main` で参照する。ADR-033 で auth 用 composite action を common に集約したのと同じ構成であり、Go 9 リポ・Python 2 リポ (common / newsfeed) が同じ整形処理を共有するため、修正箇所を 1 か所に保てる。

### 出力手段

外部の Action には依存せず、自前スクリプトで整形する。gateway が既に採用している `$GITHUB_STEP_SUMMARY` 直書きの形をそのまま延長できる。

言語ごとの入力形式:

- **Go**: `go test -json` の出力を整形する。
- **C# (battle)**: `dotnet test --logger "trx;LogFileName=test-results.trx"` で生成した TRX を整形する。
- **TypeScript (client)**: vitest の `--reporter=json` オプションが出す JSON を整形する。
- **Python (common / newsfeed)**: `pytest --junitxml=report.xml` で生成した JUnit XML を整形する。

各整形処理は、以下 2 種類の出力を行う。

- **`$GITHUB_STEP_SUMMARY` への書き出し**: 通過数・失敗数と、失敗したテスト名の一覧を表形式で追記する。gateway の既存カバレッジ出力はそのまま残し、テスト結果サマリを追加する形にする。
- **PR への指摘表示**: 失敗したテストについて `::error file=<path>,line=<line>::<message>` の workflow コマンドを出力し、PR の diff 上に行単位で指摘を表示する。

### 保持しない範囲

JUnit XML / TRX 等の結果ファイルは artifact として保持しない。

### 展開方法

本 ADR に基づき、各リポへ直接 PR で展開する。リポごとの追跡 Issue は立てず、ADR-038 / ADR-049 と同様に本 ADR を追跡の単位とする。

## 不採用案

- **外部の Action (`dorny/test-reporter` など) の導入**: JUnit/TRX/JSON 等の主要フォーマットに標準対応済みで実装は速いが、制約に示した権限追加のコストが見合わず不採用。
- **JUnit/TRX artifact の保持**: 後日の傾向分析には使えるが、`$GITHUB_STEP_SUMMARY` への書き出しと PR への指摘表示で当面の要求を満たせるため、保持期間の運用判断まで増やす理由が無い。傾向分析が必要になった時点で別途検討する。
- **各リポへの Issue の個別起票による追跡**: リポ固有の設計判断が残る監査系 Issue (#171 など) とは異なり、本件は標準そのものを本 ADR で先に確定するため、個別 Issue で再検討する余地が無い。

## Amendment: 2026-07-15 テスト観点カタログのための結果 artifact 保持の有効化

「保持しない範囲」と「不採用案」で、結果ファイルの artifact 保持を「傾向分析が必要になった時点で別途検討する」として先送りしたが、全リポのテスト名を横断集約するテスト観点カタログ (ADR-055) がこの集約を必要とするため、対象 13 リポのテスト結果ファイルの artifact 保持を有効化する。集約と公開の設計は ADR-055 に従う。
