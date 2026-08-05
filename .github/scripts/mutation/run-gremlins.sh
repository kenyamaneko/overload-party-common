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

gremlins unleash "${TARGET_PATH}" \
  --output "${REPORT_PATH}" \
  --timeout-coefficient "${TIMEOUT_COEFFICIENT}" \
  ${exclude_args[@]+"${exclude_args[@]}"}

# 解析対象が 1 つも無いとき gremlins はレポートを書かずに終了コード 0 で終わるため、
# 走らなかった実行が成功と区別できなくなる。ここで落として気づけるようにする。
if [[ ! -f "${REPORT_PATH}" ]]; then
  echo "::error::gremlins wrote no report. Either '${TARGET_PATH}' does not resolve to a package directory under '${MODULE_DIR}', or the exclude-files patterns matched every file."
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

# 全ての mutant が打ち切られると killed も lived も 0 になり、検出力は 0% と報告される。
# 計測が成立しなかった実行と、テストが 1 体も倒せなかった実行を取り違えるため落とす。
if [[ "${killed}" -eq 0 && "${lived}" -eq 0 ]]; then
  echo "::error::gremlins evaluated no mutant (${timed_out} timed out). Raise timeout-coefficient until mutants finish within the limit."
  exit 1
fi

printf 'ミューテーション結果: 検出力 %.2f%% / mutant カバレッジ %.2f%% (killed %d, lived %d, timed out %d, not covered %d, not viable %d)\n' \
  "${efficacy}" "${coverage}" "${killed}" "${lived}" "${timed_out}" "${not_covered}" "${not_viable}" \
  >>"${GITHUB_STEP_SUMMARY}"
