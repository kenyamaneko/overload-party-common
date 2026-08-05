#!/usr/bin/env bash
# Pre-commit machine-checkable rule audit.
# 機械検出可能なルール違反を git commit 直前に検出する。
# 出典: rules/principles.md, rules/lang/iac.md, memory/feedback_no_adr_refs_in_code_comments.md ほか
# 意味解釈が必要なルール (What コメント / マジックナンバー / 一関数一責務 等) は本 hook 対象外。
#
# 違反の分類:
# - HARD: exit 2 で commit ブロック (Claude の見落とし、意図的に残す場面が想像できないもの)
# - SOFT: permissionDecision=ask で user に確認 (ユーザが意図して残すケースが現実的にあるもの)
#
# 呼び出し: common/.claude/settings.json の PreToolUse hook (Bash matcher) から stdin 経由で JSON を受け取る。

set -uo pipefail

input=$(cat)
if [ -z "$input" ]; then
  printf '⚠️  pre-commit-machine-audit: 空入力で起動。audit 不能のため fail-safe で commit ブロック。\n' >&2
  exit 2
fi
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)
jq_rc=$?
if [ "$jq_rc" -ne 0 ]; then
  printf '⚠️  pre-commit-machine-audit: JSON parse 失敗 (jq exit %d)。audit 不能のため fail-safe で commit ブロック。\n' "$jq_rc" >&2
  exit 2
fi

# 文字列リテラル / HEREDOC 内の偶発マッチを避けるため、コマンドの「実行可能部分」だけを抽出。
# 1. HEREDOC 開始 (<<EOF / <<'EOF' / <<"EOF") 以降を切り捨て
# 2. "..." / '...' で括られた内容を空に置換
exec_cmd=$(printf '%s' "$cmd" | sed -E '/<</q' | sed -E 's/"[^"]*"//g; s/'\''[^'\'']*'\''//g')

# --- (7/HARD) git tag 手動禁止 (principles.md 禁止事項) ---
# 書込み系のみブロック、読み取り系 (-l / --list 等) は通過。
if printf '%s' "$exec_cmd" | grep -qE '(^|[[:space:]&|;`(])git[[:space:]]+tag[[:space:]]+(-a|-s|-f|-m|[^-[:space:]])'; then
  printf '❌ git tag 手動打ちは禁止です (principles.md 禁止事項)。CI が自動生成します。\n' >&2
  exit 2
fi

# --- audit 対象判定: git commit を含むコマンドのみ ---
if ! printf '%s' "$exec_cmd" | grep -qE '(^|[[:space:]&|;`(])git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?commit'; then
  exit 0
fi
if printf '%s' "$exec_cmd" | grep -qE 'git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?commit[[:space:]]+(--help|-h)([[:space:]]|$)'; then
  exit 0
fi

# --- ステージ操作と commit の同一呼び出し禁止 ---
# PreToolUse は commit の実行前に発火するため、同じ呼び出しに書いたステージ操作は監査時点でまだ index に載っていない。
if printf '%s' "$exec_cmd" | grep -qE '(^|[[:space:]&|;`(])git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?(add|rm|mv)([[:space:]]|$)'; then
  printf '❌ git add / git rm / git mv を git commit と同じ Bash 呼び出しに書かないでください。hook がステージ済み差分を読めず監査が素通りします。ステージ操作を先に別の呼び出しで完了させてください。\n' >&2
  exit 2
fi
if printf '%s' "$exec_cmd" | grep -qE '(^|[[:space:]&|;`(])git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?checkout[[:space:]].*[[:space:]]--[[:space:]]'; then
  printf '❌ git checkout <ref> -- <path> を git commit と同じ Bash 呼び出しに書かないでください。index を書き換えるため hook がステージ済み差分を読めず監査が素通りします。先に別の呼び出しで完了させてください。\n' >&2
  exit 2
fi
if printf '%s' "$exec_cmd" | grep -qE '(^|[[:space:]&|;`(])git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?restore[[:space:]].*--staged'; then
  printf '❌ git restore --staged を git commit と同じ Bash 呼び出しに書かないでください。index を書き換えるため hook がステージ済み差分を読めず監査が素通りします。先に別の呼び出しで完了させてください。\n' >&2
  exit 2
fi
commit_flags=$(printf '%s' "$exec_cmd" | sed -E 's/.*git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?commit//' | sed -E 's/[;&|].*//')
if printf '%s' "$commit_flags" | grep -qE '(^|[[:space:]])(--all|--include|--patch|-[A-Za-z]*[aip][A-Za-z]*)([[:space:]]|$)'; then
  printf '❌ git commit の -a / --all / -i / --include / -p / --patch は使わないでください。commit 自身がステージを兼ねるため hook が差分を読めません。git add を別の呼び出しで済ませてから commit してください。\n' >&2
  exit 2
fi

# --- target repo cwd 解決 ---
# commit コマンドの書き方で監査がスキップされないようにするため
target_cwd=$(printf '%s' "$cmd" | grep -oE 'git[[:space:]]+-C[[:space:]]+"?[^"&|;[:space:]]+' | head -1 | sed -E 's|^git[[:space:]]+-C[[:space:]]+"?||')
if [ -z "$target_cwd" ]; then
  before_commit=$(printf '%s' "$cmd" | sed -E 's/git[[:space:]]+commit.*//')
  target_cwd=$(printf '%s' "$before_commit" | grep -oE '(^|[&|;[:space:]])cd[[:space:]]+"?[^"&|;[:space:]]+' | tail -1 | sed -E 's|.*cd[[:space:]]+"?||')
fi
if [ -z "$target_cwd" ]; then
  target_cwd=$(printf '%s' "$input" | jq -r '.cwd // ""' 2>/dev/null)
fi
if [ -z "$target_cwd" ]; then
  target_cwd=$(pwd)
fi
if ! cd "$target_cwd" 2>/dev/null; then
  printf '⚠️  pre-commit-machine-audit: cd "%s" 失敗、audit をスキップ\n' "$target_cwd" >&2
  exit 0
fi
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  exit 0
fi

staged=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null)
if [ -z "$staged" ]; then
  exit 0
