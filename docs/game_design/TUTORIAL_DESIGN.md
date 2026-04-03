# チュートリアル設計書

## 概要

初回プレイヤーがバトルの基本を学ぶための**ガイド付き NPC 対戦**。ナビゲーターのカフカがバトル画面上にオーバーレイで登場し、フェーズごとに操作を案内する。

**設計方針:**
- バトルエンジンそのものは変更しない（通常の NPC 戦と同じルールで動く）
- チュートリアル専用の制御は**クライアント側のオーバーレイ + サーバー側の固定デッキ順序**で実現
- チュートリアルスクリプトは **プレーンテキストファイル**（`.tut`）で管理。メタデータ（`@trigger` 等）と台詞を1ファイルに同居させ、テキスト表示には既存の useTypewriter のみ再利用する（ストーリーエンジン本体は使わない）
- カフカの台詞ウィンドウは**画面上部 30%**（相手の手札〜フィールド上部の領域）に一時表示し、台詞完了後にフェードアウト。**常時表示しない**
- 全3章構成。1章あたり約3〜5分

---

## アーキテクチャ

### 全体構成

```
                        ┌──────────────────────────────┐
                        │    TutorialOverlay (Client)   │
                        │  ┌──────────────────────────┐ │
                        │  │  KafkaBubble（台詞表示）    │ │  ← カフカの台詞
                        │  │  + HighlightMask          │ │  ← 操作対象のハイライト
                        │  │  + ForceAction            │ │  ← 強制アクション指示
                        │  └──────────────────────────┘ │
                        └────────────┬─────────────────┘
                                     │ z-60 overlay
┌────────────────────────────────────┼──────────────────┐
│              BattleFieldPage       │                   │
│  ┌────────────┐ ┌────────────┐    │                   │
│  │ Opp Field  │ │ Center HUD │    │                   │
│  ├────────────┤ ├────────────┤    │                   │
│  │ My Field   │ │  My Hand   │    │                   │
│  └────────────┘ └────────────┘    │                   │
└───────────────────────────────────┘                   │
                                                        │
                    WebSocket (通常通り)                  │
                        ↓                               │
┌───────────────────────────────────┐                   │
│        Gateway (Go)               │                   │
│  tutorial_mode フラグ付きで        │                   │
│  NPC 戦を開始                     │                   │
└──────────┬────────────────────────┘                   │
           ↓                                            │
┌───────────────────────────────────┐                   │
│        Battle (C#)                │                   │
│  ・固定シャッフル順（seed指定）     │  ← tutorial_seed  │
│  ・NPC AI は通常の StandardAi     │                   │
│  ・チュートリアル専用デッキ使用     │                   │
└───────────────────────────────────┘
```

### クライアント側の新規コンポーネント

```
src/features/tutorial/
├── components/
│   ├── TutorialBattlePage.tsx    # BattleFieldPage をラップ
│   ├── TutorialOverlay.tsx       # 台詞 + ハイライト + 指示
│   ├── KafkaBubble.tsx           # テキストウィンドウ（useTypewriter 再利用）
│   ├── HighlightMask.tsx         # 画面の特定領域をハイライト（他を暗転）
│   └── TutorialProgress.tsx      # 章の進捗インジケーター
├── hooks/
│   └── useTutorialEngine.ts      # チュートリアル進行管理
├── data/
│   ├── ja/
│   │   ├── chapter1.tut          # 第1章（メタデータ + 台詞）
│   │   ├── chapter2.tut          # 第2章
│   │   └── chapter3.tut          # 第3章
│   └── en/
│       ├── chapter1.tut
│       ├── chapter2.tut
│       └── chapter3.tut
├── parser.ts                      # .tut パーサー
└── types.ts                      # チュートリアル固有の型定義
```

