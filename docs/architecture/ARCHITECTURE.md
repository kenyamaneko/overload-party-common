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

Overload Party は複数の独立した Git リポジトリで構成される。`overload-party-common` がゲームデザイン・カードデータ・ドキュメントの Single Source of Truth（SSoT）となり、コード生成パイプラインで各リポに成果物を配布する。

バックエンドは 7 つのサービス（gateway / account / matchmaking / shop / scenario / card / battle）で構成され、Gateway 以外はすべて Go 1.25、Battle のみ C# / .NET 10 である。Gateway は WS 通信ハンドリング・認証検証・ルーティングに専念し、ドメインロジックは各サービスに閉じる。ドメインごとに独立したリポジトリ・デプロイ単位を持たせることで、変更リスクと責務を局所化する。

### 2.1 リポジトリ一覧

| リポジトリ | 役割 | 技術 | CI |
|-----------|------|------|-----|
| **common** | ゲーム設計・カードデータ・ドキュメント（SSoT） | YAML, Python, Markdown | DB マイグレーション自動適用 |
| **gateway** | WS 通信ハンドリング・認証検証・ルーティング（クライアント単一入口） | Go 1.25, Gin, gorilla/websocket | lint → test → Docker push |
| **account** | ユーザー登録・設定・パスワードリセット | Go 1.25 | lint → test → Docker push |
| **matchmaking** | マッチキュー管理・マッチロジック・バトル引き渡し | Go 1.25 | lint → test → Docker push |
| **shop** | 課金連携 (Apple/Google)・購入管理・フラグ付与・Webhook 受信 | Go 1.25 | lint → test → Docker push |
| **scenario** | シナリオ解放判定・シナリオファイル配信 | Go 1.25 | lint → test → Docker push |
| **card** | カードマスターデータ管理・デッキバリデーション・カード一覧 | Go 1.25 | lint → test → Docker push |
| **battle** | 対戦ゲームエンジン | C# / .NET 10 | test → Docker push |
| **client** | モバイル/Web フロントエンド | React 19, TypeScript, Vite, Capacitor | lint → typecheck → test |
| **infra** | GCP リソース管理 | Terraform | plan → apply（パス変更時のみ） |
| **k8s** | GKE デプロイ・運用 | Kustomize, GitHub Actions | deploy / startup / shutdown / scale |
| **ops** | DB マイグレーション・監視ジョブ・Slack コマンド | Docker, Cloud Run, Cloudflare Workers, Python | CI + 手動 dispatch |
| **analytics** | Spanner → BigQuery エクスポート | Go, Cloud Functions | 手動デプロイ |
| **newsfeed** | ニュースフィード生成 | Python, Vertex AI | 手動デプロイ |

**サービス間通信:** Gateway 以外のサービス（account / matchmaking / shop / scenario / card / battle）はクラスタ内ネットワークに閉じ、原則 Gateway からの内部 REST 経由でのみ到達可能とする。唯一の例外は shop サービスの Webhook 受信エンドポイントで、Apple / Google の課金サーバーからのサーバー間通知を受けるために外部公開する（詳細は 8.6 参照）。

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
│   ├── gamedata/               # Go パッケージ 本番用 (型・定数のみ)
│   │   ├── model/              # 生成: Go モデル
│   │   ├── constants/          # 生成: ゲーム定数
│   │   └── cardno/             # 生成: カード番号定数
│   ├── devdata/                # Go パッケージ 開発用 (ローカルモック用データ)
│   │   └── cache/              # 生成: cards_gen.json, products_gen.json (embed)
│   ├── dotnet/                 # NuGet パッケージ (battle 用)
│   │   ├── GameConstants_gen.cs
│   │   └── EventData_gen.cs
│   └── npm/                    # npm パッケージ (client 用)
│       └── src/constants.ts, eventData.ts
└── .github/workflows/
    ├── ci.yaml                 # DB マイグレーション CI
    └── publish.yaml            # 統合 publish (check → test → gamedata → api → devdata)

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

各 codegen スクリプトを実行すると、`packages/` 以下にパッケージとして生成される。main への push 時に CI が自動で publish する。

| 入力 | スクリプト | 出力先 | パッケージ |
|------|-----------|--------|-----------|
| `data/cards/*.yaml` | `generate_cards.py` | `docs/CARDS.md` | — |
| `data/cards/*.yaml` | `generate_cards.py` | `packages/devdata/cache/cards_gen.json` | Go devdata (embed) |
| `data/cards/*.yaml` | `generate_cards.py` | `packages/gamedata-dotnet/cache/cards_gen.json` | NuGet (EmbeddedResource) |
| `data/cards/*.yaml` | `generate_cards.py` | `db/seed/cards_seed.sql` | — |
| `data/mock/products.yaml` | `generate_products.py` | `packages/devdata/cache/products_gen.json` | Go devdata (embed) |
| `data/mock/products.yaml` | `generate_products.py` | `db/seed/products.sql` | — |
| `data/models.yaml` | `generate_constants.py` | `packages/gamedata/model/*_gen.go` | Go gamedata |
| `data/constants.json` | `generate_constants.py` | `packages/gamedata/constants/constants_gen.go` | Go gamedata |
| `data/constants.json` | `generate_constants.py` | `packages/gamedata-dotnet/GameConstants_gen.cs` | NuGet (`OverloadParty.GameData`) |
| `data/constants.json` | `generate_constants.py` | `packages/gamedata-npm/src/constants.ts` | npm (`@kenyamaneko/overload-party-gamedata`) |
| `data/event_schemas.json` | `generate_constants.py` | `packages/gamedata-dotnet/EventData_gen.cs` | NuGet |
| `data/event_schemas.json` | `generate_constants.py` | `packages/gamedata-npm/src/eventData.ts` | npm |

各リポはパッケージをインストールして使う（gateway: `go get gamedata` + `go get devdata`, battle: NuGet, client: npm）。生成されたファイルには `DO NOT EDIT` コメントが付く。

#### パッケージ責務

| パッケージ | 形式 | 責務 | 消費先 |
|---|---|---|---|
| `packages/gamedata/` | Go module | ゲームデータ（カード定義・定数・エフェクト型）+ ゲームステート View 型 | gateway |
| `packages/api/` | Go module | API コントラクト（REST 型・WS メッセージ・デッキ型） | gateway |
| `packages/devdata/` | Go module | ローカル開発用モックデータ（cards_gen.json, products_gen.json） | gateway (dev) |
| `packages/gamedata-dotnet/` | NuGet | カード定義・定数・イベントデータ・ゲームステート View 型・AvailableAction | battle |
| `packages/gamedata-npm/` | npm | 定数・イベントデータ・ゲームステート View 型・AvailableAction | client |
| `packages/api-npm/` | npm | REST API 型・WS メッセージ型 | client |

**gamedata と api の分離:** gamedata パッケージにはゲームデザインデータに加え、ゲームステート View 型（`ClientGameState`, `PlayerView` 等）が含まれる。これは battle サーバーが直接シリアライズし client がデシリアライズする JSON ワイヤーフォーマット（API 契約）であり、gateway はパススルーする。api パッケージは gateway-client 間の REST/WS プロトコル契約で、battle サーバーは使わない。`models.yaml` の `pkg` フィールド（`gamedata` / `api`）で生成先を振り分ける。

### 2.4 作業別クロスリファレンス

「何を変えたら、どのリポを触る必要があるか」の早見表。

