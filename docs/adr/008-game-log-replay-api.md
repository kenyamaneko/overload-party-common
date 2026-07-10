# ADR-008: ゲームログ (リプレイ) API の設計

## ステータス

Accepted (2026-03-08)

## 結論

対戦終了後のリプレイ閲覧のため、ゲームログ生成ロジックを **バトルサーバー (C#) の Service レイヤー** (`GameLogService`) に集約し、Gateway は `GameLogHandler` + `BattleClient` によるプロキシのみで完結させる。カード名解決・NPC 判定・イベント定数を保持するバトルサーバーにロジックが閉じ、Gateway に依存が漏れない。

## 背景・課題

対戦終了後のリプレイ閲覧機能が必要になった。ゲームイベントは `game_events` テーブルに時系列で保存されており、これを人間可読な形式に変換して返す API を設計する必要がある。

## 詳細

### ロジックの配置場所: バトルサーバー

- `ICardCache` (カード名解決) はバトルサーバーが保持している
- `NpcConstants.IsNpcPlayer()` による NPC 判定もバトルサーバーの Npc レイヤーに存在する
- イベントタイプの定数 (`WireActionTypes`) もバトルサーバーの Models に定義されている
- Gateway 側にこれらの依存を持ち込むと責務分離 (ADR-002) に反する

イベント → 説明文変換は `EventData` の `Dictionary<string, object>` から値を抽出し、`ICardCache` でカード名を解決する。

### エンドポイント

| エンドポイント | Content-Type | 用途 |
|---|---|---|
| `GET /api/v1/games/{gameId}/log` | `application/json` | クライアントのリプレイ UI |
| `GET /api/v1/games/{gameId}/log/text` | `text/plain` | デバッグ・開発用 |

### JSON レスポンス構造

```json
{
  "game_id": "abc-123",
  "player1_id": "player-uuid",
  "player2_id": "npc-00000000-...",
  "winner": "player1",
  "win_reason": "system_down",
  "total_turns": 8,
  "duration_seconds": 222,
  "final_budget": { "player1": 1200, "player2": 0 },
  "entries": [
    { "seq": 1, "event_type": "play_card", "description": "P1 deployed \"えくぼ\" to Frontend [-300 Budget]" }
  ]
}
```

- `winner` は `"player1"` / `"player2"` / `null` (引き分け・未完了)
- `entries[].description` は各イベントを英語の人間可読文に変換したもの
- JSON プロパティは `snake_case` (外部 API 規約に準拠)

### テキスト出力

```
=== Game abc-123 ===
P1: player-uuid  vs  P2: npc-sd-01 (NPC)
Winner: P1 (system_down) | 8 turns | 3m42s
Final Budget: P1=1200  P2=0

[1] P1 deployed "えくぼ" to Frontend [-300 Budget]
[2] P1 attacked for 600 damage (destroyed) [SLA -400]
...
[42] Game over: P1 wins
```

### エラーハンドリング

| ケース | ステータス | レスポンス |
|---|---|---|
| ゲームが見つからない | 404 | `{"error": "game not found"}` |
| その他エラー | 500 | `{"error": "..."}` |

Gateway 側は 404 の場合 `getRaw` が `nil` を返す既存の仕組みでハンドリングする。
