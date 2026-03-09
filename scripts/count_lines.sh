#!/bin/bash
# overload-party リポジトリ群のコード量・ドキュメント量調査スクリプト

BASE="/Users/kenyamamoto/Documents/key_and_notes"
REPOS=(
  overload-party-analytics
  overload-party-client
  overload-party-common
  overload-party-infra
  overload-party-k8s
  overload-party-ops
  overload-party-battle
  overload-party-gateway
  overload-party-newsfeed
)

EXCLUDE_PATHS=(
  "*/node_modules/*" "*/.git/*" "*/dist/*" "*/build/*"
  "*/.next/*" "*/obj/*" "*/bin/*" "*/coverage/*"
)

# テストファイル判定: ファイル名パターンまたはディレクトリパターンで判定
#   Go:   *_test.go
#   C#:   */tests/*  (tests/ ディレクトリ配下)
#   TS/JS: *.test.ts(x), *.spec.ts(x), */__tests__/*, */e2e/*
#   Python: test_*.py, *_test.py
is_test_file() {
  local f="$1"
  case "$f" in
    *_test.go)          return 0 ;;
    */tests/*.cs)       return 0 ;;
    *.test.ts|*.test.tsx|*.spec.ts|*.spec.tsx) return 0 ;;
    */__tests__/*)      return 0 ;;
    */e2e/*)            return 0 ;;
    */test_*.py|*_test.py) return 0 ;;
  esac
  return 1
}

count_lines_for() {
  local file_list="$1"
  if [ -z "$file_list" ]; then
    echo 0
  else
    echo "$file_list" | xargs cat 2>/dev/null | wc -l | tr -d ' '
  fi
}

build_exclude_args() {
  local args=""
  for p in "${EXCLUDE_PATHS[@]}"; do
    args="$args ! -path \"$p\""
  done
  echo "$args"
}

echo "============================================================"
echo "  overload-party リポジトリ群 コード量・ドキュメント量レポート"
echo "============================================================"
echo ""

printf "%-30s %8s %8s %8s %8s %8s %8s %8s\n" "Repository" "Prod" "Test" "T/P%" "Docs" "Config" "Data" "Total"
printf "%-30s %8s %8s %8s %8s %8s %8s %8s\n" "------------------------------" "--------" "--------" "--------" "--------" "--------" "--------" "--------"

grand_prod=0
grand_test=0
grand_docs=0
grand_config=0
grand_data=0
grand_total=0

