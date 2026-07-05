# ADR-012: マッチメイキングのハイブリッド設計（Upstash Redis キュー + Cloud Pub/Sub Exactly-Once 通知）

## ステータス

Proposed (2026-04-11)

この ADR は [ADR-010](010-matchmaking-queue-upstash-redis.md) を置き換える。Sorted Set によるキュー永続化の決定を継承しつつ、サービス分割後の非同期通知チャネルとして Cloud Pub/Sub (Exactly-Once Delivery) を採用する。

## 結論

サービス分割後も async なマッチ結果をクライアントへ確実に届けるため、マッチメイキングのデータフローを以下の 2 層構成とする:

1. **キュー永続化**: Upstash Redis **Sorted Set** ([ADR-010](010-matchmaking-queue-upstash-redis.md) から継承)
2. **非同期通知**: **Google Cloud Pub/Sub (Exactly-Once Delivery 有効)**（新規）

Exactly-Once Delivery + matchId dedup + Matchmaking 側状態保持の三重構成により、マッチ成立通知のロストと重複をユーザー体験上意識させないレベルで抑える。通知は Cloud Monitoring・Dead Letter Topic など Google Cloud の運用基盤にそのまま載り、Gateway Pod の水平スケールにも競合コンシューマパターンで自動対応する。流量は無料枠に収まり、実質の追加コストは $0。

## 背景・課題

### ADR-010 の前提（キュー永続化）

当初、マッチメイキングキューは Gateway プロセスのインメモリ map で管理されていた。デバッグ困難・障害調査不可・キュー滞留計測不可・再起動時のキュー消滅といった課題があり、ADR-010 で **Upstash Redis の Sorted Set** をバックエンドとして採用することを決めた。

- `matchmaking:queue` という Sorted Set に `ZADD <joinedAt_ms> <playerID>` でエンキューし、`ZPOPMIN matchmaking:queue 2` で先着 2 名をアトミックにデキューする
- FIFO 順序保証と O(log N) の個別キャンセル (`ZREM`) を両立するため Sorted Set を採用
- RDB ではなく Redis を選んだのは、マッチメイキングキューが揮発的・一時的データであり、DB のやるべき仕事ではないと判断したため

この前提は本 ADR でもそのまま維持する。キュー格納層については再検討の余地はなく、Upstash Redis Sorted Set を継続する。

### サービス分割に伴う新しい課題

[ADR-011](011-repository-split.md) により、マッチメイキングは Gateway から独立した Go サービス (overload-party-matchmaking) として切り出されることになった。サービス分割により **同期 REST だけでは async なマッチ結果を返せない** という新しい問題が生まれている:

- プレイヤーがキューに入ってから実際にマッチが成立するまで、数秒〜数十秒の時間差がある
- Gateway はクライアントに WebSocket 経由でマッチ結果をプッシュする必要がある
- マッチメイキングサービスは「どの Gateway Pod がそのプレイヤーの WS 接続を保持しているか」を知らない。Gateway は水平スケールするため、Pod の割り当てはロードバランサ任せ
- したがって、マッチメイキングサービスが Gateway に「対して」同期 REST で push back する方法は成り立たない

非同期かつ多対多の通知チャネルが必要である。

## 制約

本 ADR では、非同期通知チャネルに **Exactly-Once 相当の到達保証** を求めることにした。これはサービス規模や可用性 SLA ではなく、**ユーザー体験** を優先する判断である:

- マッチ成立通知が重複 push されるとクライアントが「マッチ結果を 2 回受け取る」状態になり、画面遷移の二重発火・battle 接続の二重化といった不具合につながる
- マッチ成立通知がロストすると、プレイヤーは「マッチしたはずなのにロビーに戻らない」状態になり、タイムアウト待ちを強いられる
- 規模が小さくてもこれらは実際に発生するため、規模を理由に at-most-once / at-least-once を許容する判断はしない

つまり通知チャネル選定の軸は、コストでも Google Cloud 内に閉じることでもなく、**Exactly-Once 到達保証をインフラ層で得られるか** である。

## 詳細

キュー格納先の Redis とメッセージングの Pub/Sub でインフラ系統が 2 つに分かれるが、次の理由で許容する:

