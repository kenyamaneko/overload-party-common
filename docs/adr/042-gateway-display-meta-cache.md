# ADR-042: gateway 配下に揮発キャッシュ用 Upstash Redis を導入する (対戦相手 display meta snapshot)

## ステータス

Superseded by [ADR-043](043-battle-player-summary-and-matchmaking-queue-embed.md)。旧ステータス: Proposed (2026-05-12)

## 結論

対戦相手 / 観戦対象の display meta (name / level) が production で空文字 fallback になる問題を解消するため、gateway が match_made 受信時に account から snapshot を取得し、**gateway 所有の Upstash Redis + pod-local in-memory の 2 段キャッシュ**で保持して WS payload に埋める。battle service は pure game engine のまま維持され、matchmaking → account の依存も発生しない。game state relay 都度の account 呼び出しがなくなって負荷は試合数比例に低減し、試合途中の観戦者接続も同じ snapshot を共有できる。account 障害時のフォールバック表示値は短 TTL で書き込まれ、復旧後は自動的に正しい表示値へ戻る。

## 背景・課題

gateway は WebSocket 経由で **対戦相手 / 観戦対象** の display name / level をクライアントへ伝える必要がある。

現状の実装は `accountclient.GetPlayer(ctx, playerID)` で account の `/internal/v1/players/{id}` を呼び、`battle_start` イベント等のペイロードに `opponent_name` / `opponent_level` を埋めて返している。

この経路は次の理由で再設計が必要になった:

- [ADR-037](037-internal-auth-hmac-signed-jwt.md) の移行で account の player-scoped API は `/api/v1/account/me/*` に一本化された。`/me` は JWT sub に紐づく自身しか返せないため、**対戦相手の lookup** は「JWT sub クレームのみを唯一の信頼源とする」方針との整合性が論点になる。
- gateway issue [#47](https://github.com/kenyamaneko/overload-party-gateway/issues/47) で報告された通り、production で対戦相手の display meta が **空文字 fallback** になっていた (silent な観測不可状態)。
- battle service は pure game engine という設計方針 ([ADR-036](036-gateway-passthrough-and-service-public-api.md)) のため、battle に account 依存を導入したくない。

検討対象は「**誰が account への display meta lookup を担うか**」「**そのキャッシュをどこに置くか**」の 2 軸である。

## 不採用案

### battle service が game state response に display meta を同梱

battle が account を呼んで game state response に `{name, level}` を載せる。

却下理由: battle service は pure game engine という ADR-036 の方針を崩す。battle が account 依存を持つと、battle のテスト・運用に account の状態が必要になり、責務境界が曖昧になる。

### matchmaking が account を呼んで match_made event に同梱

matchmaking が match 成立時に account を呼び、`match_made` event のペイロードに `{name, level}` を含める。

却下理由: matchmaking は現状 `player_id` と `deck_id` のみを扱う設計 (`api-matchmaking` の AsyncAPI 契約)。matchmaking → account の依存を新規導入することになり、display meta lookup のためにキュー責務の範囲を広げる遠回り設計になる。

### account が player profile 更新を Pub/Sub publish

account が profile 変更を Pub/Sub publish、gateway が subscribe して local cache を eventually consistent に保つ。

却下理由: 整合性モデルが複雑化する (購読時点の状態管理、cache 無効化の議論)。試合中の表示というユースケースには過剰。将来 display meta を試合外でも頻繁に参照する必要が出てきた場合に再検討する。

### gateway pod の in-memory cache のみ

Redis を使わず gateway pod の in-memory map で snapshot を保持。

却下理由: pod 分散 (対戦者 / 観戦者が別 pod) と pod restart で破綻する。試合途中に観戦者が接続するシナリオを満たせない。

### PostgreSQL `game_players` テーブル拡張

gateway の `game_players` テーブルに `name` / `level` カラムを追加。

却下理由: 試合中の揮発 state を OLTP に置かない方針 (ADR-010 / ADR-020 と同じ判断)。試合終了後も残るが、戦績の永続化は本 ADR のスコープ外。
