# ADR-065: gateway の同時接続数上限 (250) を維持する

## ステータス

Accepted (2026-08-05)

## 結論

gateway の同時接続数上限を 250 のまま維持する。[ADR-058](058-gateway-on-cloudrun-single-instance.md) の単一インスタンス構成と [ADR-059](059-gateway-timer-state-in-memory-with-redis-backup.md) のインメモリ主の計時設計による制約であり、引き上げるとこれらの前提が崩れる。

## 背景・課題

Cloud Run への移行で gateway は最大インスタンス数 1 に固定され、対戦の計時もインメモリを主に持つ設計になった。この構成が同時接続数の上限を生んでいる。現時点で上限に近づく接続数には至っていないため、実際に接続数が増えてきた段階で改めて検討する。
