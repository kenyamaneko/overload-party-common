# 次のステップ: Unity クライアント開発開始

## ✅ 完了済み

- [x] GitHub リポジトリ名変更: `overload-party` → `overload-party-server`
- [x] Go モジュール名更新: `github.com/kenyamamoto/overload-party-server`
- [x] 全インポートパス更新
- [x] Git リモートURL更新
- [x] README更新
- [x] ビルド・テスト確認済み
- [x] Unity クライアントリポジトリ作成済み

## 📋 次にやること

### 1. ローカルディレクトリのリネーム

```bash
cd /Users/kenyamamoto/Documents/key_and_notes/
mv overload-party overload-party-server
```

**注意**: VS Code を閉じてからリネームすることを推奨

### 2. 変更をコミット・プッシュ

```bash
cd overload-party-server

# 変更を確認
git status

# ステージング
git add .

# コミット
git commit -m "Rename repository to overload-party-server

- Update Go module name to github.com/kenyamamoto/overload-party-server
- Update all import paths across codebase
- Update README for server/client architecture
- Update git remote URL"

# プッシュ
git push origin main
```

### 3. VS Code を再起動

ディレクトリリネーム後、VS Code で新しいディレクトリを開く:
```bash
cd /Users/kenyamamoto/Documents/key_and_notes/overload-party-server
code .
```

---

## 🎮 Unity プロジェクト作成

### ステップ1: Unity Hub のインストール（未インストールの場合）

