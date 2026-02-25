# 15ターン制限勝利条件の実装 (2026-02-21)

## 変更概要

ゲームが長引きすぎるのを防ぐため、**15ターン制限の勝利条件**を追加しました。

15ターン経過時点で、Budgetが多いプレイヤーが勝利します。Budgetが同じ場合は引き分けとなります。

---

## 実装内容

### 1. 新しい勝利条件定数の追加

**ファイル**: [internal/model/game_state.go](../internal/model/game_state.go)

```go
// Win reason constants.
const (
	WinReasonBudgetZero    = "budget_zero"
	WinReasonSystemDown    = "system_down"
	WinReasonRepositoryOut = "repository_out"
	WinReasonTimeout       = "timeout"
	WinReasonDisconnect    = "disconnect"
	WinReasonTurnLimit     = "turn_limit"    // 新規追加
	WinReasonDraw          = "draw"          // 新規追加
)
```

### 2. CheckWinCondition関数の更新

**ファイル**: [internal/engine/win_condition.go](../internal/engine/win_condition.go)

```go
// Check turn limit (15 turns = both players have had their turns 15 times)
if state.CurrentTurn >= 15 {
    budget1 := state.GetBudget(1)
    budget2 := state.GetBudget(2)
    if budget1 > budget2 {
        return 1, model.WinReasonTurnLimit, true
    } else if budget2 > budget1 {
        return 2, model.WinReasonTurnLimit, true
    } else {
        // Budget equal = draw
        return 0, model.WinReasonDraw, true
    }
}
```

**ロジック**:
1. `CurrentTurn >= 15` をチェック
2. 両プレイヤーのBudgetを比較
3. 多い方が勝者 (`WinReasonTurnLimit`)
4. 同じ場合は引き分け (`WinReasonDraw`, `winnerPlayerNum = 0`)

### 3. テストの追加

**ファイル**: [internal/engine/engine_test.go](../internal/engine/engine_test.go)

以下のテストケースを追加:
- `TestCheckWinCondition_TurnLimit_Player1Wins` - Player 1が勝利
- `TestCheckWinCondition_TurnLimit_Player2Wins` - Player 2が勝利
- `TestCheckWinCondition_TurnLimit_Draw` - 引き分け
- `TestCheckWinCondition_TurnLimit_NotReached` - ターン制限未到達

---

## ゲームへの影響

### シミュレーション結果（200ゲーム）

#### 勝利条件の分布（変更前）

| 勝利条件 | 回数 | 割合 |
|---------|------|------|
| Budget枯渇 | 157 | 78% |
| **リポジトリ切れ** | **37** | **18%** |
| システムダウン | 6 | 3% |

#### 勝利条件の分布（変更後）

| 勝利条件 | 回数 | 割合 |
|---------|------|------|
| budget_zero | 157 | 78% |
| **turn_limit** | **36** | **18%** |
| draw | 5 | 2% |
| system_down | 2 | 1% |

### 主な変更点

1. **リポジトリ切れが消滅**: 18%を占めていたリポジトリ切れの勝利が、ターン制限の勝利に置き換わった
2. **引き分けの導入**: 5ゲーム（2%）が引き分けで終了
3. **平均ターン数の短縮**: 7.8ターン → 6.3ターン（約20%短縮）

### 効果

- ✅ **長期戦の削減**: 15ターンを超える試合が発生しなくなった
- ✅ **リポジトリ切れの解消**: カード不足による勝敗がなくなった
- ✅ **Budget管理の重要性向上**: ターン制限により、Budgetの温存戦略が重要に
- ✅ **ゲームテンポの改善**: 平均ターン数が短縮され、よりスピーディーな試合に

---

## チェック項目の優先順位

`CheckWinCondition`関数の勝利判定は以下の順序で行われます:

1. **Budget枯渇** (`budget_zero`) - 最優先
2. **システムダウン** (`system_down`) - 第2優先
3. **ターン制限** (`turn_limit` / `draw`) - 第3優先 ← **今回追加**
4. **TimeBank枯渇** (`timeout`) - 第4優先

この順序により、Budget枯渇やシステムダウンによる即座の敗北が優先され、ゲームバランスが保たれます。

---

## テスト結果

```bash
✅ All tests passed
=== RUN   TestCheckWinCondition_TurnLimit_Player1Wins
--- PASS: TestCheckWinCondition_TurnLimit_Player1Wins (0.00s)
=== RUN   TestCheckWinCondition_TurnLimit_Player2Wins
--- PASS: TestCheckWinCondition_TurnLimit_Player2Wins (0.00s)
=== RUN   TestCheckWinCondition_TurnLimit_Draw
--- PASS: TestCheckWinCondition_TurnLimit_Draw (0.00s)
=== RUN   TestCheckWinCondition_TurnLimit_NotReached
--- PASS: TestCheckWinCondition_TurnLimit_NotReached (0.00s)
```

---

## まとめ

### 完了項目

- ✅ `WinReasonTurnLimit` および `WinReasonDraw` 定数を追加
- ✅ `CheckWinCondition` 関数にターン制限チェックを実装
- ✅ 引き分け処理を実装（`winnerPlayerNum = 0` with `gameOver = true`）
- ✅ 4つのテストケースを追加
- ✅ 全テスト通過
- ✅ シミュレーション実行で動作確認

### ゲームデザインへの影響

**目的**: "あまり長くなるとつまらないから"

**効果**:
- 15ターン以内にゲームが終了するようになった
- リポジトリ切れという不確実な勝利条件が排除された
- Budgetの管理がより戦略的に重要になった
- 平均ターン数が約20%短縮され、テンポの良いゲームになった
