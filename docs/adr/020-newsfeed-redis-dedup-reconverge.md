# ADR-020: newsfeed に dedup + 要約責務を戻す（Upstash Redis 導入）

**Status:** Proposed
**Date:** 2026-04-21

> このADRは [ADR-019](019-newsfeed-publisher-boundary.md) を置き換えます。ADR-019 で news に移した要約・タグ付け責務を newsfeed に戻し、冪等性確保の手段を news 側の `ON CONFLICT DO NOTHING` 単体から、**newsfeed 側の Upstash Redis dedup（事前）＋ news 側 `ON CONFLICT`（二次防御）** のハイブリッドに変更します。

---

## 背景

ADR-019 では newsfeed を「fetch + publish」の thin な Cloud Run Job に縮退させ、AI 要約・タグ付け・DB 永続化・校閲 UI・配信を news サービスに集約した。実装着手後に次の問題が顕在化した。

### 1. news の責務過多

ADR-019 の責務移譲により news は以下を一手に抱えることになる:

- Pub/Sub subscriber による記事受信
- Vertex AI 要約生成
- タグ付け
- 校閲ワークフロー（承認・却下・翻訳編集）
- 管理 UI (HTMX)
- 公開 API + キャッシュ
- 将来の翻訳（en 手動追加、将来的な自動化）

これは「ニュース配信サービス」というより「ニュース加工プラットフォーム」であり、単一リポジトリで持つ責務としては広すぎる。

### 2. ADR-019 の本当の争点は「AI」ではなく「state」

ADR-019 が要約を news 側に寄せた本来の理由は、「newsfeed で dedup を行うと state が必要になり、thin ジョブの位置づけから外れる」だった。AI 呼び出し自体が嫌だったのではなく、重複再要約を防ぐための state の置き場がなかったことが争点。

ADR-014（クロスサービス SELECT 禁止）と「newsfeed の RDB 所有廃止」により newsfeed は自 DB を持たず、dedup を RDB に戻すと再度スキーマを作る羽目になる。この回避策として「要約を news 側に寄せ、重複再要約コストは news の `ON CONFLICT` で吸収」という構成を取っていた。

### 3. 軽量 KV で state 問題を解消できる

要約を newsfeed に戻す条件は「dedup state の置き場」。RDB スキーマを作るのは過剰だが、**短命・TTL 前提・単純 KV** の dedup には Upstash Redis が適合する。[ADR-010](010-matchmaking-queue-upstash-redis.md) / [ADR-012](012-matchmaking-pubsub.md) で matchmaking が既に Upstash Redis を採用済みであり、プラットフォームとして前例がある。

---

## 決定

newsfeed の責務を以下に再定義する:

1. RSS 取得
2. ULID 採番
3. **Upstash Redis による source_url ベース dedup**（事前予約、TTL 30 日）
4. **Vertex AI による日本語要約 + タグ付け**（dedup 通過分のみ）
5. `news-article-collected` への publish

news の責務は ADR-019 時点の「インジェスト以降」をそのまま維持する。

### 責務の再分配

| 機能 | 旧 (ADR-019) | 新 (本 ADR) |
|---|---|---|
| RSS 取得 | newsfeed | newsfeed（継続） |
| dedup 判定 | news (`ON CONFLICT DO NOTHING`) | **newsfeed (Upstash Redis `SETNX`) + news (`ON CONFLICT`、二次防御)** |
| ULID 採番 | newsfeed | newsfeed（継続） |
| AI 要約生成 | news | **newsfeed (Vertex AI)** |
| タグ付け | news | **newsfeed (Vertex AI、要約と同一プロセス)** |
| 生 JSON アーカイブ | 廃止 | 廃止（継続） |
| DB 永続化 | news | news（変更なし） |
| 記事配信 REST | news | news（変更なし） |
| 校閲・管理 UI | news | news（変更なし） |

### イベント契約の復帰

ADR-019 で `title` + `body` 直載せへ変更するとしていたイベント契約は**本 ADR で撤回**する。現 news 実装の `ArticleCollectedEvent` 形式に戻す:

```json
{
  "article_id": "01H...",
  "source": "aws | google-cloud | azure | oci | other",
  "source_url": "https://...",
  "source_published_at": "2026-04-21T...",
  "tags": ["..."],
  "translations": [
    {
      "lang": "ja",
      "title": "...",
      "summary": "...",
      "body": "..."
    }
  ]
}
```

- `translations` は MVP 期間中 ja 1 件固定（en は news 管理 UI で手動追加、ADR-019 時代と不変）
- `body` は newsfeed が RSS `content:encoded` から HTML を除去したプレーンテキスト
- `summary` は newsfeed の Vertex AI 出力
- `tags` は newsfeed の Vertex AI 出力（語彙: `compute / network / storage / database / ai / security / serverless / container / devops / pricing`）