**1ファイル完結のスクリプト形式（`.tut`）:**
- `@` 行 = メタデータ（trigger, highlight, action）。パーサーが TutorialStep に変換
- それ以外の行 = 台詞テキスト。改行がそのまま行送り
- `---` でステップ区切り
- メタデータと台詞が同じファイルにあるため、同期ずれが起きない
- 言語ごとにファイルを分ける（`@` 行は各言語ファイルに重複するが許容する）

### サーバー側の変更（最小限）

#### Gateway

- `npc_battle_start` メッセージに `tutorial_chapter: number` フィールドを追加（0 = 通常、1-3 = チュートリアル章番号）
- チュートリアルモードの場合、Battle に送るリクエストに `tutorial_seed` と `tutorial_deck_id` を付与

#### Battle

- ゲーム作成時に `tutorial_seed` が指定されている場合、リポジトリのシャッフルにその seed を使用（決定論的な手札順序）
- チュートリアル用の固定デッキ定義（各章ごと）をマスターデータとして保持
- NPC 側も固定 seed でシャッフル → NPC の行動は StandardAi のままだが、手札が決定的なので行動パターンが安定する

---

## チュートリアルの進行モデル

### .tut スクリプトフォーマット

各チャプターは1つの `.tut` ファイルで完結する。`@` 行がメタデータ、それ以外が台詞テキスト、`---` がステップ区切り。

```
@trigger on_enter
@action tap_to_continue
やあ、アーキテクト。準備はできたかい？
---
@trigger after_step
@action tap_to_continue
今から君に、実戦の基本を教える。
と言っても、そんなに構えなくていい。
僕が横にいるから、一歩ずつやっていこう。
---
@trigger phase_start:main
@highlight hand_card:0
@action play_card:0→frontend/0
まずはこの「えくぼ」をデプロイしよう。
SHE の看板配達員——Compute タイプのリソースだ。
タップして選んでごらん。
```

#### メタデータ一覧

| ディレクティブ | 説明 | 例 |
|---|---|---|
| `@trigger` | いつ発火するか | `on_enter`, `phase_start:main`, `turn_start:3`, `after_action:deploy`, `after_step`, `field_condition:game_over` |
| `@highlight` | ハイライト対象 | `hand`, `hand_card:0`, `field_slot:frontend/0`, `button:endTurn`, `budget`, `insight` |
| `@action` | プレイヤーに求める操作 | `tap_to_continue`, `play_card:0→frontend/0`, `attack:frontend/0→opp_frontend/0`, `end_phase`, `scale_up:frontend/0`, `monetize` |
| `@block` | 入力ブロック（省略時 true） | `true`, `false` |

#### ルール

- `@` で始まる行 = メタデータ（パーサーが抽出）
- それ以外の行 = 台詞テキスト（改行がそのまま行送り）
- `---` = ステップ区切り
- `@trigger after_step` = 直前のステップ完了後（インデックスは自動計算）
- 台詞がないステップ（操作待ちのみ）= `@` 行だけで台詞行なし

#### パーサー

```typescript
interface TutorialStep {
  trigger: TutorialTrigger
  highlight?: HighlightTarget
  requiredAction?: RequiredAction
  blockInput: boolean
  dialogue: string | null
}

function parseTutFile(raw: string): TutorialStep[] {
  return raw.split('\n---\n').map((block, i) => {
    const lines = block.trim().split('\n')
    const meta: Record<string, string> = {}
    const textLines: string[] = []
    for (const line of lines) {
      if (line.startsWith('@')) {
        const [key, ...rest] = line.slice(1).split(' ')
        meta[key] = rest.join(' ')
      } else {
        textLines.push(line)
      }
    }
    return {
      trigger: parseTrigger(meta.trigger, i),
      highlight: meta.highlight ? parseHighlight(meta.highlight) : undefined,
      requiredAction: meta.action ? parseAction(meta.action) : undefined,
      blockInput: meta.block !== 'false',
      dialogue: textLines.join('\n').trim() || null,
    }
  })
}
```

### useTutorialEngine フック

