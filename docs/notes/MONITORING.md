# モニタリング・ログ方針

決定日: 2026-02-26

---

## 概要

GKE Autopilot + Cloud SQL 構成に対する、ログ・メトリクス・アラートの方針。
分散トレーシングは現時点では不要（サービス構成がシンプルなため）。

---

## 1. 構造化ログ

### 採用技術: `log/slog` (Go 1.21+ 標準)

**選定理由:**
- 外部依存なし（標準ライブラリ）
- JSON 出力 → Cloud Logging が自動解析（構造化フィールドでフィルタ・検索可能）
- config の `LOG_LEVEL` をそのまま活用可能（`slog.LevelVar` で動的変更）
- 既存の `log.Printf` からの移行が容易
- zap の超高パフォーマンスはこのプロジェクトでは不要

**zap を不採用にした理由:**
- パフォーマンス差がボトルネックにならない（ゲームロジックのほうが支配的）
- 外部依存が増える
- slog で十分な機能がある

### 出力形式

本番環境（GKE）:
```json
{
  "time": "2026-02-26T10:30:00Z",
  "level": "INFO",
  "msg": "player reconnected",
  "playerID": "abc123",
  "gameID": "game-456"
}
```

ローカル開発（`cmd/local`）:
```
2026/02/26 10:30:00 INFO player reconnected playerID=abc123 gameID=game-456
```

### Cloud Logging 連携

- GKE 上のコンテナが stdout に JSON を出力すれば、Cloud Logging が自動収集・解析
- 追加のエージェントやサイドカーは不要（GKE Autopilot のビルトイン機能）
- `severity` フィールドを Cloud Logging の標準に合わせることで、ログレベルフィルタが機能する

### severity マッピング

slog と Cloud Logging のログレベルマッピング:

| slog Level | Cloud Logging Severity | 用途 |
|------------|----------------------|------|
| `DEBUG` | `DEBUG` | 開発時のみ。対戦エンジン内部の詳細 |
| `INFO` | `INFO` | 通常の操作ログ（接続、対戦開始/終了、API呼び出し） |
| `WARN` | `WARNING` | 問題の予兆（再接続タイムアウト間近、キャッシュミス等） |
| `ERROR` | `ERROR` | 処理失敗（DB エラー、認証失敗、想定外のエラー） |

**注意:** Cloud Logging は `level` ではなく `severity` フィールドを見る。
slog の JSONHandler をカスタマイズして `level` → `severity` に変換する。

### ログに含めるべきコンテキスト

| フィールド | 場所 | 例 |
|-----------|------|-----|
| `playerID` | WS / API ハンドラ | `"abc-123"` |
| `gameID` | 対戦関連処理 | `"game-456"` |
| `requestID` | API ミドルウェア | UUID |
| `method` / `path` | API ミドルウェア | `"POST"` / `"/api/decks"` |
| `duration` | API ミドルウェア | `"120ms"` |
| `statusCode` | API ミドルウェア | `200` |
| `error` | エラーハンドリング | エラーメッセージ |

### LOG_LEVEL 運用

| 環境 | LOG_LEVEL | 理由 |
|------|-----------|------|
| local | `DEBUG` | 開発時は全ログ表示 |
| dev | `DEBUG` | デバッグ容易性優先 |
| stg | `INFO` | 本番に近い設定 |
| prod | `INFO` | 通常運用。問題発生時に `DEBUG` に動的変更可 |

---

## 2. メトリクス

### 採用技術: Prometheus client (`prometheus/client_golang`) + GKE Managed Prometheus

**構成:**
```
[Go App] → /metrics エンドポイント (Prometheus 形式)
              ↓
[GKE Managed Prometheus] → 自動スクレイプ (PodMonitoring CRD)
              ↓
[Cloud Monitoring] → ダッシュボード + アラート
```

**GKE Managed Prometheus (GMP) の利点:**
- GKE Autopilot で自動有効化済み（追加 Pod 不要）
- `PodMonitoring` CRD を作成するだけでスクレイプ開始
- Cloud Monitoring のダッシュボード・アラートと統合
- Grafana の自前運用が不要

### ビルトインメトリクス（GKE Autopilot 自動収集）

追加設定なしで利用可能:

| メトリクス | 内容 |
|-----------|------|
| Container CPU / Memory | Pod のリソース使用率 |
| Pod restart count | 異常再起動の検知 |
| HTTP latency (Ingress) | LB レイヤーのレスポンスタイム |
| Cloud SQL CPU / Memory / Connections | DB の基本メトリクス |

