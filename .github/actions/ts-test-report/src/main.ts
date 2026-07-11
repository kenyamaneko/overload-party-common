import { appendFileSync, readFileSync } from 'node:fs'
import { buildAnnotations, buildSummary, parse } from './report.ts'

const [jsonPath, title] = process.argv.slice(2)
if (!jsonPath || !title) {
  console.error('usage: ts-test-report <json-path> <title>')
  process.exit(1)
}

const workspace = process.env.GITHUB_WORKSPACE ?? ''
const jsonText = readFileSync(jsonPath, 'utf-8')
const result = parse(jsonText, workspace)

const summaryPath = process.env.GITHUB_STEP_SUMMARY
if (summaryPath) {
  appendFileSync(summaryPath, buildSummary(title, result))
}

for (const line of buildAnnotations(result)) {
  console.log(line)
}
