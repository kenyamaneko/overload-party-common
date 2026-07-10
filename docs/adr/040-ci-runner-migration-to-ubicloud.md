# ADR-040: CI runner を Ubicloud に切り替える

## ステータス

Accepted (2026-05-12)。[ADR-038](038-ci-execution-time-reduction.md) のサードパーティ runner 却下判断 (不採用案「Ubicloud に集約」と Out of scope の Ubicloud 部分) を supersede する

## 結論

GitHub-hosted 超過課金を削減するため、CI runner を `ubicloud-standard-2` に切り替える。WIF 側は無改修で済むと判明したため、リスクは workflow ファイルの `runs-on:` 変更に限定される。

- **Phase 1 (canary)**: shop の `ci.yaml` のみ切替、実行時間と成功率を観測
- **Phase 2 (全リポ展開)**: canary で問題なしなら 17 リポ / 40 workflow / 101 ジョブの `runs-on:` を一括置換
- WIF / IAM 側の変更なし
- ADR-038 の paths-ignore / timeout-minutes / concurrency / step name ルールは引き続き適用

## 背景・課題

ADR-038 (2026-05-10) では Ubicloud を以下の理由で不採用とした:

- 利用可能リージョンが EU のみで、`asia-northeast1` Artifact Registry への push レイテンシ懸念
- 2026/5/1 以降は新規顧客が premium プランのみで月額削減幅が小さい
- 「純粋な runner 入れ替え」としても移行コストが見合わない

その後、判断材料が変わった:

- **移行コストが想定より小さい**: WIF Pool Provider の `attributeCondition` は `repository` allowlist のみで `runner_environment` 制約はなく、IP allowlist (VPC SC / authorized networks / Cloud Armor) も未設定。WIF 側は無改修で、実作業は workflow の `runs-on:` 一括置換のみ (約半日工数)
- **GitHub Actions 超過課金の圧が増大**: ADR-038 の構造的最適化 (paths-ignore / timeout / concurrency) だけでは追いつかない見通しになった
- レイテンシ懸念は canary で実測する

## 詳細

### トレードオフ

- Ubicloud へのベンダロックインが発生 (ADR-038 の「ベンダロックインなし」を放棄)
- EU リージョン経由のため deploy 系で Artifact Registry push のレイテンシ増の可能性 → canary で計測
- self-hosted runner 課金 ($0.002/min, 2026/3/1〜) が GHA 側に乗る可能性は ADR-038 と同じく要観察
