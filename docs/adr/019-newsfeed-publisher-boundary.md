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

## 不採用案

### newsfeed に要約を残し、`translations` 付きで publish

newsfeed が Vertex AI で ja 要約を作り、`translations: [{lang: "ja", title, summary, body}]` を含むイベントを publish する。ADR-011 の当初責務分担に最も近い。

却下理由:

- newsfeed が Vertex AI quota / deadline で失敗すると publish できない。「fetch + publish」という外部境界片側の薄い仕事が Vertex AI 可用性に引きずられる
- news 側は en 翻訳を管理 UI で手動追加する動線を持つ。ja を newsfeed 生成・en を news 生成とすると非対称で、校閲 UI の内部実装が不揃いになる
- 要約は「記事コンテンツの最終形を作る」仕事であり、コンテンツの SSoT である news が所有する方が責務境界と整合する

### newsfeed → summarizer (新規サービス) → news の 3 段構成

`article-collected` (raw) → summarizer サービス → `article-summarized` (enriched) → news。

却下理由:

- サービスが 1 つ増える。MVP は翻訳 1 言語のみで、疎結合の益が薄い
- 将来 en の自動生成や別モデル併走が必要になった場合、news の ingest から summarizer を切り出すリファクタは本 ADR のイベント境界を一時的に 2 本に割るだけで済む。今時点で先取りするコストが見合わない

### newsfeed に GCS アーカイブを残す

将来の監査・再生成に備えて raw JSON を GCS に保管し続ける。

却下理由:

- 現状 `raw_gcs_path` を下流で参照しているコードはない。実需のない副作用を newsfeed に残すと「fetch + publish」という責務が再び広がる
- archival が必要になった時点で、所有サービス (news) が自スキーマに合わせて archive する設計の方が自然。newsfeed に archival を残すと news 側の障害復旧時にも newsfeed の GCS を読み書きする形になり、責務境界を再度横断する

### 現状維持（newsfeed が DB 直接書き込み）

却下理由:

- 校閲 UI / 状態遷移 / 多言語対応の要件が newsfeed に流れ込み、バッチジョブが肥大化する
- 「1 スキーマ 1 所有者」原則（ADR-014）が newsfeed にも適用できる余地を放棄することになる