**news 側コードは無変更でよい**: 現在の `ArticleCollectedEvent`（`translations[]` + `tags` を含む）が本 ADR の契約と一致する。ADR-019 で述べた news 破壊的変更は不要。

### Upstash Redis 統合

matchmaking ([ADR-010](010-matchmaking-queue-upstash-redis.md) / [ADR-012](012-matchmaking-pubsub.md)) の運用パターンを踏襲する。

#### Upstash データベース

環境ごとに別インスタンス:

| 環境 | Upstash DB 名 |
|---|---|
| dev | `overload-party-dev-newsfeed` |
| stg | `overload-party-stg-newsfeed` |
| prod | `overload-party-prod-newsfeed` |

#### Secret Manager

本番環境では GCP Secret Manager から取得する:

| シークレット ID | 内容 |
|---|---|
| `newsfeed-upstash-redis-endpoint` | `host:port` 形式の Upstash エンドポイント |
| `newsfeed-upstash-redis-password` | Upstash `default` ユーザーのパスワード |

newsfeed Cloud Run Job のサービスアカウントに `roles/secretmanager.secretAccessor` を付与する。

ローカル開発では `APP_ENV=local` で `UPSTASH_REDIS_URL=redis://localhost:6379/0` を直接読み、Secret Manager 呼び出しをスキップする（matchmaking と同一の分岐）。

#### dedup キー仕様

| 項目 | 値 |
|---|---|
| キー | `newsfeed:seen:{source_url}` |
| 値 | `"1"` |
| TTL | `EX 2592000` (30 日) |
| 操作 | `SET key "1" NX EX 2592000` による check+mark のアトミック実行 |

#### パイプラインと失敗時ロールバック

```
fetch → items
for item in items:
    article_id = ULID()
    key = f"newsfeed:seen:{item.source_url}"

    reserved = redis.set(key, "1", nx=True, ex=2592000)
    if not reserved:
        duplicates += 1
        continue

    try:
        summary_result = summarizer.summarize(item.title, item.body)
        event = build_event(article_id, item, summary_result)
        publisher.publish(event)
    except Exception:
        redis.delete(key)  # 再試行可能性のためマーカーを解放
        errors += 1
        continue

    published += 1

if errors > 0:
    raise PublishError(...)  # exit 1
```

- `SETNX` 成功 → Vertex AI・publish に進む
- `SETNX` 失敗（既に seen）→ スキップ（duplicates カウント）
- Vertex AI または publish 失敗 → `DEL` でマーカー解放 → 次周期で再試行される
- プロセスクラッシュで `DEL` が走らなかった場合はマーカーが 30d TTL で自動解放される（永続損失なし）

### Vertex AI モデル

- モデル: **Gemini 2.5 Flash**（ADR-019 以前の `gemini-2.0-flash-001` を最新系へ更新）
- 出力: JSON（`{"summary": "...", "tags": [...]}`）を `response_mime_type="application/json"` で強制
- タグ語彙: 旧 summarizer を継承

---

## 検討した代替案

### 案 1: newsfeed 専用 PostgreSQL スキーマで dedup

却下。ADR-014 の「1 スキーマ 1 所有者」を尊重すると `source_url` UNIQUE 1 テーブルのためにマイグレーション運用・Cloud SQL ユーザー払い出し・Testcontainers まで抱える。短命 + TTL が本質の dedup に RDB は重すぎる。

### 案 2: newsfeed → summarizer (新規サービス) → news の 3 段構成

却下。Cloud Run サービスが 1 つ増えて運用対象が広がる。MVP の翻訳 1 言語規模では疎結合の益が見合わない。将来 en 自動化が必要になった時点で newsfeed から summarizer を切り出すリファクタは、イベント境界を 1 本追加するだけで済む。

### 案 3: news が bulk exists API を提供し、newsfeed が publish 前に問い合わせる

却下。newsfeed が news API の可用性に依存する新しい結合が発生する（2h 周期バッチ中に news がデプロイ中だと取りこぼす等）。dedup 状態は newsfeed の関心事であり news の所有データではないため、API 経由で問い合わせる設計自体が筋悪い。

### 案 4: Cloud Firestore で dedup を実装

却下。[ADR-017](017-game-config-firestore.md) は Firestore を「サービス横断 KV 共有状態」の置き場として正当化しており、newsfeed 専用・短命 KV は ADR の動機とズレる。同じ KV 用途なら既に運用前例のある Upstash Redis の方がプラットフォームとして一貫する。

### 案 5: ADR-019 のまま news に要約を寄せ続ける

却下。news が「配信」を超えて「加工プラットフォーム」に拡大する。ADR-019 本来の争点は「newsfeed に state を持たせたくない」であって「newsfeed に AI を持たせたくない」ではなかった。Upstash Redis により state を最小限で解消できるなら ADR-019 の前提が崩れる。

