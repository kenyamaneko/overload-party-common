#!/usr/bin/env bash
# 前回タグからのパッケージ変更を検知し、次バージョンを算出する。
# publish.yaml から呼ばれ、結果は $GITHUB_OUTPUT に書き出される。
#
# game-design-constants の 3 形態を publish:
#
#   - Go module       : packages/game-design-constants
#   - C# NuGet csproj : packages/game-design-constants-dotnet
#   - npm package     : packages/game-design-constants-npm
#
# 各 publish 単位は独自のタグプレフィックス "packages/{name}/v{version}" を持つ。

set -euo pipefail

TARGET="${1:-auto}"
BUMP="${2:-patch}"

# (package_name, tag_prefix, watch_path)
PACKAGES=(
  "game-design-constants:packages/game-design-constants:packages/game-design-constants/"
  "game-design-constants-dotnet:packages/game-design-constants-dotnet:packages/game-design-constants-dotnet/"
  "game-design-constants-npm:packages/game-design-constants-npm:packages/game-design-constants-npm/"
  "pubsub-events:packages/pubsub-events:packages/pubsub-events/"
)

compute_version() {
  local prefix="$1" bump="$2"
  local last_tag
  last_tag=$(git tag -l "${prefix}/v*" | sort -V | tail -1)
  if [ -z "$last_tag" ]; then
    echo "0.1.0"
    return
  fi
  local current major minor patch
  current="${last_tag#"${prefix}/v"}"
  IFS='.' read -r major minor patch <<< "$current"
  case "$bump" in
    major) echo "$((major + 1)).0.0" ;;
    minor) echo "${major}.$((minor + 1)).0" ;;
    *)     echo "${major}.${minor}.$((patch + 1))" ;;
  esac
}

has_changes() {
  local prefix="$1" path="$2"
  local last_tag
  last_tag=$(git tag -l "${prefix}/v*" | sort -V | tail -1)
  if [ -z "$last_tag" ]; then
    return 0
  fi
  ! git diff --quiet "$last_tag" -- "$path"
}

CHANGED=()

for entry in "${PACKAGES[@]}"; do
  IFS=':' read -r name prefix path <<< "$entry"

  case "$TARGET" in
    auto)
      if has_changes "$prefix" "$path"; then
        CHANGED+=("$name")
      fi
      ;;
    "$name")
      CHANGED+=("$name")
      ;;
  esac
done

# GitHub Actions の step output はハイフンを参照できないためアンダースコアに変換
for entry in "${PACKAGES[@]}"; do
  IFS=':' read -r name prefix _ <<< "$entry"
  key=$(echo "$name" | tr '-' '_')

  if [[ " ${CHANGED[*]} " == *" $name "* ]]; then
    echo "${key}=true" >> "$GITHUB_OUTPUT"
    ver=$(compute_version "$prefix" "$BUMP")
    echo "${key}_version=$ver" >> "$GITHUB_OUTPUT"
    echo "$name → v$ver"
  else
    echo "${key}=false" >> "$GITHUB_OUTPUT"
  fi
done

ANY_CHANGED=false
if [ ${#CHANGED[@]} -gt 0 ]; then
  ANY_CHANGED=true
fi
echo "any_changed=$ANY_CHANGED" >> "$GITHUB_OUTPUT"
echo "changed_list=${CHANGED[*]:-}" >> "$GITHUB_OUTPUT"
