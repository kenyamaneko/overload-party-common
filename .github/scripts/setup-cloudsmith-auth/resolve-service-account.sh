#!/usr/bin/env bash
set -euo pipefail

case "${ROLE}" in
  reader)
    slug="overload-party-reader"
    ;;
  publisher)
    slug="overload-party-publisher"
    ;;
  *)
    echo "::error::role must be 'reader' or 'publisher' (got '${ROLE}')"
    exit 1
    ;;
esac
echo "service_slug=${slug}" >> "${GITHUB_OUTPUT}"
