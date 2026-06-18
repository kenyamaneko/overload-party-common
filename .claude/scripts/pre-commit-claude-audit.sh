#!/usr/bin/env bash
# Pre-commit SOFT (semantic) rule audit via headless Claude.
# 別 Claude プロセスを auditor として起動し、staged diff を rules / GLOSSARY / prereq_docs に
# 照らしてレビューさせる。worker 自身の authorship bias を構造的に排除するため別 session で実行。
#
# 設計根拠: docs/postmortem/2026-05-21_claude-soft-rule-audit-skip.md 案 E
# 出力契約:
#   - violations >=1 → permissionDecision=ask で user 委ね
#   - violations 0 件 → exit 0
#   - audit 不能 (入力欠落 / auditor 起動失敗 / API エラー / 出力欠落 / 単一ファイル超過) → exit 2 で fail-closed block
#   - staged diff が auditor の context に収まらない場合はファイル単位でチャンク分割し全グループを監査

set -uo pipefail

input=$(cat)
if [ -z "$input" ]; then
  printf '⚠️  pre-commit-claude-audit: 空入力で起動。audit 不能のため fail-safe で commit ブロック。\n' >&2
  exit 2
fi
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)
jq_rc=$?
if [ "$jq_rc" -ne 0 ]; then
  printf '⚠️  pre-commit-claude-audit: JSON parse 失敗 (jq exit %d)。audit 不能のため fail-safe で commit ブロック。\n' "$jq_rc" >&2
  exit 2
fi

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

# auditor prompt 組み立て。引数 $1 に監査対象の diff を取る (rules / GLOSSARY / prereq_docs を毎回
# inline 注入 = fresh Read を強制)。大きな staged diff はファイル単位グループに分けて複数回呼ぶ。
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

  printf '\n\n# 対象 staged diff\n\n```diff\n%s\n```\n\n# 出力\n指定スキーマの JSON のみを返してください。\n' "$1"
}

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

# auditor の context window (200k tokens) に収めるためのプロンプト上限 (bytes)。headless claude の
# 基盤プロンプト分を差し引いた安全側の値。これを超える diff はファイル単位でチャンク分割する。
# 監査の実行有無には影響せず chunk 粒度のみ制御するため、環境変数で上書き可能 (運用調整・テスト用)。
MAX_PROMPT_BYTES="${OP_AUDIT_MAX_PROMPT_BYTES:-350000}"

# diff に割ける最小予算。これを下回るとチャンク分割しても監査が成立しないため fail-closed する。
MIN_DIFF_BUDGET_BYTES=20000

# 違反の蓄積先 (全グループ分を集約)
all_violations='[]'

# 1 グループ分の diff を auditor にかけ、違反を all_violations に集約する。
# auditor が起動失敗 / API エラー / 出力欠落いずれかなら audit 不能とみなし exit 2 で fail-closed。
audit_diff() {
  local diff_text="$1"
  [ -z "$diff_text" ] && return 0

  local out exit_code is_error err_msg viol_count group_viol
  out=$(build_prompt "$diff_text" | claude -p \
    --model claude-sonnet-4-6 \
    --tools "" \
    --output-format json \
    --json-schema "$schema" \
    --no-session-persistence 2>/tmp/op-claude-audit.stderr)
  exit_code=$?

  if [ "$exit_code" -ne 0 ]; then
    printf '⚠️  pre-commit-claude-audit: Claude auditor 起動に失敗 (exit %d)。監査不能のため fail-safe で commit ブロック。\n%s\n' \
      "$exit_code" "$(head -20 /tmp/op-claude-audit.stderr 2>/dev/null)" >&2
    exit 2
  fi

  is_error=$(printf '%s' "$out" | jq -r '.is_error // false')
  if [ "$is_error" = "true" ]; then
    err_msg=$(printf '%s' "$out" | jq -r '.result // ""')
    printf '⚠️  pre-commit-claude-audit: Claude auditor が API エラー。監査不能のため fail-safe で commit ブロック。\n%s\n' "$err_msg" >&2
    exit 2
  fi

  # structured_output.violations が配列でなければ (欠落・型不正) 監査不能とみなす。
  # jq の null indexing は length 0 を返すため、必ず type を見て判定する。
  vtype=$(printf '%s' "$out" | jq -r '.structured_output.violations | type' 2>/dev/null)
  if [ "$vtype" != "array" ]; then
    printf '⚠️  pre-commit-claude-audit: auditor 出力の structured_output.violations が配列でない (type=%s)。監査不能のため fail-safe で commit ブロック。\nresult preview:\n%s\n' \
      "$vtype" "$(printf '%s' "$out" | jq -r '.result // ""' | head -c 500)" >&2
    exit 2
  fi

  group_viol=$(printf '%s' "$out" | jq -c '.structured_output.violations')
  all_violations=$(jq -cn --argjson a "$all_violations" --argjson b "$group_viol" '$a + $b')
}

