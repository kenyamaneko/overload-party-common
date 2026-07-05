# ADR-003: モノレポ → API/WS 2リポジトリ分割案（棄却）

## ステータス

Superseded by [ADR-002](002-battle-server-csharp-separation.md)（判断は 2026-03-06 頃、2026-04-22 に事後再構築）

> **注記**: この ADR は当時実際には起票されなかった設計判断を、**後日、残存するメモと git 履歴から推測して再構築**したものです。オリジナルの記録は存在しません。推測の根拠:
>
> - `docs/notes/PROMPT_WS_REPO_SPLIT.md`（mtime 2026-03-06）にこの提案の詳細が残存
> - 同ファイル冒頭に「旧アーキテクチャ (API/WS リポジトリ分離) の方針メモ」「現在のアーキテクチャ (Gateway + Battle Server) については GATEWAY_BATTLE_ARCHITECTURE.md を参照」との注記
> - 2026-03-03 に `overload-party-gateway` / `overload-party-battle` の初期コミット (`f98374e` / `a68a547`) が存在し、両方とも「split from monorepo」と記述
> - ADR-002 / ADR-007 の間に番号と日付のギャップがあり、003〜006 は起票されずに飛んでいる

## 結論

サーバーを REST API / WebSocket の 2 リポジトリに分割する案を棄却する。ADR-002 の採用により、分割軸は **REST/WS 軸** ではなく **責務軸（Gateway / Battle）** に変更された。

## 背景・課題

2026-02 末の段階では、サーバーは Go モノレポに REST API と WebSocket ハンドラが同居していた。WebSocket 通信仕様の不一致による不具合が頻発しており、サーバーとクライアント間の型共有の仕組みを整備する必要があった。

あわせて、モノレポの責務肥大による変更影響範囲の拡大が課題になっていた。

## 不採用案

### API/WS 2 リポジトリ分割（本 ADR の提案、棄却）

サーバーを 2 つのリポジトリに分割する：

| リポジトリ | 役割 |
|-----------|------|
| `overload-party-api` | REST API サーバー（Go、既存モノレポから分離） |
| `overload-party-ws` | WebSocket サーバー（Go、新規作成） |
| `overload-party-common` | 型の SSoT（YAML + 自動生成） |
| `overload-party-client` | TypeScript クライアント |

棄却理由（ADR-002 による分割軸の変更）:

- WebSocket は独立リポではなく **Gateway に同居**（Gateway が REST + WS の両方を持つ）
- Battle Server は **ステートレス REST のみ**で WebSocket を持たない
- Battle は Go ではなく **C#** で再実装
- マッチメイキングは Gateway 内部で完結

結果、`overload-party-ws` リポジトリは作成されず、代わりに `overload-party-gateway` / `overload-party-battle` の 2 リポ構成に帰着した。のちに ADR-011 (repository-split) で他サービスも含めた多リポ化方針が確立されている。
