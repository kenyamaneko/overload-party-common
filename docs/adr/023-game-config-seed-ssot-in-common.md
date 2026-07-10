# ADR-023: game_config 初期値 SSoT の common 移管と seed の runner 化

## ステータス

Accepted (2026-04-22)

本 ADR は [ADR-017](017-game-config-firestore.md) 実装時の初期値投入方式（`ops/firestore-seed/seed_game_config.py` に初期値を Python literal で埋め込み投入）を部分的に上書きする。SSoT の置き場を ops の Python literal から common の YAML に移す変更で、ADR-017 の主決定（Firestore 採用）と運用原則（運用中は Firestore が SSoT、書き込みは運営オペレーター + ops SA に限定）は維持する。

## 結論

ゲームバランス設計値が operations リポに分散していた歪みを正すため、`overload-party-common/data/game_config_defaults.yaml` を新設して Firestore `game_config` 初期値の SSoT とし、`ops/firestore-seed` は YAML を取得・適用するだけの runner に refactor する。common/data 配下でゲーム設計値を一望でき（`deck_size` と同じ場所）、ops は db-migrate と役割分担が揃った pure runner になり、設計値の変更は common の PR 1 本で完結する。lock file パターンの再利用により、将来追加する seed 系も同じ形で拡張できる。

## 背景・課題

ADR-017 の実装に伴い、[ops/firestore-seed/seed_game_config.py](../../../overload-party-ops/firestore-seed/seed_game_config.py) に Firestore `game_config` コレクションの初期値 7 キーが Python の `DEFAULT_VALUES` dict として literal で埋め込まれた。投入対象の値は以下：

- `free_daily_battle_limit` / `premium_daily_battle_limit`（日次バトル上限）
- `initial_time_bank`（バトル開始時のタイムバンク）
- `exp_win` / `exp_loss` / `exp_draw` / `exp_formula_coefficient`（経験値計算）

これらの性質を精査すると、いずれも**ゲームバランス設計値**であり、common/data の `deck_size: 30`（[game_design_constants.yaml](../../data/game_design_constants.yaml)）と同類の「ゲーム設計そのもの」だった。運用開始後は Firestore 上で動的に触る性質（ADR-017 の決定）は変わらないが、**初期値の起点はゲーム設計であって運用ではない**。

この配置は次の観点で歪みがあった：

1. **game design content が operations repo に分散配置されている**: common/data にはゲーム定数（zone / rank / card types / faction / deck_size 等）が集約されているのに、`game_config` 初期値だけが ops の Python に散っていた。common を読んでも全設計値を一望できない
2. **db-migrate の役割分担から逸脱している**: [ADR-014](014-db-schema-split-per-service.md) 後に確立した `ops/db-migrate/schemas.lock.yaml` + `fetch-schemas.py` パターンは「**各リポが SSoT、ops は pin / fetch / apply の runner**」という明確な役割分担。firestore-seed だけがこのパターンに従っていなかった
3. **設計値の変更時に ops の Python を触る必要がある**: ゲームデザイン調整（経験値係数変更など）に ops repo への PR が必要になり、game design レイヤーと operations レイヤーの境界が曖昧になっていた

## 制約

- ゲーム設計値の SSoT を common に集約する（`deck_size` と同じ原則）
- ops リポは「取得 + 適用」の runner に徹する（db-migrate と同一責務）
- 運用中の Firestore を SSoT とする ADR-017 の原則は崩さない（初期投入のみが本 ADR の対象）
- repo 間の参照は既存の lock file パターンに揃える（新規メカニズムを増やさない）

## 詳細

### SSoT の置き場

- `overload-party-common/data/game_config_defaults.yaml` を新設し、Firestore `game_config` 初期値の SSoT とする
- 各エントリは `key` → `{ value, description }` の構造。value の型は YAML 型がそのまま Firestore の number / string / bool に対応
- **運用中の値は Firestore 自体が SSoT**（ADR-017 維持）。本 YAML は初期投入時のみ参照され、運用開始後に変更しても既存ドキュメントには反映されない

### ops/firestore-seed の役割

- `seed_game_config.py` のハードコード dict を削除し、YAML 読み取り駆動に refactor
- 2 つの取得経路をサポート：
  - `--source PATH`: ローカルパスの YAML を直接読む（sibling checkout された dev workstation 向け）
  - `--fetch`: `seed-sources.lock.yaml` 記載の ref で common から sparse-clone して取得（CI / 再現性確保向け）
- `seed-sources.lock.yaml` を新設し、`db-migrate/schemas.lock.yaml` と同じ構造で common の ref を pin する

### 配置ルール

- 定数／設定値の置き場判断基準は [docs/architecture/DATA_DESIGN.md §定数／設定値の配置ルール](../architecture/DATA_DESIGN.md#定数設定値の配置ルール) に集約する（3 分類: ゲーム語彙 / 運営チューニング値 / サービス固有設定）
- 運営チューニング値の「SSoT」列は **初期値: common の YAML / 運用中: Firestore** と明示する

### トレードオフ

- `seed_game_config.py` の CLI 互換性が破壊される（`--source` or `--fetch` の明示が必須化）。ただしこのスクリプトは ADR-017 実装直後で実運用前のため、影響範囲は限定的
- `--fetch` 経路を CI で使う場合は GitHub PAT（private repo アクセス権）が必要。db-migrate と同等のコスト
- 運用オペレーターが「初期値は common の YAML」「運用中の値は Firestore Console」と 2 箇所を意識する必要がある。境界は DATA_DESIGN に明文化することで対応
- Firestore への書き込み権限モデル、fail-fast 原則、エミュレーター構成は ADR-017 のまま変わらない

### 実装記録

実装は本 ADR 作成と同時に完了済み：

- common `676d32d`: `feat: 定数／設定値の配置ルールを明文化し Firestore game_config 初期値を SSoT 化`
- ops `551841d`: `refactor(firestore-seed): common 側 YAML を SSoT として seed を再構成`

Firestore エミュレーターによる動作確認済み（7 キー投入、冪等 skip、`--overwrite`、fail-fast いずれも OK）。

### 今後の拡張

- 将来 Firestore に別コレクションを追加する際は、本 ADR の SSoT/runner パターンを踏襲する（common/data/*.yaml + ops/firestore-seed/seed-sources.lock.yaml へエントリ追加）
- CI で `--fetch` 経路を自動実行する場合は `.github/actions/firestore-seed/` 相当の composite action を用意（ADR-017 の Firestore エミュレーター用 composite action に倣う）。本 ADR 時点では手動実行運用のため未着手
