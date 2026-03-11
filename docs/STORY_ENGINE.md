# ストーリーエンジン仕様書

## 概要

ビジュアルノベル形式のシナリオ再生エンジン。ADVスタイル（画面上部に背景+立ち絵、下部にテキストボックス）でストーリーを進行する。

**現在の用途**: ゲーム開始時のナビゲータキャラ「カフカ」による導入シナリオ
**設計方針**: 汎用エンジンとして、今後の追加シナリオにも再利用可能

## アーキテクチャ

### ディレクトリ構成

```
src/features/story/
├── types.ts                  # 型定義
├── components/
│   ├── index.ts              # barrel export (StoryPage)
│   ├── StoryPage.tsx         # ルートエントリ (/story/:scenarioId)
│   ├── StoryPlayer.tsx       # メインオーケストレーター
│   ├── BackgroundLayer.tsx   # 背景画像レイヤー
│   ├── CharacterLayer.tsx    # 立ち絵レイヤー
│   ├── TextBox.tsx           # テキストボックス
│   └── ChoiceOverlay.tsx     # 選択肢オーバーレイ
├── hooks/
│   ├── useTypewriter.ts      # タイプライターエフェクト
│   └── useStoryPlayer.ts    # シナリオ進行ロジック
└── data/
    ├── scenarios.ts          # シナリオレジストリ
    └── intro.ts              # カフカ導入シナリオ
```

### レイヤー構造

画面は4層のレイヤーで構成される（z-index順）:

```
┌─────────────────────────────────┐
│  z-40: ChoiceOverlay            │  選択肢（表示時のみ）
├─────────────────────────────────┤
│  z-30: TextBox                  │  下部30% テキストボックス
├─────────────────────────────────┤
│  z-10: CharacterLayer           │  立ち絵（bottom-30%基準）
├─────────────────────────────────┤
│  z-0:  BackgroundLayer          │  フルスクリーン背景
└─────────────────────────────────┘
```

### データフロー

```
ScenarioData (JSON/TS)
  ↓
useStoryPlayer (状態管理)
  ├── currentIndex → 現在のステップ
  ├── activeBackground → BackgroundLayer
  ├── activeCharacters → CharacterLayer
  ├── displayText → useTypewriter → TextBox
  ├── isChoicePhase → ChoiceOverlay
  └── advance/selectChoice → ユーザー入力
```

## データ型仕様

### ScenarioData

シナリオ全体を定義するトップレベル型。

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `id` | `string` | ○ | シナリオ一意ID（URLパラメータに使用） |
| `titleKey` | `string` | ○ | シナリオタイトルのi18nキー |
| `characters` | `Record<string, CharacterDef>` | ○ | 登場キャラクター定義 |
| `defaultBackground` | `string` | ○ | デフォルト背景画像パス |
| `steps` | `StoryStep[]` | ○ | シナリオステップの配列（線形進行） |

### CharacterDef

キャラクター定義。

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `id` | `string` | ○ | キャラクターID |
| `nameKey` | `string` | ○ | 名前のi18nキー |
| `color` | `string` | ○ | ネームプレートのアクセントカラー（HEX） |
| `sprites` | `Record<string, string>` | ○ | 感情キー → 立ち絵画像パスのマップ |

### StoryStep

ステップは3種類の判別共用体:

#### DialogueStep（セリフ）

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `type` | `'dialogue'` | ○ | ステップ種別 |
| `speakerId` | `string` | ○ | 話者のキャラクターID |
| `textKey` | `string` | ○ | セリフテキストのi18nキー |
| `background` | `string` | - | 背景画像パス（省略時は継承） |
| `characters` | `CharacterDisplay[]` | - | 表示キャラクター（省略時は継承） |
| `characterTransition` | `TransitionType` | - | 立ち絵の遷移アニメーション |
| `backgroundTransition` | `'fade' \| 'none'` | - | 背景の遷移アニメーション |

#### NarrationStep（ナレーション）

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `type` | `'narration'` | ○ | ステップ種別 |
| `textKey` | `string` | ○ | ナレーションテキストのi18nキー |
| `background` | `string` | - | 背景画像パス（省略時は継承） |
| `backgroundTransition` | `'fade' \| 'none'` | - | 背景の遷移アニメーション |
| `characters` | `CharacterDisplay[]` | - | 表示キャラクター（省略時は継承） |

#### ChoiceStep（選択肢）

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `type` | `'choice'` | ○ | ステップ種別 |
| `textKey` | `string` | ○ | 質問テキストのi18nキー |
| `speakerId` | `string` | - | 話者のキャラクターID |
| `choices` | `ChoiceOption[]` | ○ | 選択肢の配列 |
| `characters` | `CharacterDisplay[]` | - | 表示キャラクター（省略時は継承） |

