import { describe, expect, it } from 'vitest'
import { resultsToCsv } from './csv.js'

/** BAT-05 — Janet in Seattle has been asking for batch export for years. */

const result = (overrides = {}) => ({
  filename: 'label.png',
  overall: 'FAIL',
  elapsed_ms: 4200,
  fields: {
    brand_name: 'OLD TOM DISTILLERY',
    class_type: 'Kentucky Straight Bourbon Whiskey',
    alcohol_content_pct: 45,
    net_contents_raw: '750 mL',
    producer_name: 'OLD TOM DISTILLERY',
    ...overrides.fields,
  },
  checks: [
    { id: 'VAL-04', status: 'FAIL', advisory: false, detail: 'Body is bold.' },
    { id: 'VAL-08', status: 'REVIEW', advisory: true, detail: 'Requires measurement.' },
    { id: 'VAL-02', status: 'REVIEW', advisory: false, detail: 'Heading unclear.' },
  ],
  ...overrides,
})

const rows = (csv) => csv.split('\n')
const cells = (line) => line.match(/("([^"]|"")*"|[^,]*)/g).filter((_, i) => i % 2 === 0)

describe('resultsToCsv', () => {
  it('writes a header and one row per result', () => {
    const csv = resultsToCsv([result(), result({ filename: 'b.png' })], [])
    expect(rows(csv)).toHaveLength(3)
    expect(rows(csv)[0]).toContain('File')
  })

  it('lists failed rules but keeps advisories out of the review column', () => {
    const [, row] = rows(resultsToCsv([result()], []))
    expect(row).toContain('VAL-04')
    expect(row).toContain('VAL-02')
    expect(row).not.toContain('VAL-08')
  })

  it('includes labels that could not be read, so nothing disappears', () => {
    const csv = resultsToCsv([result()], [{ filename: 'bad.png', message: 'unreadable' }])
    expect(csv).toContain('bad.png')
    expect(csv).toContain('ERROR')
  })

  it('quotes fields containing commas or quotes', () => {
    const csv = resultsToCsv([result({ fields: { producer_name: 'Smith, Sons "Ltd"' } })], [])
    expect(csv).toContain('"Smith, Sons ""Ltd"""')
  })

  // Brand names come from whatever is printed on an uploaded label, so this is
  // attacker-controlled text heading for a spreadsheet.
  it.each(['=cmd|\'/c calc\'!A1', '+1+1', '-2+3', '@SUM(A1)'])(
    'neutralises the formula trigger in %s',
    (payload) => {
      const csv = resultsToCsv([result({ fields: { brand_name: payload } })], [])
      expect(csv).not.toMatch(new RegExp(`(^|,)"?\\${payload[0]}`, 'm'))
      expect(csv).toContain(`'${payload[0]}`)
    },
  )

  it('leaves ordinary values untouched', () => {
    const csv = resultsToCsv([result()], [])
    expect(csv).toContain('OLD TOM DISTILLERY')
    expect(csv).not.toContain("'OLD TOM")
  })
})
