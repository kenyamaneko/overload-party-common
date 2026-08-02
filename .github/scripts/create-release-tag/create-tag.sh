#!/usr/bin/env bash
# 直近のリリースタグを指定された桁だけ上げ、チェックアウト中のコミットにタグを打って push する。
set -euo pipefail

FIRST_VERSION="0.1.0"

case "${BUMP}" in
  major | minor | patch) ;;
  *)
    echo "::error::Unknown bump level '${BUMP}'. Choose one of major / minor / patch."
    exit 1
    ;;
esac

last_tag="$(git tag -l 'v*.*.*' | sort -V | tail -1)"

if [ -z "${last_tag}" ]; then
  version="${FIRST_VERSION}"
else
  # 桁が数値でないタグから採番すると誤った版を打つため、vX.Y.Z 以外は弾く
  if [[ ! "${last_tag}" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    echo "::error::Latest tag '${last_tag}' is not a vX.Y.Z release tag. Remove it before releasing."
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