- 通知チャネルは Exactly-Once を優先するため、Upstash Redis Pub/Sub (at-most-once) や Redis Streams (at-least-once + app 冪等性) では要件を満たさない
- キュー格納先を Cloud SQL や Firestore に寄せて系統を 1 つに揃える案は、「揮発データを RDB に置かない」という ADR-010 の基本方針と矛盾するため論外
- 通知側を Google Cloud に寄せるために Memorystore + Cloud Pub/Sub に統一する案は検討したが、Memorystore Basic 1GB で月 $35 以上の追加コストがかかる。同じ Redis であれば Upstash Free tier のほうが安く、系統数はどちらにせよ「キュー + メッセージング」の 2 つなので統一効果も限定的

### 全体フロー

```
  Client              Gateway (Go)            Matchmaking (Go)         Upstash Redis        Cloud Pub/Sub
    |                      |                         |                       |                    |
    | -- WS: match_request >                         |                       |                    |
    |                      | -- REST POST /enqueue ->|                       |                    |
    |                      |                         | -- ZADD queue ------->|                    |
    |                      | <-- 202 Accepted -------|                       |                    |
    |                      |                         |                       |                    |
    |                      |                         | (loop) ZPOPMIN 2 ---->|                    |
    |                      |                         | match logic           |                    |
    |                      |                         | -- Publish match_made ---------------------|
    |                      |                         |                       |                    |
    |                      | <== Pull (EO) ========== matchmaking-events-gateway subscription ====|
    |                      | matchId dedup check                              |                    |
    | <-- WS: match_found -|                         |                       |                    |
    |                      | -- ack -----------------------------------------------------> (Pub/Sub)
```

1. Client → Gateway (WS) で `match_request` を送る
2. Gateway → Matchmaking サービスに REST でリクエストを転送し、Matchmaking が `ZADD matchmaking:queue <joinedAt_ms> <playerID>` を発行してキューに積む。Gateway はクライアントに 202 系のレスポンスを返すだけで、マッチ結果はまだ返さない
3. Matchmaking のマッチングループが `ZPOPMIN matchmaking:queue 2` で先着 2 名を取り出し、マッチング処理（デッキ取得・バトルサーバへの対戦生成依頼など）を実行する
4. マッチ成立後、Matchmaking は Cloud Pub/Sub のトピック `matchmaking-events` に `match_made` メッセージを publish する
5. すべての Gateway Pod は共通の pull subscription `matchmaking-events-gateway` を購読しており、**competing consumers パターン**で 1 メッセージは 1 Pod にのみ配送される。メッセージを受信した Pod は `playerID → *websocket.Conn` の in-memory session map を参照し、自 Pod が該当プレイヤーの接続を保持していれば `match_found` を WS で push、保持していなければ無視する
6. 処理完了後、Pod は Cloud Pub/Sub に対して ack response を返す。Exactly-Once Delivery が有効な subscription では、ack は成功/失敗が明示的に返るため、ack が失敗した場合は再配送される

### Topic / Subscription 設計

| リソース | 名前 | 種別 | 備考 |
|---|---|---|---|
| Topic | `matchmaking-events` | | Matchmaking サービスが publish する唯一のトピック |
| Subscription | `matchmaking-events-gateway` | pull, Exactly-Once 有効 | Gateway Pod 群が競合して pull する |
| Dead Letter Topic | `matchmaking-events-dlq` | | 最大配信回数を超えたメッセージの退避先（ネイティブサポート） |

設定方針:

- **Exactly-Once Delivery**: subscription で有効化する。ack response が成功/失敗で明示的に返るため、publisher/subscriber クライアント両方でハンドリングを実装する
- **ack deadline**: 10 秒。WS push の想定レイテンシに対して十分な余裕があり、かつ失敗時の再配送も早い
- **ordering key**: 設定しない。マッチ成立イベントは独立しており、グローバルな順序保証は不要。将来プレイヤー単位の順序保証が欲しくなった場合は `playerID` を ordering key に追加する余地を残す
- **競合コンシューマ**: 複数 Gateway Pod が同じ subscription を pull することで、1 メッセージは 1 Pod にしか配送されない。これは Redis Streams の consumer group と同等の挙動
- **メッセージ保持期間**: デフォルト 7 日。必要に応じて最大 31 日まで拡張できる
- **Dead Letter Topic**: 最大配信回数（デフォルト 5 回）を超えたメッセージは DLQ に退避する。監視アラートを DLQ の深さに紐付ける

