#!/usr/bin/env bash
# common の claude/ 配下を消費リポの作業ツリーに同期する。
#
# 引数:
#   $1 = checkout 済みの common リポのパス
#   $2 = checkout 済みの消費リポのパス
#   $3 = スペース区切りのレイヤ名
#
# 動作:
#   各レイヤの top-level *.md を $consumer/.claude-common/<layer>/ に
#   skills/*.md を $consumer/.claude/skills/ にコピーする

set -euo pipefail

common_dir="${1:?common dir required}"
consumer_dir="${2:?consumer dir required}"
layers="${3:?layers required}"

for layer in $layers; do
  src="$common_dir/claude/$layer"
  if [ ! -d "$src" ]; then
    echo "::error::Layer $layer not found in common"
    exit 1
  fi

  mkdir -p "$consumer_dir/.claude-common/$layer"
  find "$src" -maxdepth 1 -type f -name "*.md" -exec cp -v {} "$consumer_dir/.claude-common/$layer/" \;

  if [ -d "$src/skills" ]; then
    mkdir -p "$consumer_dir/.claude/skills"
    cp -rv "$src/skills/." "$consumer_dir/.claude/skills/"
  fi
done
