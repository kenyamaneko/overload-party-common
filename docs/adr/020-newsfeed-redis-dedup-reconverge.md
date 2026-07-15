# ADR-020: newsfeed に dedup + 要約責務を戻す（Upstash Redis 導入）

## ステータス

Proposed (2026-04-21)

この ADR は [ADR-019](019-newsfeed-publisher-boundary.md) を置き換える。ADR-019 で news に移した要約・タグ付け責務を newsfeed に戻し、冪等性確保の手段を news 側の `ON CONFLICT DO NOTHING` 単体から、**newsfeed 側の Upstash Redis dedup（事前）＋ news 側 `ON CONFLICT`（二次防御）** のハイブリッドに変更する。

## 結論

news の責務過多を解消するため、newsfeed の責務を以下に再定義する:

1. RSS 取得
2. ULID 採番
3. **Upstash Redis による source_url ベース dedup**（事前予約、TTL 30 日）
4. **Vertex AI による日本語要約 + タグ付け**（dedup 通過分のみ）
5. `news-article-collected` への publish

news の責務は ADR-019 時点の「インジェスト以降」をそのまま維持する。これにより news の責務が「配信」（記事永続化 + 校閲 + 配信 + 翻訳管理）に収まり、加工（要約・タグ）は newsfeed 側に閉じる。同一記事の再要約が 30 日間発生しなくなって Vertex AI の重複呼び出しが削減され、Cloud Run Job は fetch → transform → publish の単一パイプライン（状態は外部 KV に分離）という batch ジョブとして自然な形になる。Upstash Redis / Secret Manager の採用パターンは matchmaking と揃い、news 側は現 `ArticleCollectedEvent` がそのまま使えるため改修不要。

## 背景・課題

ADR-019 では newsfeed を「fetch + publish」の thin な Cloud Run Job に縮退させ、AI 要約・タグ付け・DB 永続化・校閲 UI・配信を news サービスに集約した。実装着手後に次の問題が顕在化した。

### news の責務過多

ADR-019 の責務移譲により news は以下を一手に抱えることになる:

- Pub/Sub subscriber による記事受信
- Vertex AI 要約生成
- タグ付け
- 校閲ワークフロー（承認・却下・翻訳編集）
- 管理 UI (HTMX)
- 公開 API + キャッシュ
- 将来の翻訳（en 手動追加、将来的な自動化）

これは「ニュース配信サービス」というより「ニュース加工プラットフォーム」であり、単一リポジトリで持つ責務としては広すぎる。

### ADR-019 の本当の争点は「AI」ではなく「state」

ADR-019 が要約を news 側に寄せた本来の理由は、「newsfeed で dedup を行うと state が必要になり、thin ジョブの位置づけから外れる」だった。AI 呼び出し自体が嫌だったのではなく、重複再要約を防ぐための state の置き場がなかったことが争点。

ADR-014（クロスサービス SELECT 禁止）と「newsfeed の RDB 所有廃止」により newsfeed は自 DB を持たず、dedup を RDB に戻すと再度スキーマを作る羽目になる。この回避策として「要約を news 側に寄せ、重複再要約コストは news の `ON CONFLICT` で吸収」という構成を取っていた。

### 軽量 KV で state 問題を解消できる

要約を newsfeed に戻す条件は「dedup state の置き場」。RDB スキーマを作るのは過剰だが、**短命・TTL 前提・単純 KV** の dedup には Upstash Redis が適合する。[ADR-010](010-matchmaking-queue-upstash-redis.md) / [ADR-012](012-matchmaking-pubsub.md) で matchmaking が既に Upstash Redis を採用済みであり、プラットフォームとして前例がある。

## 不採用案

### newsfeed 専用 PostgreSQL スキーマで dedup

却下。ADR-014 の「1 スキーマ 1 所有者」を尊重すると `source_url` UNIQUE 1 テーブルのためにマイグレーション運用・Cloud SQL ユーザー払い出し・Testcontainers まで抱える。短命 + TTL が本質の dedup に RDB は重すぎる。

### newsfeed → summarizer (新規サービス) → news の 3 段構成

却下。Cloud Run サービスが 1 つ増えて運用対象が広がる。MVP の翻訳 1 言語規模では疎結合の益が見合わない。将来 en 自動化が必要になった時点で newsfeed から summarizer を切り出すリファクタは、イベント境界を 1 本追加するだけで済む。

### news が bulk exists API を提供し、newsfeed が publish 前に問い合わせる

却下。newsfeed が news API の可用性に依存する新しい結合が発生する（2h 周期バッチ中に news がデプロイ中だと取りこぼす等）。dedup 状態は newsfeed の関心事であり news の所有データではないため、API 経由で問い合わせる設計自体が筋悪い。

### Cloud Firestore で dedup を実装

却下。[ADR-017](017-game-config-firestore.md) は Firestore を「サービス横断 KV 共有状態」の置き場として正当化しており、newsfeed 専用・短命 KV は ADR の動機とズレる。同じ KV 用途なら既に運用前例のある Upstash Redis の方がプラットフォームとして一貫する。

### ADR-019 のまま news に要約を寄せ続ける

却下。news が「配信」を超えて「加工プラットフォーム」に拡大する。ADR-019 本来の争点は「newsfeed に state を持たせたくない」であって「newsfeed に AI を持たせたくない」ではなかった。Upstash Redis により state を最小限で解消できるなら ADR-019 の前提が崩れる。