### メッセージペイロード

```json
{
  "type": "match_made",
  "matchId": "mch_01HW8...",
  "players": ["player_a", "player_b"],
  "battleServerUrl": "wss://battle.overloadparty.keyandnotes.com/ws/mch_01HW8..."
}
```

- JSON シリアライズ、camelCase
- `players` には両プレイヤーの ID を含め、受信した Gateway Pod は in-memory session map でローカルに保持しているプレイヤーだけを対象に push する
- 将来 rating ベースのマッチングや private match を追加する際は `type` を増やして対応する（例: `match_cancelled`, `room_invited`）

### 冗長な冪等性（保険）

Cloud Pub/Sub の Exactly-Once Delivery は **subscription 内での重複配送を抑制する** 機能であり、subscriber 側で ack 前にクラッシュした場合などには別 Pod へ再配送されうる。これは Exactly-Once Delivery の範疇外であり、end-to-end の Exactly-Once を達成するには **アプリケーション側の冪等性** を併用する必要がある。

本 ADR では以下を保険として実装する:

- **matchId ベースの dedup**: Gateway は受信した `match_made` イベントの `matchId` を in-memory map でトラッキングし、同一 `matchId` に対する WS push は 1 回のみとする。Pod 再起動後にマップがリセットされることは許容する（Pub/Sub の ack 後は再配送されないため、再起動前の処理済みメッセージが再度届くことは基本的にない）
- **Matchmaking 側の状態保持**: Matchmaking サービスは `ZPOPMIN` でキューから取り出したプレイヤー情報を **成立確定まで in-memory で保持** する。Cloud Pub/Sub への publish が確定した後も、クライアント側の ACK（ロビー遷移シグナル）が一定時間内に返ってこなければ再キューイングできる状態を維持する。これは Matchmaking サービス自身のクラッシュ時の再処理パスにも必要であり、Exactly-Once Delivery があっても依然として必要な仕組みである

### IAM / 認証

GKE Workload Identity を用いて Pod に Google Cloud サービスアカウントを紐付ける。

| コンポーネント | ロール | スコープ |
|---|---|---|
| Matchmaking サービス | `roles/pubsub.publisher` | topic `matchmaking-events` |
| Gateway サービス | `roles/pubsub.subscriber` | subscription `matchmaking-events-gateway` |

- Upstash Redis への接続は ADR-010 の方針どおり、接続 URL を Kubernetes Secret 経由で注入する
- Cloud Pub/Sub へのアクセスは Google Cloud サービスアカウントに閉じ、API キーは発行しない

### トレードオフ

- **2 系統運用**: Upstash Redis + Cloud Pub/Sub の両方を運用対象に加える。シークレット管理・監視ダッシュボード・障害対応フローが二重化する。ただし Upstash は ADR-010 時点から既に SaaS 依存しており、Cloud Pub/Sub は既存 Google Cloud の運用基盤に載るため、追加の運用コストは限定的
- **プロトコル / クライアントライブラリの二重化**: キューは `go-redis/v9`、通知は `cloud.google.com/go/pubsub` と、別のクライアントライブラリを扱う。抽象化レイヤーを薄く保ち、それぞれの library の流儀に合わせる
- **Exactly-Once Delivery の ack response ハンドリング**: Cloud Pub/Sub の Exactly-Once を有効にすると ack が成功/失敗を返すため、publisher / subscriber 双方でレスポンス検証を明示的に実装する必要がある
- **Matchmaking のステートフル性**: 成立確定前のプレイヤー情報を in-memory で一時保持するため、Matchmaking Pod のクラッシュ時はそのプレイヤーがキューに戻らない可能性がある。Matchmaking は当面シングル Pod 運用とし、将来はリース (`SETNX` + TTL) でフェイルオーバ対応する
- **Upstash のリージョン**: Upstash Redis は asia-northeast1 に完全に同居するわけではなく、多少のレイテンシが発生しうる。マッチメイキング規模では問題にならない範囲だが、通知側 (Cloud Pub/Sub) が Google Cloud 内に閉じているのとは非対称である

