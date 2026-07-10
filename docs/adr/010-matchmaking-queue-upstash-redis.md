# ADR-010: マッチメイキングキューを Upstash Redis に移行

## ステータス

Superseded by [ADR-012](012-matchmaking-pubsub.md) (2026-04-11)。旧ステータス: Proposed (2026-04-08)

本 ADR で採用した Upstash Redis Sorted Set によるキュー永続化の決定は ADR-012 に継承されている。ADR-012 ではさらに、リポジトリ分割（[ADR-011](011-repository-split.md)）に伴うサービス間の非同期通知チャネルとして **Google Cloud Pub/Sub (Exactly-Once Delivery 有効)** を採用し、キュー層 (Upstash Redis) とメッセージング層 (Cloud Pub/Sub) を分離したハイブリッド設計としている。今後は ADR-012 を参照のこと。

## 結論

インメモリ管理によるデバッグ・障害調査・計測の課題を解消するため、**Upstash Redis** (サーバーレス Redis) をマッチメイキングキューのバックエンドとして導入する。キュー状態は `redis-cli ZRANGE` で即座に確認でき、事後調査・滞留計測が可能になる。コストは Free 枠で十分（スケールしても月額 $1 以下）、コード変更は Redis 実装の追加と注入先変更に閉じる。

## 背景・課題

マッチメイキングキューは現在 Gateway プロセスのインメモリ map で管理されている。
機能上は動作するが、以下の課題がある:

- **デバッグ困難**: キューの現在の状態を確認するには、専用のデバッグエンドポイントかログの解析が必要。DB なら SELECT 一発で済む
- **障害調査困難**: Gateway クラッシュ後に「なぜマッチしなかったか」「誰がキューにいたか」を事後調査できない
- **キュー滞留の計測不可**: マッチ待ち時間の集計やモニタリングができない
- **Gateway 再起動時にキューが消滅**: 再起動中にキューに入っていたプレイヤーは WS 切断→再接続で再キューイングする必要がある

マッチメイキングキューは FIFO（先着順ペアリング）であり、一時的・揮発的なデータを扱う。
RDB に永続化するのは設計として不適切（マッチメイキングキューは DB のやるべき仕事ではない）。

## 詳細

### Upstash Redis の評価

| 観点 | 評価 |
|------|------|
| コスト | Free 枠: 10,000 commands/日。Pay-as-you-go: $0.2/100k commands。マッチメイキングの規模では月額 $0 〜 $1 以下 |
| 運用 | フルマネージド SaaS。インフラ構築不要。接続 URL を環境変数に設定するだけ |
| プロトコル | 標準 Redis プロトコル互換。`go-redis/v9` でそのまま接続可能 |
| ベンダーロック | 標準プロトコルのため、接続先を変えるだけで別の Redis (Valkey, ElastiCache 等) に移行可能 |
| リスク | Free 枠の日次上限超過時はリクエスト拒否（サイレント失敗ではない）。SLA は Pro プラン以上で 99.99% |

### Redis データ構造

```
matchmaking:queue        — Sorted Set (score = joinedAt unix millis)
matchmaking:deck:{pid}   — String (deck_id)
```

- `ZADD matchmaking:queue <timestamp_ms> <playerID>` でエンキュー
- `ZPOPMIN matchmaking:queue 2` で先着2名をアトミックにデキュー
- `DEL matchmaking:deck:{pid}` でデッキ情報をクリーンアップ
- `ZREM matchmaking:queue <playerID>` でキャンセル

Sorted Set を使うのは、FIFO 順序の保証と `ZREM` による O(log N) の個別キャンセルのため。
List (`LPUSH`/`RPOP`) では途中要素の削除が O(N) になる。

### Gateway コード変更

既存の `MatchmakingQueue` インターフェース (`Join`, `Leave`, `GetWaiting`, `Remove`, `Count`, `IsQueued`) をそのまま Redis 実装に差し替える。

```go
// repository/redis_matchmaking_queue.go
type RedisMatchmakingQueue struct {
    client *redis.Client
}
```

ローカル開発 (`make run-local`) では従来のインメモリ実装を継続使用。
切り替えは `cmd/main/main.go` と `cmd/local/main.go` で注入先を変えるだけ。

### 環境変数

```
UPSTASH_REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379
```

### フォールバック

Redis 接続障害時の挙動:

- `Join` 失敗 → クライアントに `matchmaking_error` を返す（リトライ可能）
- `GetWaiting` 失敗 → マッチングループがスキップされる（次のサイクルでリトライ）
- キューに入った状態で Redis が落ちても、WS 切断は起きないためゲーム中のプレイヤーには影響なし

## 不採用案

### PostgreSQL テーブル

```sql
CREATE TABLE matchmaking_queue (...);
SELECT ... ORDER BY joined_at LIMIT 2 FOR UPDATE SKIP LOCKED;
```

却下理由:

- 機能的には動作するが、揮発的なキューデータを RDB に持つのは設計として不適切
- マッチング成立のたびに DELETE が走る。RDB の使い方として違和感がある

### Cloudflare Queues

- $0.40/100万メッセージで安い
- 却下理由: consumer が Cloudflare Workers 限定。Gateway (Go) から直接 dequeue できず、アーキテクチャ変更が大きい

### Cloudflare Durable Objects

- 単一アクターモデルでキュー状態を保持
- 却下理由: Workers エコシステム前提。Go Gateway との統合コストが高い

### AWS SQS FIFO

- $0.35/100万リクエスト
- 却下理由: Google Cloud (GKE) 環境からクロスクラウドアクセスになる。レイテンシとネットワーク設定の複雑さ

### インメモリ現状維持

- メリット: 追加コスト $0、レイテンシ最小
- デメリット: デバッグ困難、障害調査不可、キュー滞留計測不可（上述の課題がすべて残る）
