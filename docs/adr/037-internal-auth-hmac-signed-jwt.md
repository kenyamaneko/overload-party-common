# ADR-037: 内部サービス間認証を HMAC 署名 JWT (HS256) に切り替える

## ステータス

Superseded by [ADR-057](057-cloudrun-service-auth-iam-and-rs256.md) (2026-07-24)。旧ステータス: Accepted (2026-05-10)

内部認証を HMAC 署名 JWT (HS256) とする決定は ADR-057 が置き換える。ADR-057 は署名を非対称鍵 (RS256) に変更し、サービス間の到達制御を Cloud Run の呼び出し IAM に分離する。検証実装の共有パッケージ化 ([ADR-039](039-internal-auth-verifier-shared-package.md)) の枠組みは維持され、署名方式のみが変わる。今後は ADR-057 を参照のこと。

## 結論

`X-Player-Id` 平文 header による player_id 引き渡しはネットワーク境界の信頼に依存し偽造耐性がないため、gateway が発行する **HMAC 署名 JWT (HS256、header 名 `X-Internal-Auth`、TTL 5 分)** に切り替え、JWT の `sub` クレームを player_id の唯一の信頼源とする。秘密鍵を持たない経路からの playerID 偽造が不可能になってサービス侵入や境界ミスへの耐性が得られ、5 分 TTL でリプレイの攻撃窓も極小になる。ClusterIP / NetworkPolicy への依存が緩和されて defense in depth が効き、将来は claim 拡張 (premium / role / feature flag 等) も protocol 不変で可能。標準 JWT なので各言語のエコシステム (Go: `golang-jwt/jwt`、C#: `Microsoft.IdentityModel.Tokens`、TypeScript: `jose`) がそのまま使える。対称鍵で足りるのは、鍵を共有するのが単一クラスタ内の自社管理サービスに限られるためで、非対称鍵による発行元と検証者の隔離は将来必要になれば別途扱う。

## 背景・課題

ADR-036 で gateway を完全パススルー化し、各サービスが client 公開 API を整備する方針を定めた。これに伴い、gateway → 各サービスへ「認証済み player_id」を引き渡す経路が全サービスに広がる。

### 現状の引き渡し方式

shop の Phase 3c (overload-party-shop#70) で確立した方式は以下:

- gateway が Firebase ID Token を検証し、Firebase UID → player_id を解決
- gateway は下流サービスへの HTTP 呼び出しに `X-Player-Id: <player_id>` という**平文 header** を付与
- 各サービスは `r.Header.Get("X-Player-Id")` で受け取り、空なら 401 を返す

card / account / scenario / news の Phase 3c でも同方式を踏襲する想定だった。

### 構造的問題

`X-Player-Id` 平文方式は **「ネットワーク境界が信頼できる」前提** に依存している:

1. **偽造**: gateway 以外からサービスに到達できる経路があれば、攻撃者は任意の `X-Player-Id` を付けて他人の課金 / 所持物 / デッキ等に成りすましアクセス可能
2. **境界の脆さ**: ClusterIP の前提が崩れる経路 (NetworkPolicy ミス / Ingress 設定漏れ / docker-compose の port 公開ミス / 別 pod への侵入) ができた瞬間に破綻する
3. **サービス数の増加**: ADR-036 で全サービスが `X-Player-Id` を信頼する構造になり、攻撃面の総和が拡大する

`X-Player-Id` 自体は単独で偽造耐性を持たないため、「playerId 偽造 = 他人の課金や所持物の閲覧 / 改竄」というインパクトが信頼境界の管理ミスに直結する。

## Amendment: 2026-05-10 shop Phase 1 の X-Player-Id 並走廃止 + Phase 4 削除

初版では shop が `X-Player-Id` を実装済の前提で「Phase 1 は `X-Internal-Auth` と `X-Player-Id` の両方を受け入れる並走期間」を設け、後続の Phase 4 で `X-Player-Id` 受付を撤廃する設計だった。

shop は gateway より先行して稼働する運用が予定されておらず、並走期間を保つコスト (検証経路の二重化 / fallback テストの維持) が利得に見合わないため、Phase 1 から JWT 一本化する形に変更する。これにより全サービスで `X-Player-Id` 受付を持つフェーズが消えるため、Phase 4 (X-Player-Id 撤廃) は不要となり削除する。
