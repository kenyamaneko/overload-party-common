# モニタリング・ログ方針

監視の構成をどう決めたか、その理由は [ADR-063](../adr/063-cloud-run-monitoring-and-alerting.md) にある。本ドキュメントは現在の構成をまとめる。

---

## 概要

Cloud Run + Cloud SQL 構成に対する、ログ・メトリクス・アラートの方針。
分散トレーシングは現時点では不要（サービス構成がシンプルなため）。

---

## 構造化ログ

### 採用技術

いずれの言語も、Cloud Logging が `severity` を解釈できる JSON を標準出力に出す。`severity` で絞るアラートはこれが成り立つことを前提にしている。

| 言語 | 実装 | 対象 |
|------|------|------|
| Go | `log/slog` (Go 1.21+ 標準) | account / analytics / card / gateway / matchmaking / news / scenario / shop / support |
| C# | Cloud Logging 互換の JSON フォーマッタ | battle |
| Python | JSON フォーマッタ | newsfeed |

**Go で `log/slog` を選んだ理由:**
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

Cloud Run 上:
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

- Cloud Run 上のコンテナが標準出力に JSON を出力すれば、Cloud Logging が自動収集・解析
- 追加のエージェントやサイドカーは不要
- ログは稼働している環境のプロジェクトに直接集まる。プロジェクトをまたぐ転送は無い
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

## メトリクス

### 標準メトリクス

アプリ側の実装なしで収集される。アラートの条件はここから組む。

| メトリクス | 内容 |
|-----------|------|
| 要求数（応答コードのクラス別） | 5xx 応答の発生 |
| 応答時間 | 要求を処理し終えるまでの時間の分布 |
| ログ件数（`severity` 別） | ERROR ログの発生 |
| ジョブの試行結果 | Cloud Run ジョブの実行の成否 |
| コンテナの CPU / メモリ | インスタンスのリソース使用率 |
| Cloud SQL CPU / メモリ / 接続数 | DB の基本メトリクス |

### カスタムメトリクス

いずれも未実装で、アプリからメトリクスを出す仕組みも入っていない。残すか取り下げるかは [common#179](https://github.com/kenyamaneko/overload-party-common/issues/179) で判断する。

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

---

## アラート

アラートポリシーの定義は overload-party-infra が持ち、dev / stg / prod の 3 環境すべてに置く。

### Cloud Run サービス

Cloud Run サービス 9 本（account / battle / card / gateway / matchmaking / news / scenario / shop / support）に当てる。

| アラート | 条件 | 対象 |
|---------|------|------|
| 5xx 応答が発生した | 集計期間内の 5xx 応答が許容件数を超えた | 9 本すべて |
| 応答が遅い | 応答時間の 95 パーセンタイルが上限を超えた | gateway を除く 8 本 |
| ERROR ログが出た | 集計期間内の `severity=ERROR` のログが許容件数を超えた | 9 本すべて |

gateway に応答時間のアラートを当てないのは、WebSocket 接続では応答時間が接続の継続時間そのものになり、応答の遅さを表さないため。

ERROR ログのアラートは、どの環境でも単発では発報しない。5xx を返す障害は ERROR ログにも現れるため、両方を単発で発報させると 1 件の障害で通知が 2 通届く。要求の失敗は 5xx のアラートが受け持つ。

許容件数は環境ごとに変える。dev と stg は動作確認やテストでわざとエラーを起こすため、prod より緩めてある。

### Cloud Run ジョブ

| アラート | 条件 | 対象 |
|---------|------|------|
| 実行が失敗した | 失敗した試行が 1 件でもある | newsfeed のジョブ |

ジョブは要求を受けず動作確認のエラーが紛れ込まないため、環境を問わず 1 件の失敗で発報する。ジョブはサービスの一覧から導けないので、ジョブを増やしたときは監視対象の一覧に足す作業が要る。

### 予算アラート

環境ごとのプロジェクトに月次の予算を置き、50 / 80 / 100 % を超えたところで通知する。超過しても使用は自動で止めない（請求データの反映に数時間の遅れがあり、止めても超過を防ぎきれないため）。

### 現在のアラートで拾えないもの

- **デプロイの失敗と、稼働できるリビジョンが 1 本も無い状態**：起動に失敗したコンテナは要求を受け取らないため 5xx が出ず、起動 1 回あたりの ERROR ログも許容件数に届かない。今後の扱いは [ADR-063](../adr/063-cloud-run-monitoring-and-alerting.md) の残課題にある
- **analytics**：Cloud Functions で動いており、Cloud Run のメトリクスに乗らない
- **db-migrate ジョブ**：CI/CD が起動するジョブで、監視の要否が未決
- **Cloud Run ジョブの ERROR ログ**：ログ件数のメトリクスがジョブを対象に含めるかを確認できておらず、当てていない。実行そのものは成功してログにだけエラーが出る場合は気づけない

### 通知チャネル

メール通知が現行。Slack の通知チャンネル ID を受け取る設定はあるが、未設定のため送られない。Slack へ送るには Cloud Monitoring のコンソールで通知チャンネルを作り、その ID を各環境に設定する（OAuth の承認を伴うため Terraform では作成できない）。

---

## Cloud SQL Insights

現時点では有効にしていない。

- Terraform で `insights_config` を有効化するだけ
- クエリの実行計画・レイテンシ・ロック待ちを可視化
- 追加コスト: ごく小さい（ストレージのみ）

```hcl
insights_config {
  query_insights_enabled  = true
  query_plans_per_minute  = 5
  query_string_length     = 1024
  record_application_tags = true
  record_client_address   = false
}
```

---

## 分散トレーシング

**現時点では不採用。**

理由:
- サービス構成がシンプル
- 対戦処理はインメモリで完結し、外部サービス呼び出しが少ない
- 構造化ログで大半の問題は診断可能

将来必要になった場合:
- Cloud Trace + OpenTelemetry SDK で導入可能
- slog ベースの設計なら、後から trace ID をログに付与しやすい

---

## コスト見積もり

| サービス | 無料枠 | 想定コスト |
|---------|-------|-----------|
| Cloud Logging | 50 GB/月 | 無料枠内（ゲームサーバーのログ量は少ない） |
| Cloud Monitoring（標準メトリクス） | 基本無料 | 無料 |
| Cloud Monitoring アラートポリシー（1 環境あたり 27 本） | 基本無料 | 無料 |
| Cloud SQL Insights | ストレージのみ | 月数十円程度（有効化した場合） |

**追加コスト: ほぼゼロ**（Google Cloud の無料枠で収まる規模）

> 最終更新: 2026-08-03
