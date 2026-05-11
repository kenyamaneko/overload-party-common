# ADR-039: internal-auth verifier を gateway 配信の Go パッケージ化する

- Status: Proposed
- Date: 2026-05-11
- Deciders: kenyamaneko
- Related: ADR-037 (internal-auth HMAC JWT 化)、ADR-034 (API 契約 SSoT と Go module 配信パターン)

## Context

ADR-037 で導入した HMAC JWT verifier 一式 (`internal/adapter/internalauth/{verifier,verifier_test}.go` + `internal/port/internal_auth.go` + middleware の HeaderName / ExpectedIssuer / PlayerIDContextKey 定数) が card / shop / news / scenario / account の **5 リポで完全複製** (`diff` で import path 1 行のみ差分)。

これにより:

- JWT lib 更新やバグ修正を 5 箇所で同期する必要
- `[base] API 契約` 規則「ヘッダ名は共通パッケージの定数を使う」に対し HeaderName が repo-local で実質違反
- 新規サービス追加のたびに複製が増える

## Decision

JWT の **issuer は gateway**、HeaderName / ExpectedIssuer 等の契約値は gateway が決めるため、verifier 一式を `overload-party-gateway/packages/internalauth-go/` として Go module 配信する (ADR-034 の「契約は発行元リポが publish」原則と整合)。

各サービスは:

- `internal/adapter/internalauth/` と `internal/port/internal_auth.go` を削除し shared package を import
- middleware の HeaderName / PlayerIDContextKey を shared 定数参照に置換
- `cmd/server/main.go` の verifier 構築を shared コンストラクタ呼び出しに変更

publish は **git tag のみ** (`git tag packages/internalauth-go/v0.1.0 && git push --tags`)。Go module proxy が GitHub から取得する。npm 用の Cloudsmith 配信は不要。

## Consequences

- 重複 ~1,300 行解消、JWT lib 更新 / バグ修正は 1 PR で全サービスに伝播
- HeaderName / ExpectedIssuer 等が共有定数化され API 契約規則を遵守
- 5 リポ retrofit PR が初期コスト (1 リポあたり ~10 ファイル変更)
- 契約変更時は version bump + 5 リポ追従が必要 (現状より同期手順は明示化される)

## Implementation

1. **gateway/packages/internalauth-go/** を新設: verifier.go / verifier_test.go / port.go / constants.go + go.mod (card #19 のコードがベース)
2. tag `packages/internalauth-go/v0.1.0` を打って配信
3. card / shop / news / scenario / account を順次 retrofit (並列可)

## References

- ADR-037 / ADR-034
- 既存リファレンス実装: [card #19](https://github.com/kenyamaneko/overload-party-card/pull/19)
