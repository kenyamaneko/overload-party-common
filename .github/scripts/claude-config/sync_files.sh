#!/usr/bin/env bash
# common の claude/ 配下を消費リポの作業ツリーに同期する。
#
# 引数:
#   $1 = checkout 済みの common リポのパス
#   $2 = checkout 済みの消費リポのパス
#   $3 = スペース区切りのレイヤ名
#
# 動作:
#   各レイヤの top-level *.md を $consumer/.claude/docs/<bucket>/ に
#   skills/*.md を $consumer/.claude/skills/ にコピーする
#
#   bucket は base / flow / lang のいずれか。flow/<variant> や lang/<variant>
#   のレイヤは consumer 側で variant を落とす (1 リポに 1 variant しかないため)。

set -euo pipefail

common_dir="${1:?common dir required}"
consumer_dir="${2:?consumer dir required}"
layers="${3:?layers required}"

for layer in $layers; do
  src="$common_dir/claude-config/$layer"
  if [ ! -d "$src" ]; then
    echo "::error::Layer $layer not found in common"
    exit 1
  fi

  case "$layer" in
    flow/*) bucket="flow" ;;
    lang/*) bucket="lang" ;;
    *)      bucket="$layer" ;;
  esac

  mkdir -p "$consumer_dir/.claude/docs/$bucket"
  find "$src" -maxdepth 1 -type f -name "*.md" -exec cp -v {} "$consumer_dir/.claude/docs/$bucket/" \;

  if [ -d "$src/skills" ]; then
    mkdir -p "$consumer_dir/.claude/skills"
    cp -rv "$src/skills/." "$consumer_dir/.claude/skills/"
  fi
done