### カスタムメトリクス（アプリケーション側で実装）

| メトリクス名 | 種類 | ラベル | 用途 |
|-------------|------|--------|------|
| `game_matches_total` | Counter | `result` (win/loss/draw), `mode` (pvp/npc) | 対戦数の推移 |
| `game_match_duration_seconds` | Histogram | `mode` | 対戦時間の分布 |
| `matchmaking_queue_size` | Gauge | - | マッチメイキング待ちプレイヤー数 |
| `matchmaking_wait_seconds` | Histogram | - | マッチング待ち時間の分布 |
| `ws_connections_active` | Gauge | - | アクティブ WebSocket 接続数 |
| `ws_reconnections_total` | Counter | - | 再接続回数 |
| `api_request_duration_seconds` | Histogram | `method`, `path`, `status` | API レスポンスタイム |
| `npc_battles_total` | Counter | `difficulty` | NPC 戦の回数 |

### PodMonitoring CRD（K8s マニフェスト）

```yaml
apiVersion: monitoring.googleapis.com/v1
kind: PodMonitoring
metadata:
  name: api-server
spec:
  selector:
    matchLabels:
      app: api-server
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

---

## 3. アラート

### Cloud Monitoring アラートポリシー

| アラート | 条件 | 重要度 | 通知先 |
|---------|------|--------|--------|
| Pod 異常再起動 | restart count > 2 in 5min | High | メール / Slack |
| エラーレート急増 | 5xx rate > 5% for 5min | High | メール / Slack |
| Cloud SQL 高負荷 | CPU > 80% for 10min | Medium | メール |
| WS 接続断 | active connections = 0 (稼働時間帯) | High | メール / Slack |
| Cloud SQL 接続数超過 | connections > 80% of max | Medium | メール |

### 通知チャネル

- **Phase 1:** メール通知（設定が簡単）
- **Phase 2:** Slack Webhook 連携（リアルタイム性向上）

---

## 4. Cloud SQL Insights

- Terraform で `insights_config` を有効化するだけ
- クエリの実行計画・レイテンシ・ロック待ちを可視化
- 追加コスト: ごく小さい（ストレージのみ）

```hcl
# terraform/modules/cloudsql/main.tf に追加
insights_config {
  query_insights_enabled  = true
  query_plans_per_minute  = 5
  query_string_length     = 1024
  record_application_tags = true
  record_client_address   = false
}
```

---

## 5. 分散トレーシング

**現時点では不採用。**

理由:
- サービス構成がシンプル（API + WS + DB のみ）
- マイクロサービス間呼び出しがない
- 対戦処理はインメモリで完結し、外部サービス呼び出しが少ない
- 構造化ログ + カスタムメトリクスで大半の問題は診断可能

将来必要になった場合:
- Cloud Trace + OpenTelemetry SDK で導入可能
- slog ベースの設計なら、後から trace ID をログに付与しやすい

---

## 6. 導入ロードマップ

```
Phase 1: 構造化ログ (slog 導入 + JSON 出力)          ← 最優先
  - slog の初期化ヘルパー作成
  - 既存の log.Printf / fmt.Printf を slog に置換
  - Cloud Logging での動作確認

Phase 2: Cloud SQL Insights 有効化                   ← Terraform 1行
  - insights_config を Terraform に追加
  - apply して動作確認

Phase 3: カスタムメトリクス (Prometheus client)       ← アプリ実装
  - prometheus/client_golang 追加
  - /metrics エンドポイント追加
  - カスタムメトリクスの計装
  - PodMonitoring CRD 作成

Phase 4: ダッシュボード + アラート                    ← 運用整備
  - Cloud Monitoring ダッシュボード作成
  - アラートポリシー設定
  - 通知チャネル設定 (メール → Slack)
```

---

## コスト見積もり

| サービス | 無料枠 | 想定コスト |
|---------|-------|-----------|
| Cloud Logging | 50 GB/月 | 無料枠内（ゲームサーバーのログ量は少ない） |
| Cloud Monitoring | 基本無料 | 無料 |
| GKE Managed Prometheus | 最初の数百万サンプル無料 | 無料枠内 |
| Cloud SQL Insights | ストレージのみ | 月数十円程度 |
| Cloud Monitoring アラート | 基本無料 | 無料 |

**追加コスト: ほぼゼロ**（GCP の無料枠で収まる規模）