```typescript
function useTutorialEngine(chapter: number) {
  // 現在のステップを管理
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  // バトルの状態を監視して自動進行判定
  const gameState = useBattleStore(s => s.gameState)

  // ステップの trigger 条件を監視し、条件を満たしたらオーバーレイを表示
  // requiredAction が完了したら次のステップへ進行
  // blockInput が true の間は BattleFieldPage への入力を遮断
}
```

### HighlightMask コンポーネント

SVG の `<clipPath>` + 半透明オーバーレイで、指定領域以外を暗転させる。指定領域には明滅する枠線アニメーションを付与して「ここをタップ」を示す。

### 台詞ウィンドウの表示サイクル

台詞ウィンドウは**常時表示しない**。ステップごとに以下のサイクルを回す:

```
[台詞なし: バトル画面100%]
        ↓ ステップ発火
[台詞ポップイン: 上部に0.3sでスライドイン + 暗転]
        ↓ プレイヤーがタップして台詞を読み進める
[台詞完了 → 0.3sでフェードアウト]
        ↓ requiredAction がある場合
[ハイライトのみ残る: 台詞ウィンドウは消えている]
        ↓ プレイヤーが指示された操作を実行
[ハイライトも解除 → バトル画面100%に戻る]
        ↓ 次のステップの trigger を待つ
[台詞なし: バトル画面100%]
```

### 画面レイアウト（台詞表示時）

```
┌─────────────────────────────┐
│ ┌─────────────────────────┐ │  ← 上部: カフカ台詞ウィンドウ
│ │                          │ │     相手の手札+フィールド上部を借りる
│ │ ここにカードを             │ │     グラスモーフィズム背景
│ │ デプロイしてみよう         │ │     高さ: 画面の 30%
│ │                      ▼  │ │     （シナリオモード TextBox と同等）
│ └─────────────────────────┘ │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│ ░░░░░░░ 暗転 ░░░░░░░░░░░░░ │
│ ░░░┌─────────────┐░░░░░░░░ │
│ ░░░│  ハイライト  │░░░░░░░░ │  ← 操作対象のみ明るい
│ ░░░│  (操作可能)   │░░░░░░░░ │
│ ░░░└─────────────┘░░░░░░░░ │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│ ░░░░░░░ 暗転 ░░░░░░░░░░░░░ │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░ │
└─────────────────────────────┘
```

### 画面レイアウト（台詞非表示時 = 通常バトル画面）

```
┌─────────────────────────────┐
│  相手の手札 (9%)             │  ← 通常通り表示
├─────────────────────────────┤
│  相手のフィールド (35%)       │
├─────────────────────────────┤
│  センター HUD (7%)           │
├─────────────────────────────┤
│  自分のフィールド (35%)       │
├─────────────────────────────┤
│  自分の手札 (14%)            │  ← 操作可能
└─────────────────────────────┘
```

台詞がない間はバトル画面が完全に見える。チュートリアル中であることを示す小さなインジケーター（画面右上）のみ常時表示。

---

## ストーリー構成

### 全体の位置づけ

```
イントロ（既存の intro.ks）
  → ファクション選択
  → ホーム画面
  → 初回ログイン時に「カフカからの招待」バナー表示
  → チュートリアル第1章へ
```

カフカがチュートリアル中に使うトーンは intro.ks と統一する。飄々としていて、断定的だが親切。「〜だよ」「〜かい」口調。

### 第1章: 「最初のデプロイ」（T1〜T2 終了まで）

**目的:** デプロイ・フェーズの概念・手札の読み方を学ぶ
**使用デッキ:** SHE スターター（チュートリアル専用の固定構成）
**NPC:** Neutral デッキの弱い NPC（ファクション非所属の汎用キャラ）

#### スクリプト: `ja/chapter1.tut`

