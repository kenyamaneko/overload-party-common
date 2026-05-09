# Composite actions

`overload-party-*` リポの CI から共通利用する composite action 集。各 action は `kenyamaneko/overload-party-common/.github/actions/<name>@main` の形で import する。

private リポから利用するには、対象リポの **Settings → Actions → General → Access** が `Accessible from repositories owned by the user 'kenyamaneko'` に設定されている必要がある (ADR-033 で全リポに設定済の前提)。

## `setup-go-private-modules`

Cross-Repo Deps GitHub App token を発行し、`git insteadOf` で `overload-party-*` private Go module の解決を通す。詳細は [ADR-033](../../docs/adr/033-cross-repo-auth-github-app-migration.md) を参照。

```yaml
- uses: actions/checkout@v4
- uses: kenyamaneko/overload-party-common/.github/actions/setup-go-private-modules@main
  with:
    app-id: ${{ vars.CROSS_REPO_DEPS_APP_ID }}
    private-key: ${{ secrets.CROSS_REPO_DEPS_APP_PRIVATE_KEY }}
- uses: actions/setup-go@v5
```

## `setup-cloudsmith-auth`

GitHub Actions OIDC を Cloudsmith service account の short-lived API key (2 時間有効) と交換し、NuGet / npm client が `keyandnotes/overload-party-{nuget,npm}` repository を読めるよう CI 環境を設定する。consumer (`dotnet restore` / `npm install`) 用途。

呼び出し側 job に `permissions.id-token: write` が必要。

```yaml
jobs:
  build:
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: kenyamaneko/overload-party-common/.github/actions/setup-cloudsmith-auth@main
        with:
          role: reader
          formats: "nuget,npm"
      - run: dotnet restore
```

inputs:

| name | required | values | 用途 |
|---|---|---|---|
| `role` | yes | `reader` / `publisher` | impersonate する Cloudsmith SA。consumer は `reader` |
| `formats` | yes | `nuget` / `npm` / `nuget,npm` | 設定する client。必要なものだけ |

NuGet は `~/.nuget/NuGet/NuGet.Config` (user-level) に `cloudsmith-overload-party-nuget` という名前でフィードと credential を追加する。npm は `${HOME}/.npmrc` に Cloudsmith registry の `_authToken` を追記する。

## `publish-to-cloudsmith`

publisher SA を OIDC で impersonate し、与えられた package を Cloudsmith に push する。publisher リポ (common / battle / shop) の publish workflow 用途。

呼び出し側 job に `permissions.id-token: write` が必要。

```yaml
jobs:
  publish:
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - run: dotnet pack -c Release
      - uses: kenyamaneko/overload-party-common/.github/actions/publish-to-cloudsmith@main
        with:
          format: nuget
          package-path: ./bin/Release/OverloadParty.GameDesignConstants.0.2.0.nupkg
```

inputs:

| name | required | values | 用途 |
|---|---|---|---|
| `format` | yes | `nuget` / `npm` | push する package format |
| `package-path` | yes | path | `.nupkg` ファイル / `.tgz` ファイル / `package.json` を含むディレクトリ |
