#!/usr/bin/env bash
set -euo pipefail

generated=(
  packages/game-design-constants/
  packages/game-design-constants-dotnet/
  packages/game-design-constants-npm/
)

if ! git diff --exit-code -- "${generated[@]}"; then
  echo "::error::Generated files are out of sync. Run generate scripts and commit."
  git diff --stat
  exit 1
fi
