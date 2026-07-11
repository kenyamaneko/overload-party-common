import { describe, expect, it } from 'vitest'
import { buildAnnotations, buildSummary, escapeData, escapeProperty, extractLocation, parse } from '../src/report.ts'

describe('vitest json レポート解析', () => {
  it('通過・失敗・スキップが混在するとき、それぞれの件数が集計される', () => {
    const json = JSON.stringify({
      testResults: [
        {
          name: '/repo/src/foo.test.ts',
          assertionResults: [
            { status: 'passed', fullName: '対象 成功する', failureMessages: [] },
            {
              status: 'failed',
              fullName: '対象 失敗する',
              failureMessages: [
                'AssertionError: expected 1 to be 2\n    at /repo/src/foo.test.ts:5:15\n    at internal',
              ],
            },
            { status: 'pending', fullName: '対象 未実行', failureMessages: [] },
          ],
        },
      ],
    })

    const result = parse(json, '/repo')

    expect(result.passed).toBe(1)
    expect(result.failed).toBe(1)
    expect(result.skipped).toBe(1)
  })

  it('未知のstatus値を持つとき、エラーになる', () => {
    const json = JSON.stringify({
      testResults: [
        {
          name: '/repo/src/foo.test.ts',
          assertionResults: [{ status: 'running', fullName: '対象 実行中', failureMessages: [] }],
        },
      ],
    })

    expect(() => parse(json, '/repo')).toThrow('unknown vitest assertion status: running')
  })

  it('失敗したテストがあるとき、テスト名とメッセージと相対パスの失敗位置を保持する', () => {
    const json = JSON.stringify({
      testResults: [
        {
          name: '/repo/src/foo.test.ts',
          assertionResults: [
            {
              status: 'failed',
              fullName: '対象 失敗する',
              failureMessages: [
                'AssertionError: expected 1 to be 2\n    at /repo/src/foo.test.ts:5:15\n    at internal',
              ],
            },
          ],
        },
      ],
    })

    const result = parse(json, '/repo')

    expect(result.failures).toEqual([
      { name: '対象 失敗する', message: 'AssertionError: expected 1 to be 2', file: 'src/foo.test.ts', line: 5 },
    ])
  })
})

describe('失敗位置の抽出', () => {
  it('スタックトレースに file:line があるとき、ワークスペース相対パスと行番号を返す', () => {
    const { file, line } = extractLocation(
      'AssertionError: boom\n    at /repo/src/foo.test.ts:5:15\n    at internal',
      '/repo'
    )

    expect(file).toBe('src/foo.test.ts')
    expect(line).toBe(5)
  })

  it('file:line が見つからないとき、file と line はともに null になる', () => {
    const { file, line } = extractLocation('予期しない例外が発生しました', '/repo')

    expect(file).toBeNull()
    expect(line).toBeNull()
  })
})

describe('サマリ生成', () => {
  it('失敗が無いとき、失敗したテストの一覧は出力されない', () => {
    const summary = buildSummary('単体テスト結果', { passed: 3, failed: 0, skipped: 0, failures: [] })

    expect(summary).toContain('## 単体テスト結果')
    expect(summary).not.toContain('失敗したテスト')
  })

  it('失敗があるとき、失敗したテストの名前一覧が出力される', () => {
    const summary = buildSummary('単体テスト結果', {
      passed: 1,
      failed: 1,
      skipped: 0,
      failures: [{ name: '対象 失敗する', message: 'msg', file: 'a.ts', line: 1 }],
    })

    expect(summary).toContain('失敗したテスト')
    expect(summary).toContain('- 対象 失敗する')
  })
})

describe('注釈生成', () => {
  it('失敗位置がわかるとき、file と line を伴う ::error:: になる', () => {
    const annotations = buildAnnotations({
      passed: 0,
      failed: 1,
      skipped: 0,
      failures: [{ name: '対象 失敗する', message: '期待値と異なる', file: 'src/foo.test.ts', line: 5 }],
    })

    expect(annotations).toEqual(['::error file=src/foo.test.ts,line=5::対象 失敗する: 期待値と異なる'])
  })

  it('失敗位置がわからないとき、file と line を伴わない ::error:: になる', () => {
    const annotations = buildAnnotations({
      passed: 0,
      failed: 1,
      skipped: 0,
      failures: [{ name: '対象 失敗する', message: '予期しない例外', file: null, line: null }],
    })

    expect(annotations).toEqual(['::error::対象 失敗する: 予期しない例外'])
  })
})

describe('workflowコマンド本文エスケープ', () => {
  it.each([
    { label: 'パーセント記号を含む', input: '100%失敗', want: '100%25失敗' },
    { label: '復帰(CR)を含む', input: '1行目\r2行目', want: '1行目%0D2行目' },
    { label: '改行(LF)を含む', input: '1行目\n2行目', want: '1行目%0A2行目' },
  ])('$label', ({ input, want }) => {
    expect(escapeData(input)).toBe(want)
  })
})

describe('workflowコマンドプロパティエスケープ', () => {
  it.each([
    { label: 'コロンを含む', input: 'src/foo:bar.ts', want: 'src/foo%3Abar.ts' },
    { label: 'カンマを含む', input: 'a,b.ts', want: 'a%2Cb.ts' },
  ])('$label', ({ input, want }) => {
    expect(escapeProperty(input)).toBe(want)
  })
})
