# Overload Party - システムアーキテクチャ設計書

---

## 目次

1. [概要](#1-概要)
2. [プロジェクト構成](#2-プロジェクト構成multi-repo)
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

## 2. プロジェクト構成（Multi-repo）

Overload Party は 9 つの独立した Git リポジトリで構成される。`overload-party-common` がゲームデザイン・カードデータ・ドキュメントの Single Source of Truth（SSoT）となり、コード生成パイプラインで各リポに成果物を配布する。

### 2.1 リポジトリ一覧

| リポジトリ | 役割 | 技術 | CI |
|-----------|------|------|-----|
| **common** | ゲーム設計・カードデータ・ドキュメント（SSoT） | YAML, Python, Markdown | DB マイグレーション自動適用 |
| **gateway** | REST API + WebSocket サーバー | Go 1.25, Gin, PostgreSQL | lint → test → Docker push |
| **battle** | 対戦ゲームエンジン | C# / .NET 10 | test → Docker push |
| **client** | モバイル/Web フロントエンド | React 19, TypeScript, Vite, Capacitor | lint → typecheck → test |
| **infra** | GCP リソース管理 | Terraform | plan → apply（パス変更時のみ） |
| **k8s** | GKE デプロイ・運用 | Kustomize, GitHub Actions | deploy / startup / shutdown / scale |
| **ops** | DB マイグレーション・監視ジョブ・Slack コマンド | Docker, Cloud Run, Cloudflare Workers, Python | CI + 手動 dispatch |
| **analytics** | Spanner → BigQuery エクスポート | Go, Cloud Functions | 手動デプロイ |
| **newsfeed** | ニュースフィード生成 | Python, Vertex AI | 手動デプロイ |

### 2.2 リポジトリ構成（ディレクトリ）

```
overload-party-common/          # 共有データ・定義の SSoT
├── data/
│   ├── cards/                  # カード定義 YAML (5 faction files)
│   │   ├── sd.yaml
│   │   ├── tenki.yaml
│   │   ├── sugar.yaml
│   │   ├── tuners.yaml
│   │   └── neutral.yaml
│   └── constants.json          # ゲーム定数 (Phase, Zone, Rank, 初期値 等)
├── db/
│   ├── schema_postgres.sql     # PostgreSQL DDL（SSoT）
│   └── grant_iam.sql           # IAM 認証権限付与
├── docs/                       # 全ドキュメント
├── packages/
│   ├── generate_from_yaml.py   # カード＆定数のコード生成スクリプト
│   ├── gamedata/               # Go パッケージ (gateway 用)
│   │   ├── model/              # 生成: Go モデル
│   │   ├── constants/          # 生成: ゲーム定数
│   │   ├── cardno/             # 生成: カード番号定数
│   │   └── cache/              # 生成: cards_gen.json (embed)
│   ├── dotnet/                 # NuGet パッケージ (battle 用)
│   │   ├── GameConstants_gen.cs
│   │   └── EventData_gen.cs
│   └── npm/                    # npm パッケージ (client 用)
│       └── src/constants.ts, eventData.ts
└── .github/workflows/
    ├── ci.yaml                 # DB マイグレーション CI
    └── publish-packages.yaml   # data/ 変更時にパッケージ publish

overload-party-gateway/         # Go API サーバー
├── internal/
│   ├── model/gen.go            # packages/gamedata/model の re-export
│   ├── constants/gen.go        # packages/gamedata/constants の re-export
│   └── ...
└── go.mod                      # packages/gamedata モジュールを依存

overload-party-battle/          # C# 対戦エンジン
├── src/
│   └── OverloadParty.Battle.Models/
│       └── GlobalUsings.cs     # global using OverloadParty.GameData
└── nuget.config                # GitHub Packages NuGet feed

overload-party-client/          # React + Capacitor クライアント
├── src/                        # @kenyamaneko/overload-party-gamedata パッケージを import
│   └── ...
├── .npmrc                      # GitHub Packages npm registry
└── package.json                # @kenyamaneko/overload-party-gamedata 依存
```

### 2.3 コード生成パイプライン

`python3 packages/generate_from_yaml.py --gen-dir packages/` を実行すると、common の `packages/` 以下にパッケージとして生成される。main への push 時に CI が自動で publish する。

| 入力 | 出力先 | パッケージ |
|------|--------|-----------|
| `data/cards/*.yaml` | `docs/CARDS.md` | — |
| `data/cards/*.yaml` | `packages/gamedata/cardno/cardno_gen.go` | Go module |
| `data/cards/*.yaml` | `packages/gamedata/cache/cards_gen.json` | Go module (embed) |
| `data/cards/*.yaml` | `packages/dotnet/cache/cards_gen.json` | NuGet (EmbeddedResource) |
| `data/models.yaml` | `packages/gamedata/model/*_gen.go` | Go module |
| `data/constants.json` | `packages/gamedata/constants/constants_gen.go` | Go module |
| `data/constants.json` | `packages/dotnet/GameConstants_gen.cs` | NuGet (`OverloadParty.GameData`) |
| `data/constants.json` | `packages/npm/src/constants.ts` | npm (`@kenyamaneko/overload-party-gamedata`) |
| `data/event_schemas.json` | `packages/dotnet/EventData_gen.cs` | NuGet |
| `data/event_schemas.json` | `packages/npm/src/eventData.ts` | npm |

各リポはパッケージをインストールして使う（gateway: `go get`, battle: NuGet, client: npm）。生成されたファイルには `DO NOT EDIT` コメントが付く。

### 2.4 作業別クロスリファレンス

「何を変えたら、どのリポを触る必要があるか」の早見表。

| やりたいこと | 編集するリポ | 次にやること | 影響を受けるリポ |
|-------------|------------|------------|----------------|
| カードの追加・変更 | common (`data/cards/*.yaml`) | `--gen-dir packages/` で生成 → main push で自動 publish | gateway, battle, client（パッケージ更新） |
| ゲーム定数の変更 | common (`data/constants.json`) | `--gen-dir packages/` で生成 → main push で自動 publish | gateway, battle, client（パッケージ更新） |
| DB スキーマの変更 | common (`db/schema_postgres.sql`) | main に push（CI が自動適用） | gateway, battle（コード側の対応） |
| IAM 権限の変更 | common (`db/grant_iam.sql`) | main に push（CI が自動適用） | — |
| API エンドポイント追加 | gateway | CI が自動で Docker push | k8s（deploy で反映） |
| 対戦ロジックの変更 | battle | CI が自動で Docker push | k8s（deploy で反映） |
| クライアント UI の変更 | client | CI で lint/test | — |
| GCP リソースの追加・変更 | infra (`environments/`, `modules/`) | `terraform plan` → PR → merge で自動 apply | — |
| K8s マニフェストの変更 | k8s (`k8s/overlays/`) | `deploy.yaml` を手動 dispatch | — |
| DB マイグレーション（手動） | ops | `db-migrate.yaml` を手動 dispatch | — |
| 環境の起動 | k8s | Slack コマンド (`/gke-up`) → `env-lifecycle.yaml` | infra（Cloud SQL 起動） |
| 環境の停止 | — | 毎日 2:00 AM JST に自動実行 | k8s（Ingress 削除、DNS 変更、Cloud SQL 停止） |
| 分析パイプラインの変更 | analytics | `scripts/deploy.sh` で手動デプロイ | — |
| ニュースフィードの変更 | newsfeed | Docker build → Cloud Run にデプロイ | — |

### 2.5 リポジトリ間の依存グラフ

```
                    ┌─────────┐
                    │ common  │ ← SSoT (cards, constants, schema, docs)
                    └────┬────┘
           ┌─────────────┼─────────────┐
           │  codegen     │  codegen     │ codegen
           ▼             ▼             ▼
      ┌─────────┐  ┌─────────┐  ┌─────────┐
      │ gateway │  │ battle  │  │ client  │
      └────┬────┘  └────┬────┘  └─────────┘
           │ Docker      │ Docker
           ▼             ▼
      ┌─────────────────────┐
      │    k8s (deploy)     │ ← Kustomize + GitHub Actions
      └─────────────────────┘
                │
      ┌─────────┼─────────┐
      ▼         ▼         ▼
   ┌──────┐ ┌──────┐ ┌───────────┐
   │ infra│ │ ops  │ │ analytics │  ← 独立したライフサイクル
   └──────┘ └──────┘ └───────────┘
```

---

## 3. 技術スタック

### 3.1 フロントエンド

```
React + Capacitor (TypeScript)
├── React 19
├── WebSocket Client (native WebSocket API)
├── State Management (Zustand)
├── UI Framework (Tailwind CSS)
├── Animation (Framer Motion)
├── Audio (Howler.js)
└── Capacitor (iOS / Android ネイティブラッパー)
```

**選定理由:**
- MVPの開発速度を最優先
- クロスプラットフォーム対応（Web, iOS, Android）
- React エコシステムの豊富なライブラリ
- 将来的に演出面で不足があれば Unity への移行を検討

### 3.2 バックエンド

バックエンドは **Gateway Server**（Go）と **Battle Server**（C#）の 2 サーバー構成。

```
Gateway Server (Go 1.25+)
├── Web Framework (Gin)
├── WebSocket (gorilla/websocket)
├── PostgreSQL Client (pgxpool)
├── Cloud SQL Auth Proxy (サイドカー)
└── Firebase Admin SDK

Battle Server (C# / .NET 10)
├── ASP.NET Core (REST API)
├── PostgreSQL Client (Dapper)
├── Cloud SQL Auth Proxy (サイドカー)
└── xUnit (テスト)
```

**責務分離:**
- **Gateway**: 認証、WebSocket 管理、マッチメイキング、プレイヤーデータ、デッキ、ショップ/IAP
- **Battle**: ゲームエンジン、アクション処理、エフェクト、NPC AI、勝利判定、ゲームログ

**選定理由:**
- Gateway (Go): 高パフォーマンスな並行処理、WebSocket 常時接続に最適
- Battle (C#): 複雑なゲームロジックの表現力、型安全性、.NET エコシステム
- GKE Autopilot でゲームサーバー管理

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
├── keyandnotes-platform
│   ├── GKE Autopilot (Gateway + Battle サーバー — 全環境共有)
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

CD: GitHub Actions (on k8s リポ)
├── Kustomize でイメージタグ更新
└── kubectl apply -k で GKE にデプロイ
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
│  │  │  (Zustand) │  │  Motion    │  │  (Howler)  │        │  │
│  │  └────────────┘  └────────────┘  └────────────┘        │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebSocket (wss://)
                             │ HTTPS (REST API)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  GKE Autopilot (Application Layer)              │
│                                                                 │
│  ┌───────────────────────┐      ┌───────────────────────┐      │
│  │   gateway Pod (Go)    │      │   battle Pod (C#)     │      │
│  │  ┌─────────────────┐  │      │  ┌─────────────────┐  │      │
│  │  │  REST API       │  │      │  │  Game Engine     │  │      │
│  │  │  (Gin)          │  │      │  │  (ASP.NET Core)  │  │      │
│  │  └─────────────────┘  │      │  └─────────────────┘  │      │
│  │  ┌─────────────────┐  │      │  ┌─────────────────┐  │      │
│  │  │  WebSocket      │  │ HTTP │  │  Effect System   │  │      │
│  │  │  Handler        │──┼──────┼─>│  + NPC AI        │  │      │
│  │  └─────────────────┘  │      │  └─────────────────┘  │      │
│  │  ┌─────────────────┐  │      │  ┌─────────────────┐  │      │
│  │  │  Matchmaking    │  │      │  │  Cloud SQL      │  │      │
│  │  │  (In-Memory)    │  │      │  │  Auth Proxy     │  │      │
│  │  └─────────────────┘  │      │  │  (sidecar)      │  │      │
│  │  ┌─────────────────┐  │      │  └─────────────────┘  │      │
│  │  │  Cloud SQL      │  │      └───────────────────────┘      │
│  │  │  Auth Proxy     │  │                                      │
│  │  │  (sidecar)      │  │                                      │
│  │  └─────────────────┘  │                                      │
│  └───────────────────────┘                                      │
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

**サーバー間通信:**
- Gateway → Battle: 内部 REST API（`http://battle:9002/api/v1/...`）
- Battle は認証を行わず、Gateway を信頼（内部ネットワーク）
- DB 所有権: Gateway = プレイヤー系テーブル、Battle = ゲーム状態 + イベント

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

GKE Autopilot クラスタは共有プロジェクト `keyandnotes-platform` に配置し、Namespace で環境を分離する。各環境の Cloud SQL は環境別プロジェクト（`overload-party-dev` 等）に配置し、**Workload Identity + Cloud SQL Auth Proxy** でクロスプロジェクトアクセスする。

```
[GKE Autopilot Cluster] keyandnotes-platform / asia-northeast1
  ├── Namespace: dev
  │     ├── Deployment: gateway (Go)    replicas: 0 (開発時以外)
  │     └── Deployment: battle  (C#)    replicas: 0 (開発時以外)
  ├── Namespace: staging
  │     ├── Deployment: gateway (Go)    replicas: 0 (開発時以外)
  │     └── Deployment: battle  (C#)    replicas: 0 (開発時以外)
  ├── Namespace: prod
  │     ├── Deployment: gateway (Go, port 9001)
  │     │     resources: { cpu: "250m-500m", memory: "512Mi-1Gi" }
  │     ├── Deployment: battle  (C#, port 9002)
  │     │     resources: { cpu: "250m-500m", memory: "512Mi-1Gi" }
  │     ├── Service: type=ClusterIP
  │     └── Ingress: External HTTP(S) LB (WebSocket対応)
  └── マッチメイキングは gateway Pod 内のインメモリ実装
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
[クライアント] → [Gateway Pod] → [Battle Pod] → [Cloud SQL PostgreSQL]
                  ↑WS管理          ↑ゲームロジック    ↑毎アクション読み書き（SELECT FOR UPDATE）
                  ↑ブロードキャスト  ↑バリデーション    ↑GameEvents追記（イベントソーシング）
```

### 4.3 通信フロー

#### 4.3.1 ゲーム開始フロー

```
Client              Gateway Pod          Battle Pod           Cloud SQL
     │                    │                    │                    │
     │  1. Connect WS     │                    │                    │
     ├───────────────────>│                    │                    │
     │                    │                    │                    │
     │  2. Join Game      │                    │                    │
     ├───────────────────>│                    │                    │
     │                    │  3. GET state      │                    │
     │                    ├───────────────────>│                    │
     │                    │                    │  4. Read GameState │
     │                    │                    ├───────────────────>│
     │                    │                    │<───────────────────┤
     │                    │<───────────────────┤                    │
     │                    │                    │                    │
     │  5. GameState      │                    │                    │
     │<───────────────────┤                    │                    │
```

#### 4.3.2 アクション実行フロー

```
Player A (Client)   Gateway Pod          Battle Pod           Cloud SQL      Player B (Client)
     │                    │                    │                    │                │
     │  1. Play Card      │                    │                    │                │
     ├───────────────────>│                    │                    │                │
     │                    │  2. POST action    │                    │                │
     │                    ├───────────────────>│                    │                │
     │                    │                    │  3. Validate +     │                │
     │                    │                    │     Update State   │                │
     │                    │                    ├───────────────────>│                │
     │                    │                    │<───────────────────┤                │
     │                    │                    │  4. Record Event   │                │
     │                    │                    ├───────────────────>│                │
     │                    │<───────────────────┤                    │                │
     │                    │                    │                    │                │
     │  5. State Update   │                    │                    │                │
     │  + available_actions│                   │                    │                │
     │  + turn_controls   │                    │                    │                │
     │<───────────────────┤────────────────────────────────────────────────────────>│
     │                    │  (WebSocket broadcast)                  │                │
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
- **games / game_states / game_events / game_actions** — ゲームライフサイクル・状態・イベントログ・アクション入力ログ
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
| 検証方法 | gateway が ID Token をデコードし `admin` クレームを確認 |
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

> 課金プラン・スタミナ仕様・カード入手モデル等のビジネスルールは [MONETIZATION.md](../business/MONETIZATION.md) を参照。
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

### 8.6 Webhook 受信（gateway 内）

Apple / Google からのサーバー通知は GKE 上の **gateway** で受信する。

```
Apple Server Notifications V2  ──>  gateway (GKE)  ──>  Cloud SQL
Google RTDN (Pub/Sub push)     ──>  gateway (GKE)  ──>  Cloud SQL
```

| 項目 | 内容 |
|------|------|
| 受信先 | gateway Pod (GKE Autopilot) |
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
| 接続登録 | `playerID → WebSocket接続` のマップを Gateway Pod 内インメモリ管理 |
| ゲーム参加 | `gameID → []playerID` のマップを Gateway Pod 内で管理 |
| ブロードキャスト | Gateway がゲーム内の全プレイヤーに状態更新を送信 |
| ゲームロジック | Gateway が Battle Server に内部 REST で委譲し、結果をクライアントに中継 |
| スレッドセーフティ | `sync.RWMutex` で同時アクセスを制御 |

### 9.2 再接続処理

```
再接続リクエスト
        │
        ▼
Gateway が Battle Server から最新 GameState を取得
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
     ├── マッチメイキング中 → 即座にキューから離脱
     │
     ├── 対戦中:
     │     ├── 対戦相手に `opponent_disconnected` 通知
     │     │
     │     ▼
     │   60秒タイマー開始
     │     │
     │     ├── 60秒以内に再接続 → 対戦相手に `opponent_reconnected` 通知、タイマー解除
     │     │
     │     └── 60秒超過 → 切断プレイヤーの敗北
     │          ├── forfeit アクション送信
     │          ├── game_over (reason: disconnect) を全プレイヤーに通知
     │          └── 経験値付与（通常の勝敗と同等に扱う）
     │
     └── その他（ホーム画面等） → 特別な処理なし
```

**切断時の処理中断方針:**

| 処理 | 切断時 | 理由 |
|------|--------|------|
| ゲームアクション (Battle Server HTTP) | タイムアウト付きで完了させる | 60秒猶予内の再接続時に最後のアクションが反映されている |
| 経験値付与 | タイムアウト付きで完了させる | ゲーム結果の永続化 |
| マッチメイキング | 即座にキャンセル | 切断＝対戦意思なし |
| NPC バトル開始 | 即座にキャンセル | 切断＝対戦準備未完了 |

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
| データストア | Gateway Pod のインメモリ（Go の `sync.Map` + スライス） |
| マッチングワーカー | Pod内の goroutine（1秒間隔のティッカー） |
| キュー離脱 | 明示的な離脱 or WebSocket 切断時に即座に離脱 |
| Pod再起動時 | キュー消失 → プレイヤーは再キュー（WebSocket切断検知で自動リトライ） |

> **注:** マッチメイキングキューは Gateway Pod のインメモリで管理する。DBには書き込まない。マッチ成立後のゲーム作成は Gateway が Battle Server に委譲する。

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
| `opponent_disconnected` | 対戦相手の切断通知 |
| `opponent_reconnected` | 対戦相手の再接続通知 |
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
| 計算タイミング | 状態更新ごと（Battle Server）、NPC ターン開始時（`GameService`） |
| 関数 | `Engine.ComputeAvailableActions(state, game, playerNum, ...)` |
| 戻り値 | `List<AvailableAction>`（タイプ別 discriminated union） |
| クライアント向け | `ClientGameState.my.available_actions` に含めて Gateway 経由で WebSocket 送信 |
| NPC 向け | `RunNpcTurnIfNeeded` 内で計算し Strategy に渡す |

**AvailableAction のアクションタイプ:**

| Type | 主要フィールド |
|------|---------------|
| `play_card` | `HandInstanceID`, `CardID`, `ValidZones`, `ValidTargets`, `Cost` |
| `attack` | `SourceInstanceID`, `ValidTargets` |
| `scale_up` | `SourceInstanceID`, `Cost`, `TargetRank`, `NeedsFamily`, `RequiredCount` |
| `monetize` | `SourceInstanceID`, `RemainingCapacity` |
| `use_effect` | `SourceInstanceID`, `ValidTargets`, `EffectTargetType` |
| `set_reactive` | `SourceInstanceID` |

ゲームフロー制御（フェーズ終了、手札破棄）は `available_actions` に含めず、`turn_controls` メッセージとして別途送信される。

**NPC AI アーキテクチャ（Battle Server / C#）:**

```
Engine.ComputeAvailableActions()
        │
        ▼
┌─────────────────────┐
│  IStrategy interface │  DecideMainPhaseActions(state, game, playerNum, available)
│                      │  DecideBattlePhaseActions(state, game, playerNum, available)
│                      │  DecideDiscard(state, playerNum)
│                      │  DecideStartingResources(deckCards)
└────────┬────────────┘
         │
    ┌────┴────┐
    ▼         ▼
StandardAi   FactionAi (SHE / Tenki / Sugar / Tuners)
```

NPC は `List<AvailableAction>` から最適なアクションを選択するのみ。
アクションの有効性判定はすべて Engine 側が担当し、ロジック重複を排除。

**NPC の決定フロー（Main Phase）:**

| 順序 | 処理 | ヘルパー |
|------|------|---------|
| 1 | Strategy/Incident カードを使用 | `DoImmediateActions()` — `EvaluateCard` でスコアリング |
| 2 | Resource カードをデプロイ | `DoDeployActions()` — `PickBestZone` でゾーン選択 |
| 3 | フィールドエフェクトを発動 | `DecideActivateActions()` — `SelectTargetFromValid` でターゲット制約 |
| 4 | スケールアップ | `DoScaleUpActions()` — `AvailableAction.Cost` / `TargetRank` を使用 |
| 5 | Insight 配分 | `DoDistributeYieldActions()` — `RemainingCapacity` で greedy 配分 |
| 6 | フェーズ終了 | `MakeEndPhaseAction()` |

**NPC 関連ファイル（battle リポ: `src/OverloadParty.Battle.Npc/`）:**

| ファイル | 役割 |
|---------|------|
| `StandardAi.cs` | IStrategy インターフェース、StandardAI 実装 |
| `FactionAi.cs` | FactionAI（陣営別パラメータ・オーバーライド） |
| `ActionFilter.cs` | AvailableAction 用ヘルパー（`FilterByType`, `PickBestZone` 等） |
| `ActionEvaluator.cs` | カードスコアリング、ターゲット選択ヒューリスティクス |
| `Targeting.cs` | ターゲット選択戦略（`WeakestInZone`, `StrongestInZone` 等） |
| `NpcDecks.cs` | 陣営別デッキ定義 |

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

- PodDisruptionBudget + preStop hook で WebSocket 接続のグレースフルドレインを保護
- Pod Anti-Affinity でゾーン分散し障害影響を最小化
- sessionAffinity (ClientIP) で同一クライアントを同一 Pod にルーティング

> 具体的なリソース値・レプリカ数は k8s リポの Kustomize マニフェストを参照。

### 12.3 接続プーリング (pgxpool)

pgxpool で接続プールを管理。Pod あたりの接続数を制限し、Cloud SQL の最大接続数を超えないようにする。

> 具体的なパラメータ値は gateway / battle の接続設定コードを参照。

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
| `monetize` | Main Phase | バックエンドのコンピュート | — | — | Insight Pool 残量 ≥ 分配量、TP上限 |
| `use_effect` | Main/Battle Phase | 効果を持つカード | 効果の対象 | 効果コスト | 1ターン1回制限 |

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
  - **起動時** (`env-lifecycle.yaml`): Ingress の外部 IP 取得後、Cloudflare API で A レコードを更新
  - **停止時** (`nightly-shutdown.yaml`): DNS を `127.0.0.1` に変更し、予約済み IP を削除
- Cloudflare 認証情報は `CLOUDFLARE_` プレフィックスで統一。DNS トークン (`CLOUDFLARE_DNS_API_TOKEN`) は secrets、ゾーン ID (`CLOUDFLARE_ZONE_ID`) は variables で管理

---

## 14. デプロイメント

### 14.1 インフラ管理 (Terraform)

GCPリソースは **Terraform** で管理する。

**GCP プロジェクト構成（4プロジェクト）:**

| プロジェクト | 用途 | 主なリソース |
|-------------|------|------------|
| `keyandnotes-platform` | 共有インフラ | GKE Autopilot, Artifact Registry, ArgoCD |
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
| GCS CNAME バケット（アセット） | `google_storage_bucket` + `google_storage_bucket_iam_member` | 各環境 |
| Cloudflare CDN（CNAME） | `cloudflare_record` | infra/cloudflare |
| IAM / Service Account | `google_service_account`, `google_project_iam_*` | 各環境 |
| Workload Identity 連携 | `google_service_account_iam_member` | 各環境（shared GKE → 環境 GSA） |

**環境戦略:**

| リソース | shared | dev | staging | prod |
|---------|--------|-----|---------|------|
| GKE クラスタ | `keyandnotes-shared`（1クラスタ） | — | — | — |
| Artifact Registry | `overload-party`（Docker） | — | — | — |
| GKE Namespace | — | `overload-party-dev` | `overload-party-stg` | `overload-party-prod` |
| gateway Pods | — | 0（開発時のみ起動） | 0（開発時のみ起動） | TBD（常時稼働） |
| battle Pods | — | 0（開発時のみ起動） | 0（開発時のみ起動） | TBD（常時稼働） |
| Cloud SQL インスタンス | — | `overload-party-db` | `overload-party-db` | `overload-party-db` |
| Cloud SQL tier | — | db-g1-small | db-g1-small | TBD |
| Workload Identity | — | KSA `overload-party-app` → GSA `overload-party-app@..dev` | 同パターン | 同パターン |


> dev/stg は毎日 2:00 JST に自動停止してコストを最小化する。Cloud SQL・K8s ともに K8s リポジトリの GitHub Actions (`nightly-shutdown.yaml`) で一元管理している。

**自動停止の仕組み (2:00 AM JST):**

| 対象 | 方式 | 管理場所 |
|------|------|---------|
| Cloud SQL | `gcloud sql instances patch --activation-policy=NEVER` | k8s: `.github/workflows/nightly-shutdown.yaml` |
| K8s (Ingress, Pod) | GitHub Actions cron | k8s: `.github/workflows/nightly-shutdown.yaml` |

**Slack コマンドの経路:**

```
Slack → Cloudflare Worker (即時応答 + 署名検証)
         ↓ Bearer token 認証
       Cloud Run (FastAPI: コマンド処理)
         ↓ GitHub API / sqladmin API 等
       各バックエンド
```

Cloudflare Worker が Slack の 3 秒タイムアウトを吸収し、Cloud Run のコールドスタートの影響を回避する（詳細: [ADR-009](../adr/009-slack-commands-gke-via-github-actions.md)）。

**手動操作:**

| 操作 | Slack コマンド | GitHub Actions ワークフロー | 内容 |
|------|---------------|---------------------------|------|
| Cloud SQL 起動 | `/db-start dev` | — (sqladmin API 直接呼び出し) | Cloud SQL 起動 (RUNNABLE 待ち) |
| Cloud SQL 停止 | `/db-stop dev` | — (sqladmin API 直接呼び出し) | Cloud SQL 停止 |
| 環境起動 | `/gke-up dev` | `env-lifecycle.yaml` | Namespace 存在確認 → Cloud SQL 起動 → Pod スケール 1 → Ingress 適用 → DNS 更新 |
| 環境停止 | `/gke-down dev` | `env-lifecycle.yaml` | Namespace 存在確認 → Ingress 削除 → Pod スケール 0 → DNS 変更 → Cloud SQL 停止 |

**ディレクトリ構成:**

```
overload-party-infra/
├── environments/
│   ├── platform/     # GKE, Artifact Registry, WIF, CI SA
│   ├── dev/          # Cloud SQL, IAM (Workload Identity)
│   ├── stg/
│   ├── prod/
│   └── cloudflare/   # CDN (CNAME)
├── modules/
│   ├── assets/       # GCS バケット（公開: アセット、非公開: シナリオ）
│   ├── ci-cd/        # WIF, CI SA
│   ├── database/     # Cloud SQL インスタンス + DB + IAM
│   ├── db-migration/ # Cloud Run Job (psqldef)
│   ├── network/      # VPC, サブネット
│   └── newsfeed/     # Cloud Run (newsfeed サービス)
└── (scripts/ は削除済み — Slack コマンド経由で操作)
```

**Terraform state:** `gs://keyandnotes-tf-state` に GCS backend で管理。prefix で `terraform/platform`, `terraform/dev` 等に分離。

### 14.2 CI/CD

全リポのワークフロー一覧・リポ間連携・認証・デプロイ方式の詳細は **[CI_CD.md](CI_CD.md)** を参照。

**K8s デプロイ設定:**

| 設定 | 値 | 理由 |
|------|-----|------|
| Strategy | RollingUpdate | 既存ゲームを中断せずにデプロイ |
| maxUnavailable | 0 | 既存Podを停止する前に新Podを起動 |
| maxSurge | 25% | 新旧Pod共存時の最大増分 |
| Region | asia-northeast1 | 日本ユーザー向け低レイテンシ |

### 14.4 アセット配信（Cloudflare CDN + GCS）

ゲームアセットの配信は、コンテンツの性質に応じて2系統に分かれる:

| 種別 | 配信元 | 理由 |
|------|--------|------|
| 画像・音声（カードイラスト、BGM、SE、ストーリー背景・立ち絵等） | GCS 公開バケット + Cloudflare CDN | バイナリファイルは CDN 配信が効率的。認証不要（スクリプトなしでは意味をなさない） |
| ストーリースクリプト（.ks） | ゲームサーバー API (`GET /api/v1/scenarios/{id}/script`) | エピソードのアンロック判定・言語切替をサーバー側で制御する必要がある。テキストなので転送コストは無視できる |

GCS 公開バケットに Cloudflare CDN を前段に置く構成。Cloudflare Free プランは帯域無制限のため、トラフィック増加時もコストを抑えられる。React アプリのビルドに含めない画像・音声は CDN から取得し、ブラウザ / Capacitor のキャッシュ機構で管理する。

**構成:**

| コンポーネント | 役割 |
|--------------|------|
| GCS CNAME バケット (`overload-party-assets-{env}.keyandnotes.com`) | アセットファイルのストレージ。バケット名 = サブドメインにすることで、Host ヘッダから GCS が自動解決 |
| Cloudflare CDN | CNAME (→ `c.storage.googleapis.com`) + グローバル CDN キャッシュ + HTTPS 終端 |
| ゲームサーバー API | ストーリースクリプトの配信（認証・アンロック制御付き） |
| Service Worker | クライアント側キャッシュ管理（Cache API） |

> **前提:** Cloudflare の SSL モードは Flexible であること（GCS CNAME バケットは HTTP のみ対応）。

**CDN URL:**

| 環境 | URL |
|------|-----|
| dev | `https://overload-party-assets-dev.keyandnotes.com` |
| stg | `https://overload-party-assets-stg.keyandnotes.com` |
| prod | `https://overload-party-assets.keyandnotes.com` |

**配信フロー:**

```
CI (GitHub Actions)         Cloudflare CDN    GCS Bucket     Client (React)
     │                          │                │               │
     │  1. アセット最適化       │                │               │
     │     (WebP変換 +          │                │               │
     │      マニフェスト生成)   │                │               │
     │  2. gcloud storage cp    │                │               │
     ├─────────────────────────────────────────>│               │
     │                          │                │  3. マニフェスト取得
     │                          │<──────────────────────────────┤
     │                          │  (cache miss)  │               │
     │                          ├───────────────>│               │
     │                          │<───────────────┤               │
     │                          │───────────────────────────────>│
     │                          │                │  4. 差分アセットDL
     │                          │  (cache hit)   │  (CDN キャッシュ経由)
     │                          │───────────────────────────────>│
     │                          │                │  5. Cache API で
     │                          │                │     ローカル保存
```

**更新シナリオ:**

| シナリオ | 対応 |
|---------|------|
| 新カード追加 | 新アセット + マニフェスト更新を `gcloud storage cp` でデプロイ。クライアントは次回起動時に差分DL |
| 既存イラスト差し替え | 該当ファイルを差し替えて再デプロイ。マニフェストのハッシュが変わるため、クライアントが自動検知して再DL |
| アプリ本体更新 | Capacitor ネイティブ部分の変更のみストア審査が必要。Web 部分は OTA 更新可能 |

### 14.5 スケーリング指針

#### 現状の構成

- Gateway: Deployment (replicas: 1) — WebSocket 接続・ゲームセッションをインメモリで保持
- Battle: Deployment (replicas: 1, strategy: Recreate) — ゲームロジックはステートレス（状態は PostgreSQL）

#### 同時接続数の目安

| 接続数 | 対応 |
|--------|------|
| 〜200 | 現状のまま（replicas: 1）で十分 |
| 200〜1,000 | Gateway の垂直スケーリング（CPU / メモリ増強） |
| 1,000〜 | Gateway の水平スケール検討（下記参照） |

Go の goroutine モデル上、1 Pod で数千 WebSocket 接続は処理可能。
ボトルネックになるのは接続数よりも、ゲームアクション処理時の Battle Server への HTTP 往復。

#### Gateway を水平スケールする場合

Gateway はインメモリでゲームセッション（ConnectionHub, GameRelay, SpectateRelay）を持つため、
同じゲームの全プレイヤーが同一 Pod に接続している必要がある。

水平スケールに必要な変更:

1. **セッション状態の外部化** — Redis 等にゲームルーム情報を移し、どの Pod からでもセッションを参照可能にする
2. **ルーム単位ルーティング** — Gateway を StatefulSet + Headless Service にし、Ingress または別の Gateway 層で room ID ベースのルーティングを行う

どちらもアプリケーション側の変更を伴うため、必要になった時点で検討する。

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

---

> **実装ロードマップ・環境変数・開発セットアップ・テストコマンド** は各リポジトリの README を参照。