#### ChoiceOption

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `labelKey` | `string` | ○ | ボタンラベルのi18nキー |
| `responseKey` | `string` | ○ | 選択後に表示するセリフのi18nキー |
| `responseSpeakerId` | `string` | - | レスポンスの話者（省略時は親ステップの`speakerId`） |

### CharacterDisplay

ステップ内でのキャラクター表示指定。

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `characterId` | `string` | ○ | `CharacterDef.id` への参照 |
| `emotion` | `string` | ○ | `CharacterDef.sprites` のキー |
| `position` | `'left' \| 'center' \| 'right'` | ○ | 画面上の立ち位置 |

### TransitionType

`'fade' | 'slide-left' | 'slide-right' | 'none'`

## 継承ルール

データ量を削減するため、一部フィールドは省略時に前のステップから継承される:

- **background**: 省略時、直前にbackgroundを指定したステップの値を使用。どのステップにもない場合は `defaultBackground` を使用。
- **characters**: 省略時、直前にcharactersを指定したステップの値を使用。どのステップにもない場合は空配列（立ち絵なし）。

継承はステップ配列を後方スキャンして最新の明示値を探す方式。

## テキスト送りモード

3つのモードを切り替え可能:

| モード | 動作 | UI |
|---|---|---|
| **manual**（デフォルト） | タップでタイプライター完了 → 再タップで次ステップ | 「タップして続ける」表示 |
| **auto** | テキスト完了後2秒で自動的に次ステップへ | AUTOボタンがアクティブ |
| **skip** | テキスト即時完了、100ms後に自動で次ステップへ | SKIPボタンがアクティブ |

### タイプライターエフェクト

- 基本速度: 30ms/文字
- 句読点ポーズ: 。！？ → +150ms、、 → +75ms
- タップで即時全文表示（skipToEnd）
- SKIPモード時は速度0（即時表示）

## 選択肢仕様（インライン分岐）

選択肢はシナリオ全体の分岐ではなく、**次の1セリフだけが変わるインライン方式**:

1. ChoiceStepが表示される → テキストボックスに質問テキスト
2. テキスト完了後、画面中央にボタンが出現
3. ユーザーがボタンをタップ
4. 選択した `responseKey` のセリフが表示される（タイプライターで）
5. そのセリフの後、通常通り次のステップに進む

シナリオ全体が分岐することはなく、ステップ配列は常に線形に進行する。

## ルーティング

```
/story/:scenarioId
```

- フルスクリーンルート（タブバーなし）
- `scenarioId` は `scenarios.ts` のレジストリで解決
- 任意の画面から `navigate('/story/intro')` で起動可能
- シナリオ完了時は `navigate(-1)` で前の画面に戻る

## i18n

### ネームスペース

`story` ネームスペースを使用。

### キー規約

```
characters.{characterId}          # キャラクター名
ui.auto / ui.skip / ui.tapToContinue  # UI共通テキスト
{scenarioId}.{stepName}           # シナリオ固有テキスト
{scenarioId}.{choiceName}.prompt  # 選択肢の質問
{scenarioId}.{choiceName}.optionA # 選択肢ラベル
{scenarioId}.{choiceName}.responseA # 選択後セリフ
```

### ファイル配置

```
src/i18n/locales/ja/story.json
src/i18n/locales/en/story.json
```

## 新規シナリオの追加手順

1. **シナリオデータファイルを作成**
   ```
   src/features/story/data/my-scenario.ts
   ```
   `ScenarioData` 型に準拠したオブジェクトをexport。

2. **i18nキーを追加**
   `src/i18n/locales/{ja,en}/story.json` にテキストを追加。

3. **レジストリに登録**
   `src/features/story/data/scenarios.ts` の `SCENARIOS` に追加:
   ```typescript
   import { myScenario } from './my-scenario'
   const SCENARIOS = {
     'intro': intro,
     'my-scenario': myScenario,  // ← 追加
   }
   ```

4. **画像アセットを配置**
   ```
   public/assets/story/bg-*.webp    # 背景画像
   public/assets/story/*-*.webp     # キャラクター立ち絵
   ```

5. **ナビゲーション**
   任意の画面から `navigate('/story/my-scenario')` で起動。

## アセット規約

| 種類 | パス | 推奨サイズ |
|---|---|---|
| 背景画像 | `/assets/story/bg-*.webp` | 9:19.5 アスペクト比 |
| キャラクター立ち絵 | `/assets/story/{character}-{emotion}.webp` | 透過PNG/WebP、縦長 |