1. [Unity Hub をダウンロード](https://unity.com/download)
2. インストール実行
3. Unity Hub を起動

### ステップ2: Unity エディタのインストール

1. Unity Hub → **Installs** → **Install Editor**
2. **Unity 2022.3 LTS** を選択（推奨）
3. モジュール追加:
   - ✅ WebGL Build Support（ブラウザ版）
   - ✅ iOS Build Support（iOS版）
   - ✅ Android Build Support（Android版）
   - ✅ Visual Studio（エディタ統合）

### ステップ3: 新規プロジェクト作成

1. Unity Hub → **Projects** → **New project**
2. テンプレート: **2D Core** または **3D Core**
3. Project name: `overload-party-client`
4. Location: `/Users/kenyamamoto/Documents/key_and_notes/overload-party-client`
5. **Create project** をクリック

### ステップ4: Git 設定

Unity プロジェクト作成後、Git を設定:

```bash
cd /Users/kenyamamoto/Documents/key_and_notes/overload-party-client

# Git LFS 有効化
git lfs install

# Unity用 .gitignore 追加（すでにある場合はスキップ）
curl -o .gitignore https://raw.githubusercontent.com/github/gitignore/main/Unity.gitignore

# 初回コミット
git add .
git commit -m "Initial Unity project setup"
git push origin main
```

---

## 📡 WebSocket 通信の実装

### ステップ5: WebSocket ライブラリのインストール

#### 方法A: NativeWebSocket（推奨）

1. Unity エディタで **Window → Package Manager**
2. 左上の **+** → **Add package from git URL**
3. URL: `https://github.com/endel/NativeWebSocket.git#upm`
4. **Add** をクリック

#### 方法B: WebSocket Sharp

Asset Store から "WebSocket Sharp" を検索してインポート

### ステップ6: WebSocket クライアントの実装

**Assets/Scripts/Network/WebSocketClient.cs** を作成:

```csharp
using System;
using System.Threading.Tasks;
using NativeWebSocket;
using UnityEngine;

public class WebSocketClient : MonoBehaviour
{
    private WebSocket websocket;
    public string serverUrl = "ws://localhost:8080/ws/game";

    async void Start()
    {
        await ConnectToServer();
    }

    async Task ConnectToServer()
    {
        websocket = new WebSocket(serverUrl);

        websocket.OnOpen += () =>
        {
            Debug.Log("WebSocket接続成功");
        };

        websocket.OnMessage += (bytes) =>
        {
            var message = System.Text.Encoding.UTF8.GetString(bytes);
            Debug.Log($"受信: {message}");
            HandleMessage(message);
        };

        websocket.OnError += (e) =>
        {
            Debug.LogError($"WebSocketエラー: {e}");
        };

        websocket.OnClose += (e) =>
        {
            Debug.Log("WebSocket切断");
        };

        await websocket.Connect();
    }

    void Update()
    {
        #if !UNITY_WEBGL || UNITY_EDITOR
        websocket?.DispatchMessageQueue();
        #endif
    }

    private void HandleMessage(string message)
    {
        // TODO: JSONをパースしてゲームステートを更新
    }

    public async void SendAction(string actionType, object payload)
    {
        if (websocket.State != WebSocketState.Open)
        {
            Debug.LogWarning("WebSocket未接続");
            return;
        }

        var action = new
        {
            type = actionType,
            payload = payload
        };

        string json = JsonUtility.ToJson(action);
        await websocket.SendText(json);
        Debug.Log($"送信: {json}");
    }

    private async void OnApplicationQuit()
    {
        if (websocket != null)
        {
            await websocket.Close();
        }
    }
}
```

---

## 🎨 ゲーム画面の基本構成

### ステップ7: シーン構成

Unity で以下のシーンを作成:

1. **TitleScene** - タイトル画面
2. **LobbyScene** - ロビー・マッチメイキング
3. **GameScene** - 対戦画面
4. **ResultScene** - 結果画面

**File → Build Settings** で各シーンを追加

### ステップ8: 基本的なUI配置（GameScene）

**GameScene** で以下を配置:

```
Canvas
├── PlayerField (自分のフィールド)
│   ├── FrontendZone (3スロット)
│   ├── BackendZone (3スロット)
│   └── SupportZone (3スロット)
├── OpponentField (相手のフィールド)
│   ├── FrontendZone (3スロット)
│   ├── BackendZone (3スロット)
│   └── SupportZone (3スロット)
├── Hand (手札表示エリア)
├── BudgetDisplay (Budgetゲージ)
├── DVPoolDisplay (DVプール)
├── PhaseIndicator (現在のフェーズ)
└── ActionButtons
    ├── EndPhaseButton
    ├── AttackButton
    └── PlayCardButton
```

---

## 🔧 サーバー側の準備

### ステップ9: WebSocket エンドポイントの確認

**overload-party-server** 側で以下を確認:

```go
// internal/handler/ws/manager.go
// WebSocketエンドポイント: /ws/game
```

ローカルでサーバーを起動:
```bash
cd overload-party-server
go run cmd/server/main.go
```

デフォルトポート: `http://localhost:8080`
WebSocket: `ws://localhost:8080/ws/game`

### ステップ10: WebSocket メッセージ仕様の確認

**docs/WEBSOCKET_API.md** を参照（未作成の場合は作成）

基本的なメッセージフォーマット:

**クライアント → サーバー**:
```json
{
  "type": "play_card",
  "payload": {
    "cardInstanceId": "card-123",
    "zone": "frontend",
    "slotIndex": 0
  }
}
```

**サーバー → クライアント**:
```json
{
  "type": "game_state_update",
  "payload": {
    "currentTurn": 1,
    "currentPhase": "main",
    "budget": 5000,
    "field": { ... }
  }
}
```

---

## 📚 参考資料

### ゲームルール
- `docs/GAME_RULES.md` - ゲームルール詳細
- `docs/CARDS.md` - カード仕様
- `data/cards.json` - カードデータ（JSON）

### API仕様
- `internal/handler/ws/message.go` - WebSocketメッセージ定義
- `internal/model/game_state.go` - ゲームステート構造

---

## ⚠️ 重要な注意点

### Unity で気をつけること

1. **Git LFS を必ず有効化**
   - アセット（画像、音声）は Git LFS で管理

2. **Library フォルダは .gitignore に追加**
   - 既に追加されているはずだが確認

3. **iOS/Android ビルド時**
   - WebSocket ライブラリがプラットフォーム対応しているか確認

### サーバー側で気をつけること

1. **CORS 設定**
   - Unity WebGL ビルド時に必要
   - `cmd/server/main.go` で CORS を有効化

2. **認証**
   - 本番環境では Firebase Authentication を使用
   - 開発環境では簡易認証でOK

---

## 🎯 最初のマイルストーン

### Phase 1: 接続確認（1-2日）
- [ ] Unity プロジェクト作成
- [ ] WebSocket ライブラリ導入
- [ ] サーバーへの接続成功
- [ ] メッセージ送受信確認

### Phase 2: 基本UI（3-5日）
- [ ] フィールド表示
- [ ] 手札表示
- [ ] Budget/DV表示
- [ ] カードのドラッグ&ドロップ

### Phase 3: ゲームロジック連携（1週間）
- [ ] カード配置
- [ ] ターン進行
- [ ] 攻撃処理
- [ ] 勝敗判定

### Phase 4: 演出・UI改善（2週間）
- [ ] カードアニメーション
- [ ] エフェクト
- [ ] サウンド
- [ ] チュートリアル

---

## 📞 質問・相談事項

Unity 開発中に出てきそうな質問:

1. **カードデータの取得方法**
   - サーバーから API で取得 vs Unity にハードコード

2. **カード画像の管理**
   - Sprite Atlas を使用
   - Addressables を使用

3. **状態管理**
   - UniRx を使用
   - シンプルな MonoBehaviour で管理

4. **テスト方法**
   - Unity Test Framework を使用
   - サーバーと分離してテスト

---

## 🔄 今日のまとめ

### 達成したこと
- ✅ 15ターン制限勝利条件の実装
- ✅ AozoraAI のコンボロジック実装
- ✅ AI の攻撃性向上（deployFloor調整）
- ✅ ターン制限詳細分析の実装
- ✅ 専用AI対戦シミュレーション
- ✅ リポジトリ名変更（server/client分離）
- ✅ Go モジュール名・インポートパス更新

### 次回セッションでやること
1. ディレクトリリネーム（`overload-party` → `overload-party-server`）
2. 変更のコミット・プッシュ
3. Unity プロジェクト作成
4. WebSocket 通信の実装開始

---

**このドキュメントを残しておけば、次回すぐに作業を再開できます！**
