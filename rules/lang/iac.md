> NOTE: このファイルは原則として人間が運用する。例外的に許可があった場合のみClaude Codeが修正しても良い。

# overload-party IaC 固有ルール (overlay)

共通ルール (`keyandnotes-rules` の `rules/lang/iac.md`) を土台に、overload-party 固有分を定義する。CLAUDE.md の「ファイル編集前のルール適用手順」に従い、IaC 編集時に共通とあわせて Read する。

## [lang/iac] Secret / 認証情報

- k8s Secret を介した env への直接注入は新規採用しない
