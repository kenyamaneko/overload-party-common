> NOTE: このファイルは原則として人間が運用する。例外的に許可があった場合のみClaude Codeが修正しても良い。

## [lang/csharp] 設計思想

- 下流で例外を catch せず、handle できる層まで自動伝搬させる
  - 理由: エラーハンドリングを簡潔かつ責務を分離して保守性を高める
- ASP.NET 系では `app.UseExceptionHandler` を唯一の catch 地点とする

## [lang/csharp] コーディング方針

- `FirstOrDefault` + silent default を禁止する。契約上存在するなら `First()` または `MustGet` 系を使う
- `switch` / `if/else` には必ず default を書き、`throw` とする。sentinel 値 (空文字・0・`"?"`) を返さない
- 値を返す分岐には switch 式を使い、default アームは `throw`。副作用を伴う分岐には switch 文を使う
- フィルタ・変換・集計には LINQ を使う。副作用を伴うループには `foreach` 文を使い、`List<T>.ForEach()` は使わない

## [lang/csharp] パーサ方針

- YAML / JSON 等の構造化データパーサで unknown 値を silent drop しない。typo 検知のため全パーサで unknown → throw を徹底する

## [lang/csharp] テスト方針

- テストのグルーピングはコメント区切りでなく xUnit のネストクラスで構造化する。被テストメンバ単位でネストクラスを作り、メソッド名からは冗長なメンバ名接頭辞を落とす
  - ネストクラス名が内部で参照する型 (enum・モデル型) と衝突する場合は接尾辞で回避する (例: `PhaseConversion` / `FieldAccessor`)
- 入力と期待値だけが異なる同一の振る舞いは `[Theory]` + `[InlineData]` でケースを表化する。setup とアサーション構造が同一で、primitive な入力/期待値のみ異なる場合に限る
  - 生成 (factory) や mock の配線が構造的に異なるケースは `[Theory]` 化せず `[Fact]` のまま個別に残す

## [lang/csharp] docs コメント

- 型・メソッドには XML doc コメントを書く。`<summary>` を必須とし、戻り値があれば `<returns>`、引数があれば各 `<param>` を必須とする

## [lang/csharp] 命名

- 非同期メソッドは Async サフィックスを付ける
- プロパティは名詞にする
  - getter に動詞を付けない
- インターフェースは I で始める
