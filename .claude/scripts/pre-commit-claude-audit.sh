#!/usr/bin/env bash
# Pre-commit SOFT (semantic) rule audit via headless Claude.
# 別 Claude プロセスを auditor として起動し、staged diff を rules / GLOSSARY / prereq_docs に
# 照らしてレビューさせる。worker 自身の authorship bias を構造的に排除するため別 session で実行。
#
# 設計根拠: docs/postmortem/2026-05-21_claude-soft-rule-audit-skip.md 案 E
#
# 各違反を 2 軸で分類し、principles「ルール違反への対応」に従って自律修正と user 委譲を仕分ける:
#   - clarity    : 違反の明白度 (obvious = 解釈の余地なし / interpretive = 解釈次第)
#   - fix_safety : 是正の安全性 (safe = 修正しても設計上の実害なし / harmful = 是正に実害ありうる)
# 出力契約:
#   - obvious かつ safe の違反あり → permissionDecision=deny で worker に差し戻し自律修正させる
#   - それ以外の違反のみ (interpretive / harmful を含む) → permissionDecision=ask で user に判断委譲
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
# 共通ルールは keyandnotes-rules に集約 (兄弟リポとして配置)。repos.yaml / GLOSSARY / prereq_docs は common に残る。
RULES_DIR="${COMMON_DIR}/../../keyandnotes-rules/rules"

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

# 共有ルールが解決できなければ audit プロンプトを組めない。fail-closed で commit をブロックする。
if [ ! -f "${RULES_DIR}/principles.md" ]; then
  printf '⚠️  pre-commit-claude-audit: 共有ルール %s が見つからない。keyandnotes-rules を兄弟リポとして配置してください。audit 不能のため fail-safe で commit ブロック。\n' "${RULES_DIR}/principles.md" >&2
  exit 2
fi

# principles.md が @import する base ルール一覧を手書きリストで複製すると、principles.md 側の
# 更新に追従しない二重管理になる。keyandnotes-rules の共有ロジックから動的に導出する。
COMMON_LIB="${COMMON_DIR}/../../keyandnotes-rules/scripts/claude-audit-common.sh"
if [ ! -f "$COMMON_LIB" ]; then
  printf '⚠️  pre-commit-claude-audit: 共有ロジック (%s) が見つからない。audit 不能のため fail-safe で commit ブロック。\n' "$COMMON_LIB" >&2
  exit 2
fi
# shellcheck source=/dev/null
source "$COMMON_LIB"

# testing.md は呼び出し側 (このスクリプト) が既に無条件で emit_rule しているため、自動導出から除外する。
auto_inject_refs_raw=$(kn_auto_inject_refs "$RULES_DIR" "${RULES_DIR}/principles.md" "testing.md")
if [ $? -ne 0 ]; then
  printf '⚠️  pre-commit-claude-audit: principles.md が参照する base ルールの自動導出に失敗。audit 不能のため fail-safe で commit ブロック。\n' >&2
  exit 2
fi
AUTO_INJECT_REFS=()
while IFS= read -r ref; do
  [ -n "$ref" ] && AUTO_INJECT_REFS+=("$ref")
done <<< "$auto_inject_refs_raw"

# 共通ベース (keyandnotes-rules) と overload-party overlay (common) を対で注入する。
# base を注入したら同じ相対パスの overlay も必ず注入する不変条件をこの関数に閉じ込め、
# base だけ足して overlay が監査から漏れる事故を構造的に防ぐ。
emit_rule() {
  local rel="$1"
  local base="${RULES_DIR}/${rel}"
  local overlay="${COMMON_DIR}/rules/${rel}"
  if [ -f "$base" ]; then
    printf '\n\n## rules/%s\n' "$rel"
    cat "$base"
  fi
  if [ -f "$overlay" ]; then
    printf '\n\n## rules/%s (overload-party overlay)\n' "$rel"
    cat "$overlay"
  fi
}

