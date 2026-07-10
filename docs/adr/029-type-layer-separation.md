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

## 詳細

| レイヤ | 置き場所 | 役割 |
|---|---|---|
| domain | `internal/domain/` | エンティティ・値オブジェクト・状態機械定数・ドメインイベント |
| wire | `packages/api-<service>/` | REST request/response、webhook payload、Pub/Sub event の外部公開契約 |
| persistence | repository 実装内部 | DB 行マッピング (専用の row 型は持たず positional `Scan` で domain 型へ直接読み書き) |

依存方向:

- service / port は domain だけを扱う
- handler (REST) と adapter (Pub/Sub) のみが domain ⇄ wire 境界変換を担う
- repository は domain 型を読み書きする
- `packages/api-<service>/` は別 Go module で `internal/` を import できないため、依存方向は物理的に強制される

### inter-service event は domain と wire の両方に同形状で生成する

サービス間で発行されるイベント型 (例: `FactionPurchasedEvent`, `PremiumUpdatedEvent`) は **両レイヤに同形状で生成** する。

- producer (service) は domain 版を構築・JSON marshal する → wire 依存をなくすため
- 外部 subscriber (gateway 等) は wire 版を import して unmarshal する → 外部公開契約だから

`packages/api-<service>/` は別 module で `internal/domain` を import できず、共有型として参照させる手段がない。代わりに `data/models.yaml` の SSoT から両方に同形状を生成することで、二重定義の維持コストを codegen に閉じ込める。

### codegen の target 指定

`scripts/generate_types.py` (各サービス) は section 単位で `target: domain` / `target: wire` / `targets: [domain, wire]` を受け付け、出力先を切り替える。`db:"..."` タグの emit は廃止 (永続化型を持たない方針のため)。

### 適用範囲

新規サービスは本 ADR に従って構築する。既存サービスは順次移行し、移行タイミングは各サービス側で判断する。pioneer は **shop** ([overload-party-shop#31](https://github.com/kenyamaneko/overload-party-shop/issues/31)、完了)。CLAUDE.md / ARCHITECTURE.md でレイヤ分離方針を明示すること。

### 対象外

- DB row 型の codegen: 現状 pgx の positional `Scan` で domain 型に直接読み書きする運用が成立しているため、persistence 層に専用の codegen 対象は持たせない。将来 sqlc 等の導入時に再考する
- C# (battle) への適用: 言語と ORM 事情が異なるため、必要時に別 ADR で議論する

### トレードオフ

- inter-service event のみ重複定義が生じる。メンテコストは codegen に閉じ込めることで軽減
- handler / adapter で詰め替えコードが発生する
- 既存サービスの移行は機械的だが規模が大きい (shop の場合 40+ ファイル変更)
