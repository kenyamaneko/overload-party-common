# ADR-046: 横断 ID 採番方式の策定 (UUID v7 を新基準とする)

## ステータス

Proposed (2026-06-05)

## コンテキスト

各リポの ID 採番方式が用途を明示しないまま実装ごとに分岐している。横断 audit (2026-06-04 battle 全体レビュー) で次の状況が明らかになった:

- **battle.games.game_id**: `db/schema.sql` と `data/openapi.yaml` で `VARCHAR(26) -- ULID` と宣言しているが、実装は `Guid.NewGuid().ToString("N")` で 32 文字 hex を生成。SSoT と実体が乖離しており、本番 INSERT は列幅超過で失敗する状態
- **account.players.player_id**: `UUID` 型 + `gen_random_uuid()` (UUID v4)
- **news.news_articles.article_id**: `VARCHAR(26)` ULID (newsfeed が `oklog/ulid/v2` で採番)
- **matchmaking match_id**: `oklog/ulid/v2` で採番 (Postgres スキーマは持たない)
- **card / shop / scenario のマスタデータ ID**: `VARCHAR(10-50)` の人間可読 slug (`SH-0001`, `she_ep1`, `pack_xxx` 等)
- **account / scenario の Pub/Sub event_id**: `UUID` (UUID v4)

問題は ULID と UUID v4 が「採用基準なしに混ざっている」点であり、ULID か UUID かそれ自体ではない。新規テーブルを追加するたびに「何で採番するか」が個別判断になり、宣言と実装の乖離 (battle で発生) が再発する余地が残っている。

## 決定

ID 採番方式を用途別に 4 分類し、新基準を以下に統一する。

| 用途 | 方式 | DB 列型 | 採番場所 |
|------|------|---------|----------|
| マスタデータ ID | 人間可読 slug | `VARCHAR(N)` | 設計者が手で命名 |
| 対外露出する長寿命エンティティ ID | UUID v4 | `UUID` | アプリ側採番 |
| 内部ログ / セッション / 履歴系 ID | UUID v7 | `UUID` | アプリ側採番 |
| Pub/Sub `event_id` (重複排除キー) | UUID v4 | `UUID` | publisher アプリ採番 |

slug を除く全 ID をアプリ側採番に統一する (DB default に採番させない)。理由は後述。

### なぜこの分類か

**マスタデータ ID に slug を使う理由**: カード ID やパック ID は domain knowledge そのもので、ログ・運用調査・テストフィクスチャで人間が直接読み書きする。`SH-0001` のように陣営・連番が表記に乗ることが価値で、ランダム ID に置き換える理由がない。

**対外露出する長寿命 ID に UUID v4 を残す理由**: `player_id` のように URL / API レスポンスで外部に晒される ID は **生成時刻を漏らしたくない**。ULID / UUID v7 は上位 48 bit がミリ秒タイムスタンプなので、ID 単体からアカウント作成時刻が逆引きでき、enumeration 攻撃の手掛かりにもなる。長寿命エンティティは件数が小さく append-heavy でもないため、UUID v4 のランダム挿入による B-tree 性能劣化も実害が出ない。

**内部ログ系に UUID v7 を採用する理由**: `game_id` / 試合履歴 / セッション系の表は append-heavy で件数が時間に比例して伸びる。UUID v4 を PK に使うとランダム挿入で B-tree が断片化し、ページ分割・random I/O・WAL 書き込み量が増えて insert throughput と index サイズの両方が劣化する。UUID v7 は時系列順に append されるので右端ページに集中して書き込まれ、insert は実質 sequential I/O に近づき index も密に埋まる。あわせて以下の運用上の恩恵が乗る:

- 時間範囲クエリを ID 範囲で書ける (`WHERE id BETWEEN <t1 の v7> AND <t2 の v7>`) のでパーティション pruning やアーカイブ削除が ID 列だけで成立する
- cursor pagination が `id > $last_id` の一発で書ける ((created_at, id) の複合 cursor が不要)
- 障害調査で ID から発生時刻が即座に分かる

