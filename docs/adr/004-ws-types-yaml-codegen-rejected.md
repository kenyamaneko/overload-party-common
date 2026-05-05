# ADR-004: WebSocket 型の YAML SSoT 化と Go/TS 自動生成（棄却）

**Status:** Superseded (retrospectively reconstructed)
**Date:** 2026-03-06 頃 (推定)
**Superseded by:** ADR-002 (battle-server-csharp-separation) / `GATEWAY_BATTLE_ARCHITECTURE` のパススルー方針
**Reconstructed:** 2026-04-22

---

> **注記**: この ADR は当時実際には起票されなかった設計判断を、後日、残存するメモと git 履歴から推測して再構築したもの。ADR-003 と同一の検討パッケージに含まれていた。

## 背景

WS 通信型をサーバー側（Go）とクライアント側（TS）で手書きしていたため、フィールド名・optional 性・enum 値の不一致による不具合が発生していた。

## 決定（案）

WebSocket メッセージ型を `overload-party-common/data/ws/*.yaml` で一元定義し、Python スクリプトで Go struct と TypeScript interface を自動生成する：

```
data/ws/
  ├── types.yaml            # 共有サブ型 (CardInstance, FieldState, Position 等)
  ├── server_messages.yaml  # Server → Client メッセージ
  └── client_messages.yaml  # Client → Server メッセージ

scripts/generate_ws_types.py
  → overload-party-ws/internal/ws/types_gen.go
  → overload-party-client/src/generated/ws_types.ts
```

### 型の表記ルール（案）

- プリミティブ: `string`, `int`, `bool`, `float`
- 参照型: `TypeName`（types.yaml 内の別型、または constants.json の enum）
- 配列: `TypeName[]` / nullable 配列要素: `TypeName?[]`
- object（構造不定）: `object`（Go: `json.RawMessage`、TS: `Record<string, unknown>`）

## 棄却理由

Battle を C# に移行し、Gateway がその JSON を `json.RawMessage` でパススルーする方針（ADR-002）に変更されたため、**Gateway 側で WS メッセージ型を Go struct として持つ必要がなくなった**。

現行の型共有方針：

- ゲーム状態型は `data/models.yaml` から **C# + TS のみ**生成（Go 側は生成しない）
- Battle (C#) の CamelCase JSON を Gateway が中継
- WS メッセージは薄いエンベロープ（`{ type, data }`）のみ型付け

Go ↔ TS の双方向 codegen は実装されず、`generate_ws_types.py` も作成されなかった。

## 推測の根拠

- `docs/notes/PROMPT_WS_REPO_SPLIT.md` の「YAML スキーマ仕様」「generate_ws_types.py」セクションに詳細記載
- `scripts/generate_ws_types.py` は現在のリポジトリに存在しない
- 現行では `data/models.yaml` → C# + TS 生成が採用されており、方針の差し替えが確認できる
