# ADR-029: 型を domain / wire / persistence の 3 層に物理分離する

## ステータス

Accepted (2026-04-30)

## 結論

wire 型が domain / persistence を兼任して依存方向が逆転していた構造を正すため、各サービスは型を **責務ごとに 3 つのレイヤに物理分離** する。service が wire 契約パッケージを import しない構造が別 module 境界により物理的に強制され、外部公開される型から内部状態機械・永続化詳細が消え、型変更の影響範囲が責務ごとに分離される。

## 背景・課題

[ADR-015](015-package-split.md) で「送信側サービスが契約型を所有」と決めた結果、各サービスは `packages/api-*` 配下に外部公開用の wire 型を持つ。ところが運用してみると、**この wire 型を service 層・repository 層も共用してしまう** 構造になりがちで、以下の問題が顕在化した（pioneer は overload-party-shop）。

1. **依存方向の逆転**: ビジネスロジック (service) が delivery 層 (wire 契約パッケージ) を import している。クリーンアーキテクチャ原則「ビジネスロジックは外部アダプターに依存しない」に反する。
2. **内部型の意図しない外部公開**: `packages/api-shop` は別 Go module で gateway 等が import する前提のため、`db:"..."` タグ付きの永続化モデルや内部状態機械の status 文字列までが外部に漏れる。
3. **変更の波及**: wire / DB row / domain entity が 1 つの型で兼用されているため、片方の変更がもう片方にも波及する。

事実上、`packages/api-*` が「wire / domain / persistence の混合層」になっていた。
