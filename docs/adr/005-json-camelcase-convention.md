# ADR-005: JSON フィールド命名の camelCase 統一

## ステータス

Accepted（判断は 2026-03-06 頃、2026-04-22 に事後文書化）

> **注記**: この ADR は当時実際には起票されなかった設計判断を、後日、残存するメモと実装から推測して再構築したもの。**ただし決定内容そのものは現行コードで維持されている**。推測の根拠:
>
> - `docs/notes/PROMPT_WS_REPO_SPLIT.md` 末尾の「既存の命名規則の不一致（修正対象）」セクションに「**推奨:** JSON フィールドはすべて camelCase に統一する」と明記
> - 現行の Battle / Gateway / Client 実装を確認した結果、全レイヤで camelCase が採用されている
> - `docs/notes/GATEWAY_BATTLE_ARCHITECTURE.md` の「パススルー方針: Battle Server（C# ASP.NET）の CamelCase JSON 出力を `json.RawMessage` でそのままクライアントに中継する」との整合性

## 結論

言語ごとに指向が分かれていた JSON フィールド命名を、**camelCase に統一**する。TS と C# のネイティブ記法が camelCase で一致しており、Go だけタグで吸収すれば全体が揃う（snake_case を採用すると TS 側で毎回変換が必要になる）。

## 背景・課題

API 初期の実装で JSON フィールド名が混在していた：

| 現象 | 例 |
|------|-----|
| snake_case | `hand_instance_id`, `game_id`, `current_turn` |
| camelCase | `cardInstanceId`, `actionType` |
| ドキュメントバグ | `game_state` 内に `my` が 2 回出現 |

TypeScript ネイティブ流は camelCase、Go ネイティブ流は snake_case タグ、と言語ごとに指向が分かれるため、早期に方針を統一する必要があった。

## 詳細

| レイヤ | 内部表記 | JSON 上の表記 |
|--------|---------|-------------|
| Go struct | PascalCase | `json:"camelCase"` タグで変換 |
| C# (ASP.NET) | PascalCase | `JsonPropertyNamingPolicy.CamelCase` で自動変換 |
| TypeScript | camelCase (native) | camelCase (そのまま) |
| YAML 型定義 | snake_case（内部名） | `json:` フィールドで camelCase を明示 |

Gateway が Battle の JSON を**変換せずパススルーできる**のは、この命名統一が前提になっているため。ADR-002 のパススルー方針と密結合。
