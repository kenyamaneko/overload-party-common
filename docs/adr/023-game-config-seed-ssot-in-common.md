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
