> NOTE: このファイルは原則として人間が運用する。例外的に許可があった場合のみClaude Codeが修正しても良い。

# overload-party 固有ルール (overlay)

共通ルール (`keyandnotes-rules` の `rules/principles.md`) を土台に、overload-party 固有の方針を定義する。本ファイルは CLAUDE.md から共通ルールに続けて @import される。共通と衝突する場合は本ファイルを優先する (共通 principles「[base] ルールの階層と優先順位」)。

## [overload-party] メッセージング

- Pub/Sub トピック名は k8s ConfigMap で外部化し、コードからは環境変数経由で参照する