## 不採用案

### 案1: Upstash Redis Pub/Sub (at-most-once)

`PUBLISH` / `SUBSCRIBE` コマンドによる fire-and-forget 配信。

却下理由:

- at-most-once のためメッセージロストが発生しうる（publish 時に購読者が存在しない、瞬断中、Pod 再起動中など）
- 「マッチしたのにロビーに戻らない」というユーザー体験上最悪のケースを発生させる
- Exactly-Once を必要とする本 ADR の要件を満たさない

### 案2: Upstash Redis Streams + Consumer Groups (at-least-once + アプリ冪等性)

`XADD` / `XREADGROUP` / `XACK` による consumer group パターン。

却下理由:

- at-least-once までは達成できるが、Exactly-Once はインフラ層で表現できず、重複排除のロジックをアプリケーション側で厚く実装することになる
- dedup のためのトラッキング状態（matchId → 処理済みフラグ）を Redis もしくは in-memory で持つ必要があり、Matchmaking 側・Gateway 側の両方で冪等性実装が重くなる
- 同じ冪等性を実装するにしても、Cloud Pub/Sub の Exactly-Once Delivery を基盤として matchId dedup を「保険」として実装するほうが、開発コスト・可読性・運用負荷の面で有利

### 案3: Cloud Pub/Sub + Memorystore (Google Cloud 一系統)

通知を Cloud Pub/Sub、キュー永続化を Memorystore (Redis) に統一する案。

却下理由:

- Exactly-Once と Google Cloud ネイティブ統合の両方を満たすが、**Memorystore Basic 1GB で月額 $35 以上の固定費** が発生する
- ADR-010 の「Upstash Free tier で収まる規模」を考えると追加コストの割に得るものが少ない
- キュー + メッセージングで結局 2 系統になる点は Upstash + Cloud Pub/Sub 案と変わらないため、「Google Cloud 一系統に揃える」という統一感の利点は限定的
- 同じ Redis を使うなら Upstash のほうが安く、Google Cloud から外れる程度のトレードオフは受け入れられる

### 案4: Cloud Pub/Sub + Cloud SQL

キュー永続化を Cloud SQL に寄せる案。

却下理由:

- マッチメイキングキューは揮発的・一時的データであり、RDB に持つのは設計として不適切（ADR-010 の却下理由を継承）
- 既存 Cloud SQL インスタンスがあるためコストは限定的だが、設計観点で論外

### 案5: Managed Service for Apache Kafka

Google Cloud マネージド Kafka。

却下理由:

- Exactly-Once Delivery・Consumer Group・順序保証など機能的には要件を満たすが、最小クラスタでも月 $100+ かかる
- マッチメイキング通知の流量（1 日 100 マッチ × 数百バイト程度）に対してオーバースペック
- Gateway / Matchmaking 共に Kafka クライアントを持ち込むことになり、学習コスト・運用コストが高い

### 案6: QStash (Upstash)

Upstash が提供する HTTP ベースのメッセージングサービス。

却下理由:

- HTTP push 型のため、リアルタイム通知に向かない（数百 ms 〜秒単位の遅延が想定される）
- consumer group 相当の「複数 Pod で競合受信する」モデルがなく、Gateway 水平スケールとの相性が悪い

### 案7: Gateway ↔ Matchmaking 直接 push back (REST / WS)

Matchmaking が Gateway の内部 API を直接呼ぶ、あるいは常時 WebSocket で接続する案。

却下理由:

- Gateway は水平スケールするため、「どの Pod がそのプレイヤーの WS 接続を保持しているか」を Matchmaking は知らない。追跡するには playerID → Pod IP のマップを別ストアに持つ必要があり、Pub/Sub と同じかそれ以上の複雑さになる
- Pod 間の直接 push は GKE 内の Pod IP 動的性・NAT の制約もあり脆い
- サーバ間 WS を張る案は再接続・backoff・heartbeat のロジックが二重化する
