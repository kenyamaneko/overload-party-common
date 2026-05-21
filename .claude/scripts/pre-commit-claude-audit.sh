#!/usr/bin/env bash
# Pre-commit SOFT (semantic) rule audit via headless Claude.
# 別 Claude プロセスを auditor として起動し、staged diff を rules / GLOSSARY / prereq_docs に
# 照らしてレビューさせる。worker 自身の authorship bias を構造的に排除するため別 session で実行。
#
# 設計根拠: docs/postmortem/2026-05-21_claude-soft-rule-audit-skip.md 案 E
# 出力契約: violations >=1 → permissionDecision=ask で user 委ね / 0 件 → exit 0

set -uo pipefail

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# 文字列リテラル / HEREDOC 内の偶発マッチを避けるため実行可能部分のみ抽出 (machine-audit と同手法)
exec_cmd=$(printf '%s' "$cmd" | sed -E '/<</q' | sed -E 's/"[^"]*"//g; s/'\''[^'\'']*'\''//g')

if ! printf '%s' "$exec_cmd" | grep -qE '(^|[[:space:]&|;`(])git[[:space:]]+commit'; then
  exit 0
fi
if printf '%s' "$exec_cmd" | grep -qE 'git[[:space:]]+commit[[:space:]]+(--help|-h)([[:space:]]|$)'; then
  exit 0
fi

target_cwd=$(printf '%s' "$cmd" | sed -nE 's|^cd[[:space:]]+"?([^"&[:space:]]+)"?[[:space:]]*&&.*|\1|p')
if [ -z "$target_cwd" ]; then
  target_cwd=$(pwd)
fi
if ! cd "$target_cwd" 2>/dev/null; then
  exit 0
fi
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  exit 0
fi

staged_diff=$(git diff --cached -U10 --diff-filter=ACM 2>/dev/null)
if [ -z "$staged_diff" ]; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# target repo の lang / prereq_docs を repos.yaml から解決
resolved=$(python3 - "$COMMON_DIR" "$target_cwd" <<'PY'
import sys, os, json, yaml
common_dir, target_cwd = sys.argv[1], sys.argv[2]
with open(os.path.join(common_dir, "rules/repos.yaml")) as f:
    data = yaml.safe_load(f)
target_abs = os.path.realpath(target_cwd)
for r in data.get("repos", []):
    repo_abs = os.path.realpath(os.path.join(common_dir, r["path"]))
    if target_abs == repo_abs:
        print(json.dumps({
            "name": r["name"],
            "lang": r.get("lang", "none"),
            "prereq_docs": r.get("prereq_docs", []),
        }))
        break
PY
)

if [ -z "$resolved" ]; then
  exit 0
fi

repo_name=$(printf '%s' "$resolved" | jq -r '.name')
lang=$(printf '%s' "$resolved" | jq -r '.lang')

# auditor prompt 組み立て (rules / GLOSSARY / prereq_docs を毎回 inline 注入 = fresh Read を強制)
build_prompt() {
  cat <<HEADER
あなたは overload-party リポフリートの SOFT (意味解釈型) ルール auditor です。
別の Claude が書いた staged diff を、以下のルール集と用語集に照らしてレビューしてください。

レビュー方針:
- 明確なルール違反のみ列挙する。主観的な改善提案・スタイル好みは含めない
- 各違反は file / line (任意) / rule / evidence / why を埋める
- 違反 0 件なら "violations": [] を返す

# 適用ルール (target repo: ${repo_name}, lang: ${lang})

## rules/principles.md
HEADER
  cat "${COMMON_DIR}/rules/principles.md"

  if [ "$lang" != "none" ] && [ -f "${COMMON_DIR}/rules/lang/${lang}.md" ]; then
    printf '\n\n## rules/lang/%s.md\n' "$lang"
    cat "${COMMON_DIR}/rules/lang/${lang}.md"
  fi

  if [ -f "${COMMON_DIR}/docs/game_design/GLOSSARY.md" ]; then
    printf '\n\n## docs/game_design/GLOSSARY.md\n'
    cat "${COMMON_DIR}/docs/game_design/GLOSSARY.md"
  fi

  printf '%s' "$resolved" | jq -r '.prereq_docs[]?' | while IFS= read -r doc; do
    [ -z "$doc" ] && continue
    if [ -f "${COMMON_DIR}/${doc}" ]; then
      printf '\n\n## (prereq) %s\n' "$doc"
      cat "${COMMON_DIR}/${doc}"
    fi
  done

  printf '\n\n# 対象 staged diff\n\n```diff\n%s\n```\n\n# 出力\n指定スキーマの JSON のみを返してください。\n' "$staged_diff"
}

prompt=$(build_prompt)

schema='{
  "type": "object",
  "required": ["violations"],
  "additionalProperties": false,
  "properties": {
    "violations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["file", "rule", "evidence", "why"],
        "additionalProperties": false,
        "properties": {
          "file": {"type": "string"},
          "line": {"type": ["integer", "null"]},
          "rule": {"type": "string"},
          "evidence": {"type": "string"},
          "why": {"type": "string"}
        }
      }
    }
  }
}'

# auditor 起動。--tools "" で tool 利用を完全封じる (= hook 再帰も発生しない)。
# --no-session-persistence で session を永続化しない。
auditor_out=$(printf '%s' "$prompt" | claude -p \
  --model claude-sonnet-4-6 \
  --tools "" \
  --output-format json \
  --json-schema "$schema" \
  --no-session-persistence 2>/tmp/op-claude-audit.stderr)
auditor_exit=$?

if [ "$auditor_exit" -ne 0 ]; then
  reason=$(printf 'Claude auditor 起動に失敗 (exit %d):\n%s\n\n意図的に commit するなら許可、原因調査するなら拒否してください。' "$auditor_exit" "$(head -20 /tmp/op-claude-audit.stderr 2>/dev/null)")
  jq -nc --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
  exit 0
fi

is_error=$(printf '%s' "$auditor_out" | jq -r '.is_error // false')
if [ "$is_error" = "true" ]; then
  err_msg=$(printf '%s' "$auditor_out" | jq -r '.result // ""')
  reason=$(printf 'Claude auditor が API エラー:\n%s\n\n意図的に commit するなら許可、原因調査するなら拒否してください。' "$err_msg")
  jq -nc --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
  exit 0
fi

violations_count=$(printf '%s' "$auditor_out" | jq -r '.structured_output.violations | length' 2>/dev/null)
if [ -z "$violations_count" ] || [ "$violations_count" = "null" ]; then
  raw_preview=$(printf '%s' "$auditor_out" | jq -r '.result // ""' | head -c 500)
  reason=$(printf 'Claude auditor 出力に structured_output が無い。result preview:\n%s\n\n意図的に commit するなら許可、原因調査するなら拒否してください。' "$raw_preview")
  jq -nc --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
  exit 0
fi

if [ "$violations_count" -eq 0 ]; then
  exit 0
fi

reason=$(
  printf 'Claude auditor が SOFT 違反 %d 件を検出 (target: %s):\n\n' "$violations_count" "$repo_name"
  printf '%s' "$auditor_out" | jq -r '.structured_output.violations[] | "- \(.file)\(if .line then ":\(.line)" else "" end)\n    rule: \(.rule)\n    evidence: \(.evidence)\n    why: \(.why)"'
  printf '\n\n意図的に commit するなら許可、修正するなら拒否してください。'
)
jq -nc --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
exit 0
