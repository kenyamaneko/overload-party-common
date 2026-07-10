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

## 詳細

JWT の **issuer は gateway**、HeaderName / ExpectedIssuer 等の契約値は gateway が決めるため、verifier 一式 + Gin middleware を gateway のパッケージとして配信する。パッケージ構成は constants.go / port.go / verifier.go / middleware.go + go.mod (リファレンス実装は [card #19](https://github.com/kenyamaneko/overload-party-card/pull/19))。

middleware を同梱する判断:

- 5 consumer 全部 Gin で完全複製、Gin transitive dep は無痛
- HeaderName / PlayerIDContextKey は middleware だけが直接参照する。定数だけ共有して middleware は repo-local だと契約と実装の境界が曖昧になる
- 将来 echo / chi 等を採用する判断が出たら別 adapter package (`internalauth-echo-go` 等) を追加する。その時の split コストは新パッケージ追加のみで既存 consumer に影響しない

各サービスは:

- `internal/adapter/internalauth/` と `internal/port/internal_auth.go` を削除し shared package を import
- `internal/handler/rest/auth_middleware{,_test}.go` を削除し shared middleware を import
- handler 側の `c.GetString(PlayerIDContextKey)` 参照を shared 定数に切り替え
- `cmd/server/main.go` の verifier 構築を shared コンストラクタ呼び出しに変更

publish は gateway の `.github/workflows/publish.yaml` が自動 tag を打つ (ws-constants / api-gateway と同パターン)。`packages/internalauth-go/**` への変更が main に merge されると CI が `packages/internalauth-go/vX.Y.Z` を生成し、Go module proxy が GitHub から取得する。手動 `git tag` は禁止事項に反するので採用しない。npm 用の Cloudsmith 配信は不要。

### トレードオフ

- shared package が `github.com/gin-gonic/gin` に依存する。現状 5 consumer 全部 Gin なので無痛、将来他 framework 採用時は別 adapter package を追加
- 5 リポ retrofit PR が初期コスト (1 リポあたり ~12 ファイル変更)
- 契約変更時は version bump + 5 リポ追従が必要 (現状より同期手順は明示化される)