**ULID ではなく UUID v7 を新基準にする理由**: ULID と UUID v7 は技術的なメリット (時系列順 + ランダムサフィックス + 128 bit) が同一だが、UUID v7 は RFC 9562 (2024) で標準化された UUID の一バリアントであり、既存の `UUID` 型・既存のライブラリ・既存のツール (psql, pg_dump, datadog, etc.) がそのまま使える。ULID は表現が独立 (Crockford Base32 26 文字) で `UUID` 型に乗らず、列型を `VARCHAR(26)` で持つことになる。新基準としては「標準形式の上で時系列性を得る」UUID v7 の方が後方影響が小さい。

**Pub/Sub event_id に UUID v4 を選ぶ理由**: event_id は subscriber 側の重複排除キーとしてのみ使われ、時系列性は別途 publish 時刻フィールドが担う。ランダムで十分。

**採番をアプリ側に統一する理由**: 採番点を DB default (`gen_random_uuid()` / PG18 `uuidv7()`) に置く案も検討したが、slug を除く全 ID をアプリ側採番に統一する。ID を「永続化の副作用」ではなく「アプリが所有するドメインの値」として扱えることが理由:

- INSERT 前に ID が確定するので、集約を組み立ててから FK を先に埋めて一括 INSERT する・event_id を outbox に先発番する・idempotency キーを先行発行する、といった流れが自然に書ける。`game_id` を FK に持つ試合履歴を同一トランザクションで組む battle がまさにこれに該当する
- 特定 DB の採番機能 (PG18 `uuidv7()` 等) に依存しないので、ストアや Postgres バージョンに非依存
- generator を注入してテストで ID を固定でき、決定的なテストが書ける

アプリ側採番の代償は schema 宣言とコードの二重管理である (battle の `game_id` で宣言 ULID / 実体 GUID hex の乖離として顕在化した)。これは手運用の注意に依存せず、(1) ID 列を `VARCHAR(N)` でなく native `UUID` 型にして列幅 drift という故障モードそのものを消し、(2) 生成した ID を実列に通す検証を CI に置くことで構造的に塞ぐ。この前提のもとで二重管理の代償を許容する。

### 既存 ID の扱い

| 対象 | 対応 | 理由 |
|------|------|------|
| account `player_id` (UUID v4) | 据え置き | 型・バリアントは新基準に整合 (対外露出は UUID v4)。採番点は `gen_random_uuid()` の DB default のままだが、既存稼働分の移行リスク > 採番点統一の便益のため据え置き。新規テーブルはアプリ側採番に従う |
| news `article_id` (ULID) | 据え置き | 性能特性は UUID v7 と同等、cross-repo 参照あり、移行リスク > 統一の便益 |
| matchmaking `match_id` (ULID) | 据え置き | 同上 |
| battle `game_id` (宣言 ULID / 実体 GUID hex) | **UUID v7 へ移行** | SSoT と実体が乖離しており、修正が必要。本 ADR を契機に新基準で揃える |
| 既存 Pub/Sub `event_id` (UUID v4) | 据え置き | 既に新基準に整合 |
| **新規追加するテーブル** | 本 ADR の表に従う | — |

「ULID は据え置き、新規は UUID v7」が中途半端に見えるが、性能特性が同等な以上、既存 ULID を UUID v7 に統一する正味の便益はライブラリ・schema・FK の書き換えコストを下回る。横断統一は新規テーブルが追加されるたびに徐々に達成される。

## 検討した代替案

### 案 A: 横断 ULID 統一

全リポの長寿命・履歴系 ID を ULID に揃える。

- メリット: 既存 ULID 採用箇所と整合する
- デメリット: RFC 標準を捨てる選択になる。既存の `UUID` 型を `VARCHAR(26)` に書き換えるコストが大きく、account / 既存 UUID v4 系のテーブルを全て移行する必要がある
- 不採用理由: UUID v7 が同じ性能特性を標準型のまま提供するため、ULID を新基準にする必然性がない

### 案 B: 横断 UUID v4 統一

全 ID を UUID v4 に統一する (現状の account 方式に揃える)。

- メリット: 単一方式で運用がシンプル。account / Pub/Sub event_id は移行不要
- デメリット: append-heavy なテーブル (`game_events`, 将来追加されうるログ系) で B-tree fragmentation を抱え込む。時系列ソート・ID 範囲クエリ・運用調査の便益も失う
- 不採用理由: 高頻度 insert テーブルで性能・運用観測性が劣化する

