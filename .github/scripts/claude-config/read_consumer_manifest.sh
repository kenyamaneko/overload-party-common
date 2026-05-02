#!/usr/bin/env bash
# 消費リポの .claude/docs.yaml を読み layers / skip フラグを $GITHUB_OUTPUT に書き出す。
#
# 引数:
#   $1 = checkout 済みの消費リポのパス
#   $2 = 消費リポ名 (ログ表示用)

set -euo pipefail

consumer_dir="${1:?consumer dir required}"
repo="${2:?repo name required}"

if [ ! -f "$consumer_dir/.claude/docs.yaml" ]; then
  echo "::warning::Consumer $repo has no .claude/docs.yaml; skipping"
  echo "skip=true" >> "$GITHUB_OUTPUT"
  exit 0
fi

layers=$(yq -o=json '.layers' "$consumer_dir/.claude/docs.yaml" | jq -r 'join(" ")')
echo "layers=$layers" >> "$GITHUB_OUTPUT"
echo "skip=false" >> "$GITHUB_OUTPUT"
