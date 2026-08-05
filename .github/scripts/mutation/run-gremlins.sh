#!/usr/bin/env bash
set -euo pipefail

exclude_args=()
if [[ -n "${EXCLUDE_FILES}" ]]; then
  IFS=',' read -ra exclude_patterns <<<"${EXCLUDE_FILES}"
  for pattern in "${exclude_patterns[@]}"; do
    exclude_args+=(--exclude-files "${pattern}")
  done
fi

cd "${MODULE_DIR}"

gremlins unleash "${TARGET_DIR}" \
  --output "${REPORT_PATH}" \
  --timeout-coefficient "${TIMEOUT_COEFFICIENT}" \
  ${exclude_args[@]+"${exclude_args[@]}"}

# 解析対象が 1 つも無いとき gremlins はレポートを書かずに終了コード 0 で終わるため、
# 走らなかった実行が成功と区別できなくなる。ここで落として気づけるようにする。
if [[ ! -f "${REPORT_PATH}" ]]; then
  echo "::error::gremlins wrote no report. Either '${TARGET_DIR}' does not resolve to a package directory under '${MODULE_DIR}', or the exclude-files patterns matched every file."
  exit 1
fi

analysed_mutants=$(jq '[.files[].mutations[]] | length' "${REPORT_PATH}")
if [[ "${analysed_mutants}" -eq 0 ]]; then
  echo "::error::gremlins analysed no mutants. Check the target path and the exclude-files patterns."
  exit 1
fi

# TIMED OUT は集計値に無く、killed / lived だけが mutants_total に入る。
# 打ち切られた mutant を見落とさないよう明細から数える。
timed_out=$(jq '[.files[].mutations[] | select(.status == "TIMED OUT")] | length' "${REPORT_PATH}")

IFS=$'\t' read -r efficacy coverage killed lived not_covered not_viable < <(
  jq -r '[.test_efficacy, .mutations_coverage, .mutants_killed, .mutants_lived, .mutants_not_covered, .mutants_not_viable] | @tsv' "${REPORT_PATH}"
)

# 検出力は killed と lived だけから出るため、打ち切られた mutant が多いほど少数の標本で
# 高い値が出る。倒せた数より打ち切られた数が多い実行は、検出力ではなく上限の低さを表す。
evaluated=$((killed + lived))
if [[ "${timed_out}" -gt "${evaluated}" ]]; then
  echo "::error::gremlins timed out on ${timed_out} of $((evaluated + timed_out)) mutants and judged only ${evaluated}. The score is not representative. Raise timeout-coefficient until mutants finish within the limit."
  exit 1
fi

printf 'ミューテーション結果: 検出力 %.2f%% / mutant カバレッジ %.2f%% (killed %d, lived %d, timed out %d, not covered %d, not viable %d)\n' \
  "${efficacy}" "${coverage}" "${killed}" "${lived}" "${timed_out}" "${not_covered}" "${not_viable}" \
  >>"${GITHUB_STEP_SUMMARY}"