for repo in "${REPOS[@]}"; do
  dir="$BASE/$repo"
  if [ ! -d "$dir" ]; then
    printf "%-30s %8s\n" "$repo" "(N/A)"
    continue
  fi

  # Code files (全コード)
  all_code_files=$(find "$dir" -type f \( \
    -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \
    -o -name "*.py" -o -name "*.go" -o -name "*.rs" -o -name "*.sh" \
    -o -name "*.rb" -o -name "*.java" -o -name "*.kt" -o -name "*.swift" \
    -o -name "*.dart" -o -name "*.vue" -o -name "*.svelte" \
    -o -name "*.cs" \
    -o -name "*.css" -o -name "*.scss" -o -name "*.html" \
    \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/dist/*" ! -path "*/build/*" ! -path "*/.next/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" 2>/dev/null)

  prod_files=""
  test_files=""
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if is_test_file "$f"; then
      test_files="${test_files}${f}"$'\n'
    else
      prod_files="${prod_files}${f}"$'\n'
    fi
  done <<< "$all_code_files"

  prod_lines=$(count_lines_for "$prod_files")
  test_lines=$(count_lines_for "$test_files")

  # Doc files
  doc_lines=$(find "$dir" -type f \( \
    -name "*.md" -o -name "*.txt" -o -name "*.rst" -o -name "*.adoc" \
    \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" \
    -exec cat {} + 2>/dev/null | wc -l | tr -d ' ')

  # Config files
  config_lines=$(find "$dir" -type f \( \
    -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" \
    -o -name "*.ini" -o -name ".env*" -o -name "Dockerfile*" \
    -o -name "docker-compose*" -o -name "*.tf" -o -name "*.hcl" \
    -o -name "*.conf" -o -name "*.cfg" \
    \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/dist/*" ! -path "*/.next/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" \
    -exec cat {} + 2>/dev/null | wc -l | tr -d ' ')

  # Data files
  data_lines=$(find "$dir" -type f \( \
    -name "*.csv" -o -name "*.sql" -o -name "*.graphql" -o -name "*.proto" \
    \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" \
    -exec cat {} + 2>/dev/null | wc -l | tr -d ' ')

  prod_lines=${prod_lines:-0}
  test_lines=${test_lines:-0}
  doc_lines=${doc_lines:-0}
  config_lines=${config_lines:-0}
  data_lines=${data_lines:-0}

  if [ "$prod_lines" -gt 0 ]; then
    ratio=$((test_lines * 100 / prod_lines))
    ratio_str="${ratio}%"
  else
    ratio_str="-"
  fi

  total=$((prod_lines + test_lines + doc_lines + config_lines + data_lines))

  grand_prod=$((grand_prod + prod_lines))
  grand_test=$((grand_test + test_lines))
  grand_docs=$((grand_docs + doc_lines))
  grand_config=$((grand_config + config_lines))
  grand_data=$((grand_data + data_lines))
  grand_total=$((grand_total + total))

  printf "%-30s %8d %8d %8s %8d %8d %8d %8d\n" "$repo" "$prod_lines" "$test_lines" "$ratio_str" "$doc_lines" "$config_lines" "$data_lines" "$total"
done

printf "%-30s %8s %8s %8s %8s %8s %8s %8s\n" "------------------------------" "--------" "--------" "--------" "--------" "--------" "--------" "--------"

if [ "$grand_prod" -gt 0 ]; then
  grand_ratio=$((grand_test * 100 / grand_prod))
  grand_ratio_str="${grand_ratio}%"
else
  grand_ratio_str="-"
fi

printf "%-30s %8d %8d %8s %8d %8d %8d %8d\n" "TOTAL" "$grand_prod" "$grand_test" "$grand_ratio_str" "$grand_docs" "$grand_config" "$grand_data" "$grand_total"

echo ""
echo "============================================================"
echo "  ファイル種別ごとの内訳 (上位拡張子)"
echo "============================================================"
echo ""

for repo in "${REPOS[@]}"; do
  dir="$BASE/$repo"
  if [ ! -d "$dir" ]; then
    continue
  fi

  echo "--- $repo ---"
  find "$dir" -type f \
    ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/dist/*" ! -path "*/build/*" ! -path "*/.next/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" \
    -name "*.*" | \
    sed 's/.*\.//' | sort | uniq -c | sort -rn | head -15
  echo ""
done

echo "============================================================"
echo "  リポジトリごとのファイル数"
echo "============================================================"
echo ""

printf "%-30s %8s %8s %8s %8s %8s %8s\n" "Repository" "Prod" "Test" "Docs" "Config" "Data" "Total"
printf "%-30s %8s %8s %8s %8s %8s %8s\n" "------------------------------" "--------" "--------" "--------" "--------" "--------" "--------"

for repo in "${REPOS[@]}"; do
  dir="$BASE/$repo"
  if [ ! -d "$dir" ]; then
    continue
  fi

  all_code_files=$(find "$dir" -type f \( \
    -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \
    -o -name "*.py" -o -name "*.go" -o -name "*.rs" -o -name "*.sh" \
    -o -name "*.rb" -o -name "*.java" -o -name "*.kt" -o -name "*.swift" \
    -o -name "*.dart" -o -name "*.vue" -o -name "*.svelte" \
    -o -name "*.cs" \
    -o -name "*.css" -o -name "*.scss" -o -name "*.html" \
    \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/dist/*" ! -path "*/build/*" ! -path "*/.next/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" 2>/dev/null)

  prod_count=0
  test_count=0
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if is_test_file "$f"; then
      test_count=$((test_count + 1))
    else
      prod_count=$((prod_count + 1))
    fi
  done <<< "$all_code_files"

  doc_count=$(find "$dir" -type f \( \
    -name "*.md" -o -name "*.txt" -o -name "*.rst" -o -name "*.adoc" \
    \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" | wc -l | tr -d ' ')

  config_count=$(find "$dir" -type f \( \
    -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" \
    -o -name "*.ini" -o -name ".env*" -o -name "Dockerfile*" \
    -o -name "docker-compose*" -o -name "*.tf" -o -name "*.hcl" \
    -o -name "*.conf" -o -name "*.cfg" \
    \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/dist/*" ! -path "*/.next/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" | wc -l | tr -d ' ')

  data_count=$(find "$dir" -type f \( \
    -name "*.csv" -o -name "*.sql" -o -name "*.graphql" -o -name "*.proto" \
    \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" | wc -l | tr -d ' ')

  total_count=$((prod_count + test_count + doc_count + config_count + data_count))

  printf "%-30s %8d %8d %8d %8d %8d %8d\n" "$repo" "$prod_count" "$test_count" "$doc_count" "$config_count" "$data_count" "$total_count"
done
