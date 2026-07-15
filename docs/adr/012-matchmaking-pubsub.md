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

この通知チャネルには、規模の小ささを理由に妥協せず、マッチ成立通知の重複・ロストをユーザーに意識させない Exactly-Once 相当の到達保証をインフラ層で確保することを求める。重複は画面遷移の二重発火や battle 接続の二重化を、ロストは「マッチしたのにロビーに戻らない」タイムアウト待ちを招くためで、通知チャネル選定の軸はコストや Google Cloud 内に閉じることではなく、この到達保証をインフラ層で得られるかに置く。

## 不採用案

### Upstash Redis Pub/Sub (at-most-once)

`PUBLISH` / `SUBSCRIBE` コマンドによる fire-and-forget 配信。

却下理由:

- at-most-once のためメッセージロストが発生しうる（publish 時に購読者が存在しない、瞬断中、Pod 再起動中など）
- 「マッチしたのにロビーに戻らない」というユーザー体験上最悪のケースを発生させる
- Exactly-Once を必要とする本 ADR の要件を満たさない

### Upstash Redis Streams + Consumer Groups (at-least-once + アプリ冪等性)

`XADD` / `XREADGROUP` / `XACK` による consumer group パターン。

却下理由:

- at-least-once までは達成できるが、Exactly-Once はインフラ層で表現できず、重複排除のロジックをアプリケーション側で厚く実装することになる
- dedup のためのトラッキング状態（matchId → 処理済みフラグ）を Redis もしくは in-memory で持つ必要があり、Matchmaking 側・Gateway 側の両方で冪等性実装が重くなる
- 同じ冪等性を実装するにしても、Cloud Pub/Sub の Exactly-Once Delivery を基盤として matchId dedup を「保険」として実装するほうが、開発コスト・可読性・運用負荷の面で有利

### Cloud Pub/Sub + Memorystore (Google Cloud 一系統)

通知を Cloud Pub/Sub、キュー永続化を Memorystore (Redis) に統一する案。

却下理由:

- Exactly-Once と Google Cloud ネイティブ統合の両方を満たすが、**Memorystore Basic 1GB で月額 $35 以上の固定費** が発生する
- ADR-010 の「Upstash Free tier で収まる規模」を考えると追加コストの割に得るものが少ない
- キュー + メッセージングで結局 2 系統になる点は Upstash + Cloud Pub/Sub 案と変わらないため、「Google Cloud 一系統に揃える」という統一感の利点は限定的
- 同じ Redis を使うなら Upstash のほうが安く、Google Cloud から外れる程度のトレードオフは受け入れられる

### Cloud Pub/Sub + Cloud SQL

キュー永続化を Cloud SQL に寄せる案。

却下理由:

- マッチメイキングキューは揮発的・一時的データであり、RDB に持つのは設計として不適切（ADR-010 の却下理由を継承）
- 既存 Cloud SQL インスタンスがあるためコストは限定的だが、設計観点で論外

### Managed Service for Apache Kafka

Google Cloud マネージド Kafka。

却下理由:

- Exactly-Once Delivery・Consumer Group・順序保証など機能的には要件を満たすが、最小クラスタでも月 $100+ かかる
- マッチメイキング通知の流量（1 日 100 マッチ × 数百バイト程度）に対してオーバースペック
- Gateway / Matchmaking 共に Kafka クライアントを持ち込むことになり、学習コスト・運用コストが高い

### QStash (Upstash)

Upstash が提供する HTTP ベースのメッセージングサービス。

却下理由:

- HTTP push 型のため、リアルタイム通知に向かない（数百 ms 〜秒単位の遅延が想定される）
- consumer group 相当の「複数 Pod で競合受信する」モデルがなく、Gateway 水平スケールとの相性が悪い

### Gateway ↔ Matchmaking 直接 push back (REST / WS)

Matchmaking が Gateway の内部 API を直接呼ぶ、あるいは常時 WebSocket で接続する案。

却下理由:

- Gateway は水平スケールするため、「どの Pod がそのプレイヤーの WS 接続を保持しているか」を Matchmaking は知らない。追跡するには playerID → Pod IP のマップを別ストアに持つ必要があり、Pub/Sub と同じかそれ以上の複雑さになる
- Pod 間の直接 push は GKE 内の Pod IP 動的性・NAT の制約もあり脆い
- サーバ間 WS を張る案は再接続・backoff・heartbeat のロジックが二重化する
