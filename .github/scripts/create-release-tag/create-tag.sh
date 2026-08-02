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
  IFS='.' read -r major minor patch <<< "${last_tag#v}"
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