---

## 結果

### 期待される効果

- **news の責務が「配信」に収まる**: 記事永続化 + 校閲 + 配信 + 翻訳管理のみ。加工（要約・タグ）は newsfeed 側に閉じる
- **Vertex AI 重複呼び出しの削減**: 同一記事の再要約が 30d 期間内は発生しない。ADR-019 想定では news 側 `ON CONFLICT` で弾く前に毎回 Vertex AI が走る構造だった
- **Cloud Run Job が batch ジョブとして自然な形**: fetch → transform → publish の単一パイプライン、状態は外部 KV に分離
- **プラットフォーム一貫性**: Upstash Redis / Secret Manager 採用パターンが matchmaking と揃う
- **news 側の改修不要**: 現 `ArticleCollectedEvent` がそのまま使える

### トレードオフ

- **newsfeed の依存が再び増える**: `redis-py` + `google-cloud-aiplatform` + `google-cloud-secret-manager`。ADR-019 で削った 2 種を戻し、さらに Redis + Secret Manager が追加される
- **Upstash Redis インスタンスが 3 つ増える**: dev/stg/prod 別に newsfeed 用 DB を立てる。Free tier 内（2h × 数十件 = 日 1k commands 未満、Free 上限 10k/日）
- **Secret Manager シークレットが 2 つ増える**: `newsfeed-upstash-redis-endpoint` / `newsfeed-upstash-redis-password`。infra 側で投入・IAM 付与が必要
- **マーカー滞留リスク**: クラッシュで `DEL` が走らない場合、最長 30d は該当 URL が再処理されない。永続損失ではなく TTL で自動解放される
- **ADR-019 実装を巻き戻すコスト**: commit 86c7413 で削除した summarizer.py / test_summarizer.py を再投入する必要がある（new: Redis dedup と Secret Manager も追加で実装）

### 移行ステップ

1. **overload-party-infra**:
   - Pub/Sub トピック `news-article-collected` の存在確認
   - Upstash Redis DB を 3 環境分新設（`overload-party-{dev,stg,prod}-newsfeed`）
   - Secret Manager に `newsfeed-upstash-redis-endpoint` / `newsfeed-upstash-redis-password` を投入
   - newsfeed Cloud Run Job のサービスアカウントに以下を付与:
     - `roles/secretmanager.secretAccessor`
     - `roles/aiplatform.user`（Vertex AI）
     - `roles/pubsub.publisher`
2. **overload-party-newsfeed**:
   - `summarizer.py` / `test_summarizer.py` を再投入（モデルを Gemini 2.5 Flash に更新）
   - `dedup.py` / `test_dedup.py` を新設（Redis `SETNX` ラッパー）
   - `secret_manager.py` を新設（Secret Manager からの取得ヘルパー）
   - `config.py` に `APP_ENV` 分岐（local は env var 直読み、それ以外は Secret Manager 経由）
   - `model.py` と `publisher.py` のイベント形式を `translations[]` + `tags` 構造に戻す
   - `runner.py` を dedup → summarize → publish 構造に書き換え（失敗時 `DEL` ロールバック）
   - `requirements.txt` に `redis` / `google-cloud-aiplatform` / `google-cloud-secret-manager` を追加
   - `docker-compose.yml` + `Makefile` で local Valkey を用意
   - `docs/ARCHITECTURE.md` / `README.md` を本 ADR に整合させる
3. **overload-party-news**: 変更なし（現 `ArticleCollectedEvent` 形式と一致するため）

---

## 関連 ADR

- **[ADR-019](019-newsfeed-publisher-boundary.md)**: 本 ADR により **Superseded**。newsfeed を fetch + publish 専任に縮退する決定は、dedup state の置き場問題を news 側の責務過多で代償したため本 ADR で巻き戻す
- **[ADR-010](010-matchmaking-queue-upstash-redis.md)**: Upstash Redis 採用の前例。本 ADR も接続パターン・Secret Manager 運用を踏襲
- **[ADR-011](011-repository-split.md)**: リポジトリ分割。本 ADR では「newsfeed: クラウドニュース収集・配信」の「加工」部分を newsfeed に戻す方向で再解釈する
- **[ADR-012](012-matchmaking-pubsub.md)**: 「Pub/Sub イベントは送信側が型を所有」の原則。`packages/api-news` が news リポに置かれ続ける経緯は ADR-019 §パッケージ境界を継承
- **[ADR-014](014-db-schema-split-per-service.md)**: クロスサービス SELECT 禁止の原則。news スキーマを newsfeed から直接読む案は本原則により却下した
- **[ADR-017](017-game-config-firestore.md)**: サービス横断 KV の Firestore 採用。本 ADR の dedup は専用・短命 KV のため Firestore ではなく Redis を採用
