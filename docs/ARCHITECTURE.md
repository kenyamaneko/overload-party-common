# Overload Party - システムアーキテクチャ設計書

**Version:** 2.0  
**Last Updated:** 2026-02-26  
**Status:** Implementation Phase

---

## 目次

1. [概要](#1-概要)
2. [プロジェクト構成](#2-プロジェクト構成monorepo-like)
3. [技術スタック](#3-技術スタック)
4. [システムアーキテクチャ](#4-システムアーキテクチャ)
5. [データ設計](#5-データ設計-data-architecture)
6. [API設計](#6-api設計)
7. [認証・認可](#7-認証認可)
8. [課金システム](#8-課金システム)
9. [リアルタイム通信](#9-リアルタイム通信)
10. [ゲームロジック](#10-ゲームロジック)
11. [状態管理](#11-状態管理)
12. [パフォーマンス最適化](#12-パフォーマンス最適化)
13. [セキュリティ](#13-セキュリティ)
14. [デプロイメント](#14-デプロイメント)
15. [モニタリング](#15-モニタリング)
16. [実装ロードマップ](#16-実装ロードマップ)

---

## 1. 概要

### 1.1 プロジェクト概要

Overload Partyは、クラウドインフラをテーマにした対戦型デジタルカードゲームです。2人のプレイヤーがリアルタイムで対戦し、相手のBudgetを0以下にすることを目指します。

### 1.2 主要要件

- **リアルタイム対戦**: 2人のプレイヤーが同時にプレイ
- **複雑な状態管理**: チェーンシステム、継続効果
- **強整合性**: ゲーム状態の厳密な管理
- **低レイテンシ**: 快適なゲーム体験
- **スケーラビリティ**: 多数の同時対戦に対応
- **クロスプラットフォーム**: iOS/Android対応

### 1.3 非機能要件

| 要件 | 目標値 |
|------|--------|
| レスポンスタイム | < 100ms (P95) |
| 同時接続数 | 10,000+ |
| 可用性 | 99.9% |
| データ整合性 | 100% |

---

## 2. プロジェクト構成（Monorepo-like）

Overload Party は3つの独立した Git リポジトリで構成されます。`overload-party-common` が共有データのハブとなり、server/client から **シンボリックリンク** で参照します。

### 2.1 リポジトリ構成

```
overload-party-common/          # 共有データ・定義の Single Source of Truth
├── data/
│   ├── cards/                  # カード定義 YAML (5 faction files)
│   │   ├── sd.yaml
│   │   ├── tenki.yaml
│   │   ├── sugar.yaml
│   │   ├── tuners.yaml
│   │   └── neutral.yaml
│   ├── cards.json              # 生成: 全カードの JSON データ
│   └── constants.json          # ゲーム定数 (Phase, Zone, Rank, 初期値 等)
├── docs/                       # 全ドキュメント
├── scripts/
│   └── generate_from_yaml.py   # カード＆定数のコード生成スクリプト
└── README.md

overload-party-server/           # Go ゲームサーバー
├── data -> ../common/data       # symlink
├── docs -> ../common/docs       # symlink
├── internal/
│   ├── cardno/cardno_gen.go     # 生成: カード番号 Go 定数
│   ├── model/constants_gen.go   # 生成: ゲーム定数 Go 版
│   └── ...
└── Makefile                     # `make generate` で全コード生成

overload-party-client/           # React + Capacitor クライアント
├── src/
│   ├── generated/
│   │   └── constants.ts         # 生成: ゲーム定数 TypeScript 版
│   └── ...
└── ...
```

### 2.2 コード生成パイプライン

`make generate`（サーバー側）を実行すると、common の `generate_from_yaml.py` が以下を生成します：

| 入力 | 出力 | 出力先 |
|------|------|--------|
| `data/cards/*.yaml` | `data/cards.json` | common |
| `data/cards/*.yaml` | `docs/CARDS.md` | common |
| `data/cards/*.yaml` | `internal/cardno/cardno_gen.go` | server |
| `data/constants.json` | `internal/model/constants_gen.go` | server |
| `data/constants.json` | `src/generated/constants.ts` | client |

生成されたファイルには `DO NOT EDIT` コメントが付きます。ゲーム定数（Phase, Zone, Rank, 初期値など）を変更する場合は `data/constants.json` を編集してから `make generate` を実行してください。

### 2.3 シンボリックリンクと .gitignore

server と client のリポジトリでは、common への symlink を `.gitignore` で除外しています。各リポジトリを clone した後、手動で symlink を張る必要があります：

```bash
# server
ln -s /path/to/overload-party-common/data  data
ln -s /path/to/overload-party-common/docs  docs

# client は symlink 不要（generate で直接出力）
```

---

## 3. 技術スタック

### 3.1 フロントエンド

```
React + Capacitor (TypeScript)
├── React 18+
├── WebSocket Client (native WebSocket API)
├── State Management (Zustand / Jotai)
├── UI Framework (CSS Modules / Tailwind CSS)
├── Animation (Framer Motion)
└── Capacitor (iOS / Android ネイティブラッパー)
```

**選定理由:**
- MVPの開発速度を最優先
- クロスプラットフォーム対応（Web, iOS, Android）
- React エコシステムの豊富なライブラリ
- 将来的に演出面で不足があれば Unity への移行を検討

### 3.2 バックエンド

```
GKE Autopilot (Golang 1.25+)
├── Web Framework (Gin)
├── WebSocket (gorilla/websocket)
├── PostgreSQL Client (pgxpool)
├── Cloud SQL Auth Proxy (サイドカー)
└── Firebase Admin SDK
```

**選定理由:**
- 高パフォーマンス（並行処理）
- 型安全（大規模開発）
- GKE Autopilot（WebSocket常時接続に最適、ゲームサーバー管理）
- GCP公式SDK充実

### 3.3 データベース

```
Cloud SQL PostgreSQL 16 (Regional: asia-northeast1)
├── 環境ごとに独立インスタンス (dev / stg / prod)
├── マシンタイプ: dev/stg: db-g1-small, prod: TBD
├── IAM DB 認証 (Cloud SQL Auth Proxy 経由)
├── JSONB による複雑な状態管理
└── Backup: Daily (prod)
```

**選定理由:**
- ACID トランザクション + SELECT FOR UPDATE による行ロック
- JSONB でゲーム状態を柔軟に格納
- Cloud SQL Auth Proxy + IAM 認証でセキュアな接続
- コスト効率 (Spanner 比 ~90% 削減)

### 3.4 認証

```
Firebase Authentication
├── Email/Password
└── Google Sign-In
```

### 3.5 インフラ

```
Google Cloud Platform (4プロジェクト構成)
├── overload-party-shared
│   ├── GKE Autopilot (API + WebSocket サーバー — 全環境共有)
│   ├── Artifact Registry (Docker イメージ)
│   └── Ingress (GCE L7 LB, パスベースルーティング)
├── overload-party-{dev,stg,prod}
│   ├── Cloud SQL PostgreSQL (Database — 環境ごと独立)
│   ├── Cloud Object Storage (Replays, Logs)
│   └── Cloud Monitoring
```

### 3.6 IaC・CI/CD

```
Infrastructure as Code
└── Terraform (`overload-party-infra` リポで管理)

CI: GitHub Actions
├── テスト・Lint
├── Docker イメージビルド
└── Artifact Registry プッシュ

CD: ArgoCD (on GKE)
└── GitOps によるK8sマニフェスト同期・デプロイ
```

---

## 4. システムアーキテクチャ

### 4.1 全体構成図

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               React + Capacitor Client                  │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │  │
│  │  │ Game View  │  │   Event    │  │  WebSocket │        │  │
│  │  │  (React)   │  │  Handler   │  │   Client   │        │  │
│  │  └────────────┘  └────────────┘  └────────────┘        │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │  │
│  │  │   State    │  │  Framer    │  │   Audio    │        │  │
│  │  │  (Zustand) │  │  Motion    │  │   (Howler) │        │  │
│  │  └────────────┘  └────────────┘  └────────────┘        │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebSocket (wss://)
                             │ HTTPS (REST API)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  GKE Autopilot (Application Layer)              │
│  ┌───────────────────────┐  ┌───────────────────────┐          │
│  │   api-server Pod      │  │   ws-server Pod       │          │
│  │  ┌─────────────────┐  │  │  ┌─────────────────┐  │          │
│  │  │  REST API       │  │  │  │  WebSocket      │  │          │
│  │  │  (Gin)          │  │  │  │  Handler        │  │          │
│  │  └─────────────────┘  │  │  └─────────────────┘  │          │
│  │  ┌─────────────────┐  │  │  ┌─────────────────┐  │          │
│  │  │  Game Logic     │  │  │  │  Game Logic     │  │          │
│  │  │  Engine         │  │  │  │  Engine         │  │          │
│  │  └─────────────────┘  │  │  └─────────────────┘  │          │
│  │  ┌─────────────────┐  │  │  ┌─────────────────┐  │          │
│  │  │  Cloud SQL      │  │  │  │  Matchmaking    │  │          │
│  │  │  Auth Proxy     │  │  │  │  (In-Memory)    │  │          │
│  │  │  (sidecar)      │  │  │  │                 │  │          │
│  │  └─────────────────┘  │  │  ┌─────────────────┐  │          │
│  └───────────────────────┘  │  │  Cloud SQL      │  │          │
│                              │  │  Auth Proxy     │  │          │
│                              │  │  (sidecar)      │  │          │
│                              │  └─────────────────┘  │          │
│                              └───────────────────────┘          │
└───────────────────────────────┬────────────────────────────────┘
                                │ PostgreSQL (localhost:5432)
                                ▼
                  ┌────────────────────────────────────┐
                  │          Data Layer                │
                  │  ┌──────────────────────────────┐  │
                  │  │   Cloud SQL PostgreSQL 16    │  │
                  │  │  ┌────────┐  ┌──────────┐   │  │
                  │  │  │ Games  │  │GameStates│   │  │
                  │  │  └────────┘  └──────────┘   │  │
                  │  │  ┌────────┐  ┌──────────┐   │  │
                  │  │  │Players │  │ Matches  │   │  │
                  │  │  └────────┘  └──────────┘   │  │
                  │  └──────────────────────────────┘  │
                  └────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      External Services                          │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │    Firebase      │  │  Cloud Storage   │                    │
│  │  Authentication  │  │  (Replays/Logs)  │                    │
│  └──────────────────┘  └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 インフラ基盤の選定

> 比較検討の詳細（コスト表・6軸比較）は [DESIGN_NOTES.md](DESIGN_NOTES.md#インフラ基盤の選定ログ) を参照。

#### 4.2.1 選定結果: GKE Autopilot

Cloud Run + Redis と GKE Autopilot を比較検討し、**GKE Autopilot を採用した。**

| 選定理由 | 概要 |
|---------|------|
| WebSocket適合性 | 接続時間制限なし。PDB + preStop hook で接続ドレインを完全制御 |
| アーキテクチャ簡素化 | 同一Pod内で対戦完結 → Redis Pub/Sub層不要 |
| コスト優位 | Redis + VPC Connectorの固定費不要。24h稼働時 5K接続で~$250/月（Cloud Run比 約48%減） |
| ゲームサーバー運用 | Agones統合が自然 |

**クラスタ構成（1クラスタ・Namespace分離）:**

GKE Autopilot クラスタは共有プロジェクト `overload-party-shared` に配置し、Namespace で環境を分離する。各環境の Cloud SQL は環境別プロジェクト（`overload-party-dev` 等）に配置し、**Workload Identity + Cloud SQL Auth Proxy** でクロスプロジェクトアクセスする。

```
[GKE Autopilot Cluster] overload-party-shared / asia-northeast1
  ├── Namespace: dev
  │     └── game-server replicas: 0 (開発時以外)
  ├── Namespace: staging
  │     └── game-server replicas: 0 (開発時以外)
  ├── Namespace: prod
  │     ├── Deployment: game-server (Go)
  │     │     replicas: 4 (5K接続) / 8 (10K接続)
  │     │     resources: { cpu: "1", memory: "2Gi" }
  │     │     Pod Anti-Affinity: ゾーン分散
  │     ├── Service: type=ClusterIP, sessionAffinity=ClientIP
  │     └── Ingress: External HTTP(S) LB (WebSocket対応)
  ├── Namespace: argocd
  │     └── ArgoCD (常時稼働)
  └── 各Namespaceに Deployment: matchmaker (Go)
```

#### 4.2.2 状態管理方式: PostgreSQL 直接書き込み

全アクションを Cloud SQL PostgreSQL に直接書き込む。Pod はステートレスとし、ゲーム状態は常に DB が正とする。

> インメモリ + チェックポイント方式との比較は [DESIGN_NOTES.md](DESIGN_NOTES.md#db書き込みコスト分析) を参照。

| 項目 | 内容 |
|------|------|
| 書き込み方式 | 毎アクション PostgreSQL トランザクション（SELECT FOR UPDATE） |
| マシンタイプ (prod) | TBD（同時接続数に応じてスケール） |
| 追加レイテンシ | ~5-10ms/アクション（カードゲームでは体感差なし） |
| データ安全性 | **最高** — Pod障害時のデータロストゼロ |
| Pod特性 | **完全ステートレス** — 任意のPodで任意のゲームを処理可能 |

**データフロー:**

```
[クライアント] → [GKE Pod] → [Cloud SQL PostgreSQL]
                  ↑バリデーション   ↑毎アクション読み書き（SELECT FOR UPDATE）
                  ↑ブロードキャスト  ↑GameEvents追記（イベントソーシング）
```

### 4.3 通信フロー

#### 4.3.1 ゲーム開始フロー

```
Client                GKE Pod              Cloud SQL
     │                          │                       │
     │  1. Connect WebSocket    │                       │
     ├─────────────────────────>│                       │
     │                          │                       │
     │  2. Join Game Request    │                       │
     ├─────────────────────────>│                       │
     │                          │  3. Read GameState    │
     │                          ├──────────────────────>│
     │                          │<──────────────────────┤
     │                          │                       │
     │  4. GameState Response   │                       │
     │<─────────────────────────┤                       │
     │                          │                       │
```

#### 4.3.2 アクション実行フロー

```
Player A (Client)        GKE Pod              Cloud SQL       Player B (Client)
     │                      │                       │                  │
     │  1. Play Card        │                       │                  │
     ├─────────────────────>│                       │                  │
     │                      │  2. Validate Action   │                  │
     │                      │                       │                  │
     │                      │  3. Update State      │                  │
     │                      │      (Transaction)    │                  │
     │                      ├──────────────────────>│                  │
     │                      │<──────────────────────┤                  │
     │                      │                       │                  │
     │                      │  4. Record Event      │                  │
     │                      ├──────────────────────>│                  │
     │                      │<──────────────────────┤                  │
     │                      │                       │                  │
     │  5. State Update     │  6. State Update       │                  │
     │  + available_actions │  (actions なし)         │                  │
     │  + turn_controls     │                        │                  │
     │<─────────────────────┤─────────────────────────────────────────>│
     │                      │  (WebSocket broadcast) │                  │
```

> **Note:** `available_actions` は `my` の配下に含まれ、アクティブプレイヤーのみに送信される。
> カードに紐付かないゲームフロー制御（フェーズ終了、手札破棄）は `turn_controls` として別メッセージで送信。
> サーバーが毎状態更新時にフェーズごとの有効アクションを計算し送信することで、
> クライアント側にゲームロジックを重複して持たせない設計（Master Duel 方式）。
> 詳細は `API_REFERENCE.md` の `game_state` / `turn_controls` セクションを参照。

#### 4.3.3 ゲーム開始フロー

マッチ成立後、スターター選出フェーズは存在しない。デッキ30枚をシャッフルし、初期手札5枚をドローして即座に T1 が開始される（フィールドは空の状態）。

プレイヤーは手札からカードをデプロイして盤面を構築していく。デプロイターンが 0 のカード（Serverless 等）は即座に表向きで稼働し、1 以上のカードは裏向きで配置される。

---

## 5. データ設計 (Data Architecture)

PostgreSQL をデータストアとして使用。テーブル構成、カラム仕様、JSONスキーマの詳細は **[DATA_DESIGN.md](DATA_DESIGN.md)** を参照。

主要テーブル:
- **games / game_states / game_events** — ゲームライフサイクル・状態・イベントログ
- **players / player_daily_battle** — プレイヤー管理・デイリーバトル制限
- **card_definitions** — カード定義マスター（起動時にメモリキャッシュ）
- **player_cards / decks / deck_cards** — 所持カード・デッキ構築
- **products / subscriptions / one_time_purchases** — ショップ・課金
- **cosmetic_items / player_items** — コスメティクス

---

## 6. API設計

- **REST API**: プレイヤー管理、デッキ管理、NPC 対戦、ショップなど
- **WebSocket API**: PvP マッチメイキング、リアルタイム対戦、スタンプ送信など

各エンドポイントの詳細（パス、リクエスト/レスポンス構造、認証方式）は **[API_REFERENCE.md](API_REFERENCE.md)** を参照。

---

## 7. 認証・認可

### 7.1 Firebase Authentication

| 項目 | 内容 |
|------|------|
| サービス | Firebase Authentication |
| 対応ログイン方式 | Email/Password、Google Sign-In |
| トークン形式 | Firebase ID Token（JWT） |
| 検証方法 | Firebase Admin SDK で `VerifyIDToken` |

**通信経路別の認証方式:**

| 通信経路 | 認証タイミング | 理由 |
|---------|-------------|------|
| REST API | **毎リクエスト** | ステートレスな HTTP 通信のため、都度検証が必要 |
| WebSocket | **接続時のみ** | 接続確立後は同一セッション内で信頼。JWT検証は ~0.1ms のローカル CPU 処理（ネットワーク通信なし）だが、WebSocket メッセージごとに検証する必要はない |

**REST APIリクエスト認証フロー:**

```
クライアント                    GKE Pod
     │                              │
     │  Authorization: <ID Token>   │
     ├─────────────────────────────>│
     │                              │ Firebase Admin SDKで検証
     │                              │  ┌──────────────┐
     │                              │  │ 検証成功？    │
     │                              │  ├──────────────┤
     │                              │  │ Yes → 処理続行│
     │                              │  │ No  → 401返却 │
     │                              │  └──────────────┘
```

### 7.2 管理者認可 (Admin Authorization)

| 項目 | 内容 |
|------|------|
| 方式 | Firebase Custom Claims (`admin: true`) |
| 設定方法 | Firebase Admin SDK で `SetCustomUserClaims` を実行（CLIまたはスクリプト） |
| 検証方法 | api-server が ID Token をデコードし `admin` クレームを確認 |
| 未認可時 | HTTP 403 Forbidden |

> Admin ユーザーの登録は Firebase Console または管理スクリプトで行い、アプリ上での自己昇格はできない設計とする。

### 7.3 WebSocket認証

| 項目 | 内容 |
|------|------|
| トークン送信方法 | 接続時のクエリパラメータ `?token=<ID Token>` |
| 検証タイミング | WebSocket接続アップグレード前 |
| 失敗時の動作 | HTTP 401 を返してアップグレード拒否 |

---

## 8. 課金システム

> 課金プラン・スタミナ仕様・カード入手モデル等のビジネスルールは [MONETIZATION.md](MONETIZATION.md) を参照。
> 本セクションではアーキテクチャとしての技術的実装方針を記載する。

### 8.1 決済基盤

| プラットフォーム | 決済手段 | SDK |
|----------------|---------|-----|
| iOS | App Store In-App Purchase | StoreKit 2 |
| Android | Google Play Billing | Google Play Billing Library 7+ |

> プレミアムプラン: Auto-renewable Subscription（月額サブスク）。カードセット・コレクション: Non-consumable（買い切り）。

### 8.2 サーバーサイド検証

購入レシートは**必ずサーバーサイドで検証**する。クライアント側の検証結果は信頼しない。

```
Client                GKE Pod                   Apple / Google
     │                          │                          │
     │  1. ストア購入UI起動     │                          │
     │  ──(StoreKit/Billing)──> │                          │
     │                          │                          │
     │  2. 決済完了              │                          │
     │  (receipt / purchaseToken)│                          │
     │  ───────────────────────>│                          │
     │                          │  3. Receipt 検証          │
     │                          │  POST verifyReceipt (Apple)│
     │                          │  GET purchases (Google)   │
     │                          ├─────────────────────────>│
     │                          │<─────────────────────────┤
     │                          │  4. 検証OK → DB更新       │
     │                          │     (冪等: purchase_token │
     │                          │      で重複チェック)       │
     │                          │                          │
     │  5. 購入結果レスポンス    │                          │
     │<─────────────────────────┤                          │
```

### 8.3 検証API・サーバー通知

**買い切り商品の検証:**

| プラットフォーム | 検証方式 | エンドポイント |
|----------------|---------|---------------|
| Apple | App Store Server API v2 | `GET /inApps/v2/history/{transactionId}` |
| Google | Google Play Developer API | `GET /androidpublisher/v3/.../purchases/products/{productId}/tokens/{token}` |

**サブスク（プレミアムプラン）の状態管理:**

| プラットフォーム | サーバー通知 | 用途 |
|----------------|-------------|------|
| Apple | App Store Server Notifications V2 | 更新・解約・猶予期間・返金等のイベントを受信 |
| Google | Real-time Developer Notifications (RTDN) via Pub/Sub | 同上 |

> サブスクの状態変更（自動更新・解約・猶予期間等）はサーバー通知で受信し、`premium_expires_at` を更新する。クライアント起点のポーリングは行わない。

### 8.6 Webhook 受信（api-server 内）

Apple / Google からのサーバー通知は GKE 上の **api-server** で受信する。

```
Apple Server Notifications V2  ──>  api-server (GKE)  ──>  Cloud SQL
Google RTDN (Pub/Sub push)     ──>  api-server (GKE)  ──>  Cloud SQL
```

| 項目 | 内容 |
|------|------|
| 受信先 | api-server Pod (GKE Autopilot) |
| ランタイム | Go |
| 責務 | サーバー通知の受信・署名検証・DB 更新 |
| 認証 | Apple: JWS 署名検証 / Google: Pub/Sub push トークン検証 |
| エンドポイント | `POST /webhooks/apple` / `POST /webhooks/google` |

### 8.7 冪等性と不正対策

| 対策 | 実装方法 |
|------|---------|
| 重複購入防止 | `purchase_token`（Apple: `transactionId` / Google: `purchaseToken`）を Cloud SQL に保存し、UNIQUE制約で重複INSERT を排除 |
| レシート再利用防止 | 検証済みトークンをDBに記録。同一トークンでの再リクエストは既存結果を返却 |
| クライアント改ざん防止 | 課金状態（`is_premium`、`PlayerCards`）はサーバーのみが更新。クライアントからの直接変更は不可 |

### 8.8 購入処理のトランザクション

**買い切り商品（カードセット・コレクション）:**

```
BEGIN
  1. one_time_purchases に purchase_token が存在しないことを確認
  2. one_time_purchases に INSERT (purchase_token, player_id, product_id, verified_at)
  3. 商品種別に応じた処理:
     - カードセット → PlayerCards に対象カードを一括 INSERT
     - コレクション → 所持テーブルに INSERT
COMMIT
```

> トランザクション全体が成功するか全体がロールバックされるため、「決済済みだがカードが付与されない」状態は発生しない。

**サブスクリプション（プレミアムプラン）:**

```
サーバー通知受信時（payment-webhook が処理）:
  1. 通知種別に応じた処理:
     - 新規登録/更新成功 → is_premium = true, premium_expires_at = 次回更新日
     - 解約（期間終了）→ premium_expires_at 以降に is_premium = false
     - 猶予期間         → is_premium = true を維持、premium_expires_at を猶予期限に延長
     - 返金             → is_premium = false（即時失効）
```

**猶予期間のポリシー:**

| 項目 | 内容 |
|------|------|
| Apple | Billing Retry Period（最大60日）中はプレミアム維持 |
| Google | Grace Period（通常3〜7日）中はプレミアム維持 |
| 猶予終了後 | `is_premium = false`、スタミナ制に戻す |

> 猶予期間中もプレミアムを維持する方針。決済が復旧すれば自動更新され、復旧しなければ猶予終了後に失効する。ユーザー体験を優先し、一時的な決済エラーでプレミアムが途切れることを防ぐ。

---

## 9. リアルタイム通信

### 9.1 WebSocket接続管理

| 機能 | 内容 |
|------|------|
| 接続登録 | `playerID → WebSocket接続` のマップをPod内インメモリ管理 |
| ゲーム参加 | `gameID → []playerID` のマップを管理（同一Pod内で対戦完結） |
| ブロードキャスト | ゲーム内の全プレイヤー（Pod内の2人）に同じメッセージを送信 |
| スレッドセーフティ | `sync.RWMutex` で同時アクセスを制御 |

### 9.2 再接続処理

```
再接続リクエスト
        │
        ▼
Cloud SQL から最新 GameState を取得
        │
        ▼
接続をConnectionManagerに再登録
        │
        ▼
最新状態をクライアントに送信
```

### 9.3 切断検知とタイムアウト

| パラメータ | 値 |
|-----------|-----|
| Ping/Pong 間隔 | 15秒 |
| Pong 応答タイムアウト | 5秒（応答なしで切断と判定） |
| 再接続猶予時間 | **60秒** |
| 猶予超過時の処理 | 切断プレイヤーの**敗北**（不戦勝） |

**切断処理フロー:**

```
Pong 応答なし（5秒）
     │
     ▼
切断と判定
     │
     ├── 対戦相手に `opponent_disconnected` 通知
     │
     ▼
60秒タイマー開始
     │
     ├── 60秒以内に再接続 → §8.2 の再接続処理を実行、タイマー解除
     │
     └── 60秒超過 → 切断プレイヤーの敗北
          ├── Games.winner_id = 対戦相手
          ├── 勝敗カウント更新（通常の勝敗と同等に扱う）
          └── 対戦相手に `game_end` (reason: `opponent_timeout`) 通知
```

> **切断ペナルティ:** 初期段階では導入しない。悪質な切断が増加した場合に、常習者への追加ペナルティを検討する。

### 9.4 WebSocket ヘルスチェック

| 項目 | 内容 |
|------|------|
| サーバー → クライアント | 15秒間隔で Ping 送信 |
| クライアント → サーバー | Pong 応答（WebSocket プロトコル標準） |
| タイムアウト | 5秒以内に Pong がなければ切断と判定 |

## 9.5 マッチメイキング詳細設計

### 9.5.1 マッチメイキングアルゴリズム

ランダムマッチメイキングを採用する。キュー内のプレイヤーを待機時間順にFIFOでマッチングする。

> **レーティング制は廃止。** 教育系カードゲームとしてデッキ構築と学習を楽しむことを重視し、スキルベースのマッチングは行わない。

**マッチングキューのデータ構造:**

| フィールド | 型 | 説明 |
|---|---|---|
| `player_id` | string | プレイヤーID |
| `deck_id` | string | 使用デッキID |
| `enqueued_at` | timestamp | キュー登録時刻 |

**マッチング処理フロー:**

```
1. プレイヤーがキューに参加
   ├─ スタミナチェック（無課金の場合）
   ├─ デッキ有効性チェック（30枚・制限ルール適合）
   └─ キューに登録

2. マッチングループ（1秒間隔で実行）
   ├─ キュー内のプレイヤーを登録時刻順にソート
   ├─ 先頭から2人ずつペアリング
   └─ マッチ成立したペアごとにゲーム作成

3. ゲーム作成
   ├─ Gamesレコード作成
   ├─ 先攻/後攻をランダム決定
   ├─ 両プレイヤーにWebSocketで通知（game_matched）
   └─ デッキシャッフル・初期手札ドロー → T1 開始（フィールド空）
```

**キューの実装方式:**

| 項目 | 内容 |
|------|------|
| データストア | matchmaker Pod のインメモリ（Go の `sync.Map` + スライス） |
| マッチングワーカー | Pod内の goroutine（1秒間隔のティッカー） |
| キュー離脱 | 明示的な離脱 or 60秒の Heartbeat タイムアウト |
| Pod再起動時 | キュー消失 → プレイヤーは再キュー（WebSocket切断検知で自動リトライ） |

> **注:** マッチメイキングキューはPodインメモリで管理する。DBには書き込まない。マッチ成立後のゲーム作成のみCloud SQLに書き込む。

### 9.5.2 WebSocket メッセージ

**Client → Server:**

| タイプ | 説明 |
|------|------|
| `game_enter` | ゲーム入室（`game_id`, `deck_id` を含む） |
| `matchmaking_start` | マッチメイキング開始（`deck_id` を含む） |
| `matchmaking_cancel` | マッチメイキングキャンセル |
| `game_action` | ゲームアクション（`actionType`, `data` を含む） |
| `use_stamp` | スタンプ使用 |
| `ping` | ハートビート |

**Server → Client:**

| タイプ | 説明 |
|------|------|
| `game_state` | ゲーム状態更新 |
| `game_over` | ゲーム終了通知 |
| `error` | エラーメッセージ |
| `game_entered` | ゲーム入室確認 |
| `matchmaking_started` | マッチメイキング開始確認 |
| `matchmaking_cancelled` | マッチメイキングキャンセル確認 |
| `match_found` | マッチ成立通知（`gameId`, `opponentName`, `isFirst`） |
| `action_rejected` | アクション拒否通知 |
| `action_performed` | アクション実行通知（相手のアクション情報、`battle_start` / `turn_start` バナーイベント含む） |
| `stamp_used` | スタンプ使用通知 |
| `turn_controls` | ゲームフロー制御（フェーズ終了可否、手札破棄枚数） |
| `game_state_restore` | ゲーム状態復元（再接続時） |
| `pong` | ハートビート応答 |

---

## 10. ゲームロジック

### 10.1 ターン管理

**フェーズ順序:**

| フェーズ | 内容 |
|------|------|
| `draw` | リポジトリから手札に1枚ドロー |
| `yield` | バックエンドリソースのInsight生成処理 |
| `main` | カードプレイ・スケールアップ・アタッチメント等 |
| `battle` | 攻撃実行 |
| `end` | エンドフェーズ処理、ターン切り替え |

**フェーズ進行フロー:**

```
draw → yield → main → battle → end → (ActivePlayer切替) → draw ...
```

**エンドフェーズの詳細手順:**

| 手順 | 処理 | 備考 |
|------|------|------|
| 1 | 一時効果の終了 | `duration: "this_turn"` の `temporaryEffects` を除去 |
| 2 | Elastic 値のリセット | Elastic カードのスループット / Yield を base 値に戻す |
| 3 | Insight生成 | バックエンドの各DB系・ストレージ系リソースが Insight を生成し、Insightプールに加算 |
| 4 | 手札上限チェック | 手札が **6枚** を超過している場合、サーバーが `discard_prompt` を送信 |
| 5 | プレイヤーが破棄カードを選択 | クライアントが `discard_hand` で破棄するカードを送信（15秒タイムアウト） |
| 6 | タイムアウト時の自動処理 | 手札の末尾から自動的に破棄（古い順） |
| 7 | ターン切り替え | `active_player` を反転し、次のプレイヤーの `draw` フェーズへ |

### 10.2 チェーン解決

**解決アルゴリズム:**

| 項目 | 内容 |
|------|------|
| 解決順序 | LIFO（スタックの逆順） |
| アクションタイプ | `attack` / `component_effect` / `reactive` |
| 解決後 | 解決済みエントリをクリア |

### 10.3 効果計算

**リソーススタッツ計算の優先順序:**

| 優先度 | 適用内容 |
|--------|----------|
| 1 | ベース値（カード定義） |
| 2 | Rank倍率（small / medium / large） |
| 3 | Instance Family補正（M / C / R） |
| 4 | Platformカードの効果 |
| 5 | Attachmentの効果 |
| 6 | 一時効果（そのターンのみ） |
| 7 | 現在AV = MaxAV − ダメージ蔓積量 |

### 10.4 Available Actions と NPC AI 統合

**Available Actions（Master Duel 方式）:**

サーバーが `ComputeAvailableActions()` でフェーズごとの有効アクションを計算し、クライアントとNPC AIの両方に提供する。

| 項目 | 内容 |
|------|------|
| 計算タイミング | 状態更新ごと（`game_state_view.go`）、NPC ターン開始時（`game_service.go`） |
| 関数 | `engine.ComputeAvailableActions(state, game, playerNum, ...)` |
| 戻り値 | `[]engine.AvailableAction`（タイプ別 discriminated union） |
| クライアント向け | `ClientGameState.my.available_actions` に含めて WebSocket 送信 |
| NPC 向け | `runNPCTurnIfNeeded` 内で計算し Strategy に渡す |

**AvailableAction のアクションタイプ:**

| Type | 主要フィールド |
|------|---------------|
| `play_card` | `HandInstanceID`, `CardID`, `ValidZones`, `ValidTargets`, `Cost` |
| `attack` | `SourceInstanceID`, `ValidTargets` |
| `scale_up` | `SourceInstanceID`, `Cost`, `TargetRank`, `NeedsFamily` |
| `distribute_yield` | `SourceInstanceID`, `RemainingCapacity` |
| `activate_effect` | `SourceInstanceID`, `ValidTargets`, `EffectTargetType` |
| `set_reactive` | `SourceInstanceID` |

ゲームフロー制御（フェーズ終了、手札破棄）は `available_actions` に含めず、`turn_controls` メッセージとして別途送信される。

**NPC AI アーキテクチャ:**

```
engine.ComputeAvailableActions()
        │
        ▼
┌─────────────────────┐
│  Strategy interface  │  DecideMainPhaseActions(state, game, playerNum, available)
│                      │  DecideBattlePhaseActions(state, game, playerNum, available)
│                      │  DecideDiscard(state, playerNum)
│                      │  DecideStartingResources(deckCards)
└────────┬────────────┘
         │
    ┌────┴────┐
    ▼         ▼
StandardAI   FactionAI (SD / Tenki / Sugar / Tuners)
```

NPC は `[]AvailableAction` から最適なアクションを選択するのみ。
アクションの有効性判定はすべて engine 側が担当し、ロジック重複を排除。

**NPC の決定フロー（Main Phase）:**

| 順序 | 処理 | ヘルパー関数 |
|------|------|-------------|
| 1 | Strategy/Incident カードを使用 | `doImmediateActions()` — `evaluateCard` でスコアリング |
| 2 | Resource カードをデプロイ | `doDeployActions()` — `pickBestZone` でゾーン選択 |
| 3 | フィールドエフェクトを発動 | `decideActivateActions()` — `selectTargetFromValid` でターゲット制約 |
| 4 | スケールアップ | `doScaleUpActions()` — `AvailableAction.Cost` / `TargetRank` を使用 |
| 5 | Insight 配分 | `doDistributeYieldActions()` — `RemainingCapacity` で greedy 配分 |
| 6 | フェーズ終了 | `makeEndPhaseAction()` |

**ゾーン追跡:** `ComputeAvailableActions` は初期状態で計算されるため、`usedZones map[string]bool` を `DecideMainPhaseActions` 内で管理し、デプロイ済みスロットをフィルタする。

**NPC 関連ファイル:**

| ファイル | 役割 |
|---------|------|
| `internal/npc/ai.go` | Strategy インターフェース、StandardAI 実装 |
| `internal/npc/faction_ai.go` | FactionAI（陣営別パラメータ・オーバーライド） |
| `internal/npc/action_filter.go` | AvailableAction 用ヘルパー（`filterByType`, `pickBestZone`, `findBestTargetFromValid` 等） |
| `internal/npc/evaluate.go` | カードスコアリング、ターゲット選択ヒューリスティクス |
| `internal/npc/targeting.go` | ターゲット選択戦略（`weakestInZone`, `strongestInZone` 等） |
| `internal/npc/decks.go` | 陣営別デッキ定義 |

---

## 11. 状態管理

### 11.1 楽観的ロック

| 項目 | 内容 |
|------|------|
| メカニズム | `GameStates.version` フィールドで楽観的ロック |
| 更新手順 | 読み取り→更新処理→version++→書き込み（トランザクション内） |
| 競合時 | PostgreSQL の SELECT FOR UPDATE で排他制御。競合時は自動リトライ |
| 利点 | デッドロックなし、コンフリクト時のみリトライ |

### 11.2 イベントソーシング

| 項目 | 内容 |
|------|------|
| 目的 | リプレイ機能・デバッグ用に全アクションを記録 |
| テーブル | `GameEvents`（追記のみ） |
| リプレイ方法 | 初期状態からイベントを順番に適用 |
| リプレイクエリ | `sequence_number ASC` 順に取得 |

### 11.3 トランザクション失敗時のフィードバック

PostgreSQL トランザクションが失敗した場合、クライアントに `action_rejected` メッセージを返す。

**Server → Client メッセージ:**

```json
{
  "type": "action_rejected",
  "originalAction": "attack",
  "errorCode": "CONFLICT",
  "message": "State conflict detected",
  "retryable": true
}
```

**エラーコード一覧:**

| errorCode | 意味 | retryable |
|-----------|------|-----------|
| `CONFLICT` | 楽観的ロックの競合（他プレイヤーが先に状態を更新） | `true` |
| `TIMEOUT` | トランザクションタイムアウト | `true` |
| `INVALID_STATE` | 状態不整合（フェーズ遷移済み等） | `false` |
| `INTERNAL_ERROR` | 内部エラー | `false` |

**リトライ方式:**

| レイヤー | リトライ回数 | 説明 |
|---------|------------|------|
| サーバー側 | 最大3回 | pgxpool によるトランザクション自動リトライ |
| クライアント側 | 最大2回 | `retryable: true` の場合、指数バックオフで自動リトライ |

> サーバー側で3回リトライしても失敗した場合にのみ `action_rejected` をクライアントに送信する。

---

## 12. パフォーマンス最適化

### 12.1 Cloud SQL PostgreSQL 最適化

| 最適化手法 | 内容 |
|----------|------|
| UUID 主キー | gen_random_uuid() でランダム分散 |
| JSONB インデックス | GIN インデックスで JSONB 内検索を高速化（必要に応じて） |
| Foreign Key + CASCADE | 親子関係のテーブルを外部キーで結合、CASCADE DELETE で整合性保証 |
| 接続プーリング | pgxpool による接続プール管理 |

### 12.2 GKE Autopilot 最適化

**Pod リソース設定:**

| 設定項目 | 値 | 理由 |
|----------|-----|------|
| CPU request | 1 vCPU | Goの並行処理に対応 |
| Memory request | 1 Gi | WebSocket接続管理・ゲームロジック処理 |
| Replicas (初期) | 4 | 同時5,000接続を処理 |
| Pod Anti-Affinity | ゾーン分散 | 障害時の影響を分散 |

**K8s リソース設定:**

| リソース | 設定 |
|----------|------|
| PodDisruptionBudget | `minAvailable: 90%` — WebSocket接続のドレイン保護 |
| preStop hook | `sleep 10` — 接続のグレースフルシャットダウン猶予 |
| terminationGracePeriodSeconds | 15 |
| sessionAffinity | ClientIP — 同じクライアントを同一Podにルーティング |

### 12.3 接続プーリング (pgxpool)

| パラメータ | 値 | 説明 |
|----------|-----|------|
| `MinConns` | 2 | 最小接続数 |
| `MaxConns` | 10 | 最大接続数（Pod あたり） |
| `MaxConnLifetime` | 30m | 接続の最大寿命 |

---

## 13. セキュリティ

### 13.1 アクション検証

全アクションで以下の **統一された検証順序** を適用する。各ステップで不正があれば即座にエラーを返し、後続の検証は行わない。

**統一検証順序:**

| 順序 | 検証カテゴリ | 説明 |
|------|------------|------|
| 1 | **フェーズ確認** | 現在のフェーズでそのアクションが許可されているか |
| 2 | **実行元カード確認** | 指定されたカードが手札またはフィールドに存在し、プレイヤーの所有か |
| 3 | **対象確認** | 攻撃対象・効果対象が有効か（存在する、対象に取れる等） |
| 4 | **コスト確認** | Budget・Insight Pool 等のリソースが足りているか |
| 5 | **その他の条件** | 1ターン1回制限、Resizable属性、手札上限など個別ルール |

**アクション別の検証項目:**

| アクション | 1. フェーズ | 2. 実行元 | 3. 対象 | 4. コスト | 5. その他 |
|-----------|-----------|----------|---------|----------|----------|
| `play_card` | Main Phase | 手札に存在 | 配置先が空き | — | デプロイターン 0 なら即表向き、1以上なら裏向き配置 |
| `attack` | Battle Phase | フィールド上の自コンピュート（表向き） | 相手フィールド上の表向きリソース | — | 攻撃済みでない |
| `scale_up` | Main Phase | フィールド上の自リソース（表向き） | — | — | Resizable 属性、現在Rank < 対象Rank |
| `migrate` | Main Phase | フィールド上の表向き新リソース | 表向き旧リソース | — | 新.deploy_turns >= 旧.deploy_turns |
| `distribute_yield` | Main Phase | バックエンドのコンピュート | — | — | Insight Pool 残量 ≥ 分配量、TP上限 |
| `activate_effect` | Main/Battle Phase | 効果を持つカード | 効果の対象 | 効果コスト | 1ターン1回制限 |

### 13.2 レート制限

| 項目 | 値 |
|------|-----|
| 通常リクエスト上限 | 10 req/sec |
| バースト上限 | 20 req |
| 超過時のレスポンス | HTTP 429 Too Many Requests |

### 13.3 CORS設定

環境変数 `ALLOWED_ORIGINS` で許可するオリジンを制御する。

| 環境 | AllowOrigins |
|------|-------------|
| dev | 未設定（全オリジン許可） |
| stg | `https://overloadparty-stg.keyandnotes.com`, `capacitor://localhost`, `http://localhost` |
| prod | `https://overloadparty.keyandnotes.com`, `capacitor://localhost`, `http://localhost` |
| ローカル | 全オリジン許可 |

- REST: `middleware.CORS()` で HTTP レスポンスヘッダを設定
- WebSocket: `websocket.Upgrader.CheckOrigin` でアップグレード時に Origin ヘッダを検証
- `capacitor://localhost`, `http://localhost` は Capacitor (iOS/Android) ネイティブアプリ用

| 項目 | 値 |
|------|-----|
| `AllowMethods` | GET, POST, PUT, DELETE |
| `AllowHeaders` | Authorization, Content-Type |
| `MaxAge` | 12時間 |

### 13.4 ドメイン / DNS / TLS

| 項目 | 値 |
|------|-----|
| ドメイン | `keyandnotes.com`（お名前.com + Cloudflare DNS） |
| TLS 方式 | Cloudflare SSL Flexible（Cloudflare で TLS 終端 → GKE Ingress は HTTP） |

**サブドメイン構成:**

| 環境 | サブドメイン | IP |
|------|------------|-----|
| dev | `overloadparty-dev.keyandnotes.com` | 動的（Ingress 起動時に割当） |
| stg | `overloadparty-stg.keyandnotes.com` | 動的（Ingress 起動時に割当） |
| prod | `overloadparty.keyandnotes.com` | 未定 |

- Cloudflare Universal SSL は `*.keyandnotes.com` をカバー（1 階層のみ）
- そのため `overloadparty-dev` 形式を採用（`dev.overloadparty.keyandnotes.com` は証明書対象外）
- Cloudflare DNS で Proxied (orange cloud) モードを使用
- 静的 IP は使用しない（コスト削減）。代わりに GitHub Actions で Cloudflare DNS を自動更新:
  - **起動時** (`startup.yaml`): Ingress の外部 IP 取得後、Cloudflare API で A レコードを更新
  - **停止時** (`nightly-shutdown.yaml`): DNS を `127.0.0.1` に変更し、予約済み IP を削除

---

## 14. デプロイメント

### 14.1 インフラ管理 (Terraform)

GCPリソースは **Terraform** で管理する。

**GCP プロジェクト構成（4プロジェクト）:**

| プロジェクト | 用途 | 主なリソース |
|-------------|------|------------|
| `overload-party-shared` | 共有インフラ | GKE Autopilot, Artifact Registry, ArgoCD |
| `overload-party-dev` | 開発環境 | Cloud SQL PostgreSQL, IAM |
| `overload-party-stg` | ステージング環境 | Cloud SQL PostgreSQL, IAM |
| `overload-party-prod` | 本番環境 | Cloud SQL PostgreSQL, IAM |

**管理対象リソース:**

| リソース | Terraform モジュール | 配置先プロジェクト |
|---------|---------------------|------------------|
| GKE Autopilot クラスタ | `google_container_cluster` | shared |
| Artifact Registry リポジトリ | `google_artifact_registry_repository` | shared |
| Cloud SQL インスタンス・DB | `google_sql_database_instance`, `google_sql_database` | 各環境 |
| Cloud SQL IAM ユーザー | `google_sql_user` (CLOUD_IAM_SERVICE_ACCOUNT) | 各環境 |
| External HTTP(S) LB | `google_compute_*` | shared |
| Cloud Storage バケット | `google_storage_bucket` | 各環境 |
| IAM / Service Account | `google_service_account`, `google_project_iam_*` | 各環境 |
| Workload Identity 連携 | `google_service_account_iam_member` | 各環境（shared GKE → 環境 GSA） |

**環境戦略:**

| リソース | shared | dev | staging | prod |
|---------|--------|-----|---------|------|
| GKE クラスタ | `overload-party`（1クラスタ） | — | — | — |
| Artifact Registry | `overload-party`（Docker） | — | — | — |
| ArgoCD | Namespace: `argocd`（常時稼働） | — | — | — |
| GKE Namespace | — | `dev` | `staging` | `prod` |
| game-server Pods | — | 0（開発時のみ起動） | 0（開発時のみ起動） | 4〜8（常時稼働） |
| Cloud SQL インスタンス | — | `overload-party-db` | `overload-party-db` | `overload-party-db` |
| Cloud SQL tier | — | db-g1-small | db-g1-small | TBD |
| Workload Identity | — | KSA `game-server` → GSA `game-server-dev@..dev` | 同パターン | 同パターン |


> dev/stg は毎日 2:00 JST に自動停止してコストを最小化する。Cloud SQL 操作はインフラリポジトリ (Cloud Scheduler / Terraform)、K8s 操作は K8s リポジトリ (GitHub Actions) に責務を分離している。

**自動停止の仕組み (2:00 AM JST):**

| 対象 | 方式 | 管理場所 |
|------|------|---------|
| Cloud SQL | Cloud Scheduler → sqladmin API 直接呼び出し (OAuth) | infra: `modules/scheduler/` |
| K8s (Ingress, Pod) | GitHub Actions cron | k8s: `.github/workflows/nightly-shutdown.yaml` |

**手動操作:**

| リポジトリ | スクリプト / ワークフロー | 内容 |
|-----------|--------------------------|------|
| infra | `scripts/cloudsql-start.sh <dev\|stg>` | Cloud SQL 起動 (RUNNABLE 待ち) |
| infra | `scripts/cloudsql-stop.sh <dev\|stg>` | Cloud SQL 停止 |
| k8s | `scripts/env-up.sh <dev\|stg>` | Pod スケール 1 → Ingress 適用 |
| k8s | `scripts/env-down.sh <dev\|stg>` | Ingress 削除 → Pod スケール 0 |
| k8s | `.github/workflows/startup.yaml` | K8s 手動起動 (workflow_dispatch) |

**ディレクトリ構成:**

```
overload-party-infra/
├── environments/
│   ├── dev/          # Cloud SQL, IAM (Workload Identity)
│   ├── stg/
│   └── prod/
├── modules/
│   ├── cloudsql/     # Cloud SQL PostgreSQL インスタンス + DB
│   ├── iam/          # GSA + Cloud SQL role + Workload Identity binding
│   └── scheduler/    # Cloud Scheduler: Cloud SQL 自動停止 (sqladmin API)
└── scripts/
    ├── cloudsql-start.sh
    ├── cloudsql-stop.sh
    ├── infra-up.sh
    └── infra-destroy.sh
```

**Terraform state:** `gs://overload-party-tf-state` に GCS backend で管理。prefix で `terraform/shared`, `terraform/dev` 等に分離。

### 14.2 CI: GitHub Actions

**ワークフロー 1: Game Server (`main` / PR トリガー)**

| ステップ | 内容 |
|------|------|
| 1. Lint | `golangci-lint run` |
| 2. テスト | `go test ./...` |
| 3. ビルド | Docker イメージを `$COMMIT_SHA` タグでビルド |
| 4. プッシュ | Artifact Registry にプッシュ (`asia-northeast1-docker.pkg.dev/overload-party-shared/overload-party`) |
| 5. マニフェスト更新 | K8s マニフェストリポジトリの image tag を更新（ArgoCD 連携） |

**ワークフロー 2: DB マイグレーション (`main` マージ時)**

| ステップ | 内容 |
|------|------|
| 1. psqldef インストール | GitHub Releases から最新版を取得 |
| 2. Cloud SQL Proxy 起動 | WIF 認証でプロキシを起動 |
| 3. dry-run | `psqldef --dry-run` でスキーマ差分を確認 |
| 4. apply | `psqldef` でスキーマを同期 |

> Terraform の `plan` / `apply` も GitHub Actions で実行する（`prod` は手動承認ゲート付き）。

### 14.3 CD: ArgoCD (GitOps)

K8s マニフェストの適用は **ArgoCD** による GitOps で行う。

| 項目 | 内容 |
|------|------|
| ArgoCD 配置 | GKE Autopilot クラスタ内（Namespace: `argocd`、常時稼働） |
| Application 構成 | 環境ごとに ArgoCD Application を定義（`op-dev`, `op-staging`, `op-prod`） |
| 同期対象 | K8s マニフェストリポジトリ（GitHub）の各環境ディレクトリ |
| 同期方式 | prod: 自動同期（Auto Sync）+ Self Heal / dev・staging: 手動同期 |
| デプロイ戦略 | RollingUpdate（maxUnavailable: 0, maxSurge: 25%） |
| ロールバック | ArgoCD UI または `argocd app rollback` で即座に前バージョンへ |

**デプロイフロー:**

```
開発者 → GitHub PR → GitHub Actions (CI)
  │                    ├── テスト・Lint
  │                    ├── Docker ビルド → Artifact Registry
  │                    └── K8s マニフェストリポジトリの image tag を更新
  │
  └→ ArgoCD が差分を検知 → GKE クラスタに自動デプロイ (RollingUpdate)
```

**K8s デプロイ設定:**

| 設定 | 値 | 理由 |
|------|-----|------|
| Strategy | RollingUpdate | 既存ゲームを中断せずにデプロイ |
| maxUnavailable | 0 | 既存Podを停止する前に新Podを起動 |
| maxSurge | 25% | 新旧Pod共存時の最大増分 |
| Region | asia-northeast1 | 日本ユーザー向け低レイテンシ |

### 14.4 アセット配信（Cloud Storage）

カードイラスト等のゲームアセットは **Cloud Storage** で配信する。React アプリのビルドに含めない画像は Cloud Storage から取得し、ブラウザ / Capacitor のキャッシュ機構で管理する。

**構成:**

| コンポーネント | 役割 |
|--------------|------|
| Cloud Storage | アセットファイル（イラスト・音声等）のホスティング |
| Service Worker | クライアント側キャッシュ管理（Cache API） |

> **Cloud CDN は初期段階では不要。** Service Worker + Cache API でクライアント端末にアセットをキャッシュするため、同一ユーザーが同じアセットを再DLすることはない。ユーザー規模拡大後、ダウンロード集中が問題になった場合に CDN を前段に追加する（URL 差し替えのみで対応可能な構成にしておく）。
>
> **CDN 導入時は Cloudflare Free を推奨。** Google Cloud CDN は HTTP(S) LB の固定費（~$18/月）がかかるため、小〜中規模では割高。Cloudflare Free なら CDN 自体は無料で、GCS エグレスを ~90% 削減できる。ただし Free プランでは Origin Rules（Host Header Override）が使えないため、GCS バケット名をサブドメイン名に合わせる必要がある（例: `assets-dev.keyandnotes.com`）。

**配信フロー:**

```
ビルドパイプライン                    Cloud Storage          Client (React)
     │                                   │                      │
     │  1. アセット最適化                 │                      │
     │     (WebP変換 + マニフェスト生成)  │                      │
     │  2. アップロード                   │                      │
     ├──────────────────────────────────>│                      │
     │                                   │  3. マニフェスト取得   │
     │                                   │<─────────────────────┤
     │                                   │  4. 差分アセットDL     │
     │                                   │<─────────────────────┤
     │                                   │  5. Cache API で     │
     │                                   │     ローカル保存       │
```

**更新シナリオ:**

| シナリオ | 対応 |
|---------|------|
| 新カード追加 | 新アセット + マニフェスト更新を Cloud Storage にアップロード。クライアントは次回起動時に差分DL |
| 既存イラスト差し替え | 該当ファイルを上書き。マニフェストのハッシュが変わるため、クライアントが自動検知して再DL |
| アプリ本体更新 | Capacitor ネイティブ部分の変更のみストア審査が必要。Web 部分は OTA 更新可能 |

---

## 15. モニタリング

### 15.1 Cloud Monitoring

**カスタムメトリクス:**

| メトリクス名 | 内容 |
|----------|------|
| `custom.googleapis.com/game/duration` | ゲーム所要時間 |
| `custom.googleapis.com/game/active_games` | 同時対戦数 |
| `custom.googleapis.com/matchmaking/queue_length` | マッチングキュー長 |
| `custom.googleapis.com/websocket/connections` | WebSocket接続数 |

### 15.2 ログ

**ログ構造:**

| フィールド | 内容 |
|--------|------|
| `gameID` | ゲームID |
| `eventType` | イベント種別 |
| `data` | イベント詳細データ |
| `severity` | `INFO` / `WARNING` / `ERROR` |

**ログ基盤:** Cloud Logging（`cloud.google.com/go/logging`）

---

## 16. 実装ロードマップ

### Phase 1: 基盤構築（2-3週間）

- [x] Terraform でGCPリソース構築（GKE, Cloud SQL, IAM）
- [x] Cloud SQL PostgreSQL スキーマ作成
- [x] ArgoCD セットアップ・K8sマニフェストリポジトリ整備
- [x] GitHub Actions CI パイプライン構築
- [x] Firebase Authentication設定
- [x] WebSocket接続管理実装
- [x] 基本的なREST API実装
- [ ] React + Capacitor プロジェクトセットアップ
- [ ] WebSocketクライアント実装
- [ ] 基本的な状態同期確認

### Phase 2: コアゲームロジック（4-6週間）

- [x] ターン進行システム
- [x] カード配置・移動
- [x] Budget/Insight管理
- [x] 基本攻撃
- [x] 勝利条件判定
- [ ] React UI実装（フィールド、手札）

### Phase 3: 詳細メカニクス（4-6週間）

- [x] Resizable/Elastic実装
- [x] Attachmentシステム
- [x] Platform/Reactive
- [x] Strategy/Incident
- [ ] 手動収益化UI
- [ ] アニメーション実装（Framer Motion）

### Phase 4: 高度な機能（3-4週間）

- [x] チェーンシステム
- [x] 継続効果管理
- [ ] ターンタイマー
- [x] リプレイ機能
- [x] マッチメイキング

### Phase 5: Polish & Launch（2-3週間）

- [ ] UI/UXブラッシュアップ
- [ ] サウンド実装
- [ ] チュートリアル
- [ ] パフォーマンス最適化
- [ ] セキュリティ監査
- [ ] ロードテスト
- [ ] ベータテスト
- [ ] 本番リリース

---

## 付録

### A. 環境変数

| 変数名 | 内容 |
|--------|------|
| `DATABASE_URL` | `postgresql://user:pass@host:5432/dbname` または IAM DSN |
| `FIREBASE_CREDENTIALS_PATH` | Firebaseサービスアカウントキーのパス |
| `PORT` | サーバーポート（デフォルト: 9001） |
| `ENV` | `production` / `staging` / `development` |
| `LOG_LEVEL` | `info` / `debug` / `error` |

### B. 開発環境セットアップ

| ステップ | コマンド |
|------|--------|
| Goインストール | `brew install go` |
| 依存関係インストール | `go mod download` |
| PostgreSQL 起動 | `make postgres-up` |
| ローカル実行 (モック) | `make run-local` |

### C. テスト

| テスト種別 | コマンド |
|----------|--------|
| ユニットテスト | `go test ./...` |
| 統合テスト | `go test -tags=integration ./...` |
| カバレッジ | `go test -cover ./...` |

---

**Document Version:** 2.0  
**Last Updated:** 2026-02-26  
**Next Review:** 2026-03-15
