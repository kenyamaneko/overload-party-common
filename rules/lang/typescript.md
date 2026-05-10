## [lang/typescript] wire format

- C# server (battle) からの JSON ペイロードは CamelCase 形式なので、TS 側の型定義もそれに合わせる (snake_case ではない)。例: `gameID`, `myView`, `oppView`, `faceUp` 等
