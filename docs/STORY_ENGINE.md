# ストーリーエンジン仕様書

## 概要

ビジュアルノベル形式のシナリオ再生エンジン。ADVスタイル（画面上部に背景+立ち絵、下部にテキストボックス）でストーリーを進行する。

**現在の用途**: ゲーム開始時のナビゲータキャラ「カフカ」による導入シナリオ + 陣営別シナリオストーリー
**設計方針**: ティラノスクリプト互換の `.ks` スクリプトで記述し、React コンポーネントで描画する

## スクリプト配信方式

スクリプトの配信方式は用途によって2系統ある:

| 用途 | 方式 | 配置場所 | 取得方法 |
|------|------|----------|----------|
| ナビゲーションストーリー（intro 等） | クライアントバンドル | `src/features/story/data/scripts/{lang}/` | Vite `?raw` import → `scripts.ts` レジストリ |
| シナリオストーリー（陣営別 + 最終話） | サーバー配信 | GCS バケット or ローカルファイルシステム | `GET /api/v1/scenarios/{episodeId}/script` |

**ナビゲーションストーリー** はアプリ起動直後に使用され、ネットワーク遅延を避けるためバンドルに含める。**シナリオストーリー** はエピソード数が多く（21話）、アンロック判定が必要なためサーバー配信とする。

サーバー配信のスクリプトパスは `scenario_episodes.script_path` に `stories/{lang}/she_ep1.ks` の形式で格納され、`{lang}` が実際の言語コードに置換される。未対応言語は `ja` にフォールバックする。

## アーキテクチャ

### ディレクトリ構成

```
src/features/story/
├── parser.ts                 # .ks パーサー（テキスト → KsCommand[]）
├── types.ts                  # KS コマンド型定義
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
│   └── useStoryEngine.ts     # KS コマンド実行エンジン
└── data/
    ├── scripts.ts            # シナリオレジストリ（言語別）
    └── scripts/
        ├── ja/
        │   └── intro.ks      # カフカ導入シナリオ（日本語）
        └── en/
            └── intro.ks      # カフカ導入シナリオ（英語）
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

ナビゲーションストーリーとシナリオストーリーで取得経路が異なるが、パーサー以降は共通:

```
[ナビゲーションストーリー]          [シナリオストーリー]
.ks スクリプト（言語別）            scenario_episodes.script_path
  ↓ Vite ?raw import                 ↓ GET /api/v1/scenarios/{episodeId}/script
scripts.ts (レジストリ)             API レスポンス (.script)
  ↓ getScript(scenarioId, lang)       ↓
  └──────────────┬────────────────────┘
                 ↓
           parser.ts (parseKs)
                 ↓ KsCommand[]
           useStoryEngine (コマンド実行)
             ├── displayText      → useTypewriter → TextBox
             ├── speakerName      → TextBox
             ├── activeBackground → BackgroundLayer
             ├── activeCharacters → CharacterLayer
             ├── choices          → ChoiceOverlay
             └── advance/selectChoice → ユーザー入力
```

## スクリプト書式

ティラノスクリプト互換の `.ks` 形式を使用。テキストは i18n キーではなくスクリプト内に直接記述する。

### 基本構文

```
; コメント行（実行されない）
# kafka                          ; 話者を設定（キャラID）
#                                ; 話者をクリア（ナレーション）
*label_name                      ; ラベル定義（ジャンプ先）
こんにちは。[p]                  ; テキスト + ページ送り
```

### テキスト・フロー制御

| タグ | 説明 |
|------|------|
| `[p]` | ページ送り（クリック待ち → テキストクリア） |
| `[l]` | 行送り（クリック待ち → 改行して続行） |
| `[r]` | 改行（クリック待ちなし） |
| `[s]` | 停止（glink 等の入力待ち） |
| `[cm]` | メッセージウィンドウをクリア |
| `[wait time="1000"]` | 指定ミリ秒待機 |
| `[jump target="*label"]` | ラベルへジャンプ |

### キャラクター

| タグ | 説明 |
|------|------|
| `[chara_new name="id" jname="表示名" color="#hex" storage="パス" faces="happy=パス,serious=パス"]` | キャラクター定義 |
| `[chara_show name="id" position="center" transition="fade"]` | 立ち絵表示 |
| `[chara_hide name="id"]` | 立ち絵非表示 |
| `[chara_mod name="id" face="happy"]` | 表情変更 |
| `[chara_move name="id" position="right"]` | 立ち位置変更 |

- `position`: `left` / `center` / `right`
- `transition`: `fade` / `slide-left` / `slide-right` / `none`
- `face`: `default`（storage の画像）/ faces で定義した感情キー

### 背景

| タグ | 説明 |
|------|------|
| `[bg storage="パス" transition="fade"]` | 背景変更 |
| `[bg_transition method="fade"]` | デフォルトトランジション設定 |

### 選択肢

| タグ | 説明 |
|------|------|
| `[glink text="選択肢テキスト" target="*label"]` | 選択肢ボタン |

選択肢は `[glink]` を並べた後に `[s]` で停止。選択後、対応する `*label` にジャンプする。

```
# kafka
どうする？[p]
[cm]
[glink text="戦う" target="*fight"]
[glink text="逃げる" target="*flee"]
[s]

