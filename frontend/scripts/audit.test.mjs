import { describe, expect, it } from 'vitest'

import { advisoriesIn, invalidEntries, judge } from './audit.mjs'

const TODAY = '2026-10-05'
const BRACES = 'GHSA-vfj7-8cjw-p6xm'

// The shape `npm audit --json` prints: one advisory, plus a package that only depends on it.
const REPORT = {
  auditReportVersion: 2,
  vulnerabilities: {
    braces: {
      severity: 'high',
      via: [
        {
          name: 'braces',
          title: 'braces vulnerable to stack-exhaustion denial of service',
          url: `https://github.com/advisories/${BRACES}`,
          severity: 'high',
        },
      ],
    },
    micromatch: { severity: 'high', via: ['braces'] },
  },
}

function entry(overrides = {}) {
  return {
    advisory: BRACES,
    package: 'braces',
    reason: 'Development tool only.',
    reviewBy: '2026-11-05',
    ...overrides,
  }
}

describe('advisoriesIn', () => {
  it('lists each advisory once and skips packages that only depend on one', () => {
    expect(advisoriesIn(REPORT)).toEqual([
      {
        id: BRACES,
        package: 'braces',
        severity: 'high',
        title: 'braces vulnerable to stack-exhaustion denial of service',
      },
    ])
  })

  it('finds nothing in a clean report', () => {
    expect(advisoriesIn({ auditReportVersion: 2, vulnerabilities: {} })).toEqual([])
  })

  it('fails loudly when npm audit itself failed', () => {
    expect(() => advisoriesIn({ error: { summary: 'network down' } })).toThrow('network down')
  })
})

describe('judge', () => {
  it('passes when every advisory is on the list', () => {
    expect(judge(advisoriesIn(REPORT), [entry()], TODAY)).toEqual({
      problems: [],
      blocking: [],
      unused: [],
    })
  })

  it('blocks an advisory that is not on the list', () => {
    const { blocking } = judge(advisoriesIn(REPORT), [], TODAY)
    expect(blocking.map((advisory) => advisory.id)).toEqual([BRACES])
  })

  it('reports list entries that are no longer needed, without failing', () => {
    const result = judge([], [entry()], TODAY)
    expect(result.unused).toEqual([entry()])
    expect(result.problems).toEqual([])
    expect(result.blocking).toEqual([])
  })
})

describe('invalidEntries', () => {
  it('accepts a complete entry due for review within 90 days', () => {
    expect(invalidEntries([entry({ reviewBy: '2027-01-03' })], TODAY)).toEqual([])
  })

  it('accepts an entry due for review today', () => {
    expect(invalidEntries([entry({ reviewBy: TODAY })], TODAY)).toEqual([])
  })

  it.each([
    ['a passed review date', { reviewBy: '2026-10-04' }, 'has passed'],
    ['a review date over 90 days away', { reviewBy: '2027-01-04' }, 'more than 90 days'],
    ['a date that is not YYYY-MM-DD', { reviewBy: '5 Nov 2026' }, 'must be a date'],
    ['no reason', { reason: '  ' }, 'required'],
    ['no package', { package: '' }, 'required'],
    ['an id that is not a GHSA id', { advisory: '1240992' }, 'GHSA id'],
  ])('rejects %s', (_name, overrides, message) => {
    const [problem] = invalidEntries([entry(overrides)], TODAY)
    expect(problem).toContain(message)
  })
})
