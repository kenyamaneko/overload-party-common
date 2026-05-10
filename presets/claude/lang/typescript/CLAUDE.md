<!-- このファイルは overload-party-common/presets/claude/lang/typescript/CLAUDE.md から同期されています。編集はそちらで行ってください。 -->

## [lang/typescript] wire format

- C# server (battle) からの JSON ペイロードは CamelCase 形式なので、TS 側の型定義もそれに合わせる (snake_case ではない)。例: `gameID`, `myView`, `oppView`, `faceUp` 等
