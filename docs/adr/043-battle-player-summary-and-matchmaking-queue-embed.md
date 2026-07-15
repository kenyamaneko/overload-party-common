# ADR-043: 対戦履歴を battle で永続化し matchmaking キューに player summary を同梱する (ADR-042 supersede)

## ステータス

Accepted (2026-05-15)。[ADR-042](042-gateway-display-meta-cache.md) (gateway 配下に揮発キャッシュ用 Upstash Redis を導入する) を supersede する

## 結論

ADR-042 の 2 段キャッシュ設計が実装規模過剰と判明したため、対戦相手 display meta の解決を次の構成に置き換える。

1. **battle が対戦履歴を永続化する**。新規 `player_summary` テーブルに対戦者 2 名分の `(game_id, player_num, name, level)` を保持する。
2. **battle の `CreatePvPGame` API 引数を拡張**し、対戦者 2 名分の name / level を受け取る。battle はこれを `player_summary` に書き込み、game state response に同梱して返す。
3. **matchmaking のキューと match_made event に player summary を同梱する**。`Enqueue` API request に name / level を追加し、queue entry に保存。match 成立時に発行する `MatchMadeEvent.players[]` に name / level を含めて publish する。
4. **gateway は matchmaking_start handler で `/api/v1/account/me` を呼ぶ**。`onboarding_status == completed` を検査し、未完了は同期 WS で `matchmaking_error` を player に返却。取得した name / level を matchmaking `Enqueue` に渡す。
5. **gateway の `HandleMatchMade` は event の name / level をそのまま `battle.CreatePvPGame` に渡す**。account への呼び出しを発生させない。
6. **gateway の relay 経路は battle response を WS payload にそのまま pass-through する** (現行通り)。
7. ADR-042 で導入した gateway 所有 Upstash Redis インスタンス・関連 cache adapter・DisplayResolver は全廃する。
8. account の `/internal/v1/players/{playerID}` endpoint は廃止する (cross-player lookup の用途が消えるため)。

gateway 側のコード量が大幅に減り (cache adapter / resolver / 用途別 Put API / Upstash Redis 接続をすべて廃止)、gateway 所有 Upstash Redis + Secret Manager secret + IAM 権限が不要になる。対戦当時の name / level が永続化されて試合終了後のリプレイ・履歴表示でも参照可能になり、spectator は battle response から直接 player summary を得られる。account への呼び出しは matchmaking_start (同期 WS) の 1 回のみで、match_made event 経路が account に依存しないため Pub/Sub retry シナリオが大幅に簡素化される。「JWT sub のみを唯一の信頼源とする」(ADR-037) との整合も復活する。

## 背景・課題

ADR-042 (Proposed, 2026-05-12) は対戦相手 / 観戦対象の display name / level を gateway 配下の 2 段キャッシュ (pod-local in-memory + Upstash Redis) で解決する設計を採用した。

実装中 ([gateway PR #57](https://github.com/kenyamaneko/overload-party-gateway/pull/57)、[gateway issue #47](https://github.com/kenyamaneko/overload-party-gateway/issues/47) の解決を目的とする実装) に以下が見えてきて再評価が必要になった:

- 実装規模が当該データ量に対して大きすぎる。port (DisplayMetaStore + DisplayMetaLookup) + adapter (MemoryStore / RedisStore / TwoTier) + DisplayResolver (cache→account fallback) + match_made handler の snapshot 書き込み + Pub/Sub 再配信 + 用途別 Put API、と 6 層に及ぶ
- ADR-042 が定めた整合性モデル「match 成立時点の snapshot に固定」は本質的に「試合履歴に対戦当時の player summary を含める」設計と同じことを述べている。揮発キャッシュ層を介在させる必然性が薄い
- 「試合履歴の永続化」は battle service が担うべき責務 (試合結果・winner・winner reason などは既に battle 所有)
- ADR-037 の「JWT sub のみを唯一の信頼源とする」方針との整合性が ADR-042 で崩れ、cross-player lookup endpoint (`/internal/v1/players/{id}`) を維持することになっていた

ADR-042 で却下した「battle 同梱」案と「matchmaking が account を呼ぶ」案を再評価する。本 ADR は両案のハイブリッド形 (battle が永続化 + matchmaking が gateway から受け取った summary を event に同梱) を採用する。

## 不採用案

### ADR-042 の現方針 (gateway 配下に 2 段キャッシュ) を継続

却下理由: 実装規模が当該データ量に対して過剰。試合中の揮発 state とはいえ「snapshot = 対戦当時の不変値」は本質的に履歴であり、それを揮発で扱う設計上の不整合が残る。

### battle が `CreatePvPGame` 時に account を直接呼ぶ

却下理由: battle が account に同期依存を持つことになり、battle のテスト・運用に account の状態が必要になる。本 ADR の「battle は外部から渡された値を信頼する」方針と整合せず、ADR-036 の境界拡張も過大になる。

### gateway が match_made event 受信時に account を呼んで CreatePvPGame に渡す

却下理由: account 失敗が Pub/Sub event 経路に絡む。retry policy / 再試行のフローを設計する必要があり、本案 (event 経路から account を切り離す) より失敗時挙動が複雑になる。