```
@trigger on_enter
@action tap_to_continue
やあ、アーキテクト。準備はできたかい？
---
@trigger after_step
@action tap_to_continue
今から君に、実戦の基本を教える。
と言っても、そんなに構えなくていい。
僕が横にいるから、一歩ずつやっていこう。
---
@trigger phase_start:draw
@highlight hand
@action tap_to_continue
まず、ターンの始まりだ。
リポジトリから自動的にカードが1枚ドローされる。
これが君の手札。ここから選んでフィールドに配置する——それを「デプロイ」と言う。
---
@trigger phase_start:main
@highlight hand_card:0
@action play_card:0→frontend/0
まずはこの「えくぼ」をデプロイしよう。
SHE の看板配達員——Compute タイプのリソースだ。
タップして選んでごらん。
---
@trigger after_action:deploy
@highlight field_slot:frontend/0
@action tap_to_continue
よくできた。
ただし、えくぼの「デプロイターン」は 1。
つまり、今は裏向き——構築中の状態だ。次の君のターンで表になって稼働を始めるよ。
---
@trigger after_step
@highlight hand_card:0
@action play_card:0→backend/0
次に、バックエンドにも配置しよう。
「アデリース」——RDB タイプ。データベースは Insight を生成して、それが君の収入源になる。
---
@trigger after_action:deploy
@action tap_to_continue
フロントエンドは「攻撃と防御」、バックエンドは「経済」。
この2つのゾーンをバランスよく使うのが勝利の鍵だ。
---
@trigger after_step
@highlight button:endTurn
@action end_phase
メインフェーズでやりたいことが終わったら、ターンを終了する。
このボタンを押してごらん。
---
@trigger after_action:end_turn
@action tap_to_continue
先攻の最初のターンではバトルフェーズはスキップされる。
これは公平性のためのルールだよ。
---
@trigger turn_start:2
@action tap_to_continue
次は相手のターンだ。見ていてごらん。
---
@trigger turn_start:3
@action tap_to_continue
相手もリソースをデプロイした。
次の君のターンで、えくぼが稼働を開始する。
いよいよ攻撃ができるようになるよ。
---
@trigger after_step
@action tap_to_continue
第1章はここまで。基本は掴めたかい？
デプロイ、フェーズ、ゾーン。この3つを覚えておけば大丈夫。
```

### 第2章: 「攻撃と破壊」（T3〜T6 程度）

**目的:** 攻撃・ダメージ・破壊・SLAペナルティ・スケールアップを学ぶ
**前提:** 第1章のフィールド状態を引き継ぐ（= 第1章と第2章は連続した1つの NPC 戦）

#### スクリプト: `ja/chapter2.tut`

```
@trigger turn_start:3
@action tap_to_continue
さあ、ここからが本番だ。
えくぼが表向きになった——稼働開始だ！
---
@trigger after_step
@highlight budget
@action tap_to_continue
画面の数値を説明しよう。
「Budget」——これは君の資金であり、ライフポイントでもある。0になったら負けだ。
---
@trigger after_step
@highlight insight
@action tap_to_continue
「Insight」——バックエンドの DB が毎ターン生成するデータ資源。
これをバックエンドの Compute が Budget に変換する。
つまり、DB を守ることが収入を守ることになる。
---
@trigger after_step
@highlight button:toBattle
@action end_phase
今日はまず攻撃を覚えよう。
バトルフェーズに進んでごらん。
---
@trigger phase_start:battle
@highlight field_slot:frontend/0
@action attack:frontend/0→opp_frontend/0
フロントエンドの えくぼ をタップして攻撃元を選ぼう。
---
@trigger after_action:attack
@action tap_to_continue
ダメージは「スループット」の値に等しい。
相手の「可用性」が 0 以下になったら破壊——
さらに「SLAペナルティ」分の Budget が相手から消える。
---
@trigger after_step
@action tap_to_continue
ところで、えくぼ には「(R)」マークがついているだろう？
これは Resizable——ランクを上げてパラメータを倍にできるということだ。
---
@trigger after_step
@highlight field_slot:frontend/0
@action scale_up:frontend/0
えくぼ をロングプレスしてみてごらん。
---
@trigger after_action:scale_up
@action tap_to_continue
スケールアップは無料。ただし維持コストも倍になる。
これはクラウドの現実と同じだ——スペックを上げればランニングコストも上がる。
---
@trigger field_condition:my_av_decreased
@action tap_to_continue
攻撃を受けたね。可用性が減ったのが見えるだろう？
可用性は自動回復しない。Strategy や Attachment の効果でしか回復できない。
だから——耐えるのか、先に倒すのか。それが戦略だ。
---
@trigger after_step
@action tap_to_continue
攻撃とダメージの仕組みは理解できたかい？
フロントエンドで殴り合い、バックエンドで稼ぐ。
この攻守のリズムがこのゲームの根幹だよ。
```

