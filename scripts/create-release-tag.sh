#!/usr/bin/env bash
# 直近のリリースタグを指定された桁だけ上げ、チェックアウト中のコミットにタグを打って push する。
# サービスリポのルートで実行する。バージョン番号の上げ幅の判断基準は
# keyandnotes-rules の principles「バージョニング」に従う。
#
# Usage: create-release-tag.sh <major|minor|patch>

set -euo pipefail

FIRST_VERSION="0.1.0"

BUMP="${1:-}"
case "${BUMP}" in
  major | minor | patch) ;;
  *)
    echo "error: bump level must be one of major / minor / patch (got '${BUMP}')" >&2
    exit 1
    ;;
esac

last_tag="$(git tag -l 'v*.*.*' | sort -V | tail -1)"

if [ -z "${last_tag}" ]; then
  version="${FIRST_VERSION}"
else
  # 桁が数値でないタグから採番すると誤った版を打つため、vX.Y.Z 以外は弾く
  if [[ ! "${last_tag}" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    echo "error: latest tag '${last_tag}' is not a vX.Y.Z release tag. Remove it before releasing." >&2
    exit 1
  fi
  major="${BASH_REMATCH[1]}"
  minor="${BASH_REMATCH[2]}"
  patch="${BASH_REMATCH[3]}"
  case "${BUMP}" in
    major) version="$((major + 1)).0.0" ;;
    minor) version="${major}.$((minor + 1)).0" ;;
    patch) version="${major}.${minor}.$((patch + 1))" ;;
  esac
fi

tag="v${version}"
git tag "${tag}"
git push origin "${tag}"
echo "created ${tag}"