| やりたいこと | 編集するリポ | 次にやること | 影響を受けるリポ |
|-------------|------------|------------|----------------|
| カードの追加・変更 | common (`data/cards/*.yaml`) | `--gen-dir packages/` で生成 → main push で自動 publish | gateway, battle, client（パッケージ更新） |
| ゲーム定数の変更 | common (`data/constants.json`) | `--gen-dir packages/` で生成 → main push で自動 publish | gateway, battle, client（パッケージ更新） |
| DB スキーマの変更 | common (`db/schema_postgres.sql`) | main に push（CI が自動適用） | gateway, battle（コード側の対応） |
| IAM 権限の変更 | common (`db/grant_iam.sql`) | main に push（CI が自動適用） | — |
| API エンドポイント追加 | 対応するドメインサービス（account / matchmaking / shop / scenario / card 等）、およびルーティング用に gateway | CI が自動で Docker push | k8s（deploy で反映） |
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
             ┌────────────────────┼────────────────────┐
             │ codegen             │ codegen             │ codegen
             ▼                    ▼                    ▼
  ┌──────────────────────┐  ┌──────────┐        ┌─────────┐
  │ Go サービス群         │  │ battle   │        │ client  │
  │ gateway / account    │  │  (C#)    │        └─────────┘
  │ matchmaking / shop   │  └────┬─────┘
  │ scenario / card      │       │ Docker
  └──────────┬───────────┘       │
             │ Docker            │
             ▼                   ▼
      ┌─────────────────────────────┐
      │       k8s (deploy)          │ ← Kustomize + GitHub Actions
      └─────────────────────────────┘
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
   ┌──────┐    ┌──────┐    ┌───────────┐
   │ infra│    │ ops  │    │ analytics │  ← 独立したライフサイクル
   └──────┘    └──────┘    └───────────┘
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

バックエンドは Go サービス 6 本と C# の Battle Server 1 本の計 7 サービス構成。Gateway がクライアントからのトラフィックを受け、内部 REST でドメインサービスにルーティングする。

```
Go サービス群 (Go 1.25)
├── Web Framework (Gin)
├── WebSocket (gorilla/websocket) — gateway のみ
├── PostgreSQL Client (pgxpool)
├── Cloud SQL Auth Proxy (サイドカー)
└── Firebase Admin SDK — 認証検証が必要なサービス

Battle Server (C# / .NET 10)
├── ASP.NET Core (REST API)
├── PostgreSQL Client (Dapper)
├── Cloud SQL Auth Proxy (サイドカー)
└── xUnit (テスト)
```

**責務分離:**
- **gateway** (Go): WS 通信ハンドリング、認証検証、内部サービスへのルーティング
- **account** (Go): ユーザー登録・設定・パスワードリセット
- **matchmaking** (Go): マッチキュー管理、マッチロジック、バトルへの引き渡し
- **shop** (Go): 課金連携 (Apple/Google)、購入管理、フラグ付与、Webhook 受信
- **scenario** (Go): シナリオ解放判定、シナリオファイル配信
- **card** (Go): カードマスターデータ管理、デッキバリデーション、カード一覧
- **battle** (C#): ゲームエンジン、アクション処理、エフェクト、NPC AI、勝利判定、ゲームログ

**選定理由:**
- Gateway (Go): 高パフォーマンスな並行処理、WebSocket 常時接続に最適
- ドメインサービス (Go): Gateway と同じスタック (Go 1.25) で統一し、学習コスト・運用コストを抑える
- Battle (C#): 複雑なゲームロジックの表現力、型安全性、.NET エコシステム
- GKE Standard でゲームサーバー管理

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
│   ├── GKE Standard (全 7 サービス相乗り — 全環境共有)
│   │     e2-standard-2 (2 vCPU / 8 GiB) × 1 ノード
│   ├── Artifact Registry (Docker イメージ)
│   ├── Cloud Pub/Sub (matchmaking-events トピック)
│   └── Ingress (GCE L7 LB, gateway と shop のみ外部公開)
├── overload-party-{dev,stg,prod}
│   ├── Cloud SQL PostgreSQL (Database — 環境ごと独立、スキーマ単位分割)
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
│                GKE Standard (Application Layer)                 │
│   e2-standard-2 (2 vCPU / 8 GiB) × 1 ノード、全 7 サービス相乗り │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐ ┌───────────────┐  │
│  │  gateway (Go)    │  │  account (Go)    │ │ scenario (Go) │  │
│  │  WS ハンドリング │  │  登録・設定      │ │ シナリオ配信  │  │
│  │  認証検証        │  └──────────────────┘ └───────────────┘  │
│  │  内部ルーティング│  ┌──────────────────┐ ┌───────────────┐  │
│  └──────┬───────────┘  │ matchmaking (Go) │ │   card (Go)   │  │
│         │              │ キュー/マッチ    │ │ カードマスタ  │  │
│         │ 内部 REST    │ 引き渡し         │ │ デッキ検証    │  │
│         ▼              └──────────────────┘ └───────────────┘  │
│  ┌──────────────────┐  ┌──────────────────┐ ┌───────────────┐  │
│  │   shop (Go)      │  │   battle (C#)    │ │ Cloud SQL     │  │
│  │  課金・Webhook   │  │  ゲームエンジン  │ │ Auth Proxy    │  │
│  └──────────────────┘  └──────────────────┘ │ (sidecar)     │  │
│                                              └───────────────┘  │
└───┬──────────────┬──────────────────────────────────┬──────────┘
    │ Ingress      │ Ingress                          │ PostgreSQL
    │ (gateway)    │ (shop: /webhook/*)               ▼
    ▼              ▼                ┌────────────────────────────┐
  Client     Apple / Google         │        Data Layer          │
                                    │  ┌──────────────────────┐  │
                                    │  │ Cloud SQL PostgreSQL │  │
                                    │  │ （スキーマ単位分割） │  │
                                    │  │  account / card /    │  │
                                    │  │  shop / scenario /   │  │
                                    │  │  battle / newsfeed   │  │
                                    │  └──────────────────────┘  │
                                    └────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      External Services                          │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │   Firebase   │  │ Cloud Storage│  │  Upstash Redis      │   │
│  │Authentication│  │ (Replays/Log)│  │ (matchmaking queue) │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Google Cloud Pub/Sub                                      │ │
│  │  - matchmaking-events      (Exactly-Once, 9.5)            │ │
│  │  - card-definitions-updated (at-least-once, 5.3)          │ │
│  │  - subscription-events      (Exactly-Once, 9.6)           │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**サーバー間通信:**
- サービス間は内部 REST API（例: `http://battle:9002/api/v1/...`）。battle を含むドメインサービスは認証を行わず、gateway を信頼（クラスタ内ネットワークに閉じる）
- 外部公開は gateway（クライアント向け WS/REST）と shop（Apple / Google webhook 受信用）の 2 サービスのみ。他は ClusterIP で gateway からのみ到達可能
- matchmaking → gateway のマッチ成立通知は非同期で、Cloud Pub/Sub のトピック `matchmaking-events` 経由で配信する（詳細は 9.5）
- shop → account のプレミアム状態伝搬は非同期で、Transactional Outbox + Cloud Pub/Sub のトピック `subscription-events` 経由で配信する（詳細は 9.6）
- card → battle のカード定義キャッシュ無効化通知は Cloud Pub/Sub のトピック `card-definitions-updated` 経由で配信する（詳細は 5.3）
- DB 所有権はサービス単位に分離される。詳細は 5 章を参照

### 4.2 インフラ基盤の選定

> 比較検討の詳細（コスト表・6軸比較）は [DESIGN_NOTES.md](DESIGN_NOTES.md#インフラ基盤の選定ログ) を参照。

#### 4.2.1 選定結果: GKE Standard

ゲームバックエンドは **GKE Standard** クラスタ上で運用する。現状のトラフィック規模では全サービスが 1 ノードに収まっており、ノードプールの自動拡縮や bin packing の最適化を必要としない。VM 単位課金である Standard のほうが同等ワークロードでは明確に安く、sysctl やファイルディスクリプタ等のノードレベルのチューニング余地も確保できる。

| 項目 | 値 |
|------|-----|
| モード | Standard |
| リージョン | asia-northeast1 |
| マシンタイプ | `e2-standard-2`（2 vCPU / 8 GiB memory） |
| ノード数 | 1（デフォルトノードプール 1 本のみ） |
| 月額概算 | 約 $49（オンデマンド価格・1 ノード前提） |

Cloud Run はゲートウェイの長寿命 WebSocket 接続（リクエスト単位のライフサイクル、最大タイムアウト、コネクションアフィニティの制約）と適合せず採用しない。複数ノード化は HA 面では望ましいが、現状のユーザー規模と SLO に対しては明確にオーバースペックであり、必要になった時点で再検討する。単一ノードは SPOF となるが、ベストエフォートの SLO として現時点では許容する。

**クラスタ構成（1クラスタ・Namespace分離）:**

GKE Standard クラスタは共有プロジェクト `keyandnotes-platform` に配置し、Namespace で環境を分離する。各環境の Cloud SQL は環境別プロジェクト（`overload-party-dev` 等）に配置し、**Workload Identity + Cloud SQL Auth Proxy** でクロスプロジェクトアクセスする。

全 7 サービス（gateway / account / matchmaking / shop / scenario / card / battle）を **1 ノード上に 1 Pod ずつ相乗り** させる。レプリカ数は当面いずれも 1 とし、HA は追求しない。外部公開は 1 つの Ingress に集約し、gateway と shop の 2 サービスのみ外部からアクセス可能とする。それ以外は ClusterIP で、gateway からの内部 REST 経由でのみ到達可能とする。

| サービス | Service type | 公開理由 |
|----------|-------------|---------|
| gateway | Ingress (外部) | クライアントからの REST/WS エントリーポイント |
| shop | Ingress (外部) | Apple / Google からの購入 webhook 受信のため公開エンドポイントが必要 |
| account | ClusterIP | gateway からの内部 REST のみ |
| matchmaking | ClusterIP | gateway からの内部 REST + Upstash Redis + Cloud Pub/Sub |
| scenario | ClusterIP | gateway からの内部 REST のみ |
| card | ClusterIP | gateway / battle からの内部 REST のみ |
| battle | ClusterIP | gateway からの内部 REST のみ |

```
[GKE Standard Cluster] keyandnotes-platform / asia-northeast1 / e2-standard-2 × 1
  ├── Namespace: dev
  │     └── Deployment × 7 (gateway / account / matchmaking / shop / scenario / card / battle)
  │         replicas: 0 (開発時以外)
  ├── Namespace: staging
  │     └── Deployment × 7   replicas: 0 (開発時以外)
  └── Namespace: prod
        ├── Deployment × 7   replicas: 1
        ├── Service: type=ClusterIP（gateway・shop 以外）
        └── Ingress: External HTTP(S) LB (WebSocket対応)
              ├── gateway: クライアント向け REST/WS
              └── shop:    /webhook/apple, /webhook/google のみ公開
```

dev/stg は引き続き毎日 2:00 AM JST に自動停止してコストを最小化する。GKE Standard ではノードプールのサイズを 0 にすることで同等のコスト削減が可能である。

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
- **card_definitions** — カード定義マスター（card サービスが所有。battle はインメモリキャッシュ経由で参照）
- **player_cards / decks / deck_cards** — 所持カード・デッキ構築
- **products / subscriptions / one_time_purchases** — ショップ・課金
- **cosmetic_items / player_items** — コスメティクス

### 5.1 スキーマ分割とオーナーシップ

Cloud SQL インスタンスは 1 つのまま維持したうえで、**PostgreSQL スキーマをサービス単位に分割する**。各サービスには専用の DB ユーザー（IAM サービスアカウント）を払い出し、自スキーマに対してのみ `USAGE` と `SELECT/INSERT/UPDATE/DELETE` を付与する。他スキーマには `USAGE` すら付与せず、アプリ側で誤って他サービスのテーブル名を書いたクエリを実行しても DB レイヤーで拒否される。

- **書き込みは所有サービスのみ**: テーブルの write は所有サービスに限定される
- **クロスサービス read も API 経由**: 他ドメインのデータが読みたい場合は、所有サービスが提供する REST API 経由で取得する。直接のクロススキーマ SELECT は権限上も設計上も許容しない
- **1 インスタンス維持**: Cloud SQL インスタンスを複数立てるコスト（固定費・運用・バックアップ）を避けるため、物理的には単一インスタンスを継続する。将来 DB インスタンスをサービス単位に分けたくなった場合でも、接続先変更とデータ移行だけで済み、アプリ側のクエリ書き換えは不要にできる

**スキーマ配置:**

| スキーマ | 所有サービス | 主な対象テーブル |
|---|---|---|
| `shared` | （なし: マイグレーション管理） | `game_config` |
| `account` | account | `players`, `player_daily_battle`, `player_factions`, `user_settings` |
| `card` | card | `card_definitions`, `player_cards`, `decks`, `deck_cards` |
| `shop` | shop | `products`, `subscriptions`, `one_time_purchases`, `cosmetic_items`, `player_items` |
| `scenario` | scenario | `scenario_episodes`, `episode_required_factions`, `player_story_progress` |
| `battle` | battle | `games`, `game_npcs`, `game_decks`, `game_players`, `game_states`, `game_actions`, `game_events` |
| `newsfeed` | newsfeed | `news_articles` |
| （なし） | matchmaking | キューは Upstash Redis、通知は Cloud Pub/Sub のため RDB スキーマを持たない |

- **`shared` スキーマ**: 特定サービスに属さず、全サービスが SELECT のみで参照する master / config データを配置するスキーマ。write はマイグレーション管理ユーザー（psqldef などで DDL とシードデータを投入する管理専用アカウント）にのみ許可し、各サービスユーザーには `USAGE + SELECT` のみ付与する。現時点の住人は `game_config` のみで、runtime update を想定しない「シードで投入する read-only データ」の置き場として予約する
- **`factions` テーブルの廃止 (実施済み)**: 従来 DB に持っていた陣営マスター（`factions` テーブル）は廃止済み。ID 定数 (`FactionSHE` 等)・表示名 (`short_name_ja` / `short_name_en` / `full_name_ja` / `full_name_en`)・`is_collectible`・`sort_order` などの metadata は `data/factions.yaml` を SSoT として `packages/gamedata/constants/game_design/` の code-generated 定数 (`FactionMetadata` 構造体含む) に寄せた。`players.selected_faction` など 6 箇所に存在した `factions(faction_id)` への FK 制約は全て撤廃済みで、該当カラムは `VARCHAR(20)` + `CHECK` 制約で不正値を拒否する

### 5.2 カード定義のサービス間参照

`card_definitions` は **card スキーマの所有物** であり、card サービス以外は DB を直接参照せず、card サービスが提供する REST API 経由で取得する。

| 用途 | 参照方法 |
|------|----------|
| ゲーム中の効果計算（battle） | card サービスからカードマスターデータを取得し、battle プロセス内のインメモリキャッシュで参照 |
| デッキ構築画面（client） | card サービスの REST API `GET /api/v1/cards` で全カード定義を返却。クライアントはローカルキャッシュ |
| デッキバリデーション（card） | card サービス内部で `card_definitions` を直接参照 |

battle は対戦中に大量のカードデータを参照するため、毎回 card サービスに API コールする構成はレイテンシ・負荷の両面で現実的ではない。battle 側でカードマスターデータをインメモリキャッシュする前提で運用する。カードマスターは更新頻度が低く、バージョン付きで配布されている（`card_data_version` を `games` に記録済み）ため、キャッシュ戦略は比較的単純に組める。

### 5.3 カード定義キャッシュの更新通知

battle 側のインメモリキャッシュの更新戦略は以下のとおりとする。

- **初期ロード**: battle Pod 起動時に card サービスの REST API `GET /api/v1/cards` で全カード定義を取得し、プロセス内のインメモリキャッシュに保持する
- **更新通知**: card サービスがカードマスター更新時に、Google Cloud Pub/Sub のトピック `card-definitions-updated` に invalidation イベントを publish する。ペイロードは `{type: "invalidated"}` のようなシグナルのみで、どのカードが変わったかといった差分情報は含めない
- **到達保証**: このトピックの subscription は **at-least-once** で十分（Exactly-Once Delivery は不要）。重複受信しても battle 側は「キャッシュを破棄して REST API で全件再取得」するだけで、操作として冪等であるため
- **Subscription の設計**: battle Pod ごとに **別々の subscription** を割り当てる（broadcast 構成）。マッチメイキングイベント（`matchmaking-events-gateway`）が競合コンシューマで 1 Pod のみ受信するのと逆で、カード invalidation は **全 battle Pod に届く必要がある**（各 Pod が独立した in-memory キャッシュを持つため）。Pod 名や Pod インスタンス ID をサフィックスに含めた動的命名の subscription を起動時に作成・終了時に削除する運用を想定する
- **当面の前提**: 現行インフラ方針（GKE Standard 単一ノード・1 replica per service）下では battle Pod は 1 個しかないため、この broadcast 構成の挙動は単一 subscription とほぼ変わらない。ただし水平スケール時に即座に機能する設計として最初からこの形で組む
- **レスポンス形状**: card サービスの `GET /api/v1/cards` は全カード定義を 1 レスポンスで返却する。件数は 126 枚程度で、毎回全件返しても負荷上問題にならない。差分配信やページングは不要
- **バージョン整合性**: カードマスターにはバージョン番号が付与されており、`games.card_data_version` に記録される。battle が扱うゲーム状態と対応するカード定義バージョンのズレは、ゲーム開始時に battle が保持しているキャッシュのバージョンを `games.card_data_version` として記録することで検証可能にする

---

## 6. API設計

- **REST API**（クライアント向け公開 API、入口は gateway）: プレイヤー管理、デッキ管理、NPC 対戦、ショップなど
- **WebSocket API**（クライアント ↔ gateway）: PvP マッチメイキング、リアルタイム対戦、スタンプ送信など
- **内部 REST API**（サービス間通信、クラスタ内部のみ）: gateway ↔ account / card / shop / scenario / matchmaking / battle、および battle ↔ card など

各エンドポイントの詳細は以下を参照する。

| 種別 | ドキュメント |
|---|---|
| クライアント向け REST | [API_REFERENCE.md](API_REFERENCE.md) |
| クライアント向け WebSocket | [WS_REFERENCE.md](WS_REFERENCE.md) |
| サービス間 内部 REST | [internal/](internal/README.md) |

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

購入レシートは**必ずサーバーサイドで検証**する。クライアント側の検証結果は信頼しない。検証処理は shop サービスが担当し、gateway は認証済みのリクエストを shop サービスに中継するのみ。所有スキーマが複数サービスに分かれているため、買い切り商品とサブスクリプションでフローが大きく異なる点に注意する（詳細は [internal/shop.md](internal/shop.md) / [internal/account.md](internal/account.md) 参照）。

**買い切り商品（`faction_set` / `cosmetic`）の購入フロー:**

```
Client         gateway           shop サービス           Apple / Google
  │                │                    │                         │
  │  1. ストア購入UI起動                 │                         │
  │  ──(StoreKit/Billing)──>             │                         │
  │                │                    │                         │
  │  2. 決済完了    │                    │                         │
  │  (receipt /    │                    │                         │
  │   purchaseToken)│                    │                         │
  │  ─────────────>│                    │                         │
  │                │  2'. 内部 REST 転送 │                         │
  │                │  POST /internal/v1/players/{id}/purchases     │
  │                ├───────────────────>│                         │
  │                │                    │  3. Receipt 検証         │
  │                │                    │  GET history (Apple)    │
  │                │                    │  GET purchases (Google) │
  │                │                    ├───────────────────────>│
  │                │                    │<───────────────────────┤
  │                │                    │  4. 検証OK → shop Tx     │
  │                │                    │     - one_time_purchases │
  │                │                    │       INSERT (冪等:      │
  │                │                    │       purchase_token     │
  │                │                    │       UNIQUE)            │
  │                │                    │     - cosmetic の場合のみ│
  │                │                    │       player_items UPDATE│
  │                │<───────────────────┤                         │
  │                │                    │                         │
  │  （faction_set の場合のみ）           │                         │
  │                │  5. gateway が後続オーケストレーションを実行   │
  │                │     - account: POST /internal/v1/players/{id}/factions
  │                │     - card:    POST /internal/v1/players/{id}/grant-faction-pack
  │                │                    │                         │
  │  6. 購入結果    │                    │                         │
  │<───────────────┤                    │                         │
```

`faction_set` の場合、shop 自身は `one_time_purchases` のみ更新し、ファクションアンロックとカード付与は gateway が account / card に対して順次内部 REST を呼び出すオーケストレーションとして行う（所有権境界は §8.7 参照）。shop の DB 書き込みはアトミックだが、後続の account / card 呼び出しは eventually consistent であり、途中失敗時は運用で手動修復する（補償トランザクションは採用しない）。

**サブスクリプション（プレミアムプラン）の購入フロー:**

サブスクリプションは shop で Transactional Outbox に書き込み、Cloud Pub/Sub 経由で account に非同期伝搬する。shop → account の同期 REST 呼び出しは行わない（Pub/Sub トピック・サブスクリプションの詳細は §9.6 参照）。

```
Client    gateway    shop サービス             Apple / Google   Cloud Pub/Sub    account サービス
  │          │            │                          │               │                │
  │ 1. 購入  │            │                          │               │                │
  │─────────>│            │                          │               │                │
  │          │ 1'. POST /internal/v1/players/{id}/subscriptions       │                │
  │          ├───────────>│                          │               │                │
  │          │            │ 2. Receipt 検証           │               │                │
  │          │            ├────────────────────────>│               │                │
  │          │            │<────────────────────────┤               │                │
  │          │            │ 3. 検証OK → shop Tx      │               │                │
  │          │            │    ┌───────────────────────────────┐     │                │
  │          │            │    │ BEGIN                         │     │                │
  │          │            │    │  INSERT subscriptions         │     │                │
  │          │            │    │  INSERT subscription_outbox   │     │                │
  │          │            │    │ COMMIT                        │     │                │
  │          │            │    └───────────────────────────────┘     │                │
  │          │<───────────┤ 4. 200 OK                │               │                │
  │<─────────┤            │                          │               │                │
  │          │            │                          │               │                │
  │          │            │ 5. publisher goroutine が outbox を poll  │                │
  │          │            │    → Pub/Sub publish                     │                │
  │          │            ├─────────────────────────────────────────>│                │
  │          │            │    (topic: subscription-events)          │                │
  │          │            │                          │               │                │
  │          │            │                          │ 6. subscriber goroutine が      │
  │          │            │                          │    subscription-events-account  │
  │          │            │                          │    を pull                      │
  │          │            │                          │               ├───────────────>│
  │          │            │                          │               │ 7. players      │
  │          │            │                          │               │    UPDATE       │
  │          │            │                          │               │    is_premium / │
  │          │            │                          │               │    premium_     │
  │          │            │                          │               │    expires_at   │
```

`subscriptions` と `subscription_outbox` を同一トランザクションで書き込むことで「決済記録はあるが Pub/Sub publish に失敗した」状態を原理的に排除する。到達保証・冪等性・失敗時挙動・DLQ の詳細は §9.6 を参照。

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

> サブスクの状態変更（自動更新・解約・猶予期間・返金等）は shop サービスがサーバー通知 (webhook) で受信し、`shop.subscriptions` と `shop.subscription_outbox` を同一トランザクションで更新する。その後、`players.is_premium` / `players.premium_expires_at` は Outbox + Cloud Pub/Sub 経由で account サービスが非同期に更新する。クライアント起点のポーリングは行わない。責務分担の詳細は §8.6 / §8.8 / §9.6 を参照。

### 8.6 Webhook 受信（shop サービス）

Apple / Google からのサーバー通知は、**shop サービスが公開エンドポイントで直接受信する**。ユーザートラフィックの入口は gateway 一本に保ちつつ、課金プラットフォーム側の制約上 gateway 経由でルーティングできないため、shop にのみ例外的に公開エンドポイントを許可する。webhook 用の受信パスは他のクライアント API と明示的に区別し、レート制限も別建てで設定する。

```
Apple Server Notifications V2  ──>  shop (GKE Ingress)  ──>  Cloud SQL (shop スキーマ)
Google RTDN (Pub/Sub push)     ──>  shop (GKE Ingress)  ──>  Cloud SQL (shop スキーマ)
```

| 項目 | 内容 |
|------|------|
| 受信先 | shop サービス（GKE Ingress 経由で外部公開） |
| ランタイム | Go |
| 責務 | サーバー通知の受信・署名検証・`subscriptions` と `subscription_outbox` の同一トランザクション更新 |
| 認証 | Apple: JWS 署名検証 / Google: Pub/Sub push トークン検証 |
| エンドポイント | `POST /webhook/apple` / `POST /webhook/google` |

> account サービスの `players.is_premium` / `premium_expires_at` への伝搬は、shop が書き込んだ `subscription_outbox` を publisher goroutine が Cloud Pub/Sub (`subscription-events`) に publish し、account の subscriber goroutine が pull して反映する非同期経路で行われる。詳細は §9.6 を参照。

### 8.7 冪等性と不正対策

| 対策 | 実装方法 |
|------|---------|
| 重複購入防止 | `purchase_token`（Apple: `transactionId` / Google: `purchaseToken`）を shop スキーマの `one_time_purchases` / `subscriptions` に保存し、UNIQUE 制約で重複 INSERT を排除 |
| レシート再利用防止 | 検証済みトークンを shop スキーマに記録。同一トークンでの再リクエストは既存結果を返却 |
| クライアント改ざん防止 | 課金関連テーブルはすべてサーバー側のみが write。クライアントからの直接変更は不可（下表の所有権境界を参照） |

**所有権境界（課金関連テーブルの write 権限）:**

| スキーマ | テーブル | write するサービス | 備考 |
|---------|---------|-------------------|------|
| `shop` | `subscriptions`, `one_time_purchases`, `cosmetic_items`, `player_items`, `subscription_outbox` | shop サービスのみ | webhook / 内部 REST 経由で shop が更新。`subscription_outbox` は publisher goroutine の poll 対象 |
| `account` | `players`（`is_premium` / `premium_expires_at` を含む） | account サービスのみ | shop からは Cloud Pub/Sub (`subscription-events`) 経由で非同期に伝搬。shop → account の同期 REST 呼び出しは存在しない |
| `card` | `player_cards` | card サービスのみ | `faction_set` 購入時は gateway オーケストレーションにより shop → card の内部 REST (`POST /grant-faction-pack`) 経由で付与 |

クライアントから上記テーブルを直接書き換える経路は存在しない。Pub/Sub 経由の伝搬は eventually consistent であり、shop が購入を記録してから account の `is_premium` が反映されるまでにラグがある点に留意する（詳細は §9.6）。

### 8.8 購入処理のトランザクション

**買い切り商品（`cosmetic`）:**

shop 単独のトランザクションで完結する。所有テーブルはすべて shop スキーマ内にあるため、アトミックに決済記録と所持反映が行われる。

```
BEGIN (shop)
  1. one_time_purchases に purchase_token が存在しないことを確認
  2. one_time_purchases に INSERT (purchase_token, player_id, product_id, verified_at)
  3. player_items に UPDATE / INSERT（cosmetic アイテム所持を反映）
COMMIT
```

> shop スキーマ内で完結するため、「決済済みだが所持反映されない」状態は発生しない。

**買い切り商品（`faction_set`）:**

shop トランザクションでは `one_time_purchases` のみ更新する。ファクションアンロックとカード付与は gateway オーケストレーションにより account / card へ順次内部 REST を呼び出す形で eventually consistent に反映される。

```
1. BEGIN (shop)
     one_time_purchases に INSERT (purchase_token, player_id, product_id, verified_at)
   COMMIT
2. gateway: account に POST /internal/v1/players/{id}/factions （ファクションアンロック）
3. gateway: card    に POST /internal/v1/players/{id}/grant-faction-pack （カード付与）
```

> 2 / 3 のいずれかが失敗した場合、shop の `one_time_purchases` は既にコミット済みであり、補償トランザクションは採用しない。運用による手動修復を前提とする（`feedback_no_fallback` の方針に整合: フォールバックによる不整合状態を作らず、失敗は失敗として記録する）。

**サブスクリプション（プレミアムプラン）:**

webhook 受信・購入 API 受信のいずれの経路でも、shop は同一トランザクションで `subscriptions` と `shop.subscription_outbox` を更新する。account の `players.is_premium` / `premium_expires_at` は shop からは直接更新せず、Outbox + Cloud Pub/Sub 経由で伝搬させる。

```
1. BEGIN (shop)
     INSERT / UPDATE subscriptions
       （purchase_token, player_id, plan_id, status, expires_at 等）
     INSERT subscription_outbox
       （イベントペイロード: player_id, plan_id, status, expires_at 等）
   COMMIT
2. shop サービス内 publisher goroutine が subscription_outbox を poll
   → Cloud Pub/Sub トピック subscription-events に publish
   → publish 成功後、outbox 行を published 済みとしてマーク
3. account サービス内 subscriber goroutine が
   subscription-events-account subscription を pull
   → players.is_premium / premium_expires_at を UPDATE
```

- shop → account の同期 REST 呼び出しは存在しない
- 到達保証（at-least-once）・冪等性・DLQ・失敗時の挙動は §9.6 を参照
- 個別イベント種別（`subscription.activated` / `renewed` / `expired` / `revoked` 等）の一覧と扱いは §9.6 および [internal/account.md](internal/account.md) を参照

**猶予期間のポリシー:**

| 項目 | 内容 |
|------|------|
| Apple | Billing Retry Period（最大60日）中はプレミアム維持 |
| Google | Grace Period（通常3〜7日）中はプレミアム維持 |
| 猶予終了後 | account の Premium Subscriber が `subscription.expired` イベントを受信した時点で `players.is_premium = false` に更新し、スタミナ制に戻す |

> 猶予期間中もプレミアムを維持する方針。決済が復旧すれば自動更新され、復旧しなければ猶予終了後に失効する。ユーザー体験を優先し、一時的な決済エラーでプレミアムが途切れることを防ぐ。

---

## 9. リアルタイム通信

### 9.1 WebSocket接続管理

| 機能 | 内容 |
|------|------|
| 接続登録 | `playerID → WebSocket接続` のマップを gateway Pod 内インメモリ管理 |
| ゲーム参加 | `gameID → []playerID` のマップを gateway Pod 内で管理 |
| ブロードキャスト | gateway がゲーム内の全プレイヤーに状態更新を送信 |
| ドメイン処理の委譲 | gateway は認証・WS ルーティング・ブロードキャストに専念し、ドメイン処理（ゲームロジック・マッチメイキング・カード・シナリオ等）は対応する内部サービス (battle / matchmaking / card / scenario / account / shop) に内部 REST で委譲する |
| スレッドセーフティ | `sync.RWMutex` で同時アクセスを制御 |

内部サービスとの通信方式は 4.1 の全体構成、および各サービスの内部 REST 契約（[internal/](internal/)）を参照。

### 9.2 再接続処理

```
再接続リクエスト
        │
        ▼
gateway が対戦中であれば battle サービスの
内部 REST で最新 GameState を取得
        │
        ▼
gateway Pod 内の WS セッションマップに接続を再登録
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

ランダムマッチメイキングを採用する。キュー内のプレイヤーを待機時間順に FIFO でマッチングする。マッチングロジックは matchmaking サービスが担当し、gateway はクライアントからの `matchmaking_start` / `matchmaking_cancel` を matchmaking サービスに内部 REST で中継する。

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
   ├─ gateway がクライアントから matchmaking_start を受ける
   ├─ gateway → matchmaking サービスに内部 REST (enqueue)
   └─ matchmaking サービス:
        ├─ スタミナチェック（account サービスに問い合わせ）
        ├─ デッキ有効性チェック（card サービスに問い合わせ）
        └─ ZADD matchmaking:queue <joinedAt_ms> <playerID>

2. マッチングループ（matchmaking サービス内の goroutine）
   ├─ ZPOPMIN matchmaking:queue 2 で先着 2 名をアトミックに取り出す
   ├─ マッチ成立処理（デッキ取得、battle サーバに対戦生成依頼）
   └─ Cloud Pub/Sub (matchmaking-events) に match_made を publish

3. ゲーム作成通知
   ├─ gateway Pod 群が matchmaking-events-gateway subscription を pull
   ├─ メッセージを受信した Pod は自 Pod の in-memory session map を参照し、
   │  該当プレイヤーの WS 接続を保持していれば match_found を push
   ├─ 保持していなければメッセージを無視（別 Pod が拾う）
   └─ クライアントは match_found を受信後、battle サーバに接続 → T1 開始
```

**キューの実装方式:**

| 項目 | 内容 |
|------|------|
| データストア | Upstash Redis の Sorted Set (`matchmaking:queue`, `ZADD` / `ZPOPMIN` / `ZREM`) |
| キューの責務 | matchmaking サービスのみが read/write する。他サービスは触らない |
| マッチングワーカー | matchmaking サービス内の goroutine（定期実行） |
| キュー離脱 | 明示的な離脱は `ZREM` による O(log N) 削除。WS 切断時は gateway が matchmaking に cancel を通知して `ZREM` |
| Pod 再起動時 | キューは Upstash 側で永続化されているため消失しない。matchmaking Pod 再起動後も処理を継続できる |
| RDB | matchmaking は RDB スキーマを持たない。永続化はキューは Upstash Redis、通知は Cloud Pub/Sub に閉じる |

### 9.5.2 マッチ成立通知 (Cloud Pub/Sub)

matchmaking → gateway のマッチ成立通知は **Google Cloud Pub/Sub の Exactly-Once Delivery** を用いて配信する。同期 REST では async なマッチ結果を返せず、かつ gateway が水平スケールしたときに「どの Pod がそのプレイヤーの WS 接続を保持しているか」を matchmaking 側が知らないため、非同期かつ多対多の通知チャネルが必要になる。

通知チャネルには **Exactly-Once 相当の到達保証** を求める。これはサービス規模や SLA ではなく、マッチ成立通知の重複押出し（画面遷移の二重発火・battle 接続の二重化）やロスト（「マッチしたはずなのにロビーに戻らない」）をユーザー体験として許容しないためである。

**Topic / Subscription:**

| リソース | 名前 | 種別 | 備考 |
|---|---|---|---|
| Topic | `matchmaking-events` | — | matchmaking サービスが publish する唯一のトピック |
| Subscription | `matchmaking-events-gateway` | pull, Exactly-Once 有効 | gateway Pod 群が競合して pull する |
| Dead Letter Topic | `matchmaking-events-dlq` | — | 最大配信回数を超えたメッセージの退避先 |

**設定方針:**

- **Exactly-Once Delivery**: subscription で有効化する。ack は成功/失敗が明示的に返るため、publisher / subscriber の双方でレスポンス検証を実装する
- **ack deadline**: 10 秒。WS push の想定レイテンシに対して十分な余裕があり、失敗時の再配送も早い
- **競合コンシューマ**: 複数 gateway Pod が同じ subscription を pull することで、1 メッセージは 1 Pod にしか配送されない
- **ordering key**: 設定しない。マッチ成立イベントは独立しており、グローバルな順序保証は不要
- **DLQ**: 最大配信回数を超えたメッセージは `matchmaking-events-dlq` に退避し、DLQ の深さにアラートを紐付ける

**冪等性（保険）:**

Cloud Pub/Sub の Exactly-Once Delivery は subscription 内での重複配送を強力に抑制するが、end-to-end の Exactly-Once を達成するにはアプリ側の冪等性を併用する必要がある。gateway は受信した `match_made` イベントの `matchId` を in-memory map でトラッキングし、同一 `matchId` に対する WS push は 1 回のみとする。matchmaking サービス側も、`ZPOPMIN` で取り出したプレイヤー情報を成立確定まで in-memory で保持し、publish 失敗時の再処理パスを維持する。

**メッセージペイロード（JSON, camelCase）:**

```json
{
  "type": "match_made",
  "matchId": "mch_01HW8...",
  "players": ["player_a", "player_b"],
  "battleServerUrl": "wss://battle.overloadparty.keyandnotes.com/ws/mch_01HW8..."
}
```

**IAM:**

| コンポーネント | GCP ロール | スコープ |
|---|---|---|
| matchmaking サービス | `roles/pubsub.publisher` | topic `matchmaking-events` |
| gateway サービス | `roles/pubsub.subscriber` | subscription `matchmaking-events-gateway` |

Workload Identity で各 Pod に GCP サービスアカウントを紐付ける。Upstash Redis への接続は接続 URL を Kubernetes Secret 経由で注入する。

### 9.5.3 WebSocket メッセージ

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

## 9.6 サブスクリプション状態の非同期伝搬 (Outbox + Cloud Pub/Sub)

プレミアムサブスクリプションの状態（`players.is_premium` / `premium_expires_at`）は shop サービスの購入処理・webhook 受信を起点として変化するが、`subscriptions` テーブル（shop スキーマが所有）と `players` テーブル（account スキーマが所有）は**別スキーマ・別 DB ユーザー**のため、単一トランザクションで両方を更新することができない。両者の整合を eventually consistent に担保するため、**Transactional Outbox パターン + Cloud Pub/Sub** によるイベント駆動の非同期伝搬チャネルを shop → account の間に用意する。

### 9.6.1 背景と設計選択

- **同一トランザクション不可**: shop スキーマと account スキーマは所有サービスが異なり、各サービスの DB ユーザーは自スキーマにしか書き込み権限を持たない。アプリ側でクロススキーマ書き込みを行おうとしてもスキーマレベルで拒否される（5.1 参照）
- **gateway オーケストレーション + 補償トランザクションは採らない**: 同期 REST による「shop 更新 → account 更新 → 失敗時は shop を戻す」方式は、faction_set 購入のような一発完結の同期フローでは許容できるが、サブスクリプションでは Apple / Google の webhook 経由で renewal / refund / grace period といった**非同期状態遷移**が継続的に発生する。この遷移は gateway を経由しないため、サブスクリプションに限っては最初から非同期チャネルを用意するほうが経路を二重化せずに済む
- **Outbox パターンの利点**: shop 側で「`subscriptions` 行の書き込み」と「イベントの記録」を **同一 DB トランザクションでアトミックに** 実行できる。Cloud Pub/Sub が一時的に停止していてもイベントは `shop.subscription_outbox` に蓄積され、publisher 復旧後にまとめて publish される。publish 直前にプロセスがクラッシュしても、未 publish 行は残り続けるためイベントが失われない
- **gateway は関与しない**: この非同期パスは gateway を完全にバイパスする。gateway が課金関連の非同期イベントを保持する必要がなくなり、gateway 再起動や水平スケール時のイベントロストを考えなくて済む

### 9.6.2 全体フロー

```
Client / App Store                shop (Go)                        Cloud Pub/Sub                 account (Go)           account DB
     │                               │                                   │                           │                    │
     │  1. 購入 / 更新 / 解約          │                                   │                           │                    │
     ├─────(StoreKit / Billing)──────>│                                   │                           │                    │
     │   または Apple / Google         │                                   │                           │                    │
     │   Server Notifications         │                                   │                           │                    │
     │                                │                                   │                           │                    │
     │                                │  2. 単一 DB トランザクション:        │                           │                    │
     │                                │     BEGIN                         │                           │                    │
     │                                │       UPSERT shop.subscriptions   │                           │                    │
     │                                │       INSERT shop.subscription_   │                           │                    │
     │                                │              outbox               │                           │                    │
     │                                │     COMMIT                        │                           │                    │
     │                                │                                   │                           │                    │
     │                                │  3. publisher goroutine           │                           │                    │
     │                                │     が outbox を poll             │                           │                    │
     │                                │     (unpublished 行を select)     │                           │                    │
     │                                │                                   │                           │                    │
     │                                │  4. Publish ────────────────────>│  topic:                    │                    │
     │                                │                                   │  subscription-events       │                    │
     │                                │  5. published_at を UPDATE        │                           │                    │
     │                                │                                   │                           │                    │
     │                                │                                   │  6. subscription ────────>│                    │
     │                                │                                   │     (pull, Exactly-Once)  │  subscription-     │
     │                                │                                   │                           │  events-account    │
     │                                │                                   │                           │                    │
     │                                │                                   │                           │  7. state 比較で    │
     │                                │                                   │                           │     冪等判定 →      │
     │                                │                                   │                           │     UPDATE players │
     │                                │                                   │                           │     is_premium /    │
     │                                │                                   │                           │     premium_       │
     │                                │                                   │                           │     expires_at     │
     │                                │                                   │                           ├───────────────────>│
     │                                │                                   │                           │                    │
     │                                │                                   │                           │  8. ack            │
     │                                │                                   │<──────────────────────────┤                    │
```

- shop サービス内の **publisher goroutine** が `shop.subscription_outbox` テーブルを定期的に poll し、`published_at IS NULL` な行を Cloud Pub/Sub に publish する。publish 成功後に同一行の `published_at` を更新する。publish 失敗時は次回 poll で自然にリトライされる
- account サービス内の **subscriber goroutine** が subscription `subscription-events-account` を pull し、受信したイベントの内容に応じて `players.is_premium` と `players.premium_expires_at` を更新する
- Outbox テーブルの DDL（カラム構成・インデックス）、publisher / subscriber の詳細実装契約は [internal/shop.md](internal/shop.md#outbox-パターンsubscription-events) および [internal/account.md](internal/account.md#premium-subscriber-subscription-events) に記載する。本節ではアーキテクチャ観点の責務分担と到達保証のみを扱う

### 9.6.3 Topic / Subscription 設定

| リソース | 名前 | 種別 | 備考 |
|---|---|---|---|
| Topic | `subscription-events` | — | shop サービスの publisher goroutine が publish する唯一のトピック |
| Subscription | `subscription-events-account` | pull, Exactly-Once 有効 | account サービスが単一 subscription を pull（account Pod が複数になっても 1 メッセージは 1 Pod に配送） |
| Dead Letter Topic | `subscription-events-dlq` | — | 最大配信回数を超えたメッセージの退避先 |

**設定方針:**

- **Exactly-Once Delivery**: subscription で有効化する。`subscription-events-account` は `matchmaking-events-gateway` と同じ扱いで、重複配送を強力に抑制する
- **ack deadline**: 30 秒。account 側の `players` UPDATE はローカル DB への単純な書き込みだが、state 比較ロジック・リトライ耐性・publisher 側の poll 間隔を踏まえ、マッチメイキング通知（10 秒）より長めの余裕を取る
- **競合コンシューマ**: `matchmaking-events-gateway` と同様、account Pod 群が同一 subscription を pull する形で動作する（現行は 1 replica のため実質的に単一 Pod）。`card-definitions-updated` のような broadcast 構成は取らない（`players` 更新は「誰か 1 つの Pod が実行すれば足りる」ため）
- **ordering key**: 設定しない。各イベントは `subscriptionId` と `eventType` が自己完結しており、account 側は state 比較で順序の逆転に耐える（9.6.5 参照）
- **DLQ**: 最大配信回数を超えたメッセージは `subscription-events-dlq` に退避し、DLQ の深さにアラートを紐付ける

**IAM:**

| コンポーネント | GCP ロール | スコープ |
|---|---|---|
| shop サービス | `roles/pubsub.publisher` | topic `subscription-events` |
| account サービス | `roles/pubsub.subscriber` | subscription `subscription-events-account` |

Workload Identity で各 Pod に GCP サービスアカウントを紐付ける。

### 9.6.4 イベント種別

| `eventType` | 発火条件 | account 側の反映 |
|---|---|---|
| `subscription.activated` | 初回購入または失効後の再購入 | `is_premium = true`, `premium_expires_at = <次回更新日>` |
| `subscription.renewed` | Apple / Google からの自動更新通知 | `premium_expires_at` を延長 |
| `subscription.expired` | 猶予期間終了後の失効 | `is_premium = false` |
| `subscription.revoked` | 返金・取消（Apple: REFUND, Google: REVOKED） | `is_premium = false`（即時失効） |

ペイロードは JSON で、`eventId`（Outbox 行の UUID）・`subscriptionId`・`playerId`・`eventType`・`premiumExpiresAt`・`occurredAt` を含む。正確なフィールド定義は [internal/shop.md](internal/shop.md#outbox-パターンsubscription-events) に委ねる。

### 9.6.5 到達保証（Exactly-Once + Natural Idempotency の 2 層防御）

1. **Cloud Pub/Sub の Exactly-Once Delivery**: 第一の防御層。subscription 内での重複配送を抑制する
2. **account 側の natural idempotency**: 第二の防御層として、account subscriber は受信イベントを**そのまま当てはめず、現在の `players` 状態と比較してから UPDATE する**
   - `subscription.activated` / `renewed` を受信しても、既に `premium_expires_at` がペイロード値以上なら UPDATE をスキップ
   - `subscription.expired` / `revoked` を受信しても、既に `is_premium = false` ならスキップ
   - このため、仮に Pub/Sub レイヤーが保証に反して重複配送しても、順序が逆転しても、account 側の最終状態は決定的になる
3. **Outbox 側の損失耐性**: `shop.subscription_outbox` の行は publish 成功後のみ `published_at` を更新するため、publisher プロセスのクラッシュや Pub/Sub 側の障害で publish が失敗しても、再起動後の次回 poll で自然にリトライされる。publish が重複する可能性はあるが、前述の natural idempotency で吸収される

end-to-end の「失わない・重複しても破綻しない・順序逆転しても破綻しない」性質は、この 3 段を組み合わせることで担保される。

### 9.6.6 障害時の挙動

| 障害ポイント | 挙動 | 失われないか |
|---|---|---|
| **shop プロセス停止** | DB トランザクションは `subscriptions` 更新と outbox 挿入を同時に commit/rollback する。commit 済みなら outbox 行は残り、復旧後の publisher loop が publish する | 失われない |
| **publisher goroutine クラッシュ（publish 直前）** | 未 publish 行は `published_at IS NULL` のまま残る。プロセス再起動後の poll で再送される | 失われない |
| **publisher goroutine クラッシュ（publish 成功・published_at UPDATE 前）** | 再起動後に同じ行を再度 publish する。account 側で natural idempotency により同一状態への UPDATE は no-op となる | 失われない（重複は吸収） |
| **Cloud Pub/Sub 停止** | publisher の publish が失敗し、outbox 行は未 publish のまま蓄積される。Pub/Sub 復旧後に順次 publish される | 失われない |
| **account プロセス停止** | subscription にメッセージが滞留し、ack deadline 超過で再配送される。account 復旧後に順次 pull される。滞留が長期化すれば DLQ に落ちる | 失われない（DLQ 監視要） |
| **account の DB 更新失敗** | ack を返さず（または nack）、Pub/Sub が再配送する。一定回数失敗すると DLQ に退避 | 失われない（DLQ 監視要） |
| **メッセージ順序逆転** | natural idempotency（state 比較）により、古いイベントが後から届いても `players` の状態は後退しない | 最終状態は決定的 |

いずれのケースでも、shop の `subscriptions` テーブルが SSoT として正しく、account の `players` はその状態に eventually 追従する。クライアントは購入直後に `GET /player` を叩くと `is_premium` がまだ `false` に見える可能性があるため、購入完了後は `players` を短い間隔で再取得するリトライ UX を前提とする。反映遅延は通常秒単位。

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

### 12.2 GKE Standard 最適化

- PodDisruptionBudget + preStop hook で WebSocket 接続のグレースフルドレインを保護
- sessionAffinity (ClientIP) で同一クライアントを同一 gateway Pod にルーティング
- ノードは現状 1 台のため Pod Anti-Affinity は現時点では設定しない。マルチノード化する際にゾーン分散設定を追加する
- GKE の自動アップグレードチャネルを有効化し、ノードの OS / セキュリティパッチ管理の運用負荷を抑える

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
| `keyandnotes-platform` | 共有インフラ | GKE Standard, Artifact Registry, ArgoCD |
| `overload-party-dev` | 開発環境 | Cloud SQL PostgreSQL, IAM |
| `overload-party-stg` | ステージング環境 | Cloud SQL PostgreSQL, IAM |
| `overload-party-prod` | 本番環境 | Cloud SQL PostgreSQL, IAM |

**管理対象リソース:**

| リソース | Terraform モジュール | 配置先プロジェクト |
|---------|---------------------|------------------|
| GKE Standard クラスタ + ノードプール | `google_container_cluster`, `google_container_node_pool` | shared |
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
| 全 7 サービス Pods<br/>(gateway / account / matchmaking / shop / scenario / card / battle) | — | 0（開発時のみ起動） | 0（開発時のみ起動） | 各 1 レプリカ（相乗り） |
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

- 全 7 サービス（gateway / account / matchmaking / shop / scenario / card / battle）を `e2-standard-2` × 1 ノード上に各 replicas: 1 で相乗り
- gateway: WebSocket 接続・`playerID → *websocket.Conn` の in-memory session map を保持
- battle: ゲームロジックはステートレス（状態は PostgreSQL）
- matchmaking: キューは Upstash Redis、マッチ成立通知は Cloud Pub/Sub

#### 同時接続数の目安

| 接続数 | 対応 |
|--------|------|
| 〜200 | 現状のまま（1 ノード・全サービス replicas: 1）で十分 |
| 200〜1,000 | gateway / battle を中心に垂直スケーリング（ノードマシンタイプの引き上げ） |
| 1,000〜 | gateway の水平スケール・マルチノード化を検討（下記参照） |

Go の goroutine モデル上、1 Pod で数千 WebSocket 接続は処理可能。
ボトルネックになるのは接続数よりも、ゲームアクション処理時の battle サーバへの HTTP 往復。

#### gateway を水平スケールする場合

gateway 自体は、`playerID → WS 接続` の in-memory session map を各 Pod が個別に持つ設計を前提にしている。マッチ成立通知は Cloud Pub/Sub の competing consumers パターンで「自 Pod がその playerID の接続を持っていれば push、なければ無視」と扱えるため、単純な gateway の水平スケール（複数 Pod ロードバランス）自体はマッチメイキング経路には影響しない。

一方、対戦中のゲームセッション（ConnectionHub / GameRelay 等）は同一ゲームの両プレイヤーが同一 Pod に接続している前提の箇所が残る。これを解決するには、

1. **セッション状態の外部化** — ゲームルーム情報を外部ストアに移し、どの Pod からでも参照可能にする
2. **ルーム単位ルーティング** — gateway を StatefulSet + Headless Service にし、Ingress または別のレイヤーで room ID ベースのルーティングを行う

といった変更が必要になる。どちらもアプリケーション側の変更を伴うため、必要になった時点で検討する。

#### マルチノード化

現状は単一ノード構成であり、ノード障害がクラスタ全体の停止につながる SPOF になっている。ユーザー数が増え SLO の引き上げが必要になった段階で、ノード数を増やしつつ Pod Anti-Affinity によるゾーン分散を設定する。

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
