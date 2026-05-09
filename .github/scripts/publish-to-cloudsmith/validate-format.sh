#!/usr/bin/env bash
set -euo pipefail

case "${FORMAT}" in
  nuget|npm)
    ;;
  *)
    echo "::error::format must be 'nuget' or 'npm' (got '${FORMAT}')"
    exit 1
    ;;
esac