fi

# 本 script 自身は error message にルール名 (ADR / GCP 等) を保持するため、自己 audit 対象から除外する。
self_path=".claude/scripts/pre-commit-machine-audit.sh"
is_self() {
  case "$1" in
    "$self_path"|*/"$self_path") return 0 ;;
    *) return 1 ;;
  esac
}

hard_violations=()
soft_violations=()

# --- (1/HARD) ADR 番号参照 in code/yaml (memory:feedback_no_adr_refs_in_code_comments) ---
while IFS= read -r f; do
  [ -z "$f" ] && continue
  is_self "$f" && continue
  case "$f" in
    docs/adr/*|*/docs/adr/*) continue ;;
    docs/ARCHITECTURE.md|*/docs/ARCHITECTURE.md|ARCHITECTURE.md) continue ;;
    *.md) continue ;;
    *CHANGELOG*) continue ;;
  esac
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    hard_violations+=("$f: $line  [ADR 番号を code/yaml コメントに書かない — memory:feedback_no_adr_refs_in_code_comments]")
  done < <(git diff --cached -U0 -- "$f" 2>/dev/null | grep -nE '^\+.*\bADR-[0-9]+\b' || true)
done <<< "$staged"

# --- (2/SOFT) CLAUDE.md 編集 (principles.md 禁止事項) ---
# 例外: ユーザ自身が CLAUDE.md を更新して commit を Claude に依頼するケースがある
while IFS= read -r f; do
  [ -z "$f" ] && continue
  is_self "$f" && continue
  case "$f" in
    CLAUDE.md|*/CLAUDE.md)
      soft_violations+=("$f  [CLAUDE.md は Claude が書き換えない — principles.md 禁止事項]")
      ;;
  esac
done <<< "$staged"