### 案 C: battle のみ実体に合わせて `VARCHAR(32)` hex に SSoT を書き換え (最小修正)

横断方針を策定せず、battle の schema / openapi / docs を「ULID」から「opaque hex 32」に訂正する。

- メリット: 修正コストが最小
- デメリット: 新規テーブル追加のたびに「何で採番するか」が個別判断になり、本 ADR が解こうとしている根本問題が残る
- 不採用理由: SSoT を策定する好機を逃すと、宣言と実装の乖離 (battle で発生したもの) が再発する

### 案 D: 対外露出 ID を DB default 採番にする

`player_id` 等の対外露出 ID を `gen_random_uuid()` の DB default で採番する (本 ADR 初版の案)。

- メリット: 採番点が schema に一元化され、宣言と実装の乖離が起きない
- デメリット: INSERT 前に ID を持てないため、集約の事前組み立て・event_id の先発番・idempotency キーの先行発行ができない。採番が特定 DB 機能に縛られる
- 不採用理由: event_id のように INSERT 前発番が必須の用途がある以上アプリ採番はどのみち残る。採番点を用途ごとに DB / アプリに分けるより、native `UUID` 型 + CI 検証で乖離を塞いだ上でアプリ側に統一する方が一貫し、上記の設計上の利得も得られる

## 影響範囲

### battle (本 ADR 採択と同時に修正)

- `db/schema.sql`: `game_id VARCHAR(26) -- ULID` を `game_id UUID` に変更
- `data/openapi.yaml`: `gameID` description の「ULID」表記を「UUID v7」に修正
- `docs/DATA_DESIGN.md`: 「ULID」表記を「UUID v7」に修正
- `src/OverloadParty.Battle.Engine/GameEngine.cs:50`: `Guid.NewGuid().ToString("N")` を `Guid.CreateVersion7()` に置換。battle は net10 ターゲットなので .NET 標準 API で v7 を採番でき、サードパーティライブラリは不要。あわせて canonical 形式 (ハイフン有り) で永続化する (現状の `"N"` 書式 = ハイフン無し 32 hex をやめる)
- `db/schema.sql:65-72`, `:76-81`, `:85-109`, `:114-122`, `:126-134` の `game_id VARCHAR(26)` 全箇所を `UUID` に変更 (FK 参照含む)
- 既存テストでの `[..26]` truncate を除去

### account / news / matchmaking / card / shop / scenario / その他

- 現時点での変更なし
- 新規テーブル追加・新規 ID 採番点を追加するときに本 ADR の分類表に従う

### 横断ルール

- ID 列は native `UUID` 型で宣言する (`VARCHAR(N)` で持たない)。列幅 drift という故障モード (battle で発生) を型レベルで消すため
- 採番点を持つサービスは、採番した ID を実 schema の ID 列へ INSERT して round-trip する統合テストを 1 本持つ。採番方式と列宣言の乖離を CI で検出するため。横断 lint 等の共通ツール化は再発・規模拡大が見えた時点で判断する (現時点では過剰)
- ID 採番方式の SSoT は本 ADR とする。`rules/principles.md` への展開はしない (採番方式は rules に列挙するほどの運用ルールではなく、詳細は ADR で足りる)
- 新規テーブルの review チェックリストに ID 採番方式の確認項目を追加

## 移行計画

1. 本 ADR を Accepted に進める
2. battle で UUID v7 移行 PR を出す
   - 採番を `Guid.CreateVersion7()` (net10 標準) に置換
   - schema migration (本番未稼働 / データ件数が小さい前提)
   - openapi / DATA_DESIGN 同期
   - テスト更新 (採番 ID を実 `UUID` 列へ round-trip する統合テストを含む)
3. 他リポは新規テーブル追加時にのみ本基準を適用 (能動的な既存 ID 移行は行わない)

## 残課題

採番方式・採番点・ライブラリ・整合検証・明文化先はいずれも本 ADR 内で確定した。残るのは実施フォローアップのみ:

- battle の UUID v7 移行 PR (移行計画 step 2) と、採番 ID を実 `UUID` 列へ round-trip する統合テストの追加
