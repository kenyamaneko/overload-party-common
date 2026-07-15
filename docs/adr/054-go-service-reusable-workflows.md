# ADR-054: Go サービスの CI / Deploy workflow を common の reusable workflow に集約する

## ステータス

Accepted (2026-07-11)

## 結論

GKE の Go サービス 8 リポ (shop / gateway / account / card / matchmaking / scenario / news / support) でほぼ同形の ci.yaml / deploy.yaml を、common の **reusable workflow** (`workflow_call`) に集約する。common に `go-service-ci.yaml` と `go-service-deploy.yaml` を置き、各リポの workflow は inputs を渡すだけの caller にする。リポ固有の処理は inputs と、各リポに置くスクリプトの呼び出しで吸収する。battle (C#) と client (TypeScript) は同形のリポがないため対象外とする。

同形 workflow の手書き複製が横展開漏れの構造要因であり (2026-07-11 の CI/CD 監査で govulncheck / image-scan / concurrency / detect-code-change などの欠落約 20 件がこの複製から発生)、集約後は共通部分の変更が 1 箇所で全リポに効くため、この種のずれは構造的に生じなくなる。

## 背景・課題

8 リポの ci.yaml は changes (コード変更判定) / lint / 単体テスト / 結合テスト / image-scan / codegen-sync のほぼ同一構成で、deploy.yaml は全リポ同形 (main push → sha イメージ push) である。しかし各リポに手書き複製されているため、標準の変更 (ADR-038 / ADR-052 / detect-code-change 導入など) のたびに 8〜9 本の横展開 PR が必要になり、監査のたびに漏れが見つかる。

composite action (ADR-033 / ADR-052) は step 単位の共有であり、job 構成 (トリガー / concurrency / needs / permissions / timeout) の複製は解消できない。

## 不採用案

### composite action の積み増し

step 単位の共有は既に行っており、今回の監査で見つかった欠落の大半を占める job 構成のずれが残るため不採用。

### ci のみの集約

deploy.yaml (約 60 行 × 8 リポ) の複製が残る。deploy は ci より同質性が高く集約が容易であり、分ける理由がないため不採用。

### workflow のテンプレート生成

SSoT からの生成は既存の codegen 文化と整合するが、生成物である workflow の複製自体は残り、再生成の横展開が必要になるため不採用。reusable workflow なら参照だけで済む。
