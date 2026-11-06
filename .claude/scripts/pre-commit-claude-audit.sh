#!/usr/bin/env bash
# 監査の本体は keyandnotes-rules にあり、共通化のため、このリポでは対象リポのルートを渡して本体を呼ぶだけにする。
# worktree からも本体を見つけられるように、探索の起点は worktree でなく本リポの .git が指す位置にする。

set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"

# git 管理下でないリポでは commit が成立せず監査する対象がないため、何もしない。
git_common_dir="$(git -C "$repo_root" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || exit 0

search_dir="$(dirname "$git_common_dir")"
shared_script=""
while [ "$search_dir" != "/" ]; do
  search_dir="$(dirname "$search_dir")"
  if [ -x "${search_dir}/keyandnotes-rules/scripts/pre-commit-claude-audit.sh" ]; then
    shared_script="${search_dir}/keyandnotes-rules/scripts/pre-commit-claude-audit.sh"
    break
  fi
done

if [ -z "$shared_script" ]; then
  printf '⚠️  pre-commit-claude-audit: 共通の監査スクリプト (keyandnotes-rules/scripts/pre-commit-claude-audit.sh) が上位のディレクトリに見つからない。keyandnotes-rules を配置してください。監査不能のため fail-safe で commit ブロック。\n' >&2
  exit 2
fi

exec "$shared_script" "$repo_root"
