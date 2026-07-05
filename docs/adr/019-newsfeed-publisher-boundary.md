# ADR-019: newsfeed の責務を「取得と publish」に限定

## ステータス

Superseded by [ADR-020](020-newsfeed-redis-dedup-reconverge.md) (2026-04-21)。作成日: 2026-04-21

本 ADR は採用直後に [ADR-020](020-newsfeed-redis-dedup-reconverge.md) で置き換えられた。ADR-019 は「newsfeed に state を持たせない」ために要約責務を news に寄せたが、その結果 news が「配信」を超えて「ニュース加工プラットフォーム」化する問題が顕在化した。Upstash Redis を dedup state の置き場に採用すれば ADR-019 の前提が崩れるため、ADR-020 で要約・タグ付けを newsfeed に戻している。履歴として本 ADR は残すが、**現行方針は ADR-020 が SSoT**。

この ADR は [ADR-011](011-repository-split.md) の「newsfeed: クラウドニュース収集・配信」の配信部分を、[ADR-014](014-db-schema-split-per-service.md) の `newsfeed` スキーマ所有権と合わせて上書きする。

## 結論

責務過多になった newsfeed から配信・校閲責務を独立サービス `news` (Go) として切り出し、newsfeed の責務を **RSS 取得 + `news-article-collected` トピックへの publish** に限定する。newsfeed は RSS と Pub/Sub の 2 境界だけを持つ thin なジョブになり、Vertex AI quota / Cloud SQL 可用性の影響を受けなくなる。`news` スキーマへの書き込みは news サービスのみとなって校閲済みテキストを newsfeed の再実行が壊す経路が消え、newsfeed からは `psycopg2-binary` / `google-cloud-storage` / `google-cloud-aiplatform` 依存と Cloud SQL / GCS IAM が消える。news は Go + Clean Architecture + 管理 UI 付きのサービスとして構築されるため、多言語 / 状態遷移 / 運用者向け UI を扱える。

## 背景・課題

[ADR-011](011-repository-split.md) では newsfeed を「クラウドニュース収集・配信」の一体サービスとして位置づけた。[ADR-014](014-db-schema-split-per-service.md) では `newsfeed` スキーマ（`news_articles` 1 テーブル）を newsfeed が所有すると定めた。

その後の実装で newsfeed（Python Cloud Run Job）は以下を抱え込むことになった:

- RSS フィード取得
- ULID 採番
- GCS への生 JSON アーカイブ
- Vertex AI (Gemini) による日本語要約 + タグ抽出
- PostgreSQL への直接書き込み
- Gateway は DB を直接 SELECT して配信

この構造には次の問題が出てきた。

- **配信側の要件増**: 記事一覧・詳細・多言語対応・運用者による校閲が必要な機能として見え始め、Gateway の直読み + newsfeed 書き込みでは対応しきれない。校閲 UI、status 状態遷移、翻訳の正規化は Go サービスとして独立に構築する方が自然
- **責務過多**: newsfeed が外部 RSS 境界・GCS 境界・Vertex AI 境界・DB 境界の 4 つを単一バッチで扱っており、障害面が広い。特に Vertex AI 失敗時に「fetch は成功したが DB に書けない」という責務違反的な詰まり方をする
- **所有権の曖昧化**: 校閲済みの記事行を newsfeed の再実行が上書きしうる構造。現状は `source_url` UNIQUE + `ON CONFLICT DO NOTHING` で守られているが、「1 スキーマ 1 所有者」原則（ADR-014）が newsfeed には未適用

## 詳細

### 責務の再分配

| 機能 | 旧 (本 ADR 以前) | 新 |
|---|---|---|
| RSS フィード取得 | newsfeed | newsfeed（継続） |
| ULID 採番 | newsfeed | newsfeed（継続） |
| タグ付け | newsfeed (Vertex AI) | **news**（要約と同一プロセスで付与） |
| AI 要約生成 | newsfeed (Vertex AI) | **news** |
| 生 JSON アーカイブ | newsfeed (GCS) | **廃止** |
| DB 永続化 | newsfeed (`newsfeed.news_articles`) | **news** (`news.news_articles` + `news.news_article_translations`) |
| 記事配信 REST | gateway 直読み | **news** |
| 校閲・管理 UI | — | **news** |

### イベント契約 (`news-article-collected`)

newsfeed → news の単一 Pub/Sub トピック経由。ペイロード:

```json
{
  "article_id": "01H...",
  "source": "aws | google-cloud | azure | oci | other",
  "source_url": "https://...",
  "source_published_at": "2026-04-21T...",
  "title": "...",
  "body": "..."
}
```

- 翻訳フィールド (`translations`) は持たせない。ja 要約は news の ingest で Vertex AI を呼んで生成する
- タグも持たせない。`tags` は news 側で要約と同時に Vertex AI で付与する（newsfeed は RSS の `<category>` を解釈しない）
- `title` は RSS の原題をそのまま載せる（翻訳しない、整形しない）
- `body` は RSS の本文を **HTML を除去したプレーンテキスト** として載せる（`content:encoded` 優先、無ければ `description`）。news の管理 UI は `body` をテキストエリアで運用者が読む・編集するため、HTML 構造を残すと XSS リスクと可読性低下の両方が発生する
- `source_published_at` は RSS から取得できない場合 null

### スキーマ所有権

