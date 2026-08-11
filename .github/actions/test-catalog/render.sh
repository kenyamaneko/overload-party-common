#!/usr/bin/env bash
# テスト結果からテスト観点カタログの HTML を描画し、$OUTPUT_DIR に書き出す。
#
# 入力は環境変数:
#   SECTIONS   : --section の指定を 1 行 1 件で並べたもの
#   SUBGROUPS  : --subgroup の指定を 1 行 1 件で並べたもの (無ければ空文字)
#   TITLE      : ページの表題
#   COMMIT     : 生成元 commit の SHA
#   OUTPUT_DIR : 出力先ディレクトリ

set -euo pipefail

section_args=()
while IFS= read -r section; do
  [ -n "$section" ] || continue
  section_args+=(--section "$section")
done <<<"$SECTIONS"

subgroup_args=()
while IFS= read -r subgroup; do
  [ -n "$subgroup" ] || continue
  subgroup_args+=(--subgroup "$subgroup")
done <<<"$SUBGROUPS"

mkdir -p "$OUTPUT_DIR"
generate-test-catalog "${section_args[@]}" "${subgroup_args[@]}" \
  --format html --title "$TITLE" --commit "$COMMIT" >"$OUTPUT_DIR/index.html"
