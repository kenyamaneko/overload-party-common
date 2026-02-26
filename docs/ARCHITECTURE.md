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
17. [既知の懸念事項・TODO](#17-既知の懸念事項todo)

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
│   │   ├── sws.yaml
│   │   ├── aozora.yaml
│   │   ├── guruguru.yaml
│   │   ├── miracle.yaml
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
└── Terraform (GCPリソース管理)

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
     │<─────────────────────┤─────────────────────────────────────────>│
     │                      │  (WebSocket broadcast) │                  │
```

#### 4.3.3 Starting Resource 選出フロー

ゲーム開始時に両プレイヤーが初期リソースを選出・同時公開するフロー。

```
Player A (Client)        GKE Pod              Cloud SQL       Player B (Client)
     │                      │                       │                  │
     │  1. select_starting  │                       │                  │
     │     {frontId, backId}│                       │                  │
     ├─────────────────────>│                       │                  │
     │                      │  (Player A選出完了を記録)                 │
     │                      │                       │                  │
     │  2. waiting_opponent │                       │  3. select_starting
     │<─────────────────────┤                       │     {frontId, backId}
     │                      │<─────────────────────────────────────────┤
     │                      │                       │                  │
     │                      │  4. 両者揃った:       │                  │
     │                      │     デッキ検証         │                  │
     │                      │     コスト計算         │                  │
     │                      │     初期状態構築       │                  │
     │                      │                       │                  │
     │                      │  5. Write GameState   │                  │
     │                      ├──────────────────────>│                  │
     │                      │<──────────────────────┤                  │
     │                      │                       │                  │
     │  6. game_start       │  7. game_start        │                  │
     │  {initialState,      │  {initialState,       │                  │
     │   opponentStarters}  │   opponentStarters}   │                  │
     │<─────────────────────┤─────────────────────────────────────────>│
```

**サーバー側の検証:**
- 選出されたカードがデッキに含まれているか
- フロントエンド用カードがフロントエンド配置可能なタイプか（コンピュート系 / Object Storage）
- バックエンド用カードがリソースカードか
- 両カードのデプロイコスト合計が初期Budget（5,000）以下か

**タイムアウト:** 選出に60秒の制限。タイムアウト時はデッキの先頭2枚を自動選出する。

---

## 5. データ設計 (Data Architecture)

> **完全なスキーマ定義:** `db/schema_postgres.sql` を参照。以下は各テーブルの設計意図とカラム仕様の概要。

### 5.1 ゲーム管理 (Game Management)

ゲームのライフサイクルを管理する基盤テーブル。

#### 5.1.1 PostgreSQL スキーマ (games)

**Games** (ゲームマスター)
- **Primary Key:** `game_id`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | UUID | No | UUID |
| `player1_id` | UUID | No | プレイヤー1 ID |
| `player2_id` | UUID | No | プレイヤー2 ID |
| `player1_deck_snapshot` | JSONB | No | 使用デッキのスナップショット（カードIDリスト） |
| `player2_deck_snapshot` | JSONB | No | 使用デッキのスナップショット（カードIDリスト） |
| `status` | VARCHAR(20) | No | `'waiting'`, `'playing'`, `'finished'` |
| `winner_id` | UUID | Yes | 勝者 ID |
| `created_at` | TIMESTAMPTZ | No | 作成日時 (DEFAULT now()) |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 (DEFAULT now()) |
| `finished_at` | TIMESTAMPTZ | Yes | 終了日時 |

#### 5.1.2 JSONスキーマ (Deck Snapshot)

`Games` テーブルの `player1_deck_snapshot`, `player2_deck_snapshot` カラムに格納されるデッキ情報。

| フィールド | 型 | 説明 |
|---|---|---|
| `deckId` | string | 元になったデッキID |
| `cards` | Array[string] | デッキに含まれる `player_card_id` のリスト（順序はシャッフル前） |

#### 5.1.3 関連インデックス

- `GamesByStatus`: `Games(status, created_at DESC)`

### 5.2 ゲーム状態管理 (Game State Management)

対戦中のリアルタイムな状態を管理する構造。

#### 5.2.1 PostgreSQL スキーマ (game_states)

**GameStates** (ゲーム状態・頻繁に更新)
- **Primary Key:** `game_id`
- **Foreign Key:** `game_id REFERENCES games(game_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | UUID | No | 親テーブル参照 |
| `version` | BIGINT | No | 楽観的ロック用バージョン |
| `current_turn` | BIGINT | No | 現在ターン数 |
| `current_phase` | VARCHAR(20) | No | `'draw'`, `'dv_gen'`, `'main'`, `'battle'`, `'end'` |
| `active_player` | BIGINT | No | 現在のターンプレイヤー (1 or 2) |
| `player1_budget` | BIGINT | No | Player 1 Budget |
| `player1_dv_pool` | BIGINT | No | Player 1 DV Pool |
| `player1_field` | JSONB | No | Player 1 フィールド上のカード |
| `player1_hand` | JSONB | No | Player 1 手札 |
| `player1_repository` | JSONB | No | Player 1 リポジトリ（山札） |
| `player1_trash` | JSONB | No | Player 1 トラッシュ |
| `player1_time_bank` | BIGINT | No | Player 1 残り時間 |
| `player2_...` | ... | No | Player 2 各種ステータス（構成はPlayer1と同じ） |
| `chain_stack` | JSONB | Yes | 現在積まれているチェーンスタック |
| `current_action_timer`| BIGINT | Yes | アクションタイマー |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 (DEFAULT now()) |

#### 5.2.2 JSONスキーマ (State Details)

`GameStates` テーブルの JSON カラムに格納される詳細データ構造。

**フィールド状態 (`GameStates.player1_field / player2_field`)**

**対応カラム:** `GameStates` テーブルの `player1_field`, `player2_field`

**フィールド全体レイアウト:** (JSON Root)

| フィールド | 型 | 説明 |
|---|---|---|
| `frontend` | Array[3] | フロントエンドエリアのリソーススロット。固定長3。空きは `null`。<br>要素型: **Resource Object** |
| `backend` | Array[3] | バックエンドエリアのリソーススロット。固定長3。空きは `null`。<br>要素型: **Resource Object** |
| `support` | Array[3] | サポートゾーンのスロット。固定長3。空きは `null`。<br>要素型: **Support Object** |

**フロントエンド・バックエンドリソースのフィールド (Resource Object):**

| フィールド | 型 | 説明 |
|--------|-----|------|
| `instanceId` | string | フィールド上のインスタンス固有ID |
| `cardId` | string | カード定義ID |
| `rank` | string | `"small"` / `"medium"` / `"large"` |
| `instanceFamily` | string等 | `"M"` / `"C"` / `"R"` / null |
| `currentAV` | int | 現在耐久値 |
| `maxAV` | int | AV最大値 |
| `currentTP` | int? | 現在TP（DB系およびオブジェクトストレージは null） |
| `maxTP` | int? | TP最大値（DB系およびオブジェクトストレージは null） |
| `currentDVGen` | int? | 現在DV生成量（コンピュート系リソースは null） |
| `maxDVGen` | int? | DV生成最大値（コンピュート系リソースは null） |
| `damage` | int | 蔓積ダメージ量 |
| `attachments` | array | アタッチメントリスト（instanceId + cardId） |
| `temporaryEffects` | array | 一時効果リスト |
| `monetizedAmount` | int | このターンに収益化済みのTP量（ターン終了時リセット） |
| `hasAttacked` | bool | そのターン攻撃済みか |

**一時効果のオブジェクト構造 (`temporaryEffects` 配列内):**

| フィールド | 型 | 説明 |
|---|---|---|
| `effectType` | string | 効果種別 (`buff_tp`, `mod_av`, `disable_atk` 等) |
| `value` | int | 変動値（加減算） |
| `duration` | string | 持続期間 (`this_turn`, `until_next_turn_end`) |
| `sourceId` | string | 発生源のカード/インスタンスID |

**サポートゾーンカードのフィールド (Support Object):**

| フィールド | 型 | 説明 |
|--------|-----|------|
| `instanceId` | string | インスタンス固有ID |
| `cardId` | string | カード定義ID |
| `faceDown` | bool | 裏向きか否か |

**チェーンスタック (`GameStates.chain_stack`)**

**対応カラム:** `GameStates` テーブルの `chain_stack` (配列)

| フィールド | 型 | 説明 |
|--------|-----|------|
| `chainLevel` | int | チェーンの深さ（1から始まる） |
| `actionType` | string | `"attack"` / `"component_effect"` / `"reactive"` |
| `sourcePlayerId` | string | 発動プレイヤーID |
| `sourceInstanceId` | string | 発動リソースのinstanceId |
| `targetInstanceId` | string | 対象となるリソースのinstanceId |
| `targetChainLevel` | int | 対象チェーンのレベル |
| `effectData` | object | 発動する効果のパラメータ（変動値、対象種別など） |
| `resolved` | bool | 解決済みか否か |

### 5.3 ゲームイベント管理 (Game Event Management)

リプレイや監査のためのログデータ。

#### 5.3.1 PostgreSQL スキーマ (game_events)

**GameEvents** (イベントログ・リプレイ用)
- **Primary Key:** `game_id`, `sequence_number`
- **Foreign Key:** `game_id REFERENCES games(game_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `game_id` | UUID | No | 親テーブル参照 |
| `sequence_number` | BIGINT | No | イベント連番 |
| `event_type` | VARCHAR(50) | No | イベント種別 |
| `player_id` | UUID | Yes | 行動プレイヤー |
| `event_data` | JSONB | No | イベント詳細データ（攻撃対象、使用カードID、ダメージ量など） |
| `created_at` | TIMESTAMPTZ | No | 発生日時 (DEFAULT now()) |

**イベントデータの例:**
- `attack`: `{ "sourceId": "...", "targetId": "...", "damage": 500 }`
- `deploy`: `{ "cardId": "...", "position": 0, "cost": 300 }`

### 5.4 対戦履歴管理 (Match History)

ユーザーの対戦結果の記録。

> **レーティング制は廃止。** 教育系カードゲームとしてデッキ構築と学習を楽しむことを重視し、勝敗ランキングは設けない。

#### 5.4.1 PostgreSQL スキーマ (matches)

**Matches** (対戦履歴)
- **Primary Key:** `match_id`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `match_id` | UUID | No | UUID |
| `game_id` | UUID | No | 対応する `Games` レコード ID（`Games.player1_id/player2_id` を参照） |
| `created_at` | TIMESTAMPTZ | No | マッチ成立日時 |

> **注:** プレイヤーIDは `Games` テーブルの `player1_id` / `player2_id` を正とする。`Matches` からプレイヤーを特定する場合は `game_id` を通じて `Games` テーブルを参照する。

#### 5.4.2 関連インデックス

- `MatchesByGameId`: `Matches(game_id)`

### 5.5 プレイヤー管理 (Player Management)

ユーザーアカウントと基本情報。

#### 5.5.1 PostgreSQL スキーマ (players & player_daily_battle)

**Players** (プレイヤーマスター)
- **Primary Key:** `player_id`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | UUID |
| `firebase_uid` | VARCHAR(128)| No | Firebase Auth UID (Unique) |
| `username` | VARCHAR(50) | No | 表示名 |
| `wins` | BIGINT | Yes | 勝利数 (Default: 0) |
| `losses` | BIGINT | Yes | 敗北数 (Default: 0) |
| `is_premium` | BOOLEAN | No | 課金ステータス (Default: false) |
| `equipped_icon_no` | BIGINT | Yes | 装備中アイコン番号（`CosmeticItems` 参照。NULL: デフォルト） |
| `premium_expires_at` | TIMESTAMPTZ | Yes | サブスク有効期限 |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |

**player_daily_battle** (デイリーバトル管理)
- **Primary Key:** `player_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `remaining_battles` | BIGINT | No | 残りバトル数 (Default: 5) |
| `max_battles` | BIGINT | No | 最大バトル数 (Default: 5) |
| `last_reset_date` | DATE | No | 最終リセット日 |

#### 5.5.2 関連インデックス

- `PlayersByFirebaseUID`: `Players(firebase_uid)` (UNIQUE)

### 5.6 カード定義マスター (Card Definitions)

カードのステータス・効果テキスト・コスト等の定義データ。`CARDS.md` の内容をDB上で管理する。

#### 5.6.1 PostgreSQL スキーマ (card_definitions)

**CardDefinitions** (カード定義マスター)
- **Primary Key:** `card_no`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `card_no` | BIGINT | No | カード番号（`CARDS.md` の `#` に対応） |
| `card_name` | VARCHAR(100) | No | カード名 |
| `faction` | VARCHAR(20) | No | 陣営 (`SWS`, `Aozora`, `Guruguru`, `Miracle`, `Neutral`) |
| `card_type` | VARCHAR(30) | No | カードタイプ (`Compute`, `Container`, `Orchestrator`, `Serverless`, `AI_ML`, `Database`, `ObjectStorage`, `NoSQL`, `CacheDB`, `Platform`, `Attachment`, `Strategy`, `Incident`, `Reactive`) |
| `scalability` | VARCHAR(10) | No | 区分 (`R`, `E`, `RE`, `none`) |
| `stats` | JSONB | No | ステータス定義 |
| `effect_text` | VARCHAR(500) | Yes | 効果テキスト（表示用） |
| `effect_id` | VARCHAR(50) | Yes | 効果ロジックの識別子（サーバー側の効果処理にマッピング） |
| `restriction` | VARCHAR(20) | No | 制限区分 (`unlimited`, `semi_limited`, `limited`) |
| `is_active` | BOOLEAN | No | 有効フラグ（メンテ・バランス調整用） |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |

#### 5.6.2 JSONスキーマ (stats)

**コンピュート系リソースの場合:**

| フィールド | 型 | 説明 |
|---|---|---|
| `throughput` | int | スループット（base値） |
| `throughput_max` | int? | Elastic上限（Elastic以外は `null`） |
| `availability` | int | 可用性 |
| `maintenance_cost` | int | 維持コスト（毎ターン終了時に徴収） |
| `deploy_cost` | int | 開発コスト |
| `sla_penalty` | int | SLAペナルティ |

**DB系リソースおよびオブジェクトストレージの場合:**

| フィールド | 型 | 説明 |
|---|---|---|
| `dv_gen` | int | DV生成量（base値） |
| `dv_gen_max` | int? | Elastic上限 |
| `availability` | int | 可用性 |
| `maintenance_cost` | int | 維持コスト（毎ターン終了時に徴収） |
| `deploy_cost` | int | 開発コスト |
| `sla_penalty` | int | SLAペナルティ |

**その他のカードタイプ（Platform, Attachment, Strategy, Incident, Reactive）:**

| フィールド | 型 | 説明 |
|---|---|---|
| `deploy_cost` | int | 使用コスト（0 の場合は無料） |

#### 5.6.3 関連インデックス

- `CardsByFaction`: `CardDefinitions(faction, card_type)`
- `CardsByType`: `CardDefinitions(card_type)`

#### 5.6.4 サーバー側のカード参照設計

| 用途 | 参照方法 |
|------|----------|
| ゲーム中の効果計算 | サーバー起動時に `CardDefinitions` を全件メモリにキャッシュ。`card_no` → 定義データの `map` で O(1) 参照 |
| デッキ構築画面 | REST API `GET /api/v1/cards` で全カード定義を返却。クライアントはローカルキャッシュ |
| カードバランス更新 | Admin Dashboard からカード定義を更新後、キャッシュリフレッシュを実行 |

**キャッシュリフレッシュ方式:**

| タイミング | 方式 | 説明 |
|-----------|------|------|
| Pod 起動時 | 全件ロード | Cloud SQL から `card_definitions` を全件取得し `sync.Map` にキャッシュ |
| 定期更新 | ポーリング | 各 Pod が **5分間隔**で `CardDefinitions` の `updated_at` を確認し、更新があれば差分リフレッシュ |
| 管理者操作時 | ポーリングで反映 | Admin API でカード定義を更新すると、次回ポーリング（最大5分）で各 Pod がキャッシュをリフレッシュ |

```
[Admin Dashboard / API]
     │
     │ POST/PUT /admin/cards
     ▼
[api-server Pod]
     │
     └── Cloud SQL に書き込み → 定期ポーリングで各 Pod がキャッシュ更新
```

> **設計判断:** カード定義の更新頻度は低い（月数回程度）ため、5分間隔ポーリングで十分。最大5分の遅延は許容範囲。

### 5.7 カード・デッキ管理 (Card & Deck Management)

所持カードとデッキ構築。

#### 5.7.1 PostgreSQL スキーマ (player_cards, decks, deck_cards)

**PlayerCards** (所持カード)
- **Primary Key:** `player_id`, `player_card_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `player_card_id` | UUID | No | カード所持ユニークID |
| `card_no` | BIGINT | No | `CARDS.md` のカード番号 |
| `illustration_variant`| BIGINT | No | イラスト違いID (0:通常) |
| `acquired_at` | TIMESTAMPTZ | No | 獲得日時 |

**Decks** (デッキ定義)
- **Primary Key:** `player_id`, `deck_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `deck_id` | UUID | No | デッキID |
| `deck_name` | VARCHAR(50) | No | デッキ名 |
| `is_valid` | BOOLEAN | No | 有効デッキフラグ (30枚ルール適合) |
| `playmat_no` | BIGINT | Yes | プレイマット番号（`CosmeticItems` 参照。NULL: デフォルト） |
| `sleeve_no` | BIGINT | Yes | スリーブ番号（`CosmeticItems` 参照。NULL: デフォルト） |
| `created_at` | TIMESTAMPTZ | No | 作成日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |

**DeckCards** (デッキ内カード)
- **Primary Key:** `player_id`, `deck_id`, `player_card_id`
- **Foreign Key:** `deck_id REFERENCES decks(deck_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | ルート親参照 |
| `deck_id` | UUID | No | 親テーブル参照 |
| `player_card_id` | UUID | No | `PlayerCards` 参照 |

#### 5.7.2 関連インデックス

- `PlayerCardsByCardNo`: `PlayerCards(player_id, card_no)`
- `DecksByPlayer`: `Decks(player_id, updated_at DESC)`

### 5.8 ショップ・設定管理 (Shop & Settings)

アプリ内課金とユーザー設定。

#### 5.8.1 PostgreSQL スキーマ (products, subscriptions, etc.)

**Products** (商品マスター)
- **Primary Key:** `product_id`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `product_id` | VARCHAR(50) | No | 商品ID (e.g. `theme_aws`) |
| `name` | VARCHAR(100) | No | 商品名 |
| `type` | VARCHAR(20) | No | `card_pack` / `subscription` |
| `price` | BIGINT | No | 価格 (JPY) |
| `content` | JSONB | No | 商品内容 (カードIDリスト等) |
| `is_active` | BOOLEAN | No | 販売中フラグ |

**Subscriptions** (サブスクリプション管理)
- **Primary Key:** `player_id`, `subscription_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `subscription_id` | UUID | No | UUID |
| `product_id` | VARCHAR(50) | No | 商品ID（`premium_monthly` 等） |
| `platform` | VARCHAR(10) | No | `apple` / `google` |
| `purchase_token` | VARCHAR(256) | No | Apple: `originalTransactionId` / Google: `purchaseToken`（UNIQUE） |
| `status` | VARCHAR(20) | No | `active` / `grace_period` / `expired` / `refunded` |
| `current_period_start` | TIMESTAMPTZ | No | 現在の課金期間開始日時 |
| `current_period_end` | TIMESTAMPTZ | No | 現在の課金期間終了日時 |
| `created_at` | TIMESTAMPTZ | No | 初回購入日時 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |

**OneTimePurchases** (買い切り購入履歴)
- **Primary Key:** `player_id`, `purchase_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `purchase_id` | UUID | No | UUID |
| `product_id` | VARCHAR(50) | No | 商品ID（`faction_sws` 等） |
| `platform` | VARCHAR(10) | No | `apple` / `google` |
| `purchase_token` | VARCHAR(256) | No | Apple: `transactionId` / Google: `purchaseToken`（UNIQUE） |
| `purchased_at` | TIMESTAMPTZ | No | 購入日時 |

**UserSettings** (ユーザー設定)
- **Primary Key:** `player_id`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | ユーザーID |
| `language` | VARCHAR(10) | No | 言語設定 (Default: `ja`) |
| `bgm_volume` | BIGINT | No | BGM音量 (0-100) |
| `se_volume` | BIGINT | No | SE音量 (0-100) |
| `push_enabled` | BOOLEAN | No | 通知許可 |
| `updated_at` | TIMESTAMPTZ | No | 更新日時 |

### 5.9 コスメティクス管理 (Cosmetics)

装飾アイテム（プレイマット・スリーブ等）の定義・所持・装備。

#### 5.9.1 PostgreSQL スキーマ (cosmetic_items, player_items)

**CosmeticItems** (装飾アイテムマスター)
- **Primary Key:** `item_type`, `item_no`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `item_type` | VARCHAR(20) | No | アイテム種別（`playmat` / `sleeve` / `icon` / `stamp`） |
| `item_no` | BIGINT | No | アイテム番号（種別内で一意） |
| `item_name` | VARCHAR(100) | No | アイテム名 |
| `description` | VARCHAR(500) | Yes | 説明文 |
| `is_purchasable` | BOOLEAN | No | 購入可能フラグ |
| `is_active` | BOOLEAN | No | 有効フラグ |

**PlayerItems** (プレイヤーの装飾アイテム所持)
- **Primary Key:** `player_id`, `item_type`, `item_no`
- **Foreign Key:** `player_id REFERENCES players(player_id) ON DELETE CASCADE`

| カラム名 | 型 | Nullable | 説明 |
|---|---|---|---|
| `player_id` | UUID | No | 親テーブル参照 |
| `item_type` | VARCHAR(20) | No | アイテム種別 |
| `item_no` | BIGINT | No | アイテム番号 |
| `acquired_at` | TIMESTAMPTZ | No | 獲得日時 |

#### 5.9.2 装備状態の管理

装備中のアイテムは使用時に即座に参照できるよう、所持テーブルではなく **Players / Decks テーブルに直接保持** する。

| アイテム種別 | 装備先テーブル | カラム |
|-------------|-------------|--------|
| アイコン | `Players` | `equipped_icon_no` |
| プレイマット | `Decks` | `playmat_no` |
| スリーブ | `Decks` | `sleeve_no` |

> 対戦開始時にデッキ情報と合わせて取得できるため、追加クエリ不要。

## 6. API設計

### 6.1 WebSocket API

#### 6.1.1 メッセージタイプ一覧

**Client → Server:**

| タイプ | 説明 |
|------|------|
| `join_game` | ゲーム参加 |
| `select_starting` | Starting Resource 選出（ゲーム開始時） |
| `play_card` | カードプレイ |
| `attack` | 攻撃 |
| `activate_effect` | 効果発動 |
| `end_phase` | フェーズ終了 |
| `distribute_dv` | DV分配 |
| `scale_up` | スケールアップ |
| `set_reactive` | リアクティブセット |
| `discard_hand` | 手札上限超過時のカード選択破棄 |
| `use_stamp` | スタンプ（エモート）使用 |

**Server → Client:**

| タイプ | 説明 |
|------|------|
| `game_state` | ゲーム状態全体 |
| `game_event` | 個別イベント通知 |
| `error` | エラー通知 |
| `timer_update` | タイマー更新 |
| `chain_prompt` | チェーン応答要求 |
| `waiting_opponent` | 相手の選出待ち通知（Starting Resource） |
| `game_start` | ゲーム開始通知（初期状態 + 相手のStarting Resource公開） |
| `discard_prompt` | 手札上限超過時の破棄要求 |
| `stamp_used` | スタンプ使用通知（両プレイヤーに配信） |

#### 6.1.2 ペイロード定義

| メッセージタイプ | フィールド | 型 | 説明 |
|------------|--------|-----|------|
| `join_game` | `gameId` | string | ゲームID |
| `join_game` | `playerId` | string | プレイヤーID |
| `select_starting` | `frontendCardId` | string | フロントエンド用の `player_card_id` |
| `select_starting` | `backendCardId` | string | バックエンド用の `player_card_id` |
| `play_card` | `cardInstanceId` | string | 手札のインスタンスID |
| `play_card` | `position.zone` | string | `"frontend"` / `"backend"` / `"support"` |
| `play_card` | `position.index` | int | 0–2 |
| `play_card` | `targetInstanceId` | string | 対象インスタンスID（任意） |
| `attack` | `attackerInstanceId` | string | 攻撃側インスタンスID |
| `attack` | `targetInstanceId` | string | 攻撃対象インスタンスID |
| `scale_up` | `componentInstanceId` | string | 対象リソースID |
| `scale_up` | `targetRank` | string | `"medium"` / `"large"` |
| `scale_up` | `instanceFamily` | string | `"M"` / `"C"` / `"R"`（任意） |
| `distribute_dv` | `distributions` | array | `[{componentInstanceId, amount}]` |
| `game_state` | `gameId` | string | ゲームID |
| `game_state` | `currentTurn` | int | 現在ターン数 |
| `game_state` | `currentPhase` | string | 現在フェーズ |
| `game_state` | `activePlayer` | int | アクティブプレイヤー（1 or 2） |
| `game_state` | `myState` | object | 自分の状態 |
| `game_state` | `opponentState` | object | 相手の状態（手札は枚数のみ） |
| `game_state` | `chainStack` | array | チェーンスタック |
| `game_state` | `timers` | object | タイマー情報 |
| `game_start` | `initialState` | object | 初期ゲーム状態（`game_state` と同構造） |
| `game_start` | `opponentStarters` | array | 相手の Starting Resource 公開情報 `[{cardId, zone, index}]` |
| `discard_hand` | `cardInstanceIds` | array | 破棄するカードの `instanceId` リスト |
| `discard_prompt` | `currentHandSize` | int | 現在の手札枚数 |
| `use_stamp` | `game_id` | string | ゲームID |
| `use_stamp` | `stamp_no` | int64 | スタンプ番号（`CosmeticItems.item_no`） |
| `stamp_used` | `game_id` | string | ゲームID |
| `stamp_used` | `player_id` | string | 使用プレイヤーID |
| `stamp_used` | `stamp_no` | int64 | スタンプ番号 |
| `discard_prompt` | `requiredDiscards` | int | 破棄すべき枚数 |

### 6.2 REST API

```
# 認証
POST   /api/v1/auth/register          # ユーザー登録
POST   /api/v1/auth/login             # ログイン
POST   /api/v1/auth/refresh           # トークンリフレッシュ

# ゲーム
POST   /api/v1/games                  # ゲーム作成
GET    /api/v1/games/:id              # ゲーム情報取得
POST   /api/v1/games/:id/join         # ゲーム参加
GET    /api/v1/games/:id/events       # イベントログ取得
GET    /api/v1/games/:id/replay       # リプレイデータ取得

# マッチメイキング
POST   /api/v1/matchmaking/queue      # キュー参加（スタミナ消費）
DELETE /api/v1/matchmaking/queue      # キュー離脱
GET    /api/v1/matchmaking/status     # キュー状態取得

# プレイヤー
GET    /api/v1/players/:id            # プレイヤー情報取得
GET    /api/v1/players/:id/matches    # 対戦履歴取得
PUT    /api/v1/players/:id/profile    # プロフィール更新
GET    /api/v1/players/:id/stamina    # スタミナ状態取得

# カード定義（マスターデータ）
GET    /api/v1/cards                  # 全カード定義一覧（デッキ構築画面用）
GET    /api/v1/cards/:card_no         # カード定義詳細

# カード・デッキ
GET    /api/v1/players/:id/cards      # 所持カード一覧
GET    /api/v1/players/:id/decks      # デッキ一覧（最大10デッキ）
POST   /api/v1/players/:id/decks      # デッキ作成
GET    /api/v1/players/:id/decks/:deckId    # デッキ詳細取得
PUT    /api/v1/players/:id/decks/:deckId    # デッキ更新
DELETE /api/v1/players/:id/decks/:deckId    # デッキ削除

# カード解放
POST   /api/v1/tutorial/select-faction   # チュートリアル陣営選択（1陣営の全カード解放）
POST   /api/v1/quests/:questId/claim     # クエスト報酬受取（条件を満たした場合に陣営カード解放）

# 課金
GET    /api/v1/shop/factions         # 購入可能陣営セット一覧
POST   /api/v1/shop/purchase         # 商品購入（レシート検証 → カード/コスメ付与）
GET    /api/v1/shop/premium          # プレミアムプラン情報
POST   /api/v1/shop/premium/activate # プレミアム有効化（レシート検証 → サブスク開始）
GET    /api/v1/shop/history          # 購入履歴取得

# 設定
GET    /api/v1/players/:id/settings   # 設定取得
PUT    /api/v1/players/:id/settings   # 設定更新

# ランキング
GET    /api/v1/rankings               # ランキング取得
```

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
   └─ Starting Resource選出フェーズへ遷移
```

**キューの実装方式:**

| 項目 | 内容 |
|------|------|
| データストア | matchmaker Pod のインメモリ（Go の `sync.Map` + スライス） |
| マッチングワーカー | Pod内の goroutine（1秒間隔のティッカー） |
| キュー離脱 | 明示的な離脱 or 60秒の Heartbeat タイムアウト |
| Pod再起動時 | キュー消失 → プレイヤーは再キュー（WebSocket切断検知で自動リトライ） |

> **注:** マッチメイキングキューはPodインメモリで管理する。DBには書き込まない。マッチ成立後のゲーム作成のみCloud SQLに書き込む。

### 9.5.2 WebSocket メッセージ（マッチメイキング）

**Client → Server:**

| タイプ | 説明 |
|------|------|
| `queue_join` | マッチングキュー参加（`deckId` を含む） |
| `queue_leave` | マッチングキュー離脱 |
| `queue_heartbeat` | キュー内存在確認（30秒間隔） |

**Server → Client:**

| タイプ | 説明 |
|------|------|
| `queue_status` | キュー状態更新（待機時間、推定待ち人数） |
| `game_matched` | マッチ成立通知（`gameId`, `opponentName`, `isFirst`） |

---

## 10. ゲームロジック

### 10.1 ターン管理

**フェーズ順序:**

| フェーズ | 内容 |
|------|------|
| `draw` | リポジトリから手札に1枚ドロー |
| `dv_gen` | バックエンドリソースのDV生成処理 |
| `main` | カードプレイ・スケールアップ・アタッチメント等 |
| `battle` | 攻撃実行 |
| `end` | エンドフェーズ処理、ターン切り替え |

**フェーズ進行フロー:**

```
draw → dv_gen → main → battle → end → (ActivePlayer切替) → draw ...
```

**エンドフェーズの詳細手順:**

| 手順 | 処理 | 備考 |
|------|------|------|
| 1 | 一時効果の終了 | `duration: "this_turn"` の `temporaryEffects` を除去 |
| 2 | Elastic 値のリセット | Elastic カードのスループット / DV Gen を base 値に戻す |
| 3 | DV 生成 | バックエンドの各DB系・ストレージ系リソースが DV を生成し、DV プールに加算 |
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
| 4 | **コスト確認** | Budget・DV Pool 等のリソースが足りているか |
| 5 | **その他の条件** | 1ターン1回制限、Resizable属性、手札上限など個別ルール |

**アクション別の検証項目:**

| アクション | 1. フェーズ | 2. 実行元 | 3. 対象 | 4. コスト | 5. その他 |
|-----------|-----------|----------|---------|----------|----------|
| `play_card` | Main Phase | 手札に存在 | 配置先が空き | Budget ≥ 開発コスト | — |
| `attack` | Battle Phase | フィールド上の自コンピュート | 相手フィールド上のリソース | Request Cost ≤ DV Pool | 攻撃済みでない |
| `scale_up` | Main Phase | フィールド上の自リソース | — | Budget ≥ スケールアップコスト | Resizable 属性、現在Rank < 対象Rank |
| `distribute_dv` | Main Phase | バックエンドのコンピュート | — | — | DV Pool 残量 ≥ 分配量、TP上限 |
| `activate_effect` | Main/Battle Phase | 効果を持つカード | 効果の対象 | 効果コスト | 1ターン1回制限 |

### 13.2 レート制限

| 項目 | 値 |
|------|-----|
| 通常リクエスト上限 | 10 req/sec |
| バースト上限 | 20 req |
| 超過時のレスポンス | HTTP 429 Too Many Requests |

### 13.3 CORS設定

| 項目 | 値 |
|------|-----|
| `AllowOrigins` | `https://overload-party.com` |
| `AllowMethods` | GET, POST, PUT, DELETE |
| `AllowHeaders` | Authorization, Content-Type |
| `MaxAge` | 12時間 |

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


> dev/stg は毎日 2:00 JST に自動停止（Ingress 削除 → Pod スケール 0 → Cloud SQL 停止）してコストを最小化する。起動は GitHub Actions workflow_dispatch またはローカルスクリプトで手動実行。

**コスト管理スクリプト:**

| スクリプト / ワークフロー | 内容 |
|--------------------------|------|
| `scripts/env-up.sh <dev\|stg>` | Cloud SQL 起動 → Pod スケール 1 → Ingress 適用 |
| `scripts/env-down.sh <dev\|stg>` | Ingress 削除 → Pod スケール 0 → Cloud SQL 停止 |
| `.github/workflows/nightly-shutdown.yaml` | 毎日 2:00 JST に dev/stg を自動停止 |
| `.github/workflows/startup.yaml` | 手動起動 (workflow_dispatch) |

**ディレクトリ構成:**

```
terraform/  (overload-party-server リポジトリ)
├── environments/
│   └── dev/          # Cloud SQL, IAM (Workload Identity)
├── modules/
│   ├── cloudsql/     # Cloud SQL PostgreSQL インスタンス + DB
│   └── iam/          # GSA + Cloud SQL role + Workload Identity binding

terraform/  (overload-party-k8s リポジトリ)
├── environments/
│   └── shared/       # GKE Autopilot, Artifact Registry
├── modules/
│   ├── gke/          # GKE Autopilot クラスタ
│   └── artifact-registry/ # Docker リポジトリ
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
- [x] Budget/DV管理
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
