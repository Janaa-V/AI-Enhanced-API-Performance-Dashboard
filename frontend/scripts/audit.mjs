// Full dependency audit with a short list of reviewed exceptions (audit-allowlist.json).
//
// Production dependencies are audited separately with plain `npm audit --omit=dev`, which
// allows no exceptions; this script covers the development tools as well. It fails on any
// advisory that is not on the list, and on any list entry past its review date, so an
// exception is always written down, explained and re-checked.

import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'

// An exception is re-checked at least this often.
export const MAX_REVIEW_DAYS = 90
const DAY_MS = 24 * 60 * 60 * 1000

/** The advisories behind an `npm audit --json` report, one per GHSA id. */
export function advisoriesIn(report) {
  if (report.error) {
    throw new Error(`npm audit failed: ${report.error.summary ?? JSON.stringify(report.error)}`)
  }
  const found = new Map()
  for (const vulnerability of Object.values(report.vulnerabilities ?? {})) {
    // A string in `via` only names a vulnerable dependency; objects are the advisories.
    for (const via of vulnerability.via) {
      if (typeof via === 'object') {
        const id = via.url.split('/').pop()
        found.set(id, { id, package: via.name, severity: via.severity, title: via.title })
      }
    }
  }
  return [...found.values()]
}

/** Problems with the list itself: missing reasons, bad or too distant review dates. */
export function invalidEntries(allowlist, today) {
  const latest = new Date(Date.parse(today) + MAX_REVIEW_DAYS * DAY_MS).toISOString().slice(0, 10)
  const problems = []
  for (const entry of allowlist) {
    const label = entry.advisory ?? JSON.stringify(entry)
    if (!/^GHSA(-[0-9a-z]{4}){3}$/.test(entry.advisory ?? '')) {
      problems.push(`${label}: "advisory" must be a GHSA id`)
    }
    if (!entry.package || !entry.reason?.trim()) {
      problems.push(`${label}: "package" and "reason" are required`)
    }
    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(entry.reviewBy ?? '') ||
      Number.isNaN(Date.parse(entry.reviewBy))
    ) {
      problems.push(`${label}: "reviewBy" must be a date (YYYY-MM-DD)`)
    } else if (entry.reviewBy < today) {
      problems.push(`${label}: review date ${entry.reviewBy} has passed; re-check it`)
    } else if (entry.reviewBy > latest) {
      problems.push(`${label}: review date is more than ${MAX_REVIEW_DAYS} days away`)
    }
  }
  return problems
}

/** What fails the audit, and which list entries are no longer needed. */
export function judge(advisories, allowlist, today) {
  const allowed = new Set(allowlist.map((entry) => entry.advisory))
  const reported = new Set(advisories.map((advisory) => advisory.id))
  return {
    problems: invalidEntries(allowlist, today),
    blocking: advisories.filter((advisory) => !allowed.has(advisory.id)),
    unused: allowlist.filter((entry) => !reported.has(entry.advisory)),
  }
}

function main() {
  const run = spawnSync('npm', ['audit', '--json'], { encoding: 'utf8' })
  // npm audit exits non-zero whenever it finds anything, so the exit code is not the verdict.
  if (!run.stdout) {
    console.error(run.stderr || 'npm audit produced no output')
    process.exit(2)
  }
  const allowlist = JSON.parse(readFileSync(new URL('../audit-allowlist.json', import.meta.url)))
  const today = new Date().toISOString().slice(0, 10)
  const { problems, blocking, unused } = judge(
    advisoriesIn(JSON.parse(run.stdout)),
    allowlist,
    today,
  )

  for (const entry of unused) {
    console.warn(
      `No longer reported, remove from audit-allowlist.json: ${entry.advisory} (${entry.package})`,
    )
  }
  for (const entry of allowlist.filter((e) => !unused.includes(e))) {
    console.log(`Exception (review by ${entry.reviewBy}): ${entry.advisory} (${entry.package})`)
  }
  for (const problem of problems) console.error(`Allowlist: ${problem}`)
  for (const advisory of blocking) {
    console.error(`${advisory.severity}: ${advisory.package}: ${advisory.title} (${advisory.id})`)
  }
  if (problems.length || blocking.length) process.exit(1)
  console.log('Full audit passed.')
}

if (import.meta.url === `file://${process.argv[1]}`) main()