*fight
# kafka
いい度胸だ。[p]
[jump target="*next"]

*flee
# kafka
賢明な判断だね。[p]
[jump target="*next"]

*next
; 合流地点
```

### オーディオ（将来実装）

| タグ | 説明 |
|------|------|
| `[bgm storage="パス"]` | BGM 再生 |
| `[stopbgm]` | BGM 停止 |
| `[se storage="パス"]` | 効果音再生 |

## テキスト送りモード

3つのモードを切り替え可能:

| モード | 動作 | UI |
|---|---|---|
| **manual**（デフォルト） | タップでタイプライター完了 → 再タップで次ページ | ▼ 表示 |
| **auto** | テキスト完了後2秒で自動的に次ページへ | AUTO ボタンがアクティブ |
| **skip** | テキスト即時完了、100ms後に自動で次ページへ | SKIP ボタンがアクティブ |

### タイプライターエフェクト

- 基本速度: 30ms/文字
- 句読点ポーズ: 。！？ → +150ms、、 → +75ms
- タップで即時全文表示（skipToEnd）
- SKIP モード時は速度0（即時表示）

## 多言語対応

スクリプトファイルを言語ごとに分離する方式。既存の i18n（react-i18next）とは独立。

```
scripts/ja/intro.ks    ← 日本語版
scripts/en/intro.ks    ← 英語版
```

`i18n.language` の値に基づいて対応言語のスクリプトを読み込む。フォールバックは日本語。

## ルーティング

| ルート | 用途 | スクリプト取得元 |
|--------|------|-----------------|
| `/story/:scenarioId` | ナビゲーションストーリー | `scripts.ts` レジストリ（Vite バンドル） |
| `/scenarios/:episodeId` | シナリオストーリー | `GET /api/v1/scenarios/{episodeId}/script` |

- いずれもフルスクリーンルート（タブバーなし）
- ナビゲーション: `navigate('/story/intro')` で起動。`scenarioId` は `scripts.ts` のレジストリで解決
- シナリオ: `navigate('/scenarios/she_ep1')` で起動。API からスクリプトを取得し、アンロック判定はサーバー側で実施（403 でロック中を返す）
- 完了時は `navigate(-1)` で前の画面に戻る

## 新規シナリオの追加手順

### ナビゲーションストーリー（クライアントバンドル）

ゲーム開始時の導入など、ネットワーク不要で即座に再生する必要があるストーリー向け。

1. **スクリプトファイルを作成**
   ```
   src/features/story/data/scripts/ja/my-scenario.ks
   src/features/story/data/scripts/en/my-scenario.ks
   ```

2. **レジストリに登録**
   `src/features/story/data/scripts.ts`:
   ```typescript
   import myScenarioJa from './scripts/ja/my-scenario.ks?raw'
   import myScenarioEn from './scripts/en/my-scenario.ks?raw'

   const SCRIPTS = {
     intro: { ja: introJa, en: introEn },
     'my-scenario': { ja: myScenarioJa, en: myScenarioEn },  // ← 追加
   }
   ```

3. **画像アセットを配置**
   ```
   public/assets/story/bg-*.webp           # 背景画像
   public/assets/story/{character}-{emotion}.webp  # キャラクター立ち絵
   ```

4. **ナビゲーション**
   任意の画面から `navigate('/story/my-scenario')` で起動。

### シナリオストーリー（サーバー配信）

陣営別ストーリー等、アンロック判定が必要なストーリー向け。

1. **スクリプトファイルを作成し GCS にアップロード**
   ```
   stories/ja/my_episode.ks
   stories/en/my_episode.ks
   ```
   GCS バケットの `stories/{lang}/` 配下に配置する。

2. **シードデータに追加**
   `db/seed/scenarios.sql` にエピソード定義を追加:
   ```sql
   ('my_episode', 'main', 'SHE', 3, 'タイトル', 'Title',
     10, '{SHE}', '{she_ep2}', 'stories/{lang}/my_episode.ks', 9)
   ```
   - `category`: `main` / `side` / `event`
   - `required_level`, `required_factions`, `required_episodes` でアンロック条件を定義
   - `sort_order` で一覧画面の表示順を制御

3. **DB にシードを適用**
   ops リポジトリ経由でマイグレーションを実行。

4. **画像アセットを配置**（ナビゲーションストーリーと同様）

5. **ナビゲーション**
   シナリオ一覧画面から自動的にアクセス可能になる。直接遷移する場合は `navigate('/scenarios/my_episode')` で起動。

## アセット規約

| 種類 | パス | 推奨サイズ |
|---|---|---|
| 背景画像 | `/assets/story/bg-*.webp` | 9:19.5 アスペクト比 |
| キャラクター立ち絵 | `/assets/story/{character}-{emotion}.webp` | 透過WebP、縦長 |
