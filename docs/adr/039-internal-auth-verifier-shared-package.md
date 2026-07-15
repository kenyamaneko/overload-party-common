# ADR-039: internal-auth verifier を gateway 配信の Go パッケージ化する

## ステータス

Accepted (2026-05-11)

## 結論

5 リポで完全複製されていた HMAC JWT verifier + Gin middleware 一式を、契約の発行元である gateway から `overload-party-gateway/packages/internalauth-go/` として Go module 配信する (ADR-034 の「契約は発行元リポが publish」原則と整合)。重複 ~1,900 行が解消され、JWT lib 更新・401 形式変更・log/OTel 追加等が 1 PR で全サービスに伝播する。HeaderName / ExpectedIssuer 等が共有定数化されて「ヘッダ名は共通パッケージの定数を使う」規則を遵守でき、middleware の挙動 (401 ステータス・log 形式・span attribute 等) が drift しなくなる。

## 背景・課題

ADR-037 で導入した HMAC JWT verifier 一式 (`internal/adapter/internalauth/{verifier,verifier_test}.go` + `internal/port/internal_auth.go` + Gin middleware `internal/handler/rest/auth_middleware{,_test}.go` + HeaderName / ExpectedIssuer / PlayerIDContextKey 定数) が card / shop / news / scenario / account の **5 リポで完全複製** (`diff` で import path 1 行のみ差分)。verifier 一式 ~1,300 行 + middleware 一式 ~610 行 = 合計 ~1,900 行の重複。

これにより:

- JWT lib 更新やバグ修正を 5 箇所で同期する必要
- `[base] API 契約` 規則「ヘッダ名は共通パッケージの定数を使う」に対し HeaderName が repo-local で実質違反
- middleware が repo-local だと「定数は契約、middleware は実装の自由」と解釈される余地が残り、401 ステータス・log 形式・OTel span 等の drift リスクが残る
- 新規サービス追加のたびに複製が増える
