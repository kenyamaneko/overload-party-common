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

echo "============================================================"
echo "  overload-party リポジトリ群 コード量・ドキュメント量レポート"
echo "============================================================"
echo ""

printf "%-30s %8s %8s %8s %8s %8s\n" "Repository" "Code" "Docs" "Config" "Data" "Total"
printf "%-30s %8s %8s %8s %8s %8s\n" "------------------------------" "--------" "--------" "--------" "--------" "--------"

grand_code=0
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

  # Code files
  code_lines=$(find "$dir" -type f \( \
    -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \
    -o -name "*.py" -o -name "*.go" -o -name "*.rs" -o -name "*.sh" \
    -o -name "*.rb" -o -name "*.java" -o -name "*.kt" -o -name "*.swift" \
    -o -name "*.dart" -o -name "*.vue" -o -name "*.svelte" \
    -o -name "*.cs" \
    -o -name "*.css" -o -name "*.scss" -o -name "*.html" \
    \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/dist/*" ! -path "*/build/*" ! -path "*/.next/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" \
    -exec cat {} + 2>/dev/null | wc -l | tr -d ' ')

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

  code_lines=${code_lines:-0}
  doc_lines=${doc_lines:-0}
  config_lines=${config_lines:-0}
  data_lines=${data_lines:-0}

  total=$((code_lines + doc_lines + config_lines + data_lines))

  grand_code=$((grand_code + code_lines))
  grand_docs=$((grand_docs + doc_lines))
  grand_config=$((grand_config + config_lines))
  grand_data=$((grand_data + data_lines))
  grand_total=$((grand_total + total))

  printf "%-30s %8d %8d %8d %8d %8d\n" "$repo" "$code_lines" "$doc_lines" "$config_lines" "$data_lines" "$total"
done

printf "%-30s %8s %8s %8s %8s %8s\n" "------------------------------" "--------" "--------" "--------" "--------" "--------"
printf "%-30s %8d %8d %8d %8d %8d\n" "TOTAL" "$grand_code" "$grand_docs" "$grand_config" "$grand_data" "$grand_total"

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

printf "%-30s %8s %8s %8s %8s %8s\n" "Repository" "Code" "Docs" "Config" "Data" "Total"
printf "%-30s %8s %8s %8s %8s %8s\n" "------------------------------" "--------" "--------" "--------" "--------" "--------"

for repo in "${REPOS[@]}"; do
  dir="$BASE/$repo"
  if [ ! -d "$dir" ]; then
    continue
  fi

  code_count=$(find "$dir" -type f \( \
    -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \
    -o -name "*.py" -o -name "*.go" -o -name "*.rs" -o -name "*.sh" \
    -o -name "*.rb" -o -name "*.java" -o -name "*.kt" -o -name "*.swift" \
    -o -name "*.dart" -o -name "*.vue" -o -name "*.svelte" \
    -o -name "*.cs" \
    -o -name "*.css" -o -name "*.scss" -o -name "*.html" \
    \) ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/dist/*" ! -path "*/build/*" ! -path "*/.next/*" ! -path "*/obj/*" ! -path "*/bin/*" ! -path "*/coverage/*" | wc -l | tr -d ' ')

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

  total_count=$((code_count + doc_count + config_count + data_count))

  printf "%-30s %8d %8d %8d %8d %8d\n" "$repo" "$code_count" "$doc_count" "$config_count" "$data_count" "$total_count"
done
