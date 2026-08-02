#!/usr/bin/env bash
set -euo pipefail

: "${VERSION:?VERSION env required}"

npm install
npm version "${VERSION}" --no-git-tag-version
npm run build
