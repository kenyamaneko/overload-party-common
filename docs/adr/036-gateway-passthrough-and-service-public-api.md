# ADR-036: gateway を完全パススルー化し、client 公開 API を各サービスが整備する

## ステータス

Accepted (2026-05-10)。末尾の Amendment (2026-05-12: matchmaking を対象から除外) を含めて現行方針とする

## 結論

型 SSoT の二重管理と gateway の責務肥大を解消するため、gateway の REST handler を認証・WS hub・gateway 自身の状態のみに縮小し、それ以外は **transport は gateway を経由するが型契約は各サービスが直接公開する** 形に移行する。各サービスが client 公開仕様を `data/openapi.yaml` で直接表現し、gateway で担われていた変換層 (型変換 / リネーム / 検証等) を各サービス側に内製化する。型 SSoT が一元化されて gateway での再定義が不要になり、battle だけ特殊例外だった構成が「型は各サービス、transport は gateway」の同一パターンに揃う。client 公開仕様の改善は各サービスごとに進められ、検証・変換の二重実装が排除される。

## 背景・課題

ADR-034 で client 依存の 3 層原則 (A: API 契約由来 / B: battle 特殊例外 / C: ゲームルール定数) が確定した一方、Layer A の **置換先** と **gateway の責務範囲** は scope 外として持ち越されていた。本 ADR で確定する。

### gateway 現状の handler 分類 (実調査)

`overload-party-gateway/internal/handler/rest/` の 13 handler を実コードで分類した結果、以下の構成だった。

| 分類 | 件数 | handler |
|---|---|---|
| 完全パススルー型 (型加工なし) | 4 | `card` / `game_log` / `npc` / `player_card` |
| 加工ありパススルー型 | 6 | `auth` / `deck` / `news` / `player` / `player_settings` / `scenario` / `shop` |
| gateway 内部状態型 | 2 | `spectate` (WS Manager 状態) / `static` (announcements.json / daily_tips.json) |

加工の中身:

- **型変換** (`deck` / `player_settings` / `shop`): `apigateway.X` → `apicard.X` / `apishop.X` の構造体マッピング
- **フィールドリネーム / 隠蔽** (`player`): `InitialFaction` → `SelectedFaction`、`OnboardingStatus` 隠蔽
- **JSON ラップ** (`scenario`): レスポンスに `episodeID` / `message` を追加
- **enum マッピング** (`shop`): `Platform` 値変換
- **検証** (`shop` の `validatePurchaseRequest`)
- **デフォルト値補完** (`news` の limit / offset)
- **エラー → HTTP status マッピング** (`auth` の `ErrPlayerAlreadyRegistered`)

これらは **ビジネスロジック (ゲームルール / ドメイン演算) ではなく、各サービスの内部 API を client 向けに正規化する変換層**である。各サービスの openapi が「gateway 内部用」として最適化されているため、client 公開には gateway での正規化が必要になっている、という現状認識。

### 現状の構造的問題

1. **型 SSoT の二重管理**: 各サービスが `apigateway.X` 系の型を持ち、gateway がそれを `apishop.X` 等に変換している。同じデータの形を 2 箇所で定義する状態
2. **battle 特殊例外**: ADR-034 Amendment の Layer B で `game-state-npm` を client 直接消費としたが、battle 以外も同様に直接消費させると例外が消える
3. **gateway server の責務肥大**: 認証 / WS / 集約 / 加工 / 静的データ保持 / 内部状態を全部抱える

## Amendment: 2026-05-12 matchmaking を Phase 3c 対象から除外

[overload-party-matchmaking#14](https://github.com/kenyamaneko/overload-party-matchmaking/issues/14) の調査結果に基づき、Phase 3c の対象列挙から matchmaking を除外する。

### 経緯

「Phase 3c: 各サービス TS パッケージ整備」では対象として `shop / card / account / scenario / news / support / matchmaking` の 7 リポを列挙した。実装着手段階で matchmaking の調査を行ったところ、他 6 リポと事情が異なることが判明:

- matchmaking は **client が直接消費する REST 公開 API を持たない**。openapi.yaml は `/internal/v1/{enqueue,cancel,queue-size,health}` のみで、いずれも gateway → matchmaking 内部 API または infra probe
- client が呼ぶマッチング操作は gateway WS hub 経由 (`matchmaking_start` / `match_found` 等の WS message) で完結する
- WS message 型は gateway 側に集約済み (`api-gateway-npm` の WS section / `ws-constants-npm` / asyncapi-gateway)。matchmaking 独自の TS 型を client が必要とする経路がない

「各サービスが client 公開 API を整備する」の前提を満たさない (=公開対象がない) ため、Phase 3c rollout の本旨である「`api-{service}-npm` 新設 + client が直接消費」を matchmaking に適用する必然性がない。

### Phase 3c 対象の改訂

- Phase 3c の対象を **6 リポに改訂**: `shop / card / account / scenario / news / support`
- matchmaking は Phase 3c 対象外。`api-matchmaking-npm` は新設しない
- matchmaking の通信形態 (client は gateway WS hub 経由、直接 REST 呼び出しなし) は本 ADR 全体の例外として [APPLICATION.md の「例外: matchmaking」節](../architecture/APPLICATION.md) で明示する