### 第3章: 「経済と勝利条件」（T7〜ゲーム終了）

**目的:** 収益化・Yield・サポートカード・勝利条件を学ぶ

#### スクリプト: `ja/chapter3.tut`

```
@trigger turn_start:7
@highlight insight
@action tap_to_continue
Insightプールに数値が溜まっているのが見えるかい？
バックエンドの DB がエンドフェーズごとに自動生成してくれたものだ。
---
@trigger after_step
@action monetize
これをバックエンドの Compute で Budget に変換できる。
メインフェーズで「収益化」を実行してみよう。
---
@trigger after_action:monetize
@action tap_to_continue
1 Insight = 1 Budget。シンプルだろう？
DB の Yield が高いほど、Compute のスループットが高いほど、より多く稼げる。
攻撃だけじゃない。経済で勝つのも立派な戦略だよ。
---
@trigger after_step
@highlight hand_card:strategy
@action tap_to_continue
これはストラテジーカード。使い切りの支援効果だ。
手札から直接使って、すぐにトラッシュへ送られる。
---
@trigger after_step
@action tap_to_continue
最後に、勝ち方を整理しよう。
一番わかりやすいのは、相手の Budget を 0 にすること。
相手のカードを壊すと SLA ペナルティが発生して、Budget がどんどん削れていく。
---
@trigger after_step
@action tap_to_continue
もうひとつ——相手のフィールドから稼働中のリソースが全て消えたら「System-Down」。
これも即座に勝利だ。
フロントエンドを全部壊して、バックエンドも潰す。そうすれば相手のシステムは完全停止する。
---
@trigger field_condition:game_over
@action tap_to_continue
おめでとう、アーキテクト。これが君の初勝利だ。
---
@trigger after_step
@action tap_to_continue
デプロイ、攻撃、経済。3つの基本はもう身についている。
あとは——自分のデッキを組んで、実戦で腕を磨くだけだ。
---
@trigger after_step
@action tap_to_continue
まだまだ教えてないことは山ほどある。
Elastic の自動スケーリング、リアクティブ、チェーン……。
でもそれは、自分で確かめた方がいいよ。
---
@trigger after_step
@action tap_to_continue
じゃあ、行っておいで。
困ったらいつでも呼んでくれ。僕はいつだって、君のそばを飛んでいるから。
```

最後のステップ完了後、ホーム画面へ遷移し `tutorial_progress = 3`（全完了）に設定。

---

## チュートリアル用デッキ定義

### プレイヤーデッキ（SHE スターター / 固定順序）

章をまたいで1つの連続バトルなので、seed で手札順序を固定する。以下は意図する手札の出現順:

