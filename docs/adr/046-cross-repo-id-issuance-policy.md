# ADR-046: 横断 ID 採番方式の策定 (UUID v7 を新基準とする)

## ステータス

Proposed (2026-06-05)

## 結論

ID 採番方式が実装ごとに分岐して宣言と実装の乖離を生んでいるため、採番方式を用途別に 4 分類し、新基準を以下に統一する。

| 用途 | 方式 | DB 列型 | 採番場所 |
|------|------|---------|----------|
| マスタデータ ID | 人間可読 slug | `VARCHAR(N)` | 設計者が手で命名 |
| 対外露出する長寿命エンティティ ID | UUID v4 | `UUID` | アプリ側採番 |
| 内部ログ / セッション / 履歴系 ID | UUID v7 | `UUID` | アプリ側採番 |
| Pub/Sub `event_id` (重複排除キー) | UUID v4 | `UUID` | publisher アプリ採番 |

slug を除く全 ID をアプリ側採番に統一する (DB default に採番させない)。新規テーブル追加時の「何で採番するか」の個別判断が消え、append-heavy テーブルでは UUID v7 の時系列性により insert 性能・時間範囲クエリ・cursor pagination・障害調査の観測性が揃う。ID 列を native `UUID` 型で持つことで、battle で顕在化した列幅 drift という故障モードが型レベルで消える。

## 背景・課題

各リポの ID 採番方式が用途を明示しないまま実装ごとに分岐している。横断 audit (2026-06-04 battle 全体レビュー) で次の状況が明らかになった:

- **battle.games.game_id**: `db/schema.sql` と `data/openapi.yaml` で `VARCHAR(26) -- ULID` と宣言しているが、実装は `Guid.NewGuid().ToString("N")` で 32 文字 hex を生成。SSoT と実体が乖離しており、本番 INSERT は列幅超過で失敗する状態
- **account.players.player_id**: `UUID` 型 + `gen_random_uuid()` (UUID v4)
- **news.news_articles.article_id**: `VARCHAR(26)` ULID (newsfeed が `oklog/ulid/v2` で採番)
- **matchmaking match_id**: `oklog/ulid/v2` で採番 (Postgres スキーマは持たない)
- **card / shop / scenario のマスタデータ ID**: `VARCHAR(10-50)` の人間可読 slug (`SH-0001`, `she_ep1`, `pack_xxx` 等)
- **account / scenario の Pub/Sub event_id**: `UUID` (UUID v4)

問題は ULID と UUID v4 が「採用基準なしに混ざっている」点であり、ULID か UUID かそれ自体ではない。新規テーブルを追加するたびに「何で採番するか」が個別判断になり、宣言と実装の乖離 (battle で発生) が再発する余地が残っている。

対外露出する長寿命 ID を UUID v7 / ULID でなく UUID v4 に留めるのは、上位ビットに生成時刻を持つ形式だと ID からアカウント作成時刻を逆引きでき enumeration の手掛かりを与えるためで、件数が小さく append-heavy でない長寿命エンティティでは v4 のランダム挿入による性能劣化も実害が出ない。マスタデータに人間可読 slug を使うのは、カード ID やパック ID が運用調査やテストで人間が直接読み書きする domain knowledge であり、陣営・連番が表記に乗ること自体に価値があるためである。

## 不採用案

### 横断 ULID 統一

全リポの長寿命・履歴系 ID を ULID に揃える。

- メリット: 既存 ULID 採用箇所と整合する
- デメリット: RFC 標準を捨てる選択になる。既存の `UUID` 型を `VARCHAR(26)` に書き換えるコストが大きく、account / 既存 UUID v4 系のテーブルを全て移行する必要がある
- 不採用理由: UUID v7 が同じ性能特性を標準型のまま提供するため、ULID を新基準にする必然性がない

### 横断 UUID v4 統一

全 ID を UUID v4 に統一する (現状の account 方式に揃える)。

- メリット: 単一方式で運用がシンプル。account / Pub/Sub event_id は移行不要
- デメリット: append-heavy なテーブル (`game_events`, 将来追加されうるログ系) で B-tree fragmentation を抱え込む。時系列ソート・ID 範囲クエリ・運用調査の便益も失う
- 不採用理由: 高頻度 insert テーブルで性能・運用観測性が劣化する

### battle のみ実体に合わせて `VARCHAR(32)` hex に SSoT を書き換え (最小修正)

横断方針を策定せず、battle の schema / openapi / docs を「ULID」から「opaque hex 32」に訂正する。

- メリット: 修正コストが最小
- デメリット: 新規テーブル追加のたびに「何で採番するか」が個別判断になり、本 ADR が解こうとしている根本問題が残る
- 不採用理由: SSoT を策定する好機を逃すと、宣言と実装の乖離 (battle で発生したもの) が再発する

### 対外露出 ID を DB default 採番にする

`player_id` 等の対外露出 ID を `gen_random_uuid()` の DB default で採番する (本 ADR 初版の案)。

- メリット: 採番点が schema に一元化され、宣言と実装の乖離が起きない
- デメリット: INSERT 前に ID を持てないため、集約の事前組み立て・event_id の先発番・idempotency キーの先行発行ができない。採番が特定 DB 機能に縛られる
- 不採用理由: event_id のように INSERT 前発番が必須の用途がある以上アプリ採番はどのみち残る。採番点を用途ごとに DB / アプリに分けるより、native `UUID` 型 + CI 検証で乖離を塞いだ上でアプリ側に統一する方が一貫し、上記の設計上の利得も得られる

## Amendment: 2026-07-26 gateway が保持する game_id を現状の調査に加える

背景・課題の現状調査に gateway が含まれていない。gateway は `gateway.game_players.game_id` を `VARCHAR(26)` で持ち、battle が採番した値をアプリ層の外部キーとして参照している。ID を採番する側ではないため調査から漏れたが、battle 側の列を移行すると同時に移行しなければ列幅を超過する。

本 ADR の決定は変わらない。battle の game_id を UUID v7 へ移す作業は、gateway の該当列の移行を含めて一つの変更として扱う。

同じ形の見落としを防ぐため、ID を採番しないが他サービスの ID を保持する列も調査の対象に含める。
