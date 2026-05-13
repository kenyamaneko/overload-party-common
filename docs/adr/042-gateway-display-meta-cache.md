# ADR-042: gateway 配下に揮発キャッシュ用 Upstash Redis を導入する (対戦相手 display meta snapshot)

## ステータス

Proposed (2026-05-12)

## コンテキスト

gateway は WebSocket 経由で **対戦相手 / 観戦対象** の display name / level をクライアントへ伝える必要がある。

現状の実装は `accountclient.GetPlayer(ctx, playerID)` で account の `/internal/v1/players/{id}` を呼び、`battle_start` イベント等のペイロードに `opponent_name` / `opponent_level` を埋めて返している。

この経路は次の理由で再設計が必要になった:

- [ADR-037](037-internal-auth-hmac-signed-jwt.md) Phase 3 で account の player-scoped API は `/api/v1/account/me/*` に一本化された。`/me` は JWT sub に紐づく自身しか返せないため、**対戦相手の lookup** は ADR-037 §5 の「JWT sub クレームのみを唯一の信頼源とする」方針との整合性が論点になる。
- gateway issue [#47](https://github.com/kenyamaneko/overload-party-gateway/issues/47) で報告された通り、production で対戦相手の display meta が **空文字 fallback** になっていた (silent な観測不可状態)。
- battle service は pure game engine という設計方針 ([ADR-036](036-gateway-passthrough-and-service-public-api.md)) のため、battle に account 依存を導入したくない。

検討対象は「**誰が account への display meta lookup を担うか**」「**そのキャッシュをどこに置くか**」の 2 軸である。

## 決定

### 設計の骨子

1. **gateway が match_made イベント受信時に** `accountclient.GetPlayer` を呼び、対戦者 2 名分の `{name, level}` snapshot を取得する。
2. snapshot は新規導入する **gateway 所有の Upstash Redis インスタンス** に書き込む。
3. game state relay 時は **pod-local in-memory cache** を 1 段目、Upstash Redis を 2 段目として参照する (2 段キャッシュ)。in-memory cache は **コスト対策** として導入する (詳細は「なぜ 2 段キャッシュか (コスト対策)」節)。
4. self / opponent / spectator の display meta は **全て同一経路** (Upstash Redis cache + `/internal/v1/players/{playerID}`) で解決する。self を `/me` 経由とする経路分離は採用しない。
5. account 障害時のフォールバック表示値 (`Player {prefix}`) は **通常 snapshot とは別の短 TTL** で cache に書き込み、account 復旧後の自動回復を許容する。

### なぜこの設計か

| 観点 | 評価 |
|------|------|
| battle 純粋性 | battle service は account 非依存のまま維持される |
| サービス境界 | matchmaking → account の新規依存を発生させない (matchmaking は player_id / deck_id 以外を扱わない設計を維持) |
| ADR-037 §5 との整合 | 自身を含む player lookup は `/internal/v1/players/{playerID}` 経由。WS 認証段階で Firebase JWT により identity 検証済のため、JWT sub による self-only 強制は本ユースケースでは過剰 |
| self/opponent/spectator の対称性 | 全経路を cache + `/internal` に統一。WS 接続は Firebase 認証で identity 確認済のため self を `/me` 経由にする identity-defense 価値は限定的、resolver の対称性を優先 |
| 揮発 state の置き場所 | 試合中の揮発 state を OLTP (PostgreSQL) に置かない方針と整合 ([ADR-010](010-matchmaking-queue-upstash-redis.md) / [ADR-020](020-newsfeed-redis-dedup-reconverge.md) と同パターン) |
| pod 分散耐性 | 対戦者 / 観戦者が別 pod に分散しても Redis 経由で参照可能 |
| pod restart 耐性 | in-memory のみではキャッシュ消失で再 lookup が必要。Redis 永続でこれを回避 |
| spectator 後参加 | 試合途中で接続する観戦者も同じ snapshot を参照できる |

### gateway 責務の追記 (ADR-036 を補足)

ADR-036 の既存記述は変更しない。本 ADR で次を追記として宣言する:

> gateway の責務は「各サービスへのパススルーとしての入り口」「認証」「**バトル関連の補助**」とする。display meta の組み立て (対戦相手 / 観戦対象の name / level を WS payload に埋める) はバトル関連の補助に含まれる。

ADR-036 Decision 1 の「gateway に残すもの」のリストはこの追記によって拡張される。

### ADR-037 task A の close 条件更新

ADR-037 の既存記述は変更しない。本 ADR で次を宣言する:

- ADR-037 task A の close 条件を「**`/internal/v1/players/{id}` endpoint を削除**」から「**match 成立時の snapshot 書き込み + cache miss / 障害時のフォールバック lookup に限定**」に更新する。
- `/internal/v1/players/{id}` endpoint は account 側に維持する。呼び出し元は gateway の match_made handler と DisplayMetaResolver のフォールバック経路。
- これにより gateway #47 の本旨 (silent 404 fallback の解消、game state relay 都度の lookup 廃止) は満たされる。

### 検討した代替案

#### 案 α: battle service が game state response に display meta を同梱

battle が account を呼んで game state response に `{name, level}` を載せる。

却下理由: battle service は pure game engine という ADR-036 の方針を崩す。battle が account 依存を持つと、battle のテスト・運用に account の状態が必要になり、責務境界が曖昧になる。

#### 案 β-A1: matchmaking が account を呼んで match_made event に同梱

matchmaking が match 成立時に account を呼び、`match_made` event のペイロードに `{name, level}` を含める。

却下理由: matchmaking は現状 `player_id` と `deck_id` のみを扱う設計 (`api-matchmaking` の AsyncAPI 契約)。matchmaking → account の依存を新規導入することになり、display meta lookup のためにキュー責務の範囲を広げる遠回り設計になる。

#### 案 γ: account が player profile 更新を Pub/Sub publish

account が profile 変更を Pub/Sub publish、gateway が subscribe して local cache を eventually consistent に保つ。

却下理由: 整合性モデルが複雑化する (購読時点の状態管理、cache 無効化の議論)。試合中の表示というユースケースには過剰。将来 display meta を試合外でも頻繁に参照する必要が出てきた場合に再検討する。

#### 案 B2: gateway pod の in-memory cache のみ

Redis を使わず gateway pod の in-memory map で snapshot を保持。

却下理由: pod 分散 (対戦者 / 観戦者が別 pod) と pod restart で破綻する。試合途中に観戦者が接続するシナリオを満たせない。

#### 案 PG: PostgreSQL `game_players` テーブル拡張

gateway の `game_players` テーブルに `name` / `level` カラムを追加。

却下理由: 試合中の揮発 state を OLTP に置かない方針 (ADR-010 / ADR-020 と同じ判断)。試合終了後も残るが、戦績の永続化は本 ADR のスコープ外。

### なぜ 2 段キャッシュか (コスト対策)

Upstash Redis を単一キャッシュとして game state relay 毎に read すると、ops 数は relay 頻度に線形にスケールする。試算では試合 1,000/日 で月額 ~$18 (Pay-as-you-go) 程度になり、relay 頻度次第ではさらに膨らむ。

2 段キャッシュ (pod-local in-memory + Upstash Redis) を採用すると Redis read は WS 接続確立時の各 pod 初回のみとなり、ops 数は relay 頻度から独立する。試合 10,000/日 でも月額 ~$7 に収まる (後述「コスト試算」参照)。

in-memory cache の導入は pod-local state を増やす点で運用上の好ましさは下がる (デバッグ可視性が pod 跨ぎで分散する、pod restart で再 read が必要になる)。本来は単一キャッシュの方が運用上はシンプルだが、本ユースケースでは:

- 試合中の display meta は snapshot 固定で整合性問題が起きない
- in-memory cache miss 時は Redis から自動的に再構築される
- Redis から消えた場合の障害時挙動は別途定義済み (「失敗時挙動」節)

ため、**コスト対策のトレードオフとして in-memory 2 段目を許容する**。relay 頻度が低く Redis 単一でもコストが許容範囲に収まると判明した場合、または Redis 単一で運用上のメリットがコスト増を上回ると判断された場合は、別 ADR で再検討する。

### 実装方針

#### Redis データ構造

```
game:{game_id}:player:{player_num}   — Hash ({name: <string>, level: <int>})
```

書き込み経路は 2 種類:

- **通常 snapshot 書き込み** (match_made handler): TTL 1 時間 (試合最長時間 + buffer)
- **フォールバック書き込み** (resolver の最終フォールバック経路): account 復旧後の自動回復を許容する短 TTL (具体値は実装側で定数化)

操作:

- `HSET game:{game_id}:player:{player_num} name <name> level <level>` で書き込み
- `EXPIRE game:{game_id}:player:{player_num} <ttl>` で TTL を設定
- `HGETALL game:{game_id}:player:{player_num}` で読み出し

#### 書き込み経路 (match_made handler)

1. gateway が `match_made` event を Pub/Sub から受信
2. 対戦者 2 名分の `accountclient.GetPlayer(ctx, playerID)` を呼び出す
3. 取得した `{name, level}` を Upstash Redis に `HSET` + `EXPIRE` で書き込む
4. 自 pod の in-memory cache にも乗せる

#### 読み出し経路 (game state relay)

1. 1 段目: 自 pod の in-memory cache を参照
2. miss 時: Upstash Redis を参照 → hit したら in-memory cache に乗せる
3. miss 時: `accountclient.GetPlayer` で再 lookup (障害時のフォールバック)
4. それも失敗: フォールバック表示値 (`"Player {playerID 短縮}"`) を Redis に書き込み + Error ログ

#### Upstash インスタンス分離

既存の Upstash Redis インスタンス (matchmaking ADR-010 / newsfeed ADR-020 で利用) とは **別の新規インスタンス** を gateway 所有として確保する。理由:

- 障害分離: gateway のキャッシュ障害が matchmaking キューに波及しない
- コスト計上分離: サービスごとの利用量計測が容易
- key 名前空間の干渉回避

#### 環境変数

```
UPSTASH_REDIS_URL_GATEWAY=rediss://default:xxx@xxx.upstash.io:6379
```

### 失敗時挙動 (silent fallback 禁止 + ゲーム継続)

failure を観測可能にすることで silent ではない fallback を実現する。表示は **空文字ではなく明示的なフォールバック表示値** とし、UI 上「データ取得失敗が起きている」と認識可能にする。

| 失敗位置 | 挙動 |
|----------|------|
| match_made handler で `accountclient.GetPlayer` 失敗 | snapshot 書き込みをスキップし handler から error を返す。失敗が永続化した場合のフォールバック表示値書き込みは relay 経路の最終行に集約する |
| Redis 書き込み失敗 | Error ログ。試合は継続 (relay 時に再 lookup が走る) |
| game state relay 時の Redis 読み出し失敗 | account 直接 lookup にフォールバック + Error ログ |
| Redis cache miss | account 再 lookup + Warn ログ (本来 TTL 1 時間内に起きないため検知対象) |
| account 再 lookup も失敗 | フォールバック表示値 (`"Player {playerID 短縮}"`) を **短 TTL** で Redis に書き込み + Error ログ。account 復旧後の次回 cache miss で本来の値に再 lookup される |

これにより `accountclient.GetPlayer` の呼び出し回数は「正常時 1 試合 1 回、障害時は接続 client 数に応じて増加」となる。`/internal/v1/players/{id}` endpoint を account 側に維持する判断はこの障害時フォールバックも前提にしている。

### 整合性モデル

- 試合中の display meta は **match 成立時点の snapshot に固定** する。試合中の name 変更・level 変動は反映しない。
- name 変更は試合中に発生しないユースケース。level up は試合終了後の昇格処理で発生し、試合中の表示には影響しない。
- 観戦者は試合途中に接続しても、match 成立時点の snapshot を見ることになる。

## 結果

### Positive

- gateway #47 で報告された silent 404 + 空文字 fallback が解消する。
- battle service は pure game engine のまま維持される。
- matchmaking → account の依存を新規導入せずに済む。
- game state relay 都度の `accountclient.GetPlayer` 呼び出しがなくなり、account への負荷が試合数比例 (relay 数比例ではない) に低減する。
- 試合途中の観戦者接続も同じ snapshot を共有できる。
- account 障害時のフォールバック表示値は短 TTL で書き込まれるため、account 復旧後は自動的に正しい表示値へ戻る (cache pollution を回避)。

### Negative

- gateway の責務が「パススルー + 認証」から「パススルー + 認証 + バトル補助」に拡張される (ADR-036 の境界線が動く)。
- 新規インフラ依存 (gateway 所有 Upstash Redis インスタンス) が増える。
- account 側の `/internal/v1/players/{id}` endpoint が完全には消えず維持される (ADR-037 §5 の解釈に「cross-player lookup は match 成立時の 1 回呼び出しに限定」という but が付く)。
- 試合中の name / level 変更は表示に反映されない (snapshot 固定)。
- in-memory cache 採用により pod-local state が増え、デバッグ可視性が pod 跨ぎで分散する。本来は単一キャッシュの方が運用上シンプルだが、コスト対策のトレードオフとして許容する (「なぜ 2 段キャッシュか (コスト対策)」節)。

### 緩和策

- gateway 責務拡張の境界線は「display meta の組み立て」に限定し、本 ADR で射程を明示する。将来別の集約責務を gateway に持たせる場合は別 ADR で判断する。
- `/internal/v1/players/{id}` endpoint の維持は ADR-037 task A の close 条件更新として本 ADR で明示し、追跡可能にする。

## コスト試算

### Upstash Redis 料金 (2026-05 時点)

- Free tier: 500K commands/月、256 MB、帯域 10 GB
- Pay-as-you-go: $0.20 / 100K commands、ストレージ $0.25/GB/月、帯域無制限
- Fixed Plan: $10/月、commands 無制限、帯域 50 GB

### 1 試合あたりの ops 数 (2 段キャッシュ採用後)

- write: 2 回 (player 1 + player 2 の snapshot 書き込み)
- read: `2 + 2N` 回 (対戦者 2 名 × 各 pod 初回 read 1 回 + 観戦者 N 名 × 両 player 分 read 2 回)
- 合計: `4 + 2N` ops/試合

### シナリオ別月額

| 試合数/日 | 観戦者平均 | ops/試合 | ops/月 | 月額 |
|-----------|------------|----------|--------|------|
| 100 | 0 | 4 | 12K | $0 (Free tier) |
| 1,000 | 2 | 8 | 240K | $0 (Free tier) |
| 10,000 | 5 | 14 | 4.2M | ~$7 (Pay-as-you-go) |
| 100,000 | 10 | 24 | 72M | $10 (Fixed Plan に切替) |

- 当面は Pay-as-you-go (Free tier 内) で運用する。
- ストレージ・帯域は実質無視できる規模。

## 実装スコープ

- 本 ADR で導入する Redis は **display meta snapshot のみに使用** する。
- 将来別の揮発 state (WS session state / ゲーム進行 phase 等) を Redis 化する場合は別 ADR で射程拡張を判断する。本 ADR では gateway 揮発 state 全般への一般化は行わない。

## 関連

- [ADR-010](010-matchmaking-queue-upstash-redis.md): Upstash Redis 採用パターンの先行事例 (matchmaking queue)
- [ADR-020](020-newsfeed-redis-dedup-reconverge.md): Upstash Redis 採用パターンの先行事例 (newsfeed dedup)
- [ADR-036](036-gateway-passthrough-and-service-public-api.md): gateway の責務再定義 (本 ADR で「バトル補助」を追記)
- [ADR-037](037-internal-auth-hmac-signed-jwt.md): task A の close 条件を本 ADR で更新
- gateway issue [#47](https://github.com/kenyamaneko/overload-party-gateway/issues/47): 本 ADR の実装トリガー