| スキーマ | 所有 | 主な対象テーブル |
|---|---|---|
| `news` | news | `news_articles`, `news_article_translations` |

[ADR-014](014-db-schema-split-per-service.md) 本体・補遺にある `newsfeed` スキーマ（newsfeed 所有、`news_articles` 1 テーブル）は**本 ADR により廃止**。スキーマ名が `newsfeed` から `news` に変わり、所有サービスも newsfeed から news に移る。`news.news_article_translations` は言語別の正規化のために新設される（詳細は news リポの `docs/DATA_DESIGN.md`）。

### 冪等性

- `article_id` は newsfeed が ULID で採番し、news 側 PK として使われる
- newsfeed はローカル dedup を持たない。同一 `source_url` を複数回 publish しうる
- 重複排除は news 側の `ON CONFLICT DO NOTHING`（親記事・翻訳の両方）で吸収する

### パッケージ境界

[ADR-012](012-matchmaking-pubsub.md) の「Pub/Sub イベントは送信側が型を所有」原則に照らすと、`ArticleCollectedEvent` の型パッケージは本来 newsfeed 側にあるべき。ただし newsfeed は Python であり Go パッケージを consume しない構成のため、契約型の物理配置による実害は薄い。**本 ADR では物理配置の移動は行わず、`packages/api-news` に置いたまま**とする。将来 Go クライアントから publish する別サービスが出てきた場合に、newsfeed リポへの移管または common への切り出しを再検討する。

なお `packages/newsfeed-constants`（[ADR-015](015-package-split.md)）は newsfeed 所有のまま据え置き。newsfeed は DB を持たなくなるため Testcontainers（[ADR-016](016-repository-testing-testcontainers.md)）の適用対象からも外れる（理由が「スキーマ未固定」から「DB 責務の消失」へ変わる）。

### トレードオフ

- **news への Vertex AI 依存移植**: news の ingest 経路に外部 API 呼び出しが入る。失敗モード（IAM / quota / deadline）が subscribe 経路に追加される。Pub/Sub の ACK/NACK 方針（再送可能な障害は NACK、deterministic エラーは ACK）で吸収する
- **GCS アーカイブの喪失**: RSS 元サイトから消えた記事の再生成手段がなくなる。現時点で実需がないため受容し、archival が必要になれば news 側で後付けする
- **イベント契約の破壊的変更**: 直近 news で実装された `ArticleCollectedEvent.translations[]` 形式は、本 ADR により `title` + `body` 直載せ形式へ変更する。news の ingest 実装と `packages/api-news` の型定義に手を入れる
- **再実行時の Vertex AI コスト**: newsfeed にローカル dedup がない分、news 側が `DO NOTHING` で弾く前に Vertex AI 呼び出しが走る。`source_url` ベースの事前チェックを news の ingest に入れることで緩和可能だが、MVP 規模（2 時間周期・1 回数十件）では無視できる
- **Pub/Sub 型パッケージの物理配置**: ADR-012 の「送信側所有」原則に対して、`packages/api-news` が受信側 (news) に置かれ続ける。newsfeed が Python で Go パッケージを consume しないため実害は薄いが、将来 Go publisher が増えたタイミングで再検討する

## 不採用案

### 案1: newsfeed に要約を残し、`translations` 付きで publish

newsfeed が Vertex AI で ja 要約を作り、`translations: [{lang: "ja", title, summary, body}]` を含むイベントを publish する。ADR-011 の当初責務分担に最も近い。

却下理由:

- newsfeed が Vertex AI quota / deadline で失敗すると publish できない。「fetch + publish」という外部境界片側の薄い仕事が Vertex AI 可用性に引きずられる
- news 側は en 翻訳を管理 UI で手動追加する動線を持つ。ja を newsfeed 生成・en を news 生成とすると非対称で、校閲 UI の内部実装が不揃いになる
- 要約は「記事コンテンツの最終形を作る」仕事であり、コンテンツの SSoT である news が所有する方が責務境界と整合する

### 案2: newsfeed → summarizer (新規サービス) → news の 3 段構成

`article-collected` (raw) → summarizer サービス → `article-summarized` (enriched) → news。

却下理由:

- サービスが 1 つ増える。MVP は翻訳 1 言語のみで、疎結合の益が薄い
- 将来 en の自動生成や別モデル併走が必要になった場合、news の ingest から summarizer を切り出すリファクタは本 ADR のイベント境界を一時的に 2 本に割るだけで済む。今時点で先取りするコストが見合わない

### 案3: newsfeed に GCS アーカイブを残す

将来の監査・再生成に備えて raw JSON を GCS に保管し続ける。

却下理由:

- 現状 `raw_gcs_path` を下流で参照しているコードはない。実需のない副作用を newsfeed に残すと「fetch + publish」という責務が再び広がる
- archival が必要になった時点で、所有サービス (news) が自スキーマに合わせて archive する設計の方が自然。newsfeed に archival を残すと news 側の障害復旧時にも newsfeed の GCS を読み書きする形になり、責務境界を再度横断する

### 案4: 現状維持（newsfeed が DB 直接書き込み）

却下理由:

- 校閲 UI / 状態遷移 / 多言語対応の要件が newsfeed に流れ込み、バッチジョブが肥大化する
- 「1 スキーマ 1 所有者」原則（ADR-014）が newsfeed にも適用できる余地を放棄することになる
