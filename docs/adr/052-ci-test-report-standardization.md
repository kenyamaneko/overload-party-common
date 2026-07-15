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

## 不採用案

- **外部の Action (`dorny/test-reporter` など) の導入**: JUnit/TRX/JSON 等の主要フォーマットに標準対応済みで実装は速いが、`checks:write` 権限を要求するものが多く各リポの workflow 権限設定に手を入れるコストが見合わず不採用。
- **JUnit/TRX artifact の保持**: 後日の傾向分析には使えるが、`$GITHUB_STEP_SUMMARY` への書き出しと PR への指摘表示で当面の要求を満たせるため、保持期間の運用判断まで増やす理由が無い。傾向分析が必要になった時点で別途検討する。
- **各リポへの Issue の個別起票による追跡**: リポ固有の設計判断が残る監査系 Issue (#171 など) とは異なり、本件は標準そのものを本 ADR で先に確定するため、個別 Issue で再検討する余地が無い。

## Amendment: 2026-07-15 テスト観点カタログのための結果 artifact 保持の有効化

「保持しない範囲」と「不採用案」で、結果ファイルの artifact 保持を「傾向分析が必要になった時点で別途検討する」として先送りしたが、全リポのテスト名を横断集約するテスト観点カタログ (ADR-055) がこの集約を必要とするため、対象 13 リポのテスト結果ファイルの artifact 保持を有効化する。集約と公開の設計は ADR-055 に従う。
