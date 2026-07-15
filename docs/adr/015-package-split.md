# ADR-015: 共通パッケージ分割と SSoT 分散

## ステータス

Accepted (2026-04-11、Phase 6/7 完了)

## 結論

パッケージ所有をサービス境界と一致させるため、パッケージを **責務単位（RPC / 共通データ / ゲームデザイン）** に分類し直し、**所有サービスのリポジトリに物理配置する**。あわせて SSoT (YAML) も所有サービスのリポジトリに分散させ、各サービスが自分の契約と定数を完全に所有する構造を採る。契約変更の影響範囲が所有サービスに閉じ、gateway はバトルエンジンの内部 enum を知る必要がなくなり、common は「ゲームデザインの SSoT + 横断設計書」のみに縮小してランタイム依存がなくなる。カードマスターデータの配布経路は card サービスに一本化され、embed による SSoT 分散が解消される。

## 背景・課題

[ADR-011](011-repository-split.md) でリポジトリ単位のサービス分割を決定したが、common リポジトリの `packages/` 配下は依然としてモノリス時代の構造のままである。全サービスが参照する契約・型・マスターデータが 1 箇所に集約されており、「どのパッケージを誰が所有するか」がサービス境界と一致していない。本 ADR ではその解消方針を定める。

1. **責務の混在**: `packages/gamedata-dotnet` が以下 4 種類の責務を抱えている。
   - `BattleGatewayRpc_gen.cs`: battle ↔ gateway の RPC envelope 契約
   - `GameStateView_gen.cs` / `EventData_gen.cs`: battle が生成し client が表示する state / event payload
   - `GameConstants_gen.cs` / `VariantTypes_gen.cs`: ゲームロジック enum とゲームデザイン定数が混在
   - `cache/cards_gen.json`: カードマスターデータの embed
   これは `packages/gamedata-npm` でも同様である。

2. **カードマスターの所有権のズレ**: [ADR-011](011-repository-split.md) の責務分担では card サービスがカードマスター (`card_definitions`) の所有者となる。しかし現状は `packages/devdata/cache/cards_gen.json` や `packages/gamedata-dotnet/cache/cards_gen.json` として複数の embed が並存しており、「所有は card サービス、配布は embed」という状態が責務境界と食い違っている。

3. **SSoT が common に集中**: `data/constants.yaml`、`data/models.yaml`、`data/event_schemas.yaml` の全てが common 配下にあり、各サービスが自分の契約や定数を編集するには必ず common を経由する。サービスが「自分の契約 = 自分の所有物」として扱えない。

4. **契約の所有者が不明確**: 各 RPC パッケージをどのサービスが publish・バージョニングするかの責任が決まっていない。現状は common が全部まとめて publish しているため、例えば account の API 型を 1 フィールド追加するだけで common 全体のパッケージバージョンが上がる。

5. **ゲーム定数の分類不足**: `data/constants.yaml` に全ての enum・定数が混在している。実際に gateway のコードベースを調べると、gateway が参照しているのは以下のようにごく一部である。
   - WS メッセージタイプ (gateway 自身が所有すべき)
   - `WinReason` / `EventType` / `ActionType` の一部（battle との RPC 判定で使う）
   - `Faction` / `DeckSize` / `RestrictionCopyCount`（ゲームデザイン定数）
   にもかかわらず、現状では gateway が `TriggerType` や `EffectOp` や `BuffType` といったバトルエンジンの内部 enum まで同じパッケージから読み込む状態になっており、依存範囲が不必要に広い。