| 順番 | カード | 意図 |
|:---:|--------|------|
| 初期手札1 | えくぼ (Compute) | 第1章でフロントエンドにデプロイ |
| 初期手札2 | アデリース (RDB) | 第1章でバックエンドにデプロイ |
| 初期手札3 | えりり (Object Storage) | 温存（第2章で説明） |
| 初期手札4 | Auto Scaling (Strategy) | 第3章でストラテジー説明用 |
| 初期手札5 | むらた (Serverless) | 温存 |
| T3 ドロー | CloudFront CDN (Attachment) | 第2章でアタッチメント説明 |
| T5 ドロー | Marketplace (Strategy) | 第3章で Budget 回復 |
| T7 ドロー | アリゲーテナ (Container) | 追加の FE 要員 |

### NPC デッキ（Neutral ベース / 弱め）

NPC は Neutral カードのみで構成。StandardAi を使うが、ステータスが低めなのでプレイヤーが必ず勝てる。

---

## データフロー詳細

### チュートリアル開始

```
1. クライアント: WS で npc_battle_start を送信
   { deck_id: TUTORIAL_DECK_ID, npc_faction: "Neutral", tutorial_chapter: 1 }

2. Gateway: tutorial_chapter > 0 を検知
   → Battle への CreateGame リクエストに tutorial_seed を付与
   → プレイヤーデッキとして「チュートリアル用固定デッキ」を使用

3. Battle: game 作成時に tutorial_seed でリポジトリをシャッフル
   → 以降は通常の NPC 戦と同じフロー

4. クライアント: game_state を受信
   → tutorial_chapter > 0 なら TutorialBattlePage をレンダリング
   → useTutorialEngine が gameState を監視してステップを進行
```

### ステップ進行

```
useTutorialEngine:
  1. 現在の gameState を監視
  2. 次のステップの trigger 条件を評価
  3. 条件を満たしたら:
     a. blockInput = true → BattleFieldPage にプロップで入力ブロックを伝達
     b. TutorialOverlay を表示（KafkaBubble で台詞 + ハイライト）
     c. requiredAction があれば、その操作のみ許可
  4. requiredAction が完了（or tap_to_continue）→ 次のステップへ
  5. 全ステップ完了 → チュートリアル終了
```

### 入力フィルタリング

チュートリアル中、プレイヤーの操作を制限する方法:

```typescript
// TutorialBattlePage が BattleFieldPage をラップ
<BattleFieldPage
  inputFilter={currentStep?.blockInput ? {
    // requiredAction で指定された操作のみ許可
    allowedSlots: currentStep.requiredAction?.type === 'play_card'
      ? [{ zone: 'frontend', index: 0 }]
      : undefined,
    allowedHandCards: currentStep.requiredAction?.type === 'play_card'
      ? [currentStep.requiredAction.cardIndex]
      : undefined,
    allowedButtons: currentStep.requiredAction?.type === 'end_phase'
      ? ['endPhase', 'endTurn']
      : undefined,
  } : undefined}
/>
```

BattleFieldPage に `inputFilter` プロップを追加し、指定外の操作を無視する。既存のロジックを壊さない追加的な変更。

---

## UI デザイン

### z-index 層

```
z-90  CardDetailModal（既存）
z-60  TutorialOverlay（新規 — 台詞表示中のみ存在）
  z-62  HighlightMask（暗転 + ハイライト枠）
  z-61  KafkaBubble（台詞ウィンドウ）
z-50  GlassDialog（既存）
z-30  HandArea（既存）
z-10  FieldLayout（既存）
```

### KafkaBubble（台詞ウィンドウ）

既存の useTypewriter を流用したテキスト表示コンポーネント。立ち絵・キャラアイコンは表示しない。

- **位置:** 画面上部。相手の手札エリア + フィールド上部を一時的に借りて表示
- **高さ:** 画面の 30%（シナリオモードの TextBox と同等。4〜5行分のテキスト）
- **背景:** グラスモーフィズム（`rgba(28, 30, 46, 0.85)` + `backdrop-filter: blur(16px)`）
- **タイプライターエフェクト:** 既存の useTypewriter を再利用（30ms/文字）
- **送りマーク:** テキスト完了時に右下に ▼ を表示（タップで次へ / 閉じる）
- **アニメーション:**
  - 表示: 上からスライドイン（`translateY(-100%) → 0`、0.3s ease-out）
  - 非表示: 上にスライドアウト（`0 → translateY(-100%)`、0.3s ease-in）