# rules だけのプロンプト overhead を測り、diff に割り当てられる予算を決める
rules_bytes=$(build_prompt "" | wc -c | tr -d ' ')
diff_budget=$(( MAX_PROMPT_BYTES - rules_bytes ))
if [ "$diff_budget" -lt "$MIN_DIFF_BUDGET_BYTES" ]; then
  printf '⚠️  pre-commit-claude-audit: ルール群が大きく diff 予算を確保できない (rules=%d bytes, max=%d)。監査不能のため fail-safe で commit ブロック。\n' \
    "$rules_bytes" "$MAX_PROMPT_BYTES" >&2
  exit 2
fi

staged_bytes=$(printf '%s' "$staged_diff" | wc -c | tr -d ' ')

if [ "$staged_bytes" -le "$diff_budget" ]; then
  # fast path: 1 回で監査
  audit_diff "$staged_diff"
else
  # 大きい diff: staged ファイルを diff サイズで貪欲にグループ化し、グループ毎に監査する
  staged_files=()
  while IFS= read -r f; do
    [ -n "$f" ] && staged_files+=("$f")
  done < <(git diff --cached --name-only --diff-filter=ACM 2>/dev/null)

  group_files=()
  group_bytes=0

  # 現在のグループに溜めた staged ファイルの diff をまとめて監査し、グループをリセットする。
  flush_group() {
    [ "${#group_files[@]}" -eq 0 ] && return 0
    local gdiff
    gdiff=$(git diff --cached -U10 --diff-filter=ACM -- "${group_files[@]}" 2>/dev/null)
    audit_diff "$gdiff"
    group_files=()
    group_bytes=0
  }

  if [ "${#staged_files[@]}" -gt 0 ]; then
    for f in "${staged_files[@]}"; do
      fbytes=$(git diff --cached -U10 --diff-filter=ACM -- "$f" 2>/dev/null | wc -c | tr -d ' ')
      if [ "$fbytes" -gt "$diff_budget" ]; then
        printf '⚠️  pre-commit-claude-audit: 単一ファイルの diff が監査予算を超過 (%s: %d bytes > %d)。分割できず監査不能のため fail-safe で commit ブロック。当該ファイルの変更を分けてコミットしてください。\n' \
          "$f" "$fbytes" "$diff_budget" >&2
        exit 2
      fi
      if [ $(( group_bytes + fbytes )) -gt "$diff_budget" ] && [ "${#group_files[@]}" -gt 0 ]; then
        flush_group
      fi
      group_files+=("$f")
      group_bytes=$(( group_bytes + fbytes ))
    done
    flush_group
  fi
fi

violations_count=$(printf '%s' "$all_violations" | jq 'length')
if [ "$violations_count" -eq 0 ]; then
  exit 0
fi

reason=$(
  printf 'Claude auditor が SOFT 違反 %d 件を検出 (target: %s):\n\n' "$violations_count" "$repo_name"
  printf '%s' "$all_violations" | jq -r '.[] | "- \(.file)\(if .line then ":\(.line)" else "" end)\n    rule: \(.rule)\n    evidence: \(.evidence)\n    why: \(.why)"'
  printf '\n\n意図的に commit するなら許可、修正するなら拒否してください。'
)
jq -nc --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
exit 0
