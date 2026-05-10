# ADR-037: 内部サービス間認証を HMAC 署名 JWT (HS256) に切り替える

- Status: Accepted
- Date: 2026-05-10
- Deciders: kenyamaneko
- Related: ADR-036 (本 ADR の前提)、[overload-party-common#39](https://github.com/kenyamaneko/overload-party-common/issues/39) (ADR-034 全体トラッカー)

## Context

ADR-036 で gateway を完全パススルー化し、各サービスが client 公開 API を整備する方針を定めた。これに伴い、gateway → 各サービスへ「認証済み player_id」を引き渡す経路が全サービスに広がる。

### 現状の引き渡し方式

shop の Phase 3c (overload-party-shop#70) で確立した方式は以下:

- gateway が Firebase ID Token を検証し、Firebase UID → player_id を解決
- gateway は下流サービスへの HTTP 呼び出しに `X-Player-Id: <player_id>` という**平文 header** を付与
- 各サービスは `r.Header.Get("X-Player-Id")` で受け取り、空なら 401 を返す

card / newsfeed / account / scenario / news の Phase 3c でも同方式を踏襲する想定だった。

### 構造的問題

`X-Player-Id` 平文方式は **「ネットワーク境界が信頼できる」前提** に依存している:

1. **偽造**: gateway 以外からサービスに到達できる経路があれば、攻撃者は任意の `X-Player-Id` を付けて他人の課金 / 所持物 / デッキ等に成りすましアクセス可能
2. **境界の脆さ**: ClusterIP の前提が崩れる経路 (NetworkPolicy ミス / Ingress 設定漏れ / docker-compose の port 公開ミス / 別 pod への侵入) ができた瞬間に破綻する
3. **サービス数の増加**: ADR-036 で全サービスが `X-Player-Id` を信頼する構造になり、攻撃面の総和が拡大する

`X-Player-Id` 自体は単独で偽造耐性を持たないため、「playerId 偽造 = 他人の課金や所持物の閲覧 / 改竄」というインパクトが信頼境界の管理ミスに直結する。

## Decision

### 1. 認証 token を HMAC 署名 JWT (HS256) に変更する

gateway は Firebase 検証 + UID → player_id 解決後、以下の JWT を発行して下流サービスへ渡す:

```json
// header
{ "alg": "HS256", "typ": "JWT", "kid": "v1" }

// payload
{
  "sub": "<player_id>",
  "iss": "overload-party-gateway",
  "iat": 1730000000,
  "exp": 1730000300   // iat + 5 分
}
```

- header 名は `X-Internal-Auth`
- 共有秘密鍵は環境変数 `INTERNAL_AUTH_SECRET` で gateway + 各サービスに配布
- 鍵は十分なエントロピー (≥ 32 bytes random) で生成

### 2. 対称鍵 (HS256) を採用する

| 観点 | HS256 (対称) | RS256/EdDSA (非対称) |
|---|---|---|
| 鍵の本数 | 1 本 | 鍵ペア 1 組 |
| 鍵配布 | k8s Secret に共有 | privKey は gateway のみ、pubKey は ConfigMap で配布可 |
| サービス侵入時の影響 | 攻撃者が任意 playerID を捏造可能 | 検証しか出来ない (発行不可) |
| 検証性能 (参考) | ~50µs | ~150µs |
| ライブラリサポート | どの言語も標準 | どの言語も標準 |

現状のサービス構成 (gateway + 自社管理の数個のサービス、すべて単一 k8s クラスタ内) では HS256 で十分。RS256 が望ましいケース (サービス侵入面を gateway から隔離 / 第三者に検証だけ任せる) は本 ADR の scope 外とする。

将来的に RS256 へ移行可能な構造にしておくため、検証 middleware は **「鍵 ID から鍵を返す関数」** を引数に取る形で実装する (HS / RS の入れ替えは関数差し替えのみで完結する)。

### 3. 鍵ローテーション余地を最初から確保する

JWT header に `kid` (key ID) フィールドを最初から含める。複数鍵の同時検証許可を想定し、運用時の無停止ローテーションが可能な構造を担保する。具体的なローテーション運用手順は本 ADR の scope 外とする。

### 4. middleware 実装方針

各サービスの middleware は以下の責務を持つ:

- `X-Internal-Auth` header 取得 (空なら 401)
- JWT 検証 (署名 / `exp` / `iss`) — 失敗時 401
- 検証成功時、`sub` を context に `player_id` として書き込む
- handler は `c.GetString("player_id")` 等で context から取得 (header から直接読まない)

shop / card / newsfeed / account / scenario / news / matchmaking で同パターン。

### 5. 段階移行 (X-Player-Id との並走)

shop は既に `X-Player-Id` を採用済。card 以降の Phase 3c でいきなり JWT 化すると整合が崩れるため、以下の段階で進める:

- **Phase 1**: gateway + shop で HMAC JWT 化 (参照実装)。並走期は `X-Internal-Auth` を優先しつつ `X-Player-Id` も受け入れる
- **Phase 2**: card / newsfeed Phase 3c はこの方式で着手
- **Phase 3**: account / scenario / news / matchmaking 順次移行
- **Phase 4**: 全サービス移行完了後、`X-Player-Id` 受付を撤廃

## Consequences

### Positive

- **偽造防止**: 秘密鍵を持たない経路から playerID 偽造不可。サービス侵入や境界ミスへの耐性が獲得される
- **リプレイ防止**: 5 分 TTL で攻撃窓が極小
- **ネットワーク前提依存からの脱却**: ClusterIP / NetworkPolicy への依存を緩和し、defense in depth が効く
- **claim 拡張余地**: premium / role / feature flag 等を claim に乗せれば protocol 不変で拡張可能
- **構造化**: 標準 JWT なので各言語のエコシステムが揃っている (Go: `golang-jwt/jwt`、C#: `Microsoft.IdentityModel.Tokens`、TypeScript: `jose`)

### Negative

- **共有秘密鍵の運用**: k8s Secret 1 本だが、漏洩時の影響範囲は全サービスに及ぶ。ローテーション運用が必要になる
- **各サービスに middleware 追加**: ~15 行 / サービス。既存の `X-Player-Id` 取得処理は middleware に集約される
- **検証コスト**: ~50µs / req (Firebase 検証よりは桁違いに軽量)
- **shop の遡及対応**: 既に `X-Player-Id` で実装済の shop を JWT 方式に揃える PR が必要 (Phase 1)

### 緩和策

- **CI で固定 dev 鍵**: prod 鍵を CI に置かなくて良いため漏洩面は増えない
- **docker-compose**: 全サービスに同一 env を配るだけで済むため、ローカル環境構築は現状とほぼ同等
- **段階移行**: Phase 1〜4 の段階で並走期間を設けるため、一括変更を避けられる

## ローカル / CI / E2E への影響

### docker-compose

```yaml
x-internal-auth: &internal-auth
  INTERNAL_AUTH_SECRET: "dev-secret-not-for-prod"

services:
  gateway: { environment: { <<: *internal-auth } }
  card:    { environment: { <<: *internal-auth } }
  shop:    { environment: { <<: *internal-auth } }
```

全サービスに同一 env を配るだけ。dev 鍵は git に乗せて良い (本番鍵ではない)。本番鍵は External Secrets Operator / Sealed Secrets で別管理。

### サービスの handler ユニットテスト

middleware を**通さず** context に直接 player_id を植えるパターンに統一:

```go
// before
req.Header.Set("X-Player-Id", "player-123")

// after
c.Set("player_id", "player-123")
handler.ListDecks(c)
```

handler テストは JWT を一切意識しない。

### middleware 自体のユニットテスト

各サービス共通の検証ケース (~30 行で網羅):

- valid JWT → 200 + player_id が context にセットされる
- expired → 401
- 不正な署名 → 401
- header 欠落 → 401
- malformed JWT → 401

### gateway → service の統合テスト

各サービスの fake server (`apicardserverfake` 等) は middleware を通さず、JWT 検証はスキップ。代わりに gateway 側の outbound テストで「JWT が付いて出ているか」を fake で観測できる。

### e2e テスト (overload-party-e2e / docker-compose)

- **gateway 経由 (推奨)**: ランナーは Firebase emulator から ID Token を取得して gateway に投げる。JWT 発行は gateway が内部で行うため、ランナーは秘密鍵を意識しない
- **サービス直叩き**: ランナーが共有鍵で `signInternalJWT(playerID, secret, '5m')` を呼んで `X-Internal-Auth` 付きでサービスに直送

### CI (GitHub Actions)

```yaml
env:
  INTERNAL_AUTH_SECRET: "ci-test-secret-do-not-use-in-prod"
```

固定 dev 鍵で全テストが通る。prod 鍵を Actions Secrets に置く必要は無い (= CI からの漏洩面ゼロ)。

## 実装計画

### Phase 1: 参照実装 (gateway + shop)

- `internal/auth/internalauth/` パッケージを共有形で実装 (gateway 側で発行関数、shop 側で検証 middleware)
  - 配置先: gateway リポ内 (発行) と shop リポ内 (検証)。共通化は ADR-034 の wire 共有原則に従い、各リポがそれぞれ実装。重複は許容
- gateway: Firebase 検証後の middleware で JWT を発行し、各 client (shopclient / cardclient 等) が `X-Internal-Auth` を付けて送る
- shop: 既存の `X-Player-Id` 経由を JWT middleware 経由に置換 (並走期は両方受け入れ)

### Phase 2: card / newsfeed Phase 3c

card / newsfeed は新規に公開 API を整備するタイミングで HMAC JWT 化を同時に実施する。`X-Player-Id` は実装しない。

### Phase 3: 残りサービス順次移行

account / scenario / news / matchmaking で同パターン。

### Phase 4: X-Player-Id 撤廃

全サービスが JWT 方式に移行した後、`X-Player-Id` 受付ロジックを各サービスから削除する。

## Out of scope

以下は本 ADR の scope 外とする:

- **RS256 / EdDSA への移行**: 将来必要になったら別 ADR で扱う。本 ADR では「移行可能な抽象化」を担保するに留める
- **鍵ローテーション運用手順**: `kid` フィールドを担保するに留め、運用ランブックは別途
- **Firebase custom claims に player_id を埋め込む案**: ADR-036 で gateway 中央認証を維持と決定済のため、本 ADR では再考しない
- **mTLS / service mesh**: defense in depth のもう 1 層として有効だが、本 ADR の scope 外

## 関連

- ADR-036 (本 ADR の前提)
- [overload-party-common#39](https://github.com/kenyamaneko/overload-party-common/issues/39) — ADR-034 全体トラッカー
- Phase 1〜4 の各リポ issue は本 ADR マージ後に起票
