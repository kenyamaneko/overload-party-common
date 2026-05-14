# ADR-043: 対戦履歴を battle で永続化し matchmaking キューに player summary を同梱する (ADR-042 supersede)

## ステータス

Accepted (2026-05-15)

Supersedes: [ADR-042](042-gateway-display-meta-cache.md) (gateway 配下に揮発キャッシュ用 Upstash Redis を導入する)

## コンテキスト

ADR-042 (Proposed, 2026-05-12) は対戦相手 / 観戦対象の display name / level を gateway 配下の 2 段キャッシュ (pod-local in-memory + Upstash Redis) で解決する設計を採用した。

実装中 ([gateway PR #57](https://github.com/kenyamaneko/overload-party-gateway/pull/57)) に以下が見えてきて再評価が必要になった:

- 実装規模が当該データ量に対して大きすぎる。port (DisplayMetaStore + DisplayMetaLookup) + adapter (MemoryStore / RedisStore / TwoTier) + DisplayResolver (cache→account fallback) + match_made handler の snapshot 書き込み + Pub/Sub 再配信 + 用途別 Put API、と 6 層に及ぶ
- ADR-042 が定めた整合性モデル「match 成立時点の snapshot に固定」は本質的に「試合履歴に対戦当時の player summary を含める」設計と同じことを述べている。揮発キャッシュ層を介在させる必然性が薄い
- 「試合履歴の永続化」は battle service が担うべき責務 (試合結果・winner・winner reason などは既に battle 所有)
- ADR-037 §5 (JWT sub のみを唯一の信頼源とする) の整合性が ADR-042 で崩れ、cross-player lookup endpoint (`/internal/v1/players/{id}`) を維持することになっていた

ADR-042 で却下した「案 α (battle 同梱)」と「案 β-A1 (matchmaking が account を呼ぶ)」を再評価する。本 ADR は両案のハイブリッド形 (battle が永続化 + matchmaking が gateway から受け取った summary を event に同梱) を採用する。

## 決定

### 設計の骨子

1. **battle が対戦履歴を永続化する**。新規 `player_summary` テーブルに対戦者 2 名分の `(game_id, player_num, name, level)` を保持する。
2. **battle の `CreatePvPGame` API 引数を拡張**し、対戦者 2 名分の name / level を受け取る。battle はこれを `player_summary` に書き込み、game state response に同梱して返す。
3. **matchmaking のキューと match_made event に player summary を同梱する**。`Enqueue` API request に name / level を追加し、queue entry に保存。match 成立時に発行する `MatchMadeEvent.players[]` に name / level を含めて publish する。
4. **gateway は matchmaking_start handler で `/api/v1/account/me` を呼ぶ**。`onboarding_status == completed` を検査し、未完了は同期 WS で `matchmaking_error` を player に返却。取得した name / level を matchmaking `Enqueue` に渡す。
5. **gateway の `HandleMatchMade` は event の name / level をそのまま `battle.CreatePvPGame` に渡す**。account への呼び出しを発生させない。
6. **gateway の relay 経路は battle response を WS payload にそのまま pass-through する** (現行通り)。
7. ADR-042 で導入した gateway 所有 Upstash Redis インスタンス・関連 cache adapter・DisplayResolver は全廃する。
8. account の `/internal/v1/players/{playerID}` endpoint は廃止する (cross-player lookup の用途が消えるため)。

### なぜこの設計か

| 観点 | 評価 |
|------|------|
| 実装規模 | gateway 側 cache レイヤ全廃で大幅減 (adapter 3 種 + resolver + 用途別 Put API + match_made snapshot 書き込み が消える) |
| インフラ | gateway 所有 Upstash Redis インスタンス + Secret Manager 2 secret + IAM accessor 不要 |
| 試合履歴としての自然さ | 対戦当時の player summary が battle の試合履歴と同じテーブル群に統合される。試合終了後のリプレイ・履歴表示でも参照可能 |
| account への呼び出し回数 | gateway の matchmaking_start (= 同期 WS request) で 1 回のみ。match_made event 経路は account に依存しない |
| 失敗時の観察性 | account / onboarding 検査の失敗は同期 WS で player に即時 error 返却。match_made event の到着時点では account に依存しないため Pub/Sub retry シナリオが大幅に簡素化される |
| matchmaking → account 依存 | 発生しない (matchmaking は gateway から渡された値を保存・event に同梱するだけ) |
| ADR-037 §5 (JWT sub による self-only 強制) | 整合復活。cross-player lookup endpoint が廃止される |
| ADR-036 境界線 | battle 責務を「pure game engine」から「game engine + 不変な対戦履歴」に拡張する (本 ADR で明示) |

### ADR-042 β-A1 (却下) と本案の違い

ADR-042 で却下した β-A1 は「matchmaking が match 成立時に account を呼ぶ」案だった。却下理由は「matchmaking → account の新規依存を発生させ、matchmaking のキュー責務を超える」。

本案では呼び出し主体が gateway であり、matchmaking は account に依存しない:

- gateway が `Enqueue` 時に /me で取得した name / level を matchmaking に **渡す**
- matchmaking は与えられた値を queue entry に保存し、match_made event に同梱して publish する
- matchmaking のコードベースに account client は導入されない

「player_id + deck_id」というキュー責務の最小性は失われるが、これは display 情報の話に閉じる (gameplay の essential ではなく representation の essential)。

### 検討した代替案

#### 案: ADR-042 の現方針 (gateway 配下に 2 段キャッシュ) を継続

却下理由: 実装規模が当該データ量に対して過剰。試合中の揮発 state とはいえ「snapshot = 対戦当時の不変値」は本質的に履歴であり、それを揮発で扱う設計上の不整合が残る。

#### 案: battle が `CreatePvPGame` 時に account を直接呼ぶ (ADR-042 案 α-1)

却下理由: battle が account に同期依存を持つことになり、battle のテスト・運用に account の状態が必要になる。本 ADR の「battle は外部から渡された値を信頼する」方針と整合せず、ADR-036 の境界拡張も過大になる。

#### 案: gateway が match_made event 受信時に account を呼んで CreatePvPGame に渡す (α-3)

却下理由: account 失敗が Pub/Sub event 経路に絡む。retry policy / 再試行のフローを設計する必要があり、本案 (event 経路から account を切り離す) より失敗時挙動が複雑になる。

### 実装方針

#### battle スキーマ

```sql
CREATE TABLE battle.player_summary (
  game_id    text    NOT NULL,
  player_num int     NOT NULL,
  name       text    NOT NULL,
  level      int     NOT NULL,
  PRIMARY KEY (game_id, player_num)
);
```

- `name` は NOT NULL。空文字 (`""`) は許容する。matchmaking 側で onboarding 完了を担保すれば空文字は発生しないが、防御層の責務分離として battle 側では型レベルの厳密性 (空文字禁止) を強制しない
- 試合作成と同一 transaction で書き込み、片方失敗で両方 rollback する

#### battle API

`CreatePvPGame` request:

```json
{
  "players": [
    {"player_num": 1, "cards": [...], "name": "alice", "level": 7},
    {"player_num": 2, "cards": [...], "name": "bob", "level": 12}
  ]
}
```

game state response に player summary を同梱:

```json
{
  "game_id": "...",
  "players": [
    {"player_num": 1, "name": "alice", "level": 7},
    {"player_num": 2, "name": "bob", "level": 12}
  ],
  ...
}
```

#### matchmaking API / 契約

`Enqueue` request body 拡張:

```json
{"deck_id": 42, "name": "alice", "level": 7}
```

AsyncAPI `MatchedPlayer` 拡張:

```yaml
MatchedPlayer:
  type: object
  properties:
    player_id: { type: string }
    deck_id:   { type: integer, format: int64 }
    name:      { type: string }
    level:     { type: integer, format: int64 }
```

matchmaking は queue entry にこれらを保存し、match 成立時に `MatchMadeEvent.players[]` の各 entry に同梱して publish する。

#### gateway

- `handleMatchmakingStart`: 既存の deck 検証 + battle limit 検査に加え、`accountClient.GetMe(ctx)` を呼び `PlayerResponse` を取得する。`OnboardingStatus != completed` なら `matchmaking_error` を返却。`Name` (nil なら空文字) と `Level` を `matchmakingClient.Enqueue` に渡す
- `HandleMatchMade`: event の `players[i].Name` / `Level` をそのまま `battleClient.CreatePvPGame` の引数に渡す。account を呼ばない
- relay 経路: battle response の `players[]` を WS payload にそのまま pass-through (`battle_start` の `my_name` / `opponent_name` / `my_level` / `opponent_level`)
- 削除対象: `internal/adapter/displaymetacache/` 全体、`internal/handler/ws/displayresolver.go`、`Manager.displayCache` / `Manager.playerProfileGetter`、`Manager.writeDisplayMetaSnapshot`、Upstash Redis 接続関連 (`newDisplayMetaRedisClient` 等)

### ADR-036 境界線の更新

ADR-036 Decision 1 は「battle = pure game engine」「gateway = passthrough + auth + バトル補助」を定義していた。本 ADR で次の補足を追加する:

> battle の責務に「ゲームロジック + **不変な対戦履歴 (対戦当時の player summary を含む)**」を含める。battle は account への同期依存を持たず、対戦履歴データは外部から引数として渡される値を信頼する。

ADR-042 で追加した「gateway の責務に display meta の組み立てを含める」記述は本 ADR で取り消す (gateway は pass-through に戻る)。

### ADR-037 task A の close 条件 (再更新)

ADR-042 増補 ([#103](https://github.com/kenyamaneko/overload-party-common/pull/103)) で「`/internal/v1/players/{id}` endpoint は match_made handler と DisplayMetaResolver のフォールバック経路で使う」と書いた。本 ADR で次に置き換える:

- `/internal/v1/players/{id}` endpoint は **account 側で削除する**
- gateway の cross-player lookup 用途そのものが消えるため、原 ADR-037 task A の「endpoint 削除」close 条件に戻る
- ADR-042 で追加した「endpoint 維持」の例外は撤回する

## 失敗時挙動

| 失敗位置 | 挙動 |
|----------|------|
| gateway の `/me` 呼び出しが失敗 | matchmaking_start handler から player に同期 `matchmaking_error` を返却 (observable、retryable フラグは error 種別による) |
| `/me` 応答の `onboarding_status != completed` | matchmaking_start handler から player に同期 `matchmaking_error` を返却。UI 側で onboarding 画面へ誘導する想定 |
| matchmaking `Enqueue` 失敗 | 既存通り (gateway は同期 `matchmaking_error` を返却) |
| matchmaking match_made event 発行失敗 | matchmaking 側の責務。本 ADR スコープ外 |
| gateway `HandleMatchMade` の `CreatePvPGame` 失敗 | handler から error を返す。Pub/Sub subscriber が ack しないため event は subscription の retry policy で再試行される |
| battle `player_summary` 書き込み失敗 | battle 内部 transaction で game 作成も含めて rollback。`CreatePvPGame` は 5xx を返す |

## 結果

### Positive

- gateway 側のコード量が大幅減 (cache adapter / resolver / 用途別 Put API / Upstash Redis 接続 すべて廃止)
- gateway 所有 Upstash Redis インスタンス + Secret Manager secret + IAM 権限が不要
- 対戦履歴に対戦当時の name / level が永続化され、試合終了後のリプレイ・履歴表示でも参照可能
- spectator は battle response から直接 player summary を得られる (gateway での組み立て不要)
- account への呼び出しは matchmaking_start (同期 WS) のみ。match_made event 経路は account に依存しないため Pub/Sub retry シナリオが大幅に簡素化される
- ADR-037 §5 (JWT sub による self-only 強制) と整合復活。`/internal/v1/players/{id}` endpoint が完全廃止される

### Negative

- battle の責務が「pure game engine」から「game engine + 不変な対戦履歴」に拡張される (ADR-036 の境界線が動く)
- battle スキーマに player display 列が追加される (account の master data の snapshot を battle が永続化する)
- matchmaking のキュー責務に display 情報の保持が加わる (本来の player_id + deck_id 最小性が崩れる)
- AsyncAPI 契約 (`MatchedPlayer`) に破壊的変更が入る

### 緩和策

- battle は外部から渡された name / level を信頼するのみで account への同期依存は持たない (テスト・運用への影響は最小)
- matchmaking も同様に account に依存せず、与えられた値を保存するだけ。matchmaking のテストに account fake は不要
- ADR-036 / ADR-037 / ADR-042 との関係は本 ADR で明示し、境界線の移動を追跡可能にする

## 連動する変更

| リポ | 変更 |
|---|---|
| common | 本 ADR-043 起草 + ADR-042 supersede |
| matchmaking | `Enqueue` API request 拡張、AsyncAPI `MatchedPlayer` 拡張 (`data/asyncapi.yaml` + 再生成)、queue entry 拡張 |
| battle | `player_summary` テーブル + migration、`CreatePvPGame` API 拡張、game state response 拡張 |
| gateway | matchmaking_start で `/me` 呼び出し + onboarding ガード、cache 関連実装全廃 (`internal/adapter/displaymetacache/`、`internal/handler/ws/displayresolver.go`、Manager の cache field / writeDisplayMetaSnapshot)、match_made handler を battle pass-through 化、Upstash Redis 接続関連削除 |
| account | `/internal/v1/players/{playerID}` endpoint 削除 ([account PR #28](https://github.com/kenyamaneko/overload-party-account/pull/28) revert) |
| infra | gateway 所有 Upstash Redis 削除 ([infra PR #30](https://github.com/kenyamaneko/overload-party-infra/pull/30) revert、terraform destroy で apply) |
| k8s | gateway deployment.yaml から `APP_ENV=production` 削除 ([k8s PR #32](https://github.com/kenyamaneko/overload-party-k8s/pull/32) revert) |

## 関連

- [ADR-036](036-gateway-passthrough-and-service-public-api.md): battle 純粋性と gateway pass-through 方針の base。本 ADR で battle の責務に「対戦履歴」を加える境界線変更を行い、ADR-042 で動かした gateway 側の境界 (display meta 組み立て) は撤回する
- [ADR-037](037-internal-auth-hmac-signed-jwt.md): §5 整合復活。task A の close 条件を「endpoint 削除」原案に戻す
- [ADR-042](042-gateway-display-meta-cache.md): 本 ADR で supersede
- gateway issue [#47](https://github.com/kenyamaneko/overload-party-gateway/issues/47): 本 ADR の方針で解決される
- gateway PR [#57](https://github.com/kenyamaneko/overload-party-gateway/pull/57): ADR-042 方針で実装、本 ADR への方針転換に伴い close 済
