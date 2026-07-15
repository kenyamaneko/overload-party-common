# ADR-028: E2E / クロスサービス統合テストの戦略

## ステータス

Accepted (2026-04-26)

## 結論

複数サービスを跨ぐ業務シナリオを検証するため、新規リポジトリ `overload-party-e2e` を作成し、gateway のみを入口とする TypeScript + Playwright Test のクロスサービス E2E を手動実行で運用する。クロスサービス業務シナリオを必要時に検証でき、クライアント完成前から battle 含む WS ライフサイクルを capture できる。型は gateway の npm パッケージ 1 本に依存するため手書き request/response 型を持たず、自動 CI を置かないことで dev/stg の停止運用と整合する。

## 背景・課題

ADR-024 で各サービスは `integration` build tag による自リポジトリ内統合テスト、`cloud_integration` tag による stg 向けスモークを持つ。これらはサービス境界の正しさを担保するが、複数サービスを跨ぐ業務シナリオ（例: ショップ購入 → account へ伝播）や、gateway の WS 終端を通したマッチメイキング → battle のライフサイクルを検証できない。

サービス数は phase 1 で gateway / account / matchmaking / shop / scenario / card / battle の 7 つ。client UI は未完成、battle のロジックは不安定だがエンドポイントは整備済み。

## 不採用案

- **自動 cron による夜間 stg 実行**: 却下。dev/stg 停止運用と矛盾する。
- **直接 Pub/Sub を購読する subscriber fixture**: 却下。gateway を介さないと「客が見える状態」を検証していない。
- **`overload-party-infra` に compose を置く**: 却下。infra は本番向けの責務に閉じ、テスト用 compose は e2e で完結させる。
- **Go で書く（各サービスと同じ言語）**: 却下。UI E2E（Playwright）と同じランナーで継続するため TS。
- **各サービスの内部 event 型を再公開する**: 却下。gateway 観測点で十分。ADR-015 の方針も維持。