# --- (3/SOFT) rules/ 配下 編集 (principles.md 禁止事項) ---
# 例外: 明示許可があった場合のみ Claude Code が修正可 (memory:feedback_rules_human_only)
while IFS= read -r f; do
  [ -z "$f" ] && continue
  is_self "$f" && continue
  case "$f" in
    rules/*|*/rules/*)
      soft_violations+=("$f  [rules/ 配下は Claude が書き換えない — principles.md 禁止事項]")
      ;;
  esac
done <<< "$staged"

# --- (4/HARD) terraform variable に default 禁止 (lang/iac.md) ---
while IFS= read -r f; do
  [ -z "$f" ] && continue
  is_self "$f" && continue
  case "$f" in *.tf) ;; *) continue ;; esac
  hits=$(git diff --cached -U20 -- "$f" 2>/dev/null | awk '
    BEGIN { in_var = 0; depth = 0 }
    /^@@/ { in_var = 0; depth = 0; next }
    /^[+ ]variable[[:space:]]+"/ { in_var = 1; depth = 0 }
    in_var && /\{/ { depth++ }
    in_var && /\}/ { depth--; if (depth <= 0) in_var = 0 }
    in_var && /^\+[[:space:]]*default[[:space:]]*=/ { print "default = (variable block 内)" }
  ' || true)
  if [ -n "$hits" ]; then
    hard_violations+=("$f  [terraform variable に default = は禁止 — lang/iac.md]")
  fi
done <<< "$staged"

# --- (5/HARD) GCP 表記禁止 (principles.md 禁止事項) ---
while IFS= read -r f; do
  [ -z "$f" ] && continue
  is_self "$f" && continue
  case "$f" in
    *.lock|*.sum|*.png|*.jpg|*.jpeg|*.svg|*.ico|*.pdf|*.gif|*.woff*) continue ;;
  esac
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    hard_violations+=("$f: $line  [Google Cloud を GCP と表記しない — principles.md 禁止事項]")
  done < <(git diff --cached -U0 -- "$f" 2>/dev/null | grep -nE '^\+.*\bGCP\b' | grep -v 'GCPRO\|GCP_' || true)
done <<< "$staged"

# --- (6/HARD) 新規 workflow に timeout-minutes / concurrency 必須 (principles.md CI方針 / ADR-038) ---
added_workflows=$(git diff --cached --name-only --diff-filter=A 2>/dev/null | grep -E '\.github/workflows/.+\.ya?ml$' || true)
while IFS= read -r f; do
  [ -z "$f" ] && continue
  content=$(git show ":$f" 2>/dev/null || cat "$f" 2>/dev/null || true)
  if [ -n "$content" ]; then
    # cicd.md は timeout-minutes を runs-on を持つジョブに設定すると定める。reusable workflow を
    # 呼ぶだけのジョブには GitHub 側が設定を許さないため、runs-on の無い workflow は対象外とする。
    if printf '%s' "$content" | grep -qE '^[[:space:]]*runs-on[[:space:]]*:' \
      && ! printf '%s' "$content" | grep -qE '^[[:space:]]*timeout-minutes[[:space:]]*:'; then
      hard_violations+=("$f  [新規 workflow に timeout-minutes が必要 — principles.md CI方針 / ADR-038]")
    fi
    if ! printf '%s' "$content" | grep -qE '^concurrency[[:space:]]*:'; then
      hard_violations+=("$f  [新規 workflow に concurrency が必要 — principles.md CI方針 / ADR-038]")
    fi
  fi
done <<< "$added_workflows"

# --- 結果 ---
hard_n=${#hard_violations[@]}
soft_n=${#soft_violations[@]}

if [ "$hard_n" -eq 0 ] && [ "$soft_n" -eq 0 ]; then
  exit 0
fi

# HARD あれば即 block (SOFT も併せて表示)
if [ "$hard_n" -gt 0 ]; then
  {
    printf '\n❌ pre-commit-machine-audit: HARD 違反 %d 件 / SOFT 違反 %d 件を検出 (target: %s)\n\n' "$hard_n" "$soft_n" "$target_cwd"
    if [ "$hard_n" -gt 0 ]; then
      printf '[HARD] commit ブロック対象:\n'
      for v in "${hard_violations[@]}"; do
        printf '  - %s\n' "$v"
      done
    fi
    if [ "$soft_n" -gt 0 ]; then
      printf '\n[SOFT] (HARD があるので合わせてブロック):\n'
      for v in "${soft_violations[@]}"; do
        printf '  - %s\n' "$v"
      done
    fi
    printf '\n意味解釈が必要なルール (What コメント / マジックナンバー 等) は本 hook 対象外。pre-commit-rule-audit skill で別途確認してください。\n'
  } >&2
  exit 2
fi

# SOFT のみ → ask decision で user に判断を委ねる
reason=$(
  printf '機械検出した SOFT 違反 %d 件:\n' "$soft_n"
  for v in "${soft_violations[@]}"; do
    printf '  - %s\n' "$v"
  done
  printf '\n意図的な編集 (ユーザによる手動修正等) なら許可、想定外なら拒否してください。'
)
# JSON エスケープ済み reason を ask で返す
jq -nc --arg r "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "ask",
    permissionDecisionReason: $r
  }
}'
exit 0
