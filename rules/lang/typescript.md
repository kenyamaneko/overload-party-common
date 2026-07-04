> NOTE: このファイルは原則として人間が運用する。例外的に許可があった場合のみClaude Codeが修正しても良い。

# overload-party TypeScript 固有ルール (overlay)

共通ルール (`keyandnotes-rules` の `rules/lang/typescript.md`) を土台に、overload-party 固有分を定義する。CLAUDE.md の「ファイル編集前のルール適用手順」に従い、TS 編集時に共通とあわせて Read する。

## [lang/typescript] wire format

- C# server (battle) からの JSON ペイロードは CamelCase 形式なので、TS 側の型定義もそれに合わせる (snake_case ではない)。例: `gameID`, `myView`, `oppView`, `faceUp` 等
