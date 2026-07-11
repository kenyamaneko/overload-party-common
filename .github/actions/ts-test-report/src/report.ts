interface AssertionResult {
  status: string
  fullName: string
  failureMessages: string[]
}

interface TestFileResult {
  name: string
  assertionResults: AssertionResult[]
}

interface VitestJsonReport {
  testResults: TestFileResult[]
}

export interface TestFailure {
  name: string
  message: string
  file: string | null
  line: number | null
}

export interface ReportResult {
  passed: number
  failed: number
  skipped: number
  failures: TestFailure[]
}

const stackLocationRegex = /at\s+(?:.*\()?(\/[^\s():]+):(\d+):(\d+)\)?/

/**
 * vitest --reporter=json の出力からテスト結果一覧を集計する。
 * @param jsonText vitest --reporter=json が出力した JSON 文字列。
 * @param workspace リポジトリルートの絶対パス (失敗箇所の相対パス化に使う)。
 * @returns 通過・失敗・スキップの件数と、失敗したテストの一覧。
 */
export function parse(jsonText: string, workspace: string): ReportResult {
  const report = JSON.parse(jsonText) as VitestJsonReport

  let passed = 0
  let failed = 0
  let skipped = 0
  const failures: TestFailure[] = []

  for (const fileResult of report.testResults) {
    for (const assertion of fileResult.assertionResults) {
      switch (assertion.status) {
        case 'passed':
          passed++
          break
        case 'skipped':
        case 'pending':
        case 'todo':
          skipped++
          break
        case 'failed': {
          failed++
          const raw = assertion.failureMessages[0] ?? ''
          const message = raw.split('\n')[0].trim()
          const { file, line } = extractLocation(raw, workspace)
          failures.push({ name: assertion.fullName, message, file, line })
          break
        }
        default:
          throw new Error(`unknown vitest assertion status: ${assertion.status}`)
      }
    }
  }

  return { passed, failed, skipped, failures }
}

/**
 * スタックトレースから最初の file:line を抽出し、ワークスペース相対パスにする。
 * @param stackTrace failureMessages の本文 (メッセージ + スタックトレース)。
 * @param workspace リポジトリルートの絶対パス。
 * @returns 相対ファイルパスと行番号。見つからなければ両方 null。
 */
export function extractLocation(
  stackTrace: string,
  workspace: string
): { file: string | null; line: number | null } {
  const match = stackLocationRegex.exec(stackTrace)
  if (!match) {
    return { file: null, line: null }
  }

  let file = match[1]
  const line = Number.parseInt(match[2], 10)

  if (workspace && file.startsWith(workspace)) {
    file = file.slice(workspace.length).replace(/^\/+/, '')
  }

  return { file, line }
}

/**
 * $GITHUB_STEP_SUMMARY に書き出す Markdown を組み立てる。
 * @param title サマリ見出し。
 * @param result 集計結果。
 * @returns 追記する Markdown 本文。
 */
export function buildSummary(title: string, result: ReportResult): string {
  const lines = [
    `## ${title}`,
    '',
    '| 項目 | 件数 |',
    '|---|---|',
    `| 通過 | ${result.passed} |`,
    `| 失敗 | ${result.failed} |`,
    `| スキップ | ${result.skipped} |`,
  ]
  if (result.failed > 0) {
    lines.push('', '失敗したテスト:', '')
    for (const f of result.failures) {
      lines.push(`- ${f.name}`)
    }
  }
  lines.push('')
  return lines.join('\n')
}

/**
 * 失敗テストの workflow コマンド (::error::) 一覧を組み立てる。
 * @param result 集計結果。
 * @returns 各要素が 1 件の ::error:: コマンド文字列になる一覧。
 */
export function buildAnnotations(result: ReportResult): string[] {
  return result.failures.map((f) => {
    const message = escapeData(`${f.name}: ${f.message}`)
    return f.file !== null && f.line !== null && f.line > 0
      ? `::error file=${escapeProperty(f.file)},line=${f.line}::${message}`
      : `::error::${message}`
  })
}

/**
 * workflow コマンドのメッセージ本文をエスケープする。
 * @param s エスケープ対象の文字列。
 * @returns エスケープ後の文字列。
 */
export function escapeData(s: string): string {
  return s.replaceAll('%', '%25').replaceAll('\r', '%0D').replaceAll('\n', '%0A')
}

/**
 * workflow コマンドのプロパティ値をエスケープする。
 * @param s エスケープ対象の文字列。
 * @returns エスケープ後の文字列。
 */
export function escapeProperty(s: string): string {
  return escapeData(s).replaceAll(':', '%3A').replaceAll(',', '%2C')
}