# auditor prompt を組み立てる。ルール群を毎回 inline 注入し auditor に fresh Read を強制する。
build_prompt() {
  cat <<HEADER
あなたは overload-party リポフリートの SOFT (意味解釈型) ルール auditor です。
別の Claude が書いた staged diff を、以下のルール集と用語集に照らしてレビューしてください。

レビュー方針:
- 明確なルール違反のみ列挙する。主観的な改善提案・スタイル好みは含めない
- 各違反は file / line / rule / evidence / why / clarity / fix_safety を埋める。line は違反箇所の行番号 (diff の追加行) を必ず入れる
- 違反 0 件なら "violations": [] を返す

各違反を 2 軸で分類してください (hook が「worker が自律修正してよいか」を判定するのに使う):
- clarity (明白度):
  - "obvious"      = ルール文面に照らして違反が明白で、解釈の余地がない
  - "interpretive" = ルールの解釈次第で違反とみなされ、判断が分かれうる
- fix_safety (是正の安全性):
  - "safe"    = 違反を修正しても設計上の実害がない (例: docstring 追加, What コメント削除)
  - "harmful" = 是正することで設計上の実害が生じうる (例: 公開 API のリネーム, 責務分割による境界変更)
- diff だけでは確信が持てないときは "interpretive" / "harmful" (= 安全側) に倒す。自律修正は明白かつ安全な違反に限定するため

# 適用ルール (target repo: ${repo_name}, lang: ${lang})
HEADER

  emit_rule "principles.md"
  for ref in "${AUTO_INJECT_REFS[@]}"; do
    emit_rule "$ref"
  done
  emit_rule "testing.md"
  if [ "$lang" != "none" ]; then
    emit_rule "lang/${lang}.md"
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
        "required": ["file", "line", "rule", "evidence", "why", "clarity", "fix_safety"],
        "additionalProperties": false,
        "properties": {
          "file": {"type": "string"},
          "line": {"type": "integer"},
          "rule": {"type": "string"},
          "evidence": {"type": "string"},
          "why": {"type": "string"},
          "clarity": {"type": "string", "enum": ["obvious", "interpretive"]},
          "fix_safety": {"type": "string", "enum": ["safe", "harmful"]}
        }
      }
    }
  }
}'

# auditor の context window (200k tokens) に収めるためのプロンプト上限 (bytes)。headless claude の
# 基盤プロンプト分を差し引いた安全側の値。chunk 粒度のみ制御し監査の実行有無には影響しないため、
# 環境変数で上書き可能 (運用調整・テスト用)。
MAX_PROMPT_BYTES="${OP_AUDIT_MAX_PROMPT_BYTES:-350000}"

# diff に割ける最小予算。これを下回るとチャンク分割しても監査が成立しないため fail-closed する。
MIN_DIFF_BUDGET_BYTES=20000

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

rules_bytes=$(build_prompt "" | wc -c | tr -d ' ')
diff_budget=$(( MAX_PROMPT_BYTES - rules_bytes ))
if [ "$diff_budget" -lt "$MIN_DIFF_BUDGET_BYTES" ]; then
  printf '⚠️  pre-commit-claude-audit: ルール群が大きく diff 予算を確保できない (rules=%d bytes, max=%d)。監査不能のため fail-safe で commit ブロック。\n' \
    "$rules_bytes" "$MAX_PROMPT_BYTES" >&2
  exit 2
fi

staged_bytes=$(printf '%s' "$staged_diff" | wc -c | tr -d ' ')

if [ "$staged_bytes" -le "$diff_budget" ]; then
  audit_diff "$staged_diff"
else
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

autofix=$(printf '%s' "$all_violations" | jq -c '[.[] | select(.clarity == "obvious" and .fix_safety == "safe")]')
escalate=$(printf '%s' "$all_violations" | jq -c '[.[] | select(.clarity != "obvious" or .fix_safety != "safe")]')
autofix_count=$(printf '%s' "$autofix" | jq 'length')
escalate_count=$(printf '%s' "$escalate" | jq 'length')

# 混在時は明白な違反を先に deny で解消させ、解釈次第 / 是正に実害ありうる違反は再 commit 時に
# 別途 ask に載せる (auditor は 1 diff を一括判定するため、両者を同一 commit で同時には出せない)。
if [ "$autofix_count" -gt 0 ]; then
  reason=$(
    printf '明白かつ修正に実害のないルール違反 %d 件を検出 (target: %s)。principles「ルール違反への対応」に従い、自律修正してから再 commit してください:\n\n' "$autofix_count" "$repo_name"
    printf '%s' "$autofix" | jq -r '.[] | "- \(.file):\(.line)\n    rule: \(.rule)\n    evidence: \(.evidence)\n    why: \(.why)"'
    if [ "$escalate_count" -gt 0 ]; then
      printf '\n\n(解釈次第 / 是正に実害ありうる違反 %d 件は、上記修正後の再 commit で別途確認します。今は触れないでください。)' "$escalate_count"
    fi
    printf '\n\n検出が false positive だと判断する場合のみ、その理由を添えてユーザに確認してください。'
  )
  jq -nc --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
  exit 0
fi

reason=$(
  printf 'Claude auditor が判断を要するルール違反 %d 件を検出 (target: %s)。明白でない、または是正に設計上の実害がありうるため、修正可否を判断してください:\n\n' "$escalate_count" "$repo_name"
  printf '%s' "$escalate" | jq -r '.[] | "- \(.file):\(.line)  [明白度: \(if .clarity == "obvious" then "明白" else "解釈次第" end) / 是正の安全性: \(if .fix_safety == "safe" then "実害なし" else "実害ありうる" end)]\n    rule: \(.rule)\n    evidence: \(.evidence)\n    why: \(.why)"'
  printf '\n\n修正するなら拒否、意図的に commit するなら許可してください。'
)
jq -nc --arg r "$reason" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
exit 0