### HighlightMask（暗転 + ハイライト）

台詞表示中、または requiredAction の操作待ち中に表示:

- **暗転:** `rgba(0, 0, 0, 0.6)` の半透明オーバーレイ（SVG `<clipPath>` でハイライト領域を切り抜き）
- **ハイライト枠:** `2px solid rgba(100, 200, 255, 0.8)` + 明滅アニメーション（`opacity: 0.5 → 1.0`、1.2s cycle）
- **ポインターイベント:** ハイライト領域のみ `pointer-events: auto`、暗転部分は `pointer-events: none`（ブロック時は `auto` にして操作を吸収）

### チュートリアル進行インジケーター

台詞が表示されていない間も「チュートリアル中」であることを示す最小限の UI:
- **位置:** 画面右上
- **見た目:** 小さなアイコン（24×24px）+ 薄いグロー
- **タップ:** カフカの直前の台詞をリプレイ（「もう一度聞く」機能）

---

## チュートリアルの状態管理

### プレイヤーの進捗

Gateway の `players` テーブルに `tutorial_progress` カラムを追加:

```sql
ALTER TABLE players ADD COLUMN tutorial_progress INT NOT NULL DEFAULT 0;
-- 0: 未開始, 1: 第1章完了, 2: 第2章完了, 3: 全完了
```

### スキップ機能

- チュートリアル中はいつでも「スキップ」ボタンを表示
- スキップすると GlassDialog で確認 → tutorial_progress を 3（全完了）に設定
- 後からホーム画面の設定からチュートリアルを再プレイ可能

---

## ルーティング

```
/tutorial/:chapter    # チュートリアルバトル（chapter = 1, 2, 3）
```

実際には chapter 1 で NPC 戦を開始し、章の切れ目はゲーム内で区切る（1つの NPC 戦の中で3章分を通しで進行）。ルーティングは再プレイ用。

通常フローでは:
1. ホーム画面で「チュートリアル」バナーをタップ
2. `/tutorial/1` に遷移
3. NPC 戦開始 → 第1章〜第3章を通しで進行
4. 完了後にホーム画面へ戻る

---

## 実装の優先順位

### Phase 1（MVP）— 第1章のみ

1. **Battle:** `tutorial_seed` パラメータの受け入れ + 固定シャッフル
2. **Gateway:** `npc_battle_start` に `tutorial_chapter` フィールド追加
3. **Client:** `TutorialOverlay` + `KafkaBubble` + `HighlightMask` + `useTutorialEngine`
4. **Client:** 第1章の `ja/chapter1.tut` + `parser.ts`
5. **Client:** BattleFieldPage に `inputFilter` プロップ追加

### Phase 2 — 第2章・第3章

6. 第2章・第3章の `.tut` スクリプト
7. チュートリアル専用デッキの作成（カード選定 + seed 計算）
8. スキップ機能
9. 再プレイ機能

### Phase 3 — ポリッシュ

10. 進捗インジケーター
11. チュートリアル完了報酬（ノーマルパック 1つ等）
12. 不完全クリア時のリジューム

---

## 補足: なぜバトルエンジンを改変しないのか

チュートリアルのためにバトルエンジンに分岐を入れると:
- テスト対象が増え、バグリスクが上がる
- 「チュートリアルでは動いたのに本番では違う」という混乱を招く
- メンテナンスコストが永続的に増える

代わりに**固定 seed + クライアント側オーバーレイ**で制御する方式なら:
- バトルエンジンは一切手を入れない（0リスク）
- NPC の行動は seed で決定的にできる → 手札が確定 → AI の行動パターンが安定
- クライアント側のオーバーレイは独立したフィーチャーフラグで管理でき、剥がすのも容易
