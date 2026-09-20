import { describe, expect, it } from 'vitest'
import { resultsToCsv } from './csv.js'

/** BAT-05 — Janet in Seattle has been asking for batch export for years. */

const result = ({ fields: fieldOverrides, ...overrides } = {}) => ({
  filename: 'label.png',
  overall: 'FAIL',
  elapsed_ms: 4200,
  fields: {
    brand_name: 'OLD TOM DISTILLERY',
    class_type: 'Kentucky Straight Bourbon Whiskey',
    alcohol_content_pct: 45,
    net_contents_raw: '750 mL',
    producer_name: 'OLD TOM DISTILLERY',
    ...fieldOverrides,
  },
  checks: [
    { id: 'VAL-04', status: 'FAIL', advisory: false, detail: 'Body is bold.' },
    { id: 'VAL-08', status: 'REVIEW', advisory: true, detail: 'Requires measurement.' },
    { id: 'VAL-02', status: 'REVIEW', advisory: false, detail: 'Heading unclear.' },
  ],
  ...overrides,
})

const rows = (csv) => csv.split('\n')

/** Split a CSV line on commas that are not inside quotes. */
const cells = (line) => {
  const out = []
  let field = ''
  let quoted = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') { field += '"'; i++ } else { quoted = !quoted }
    } else if (ch === ',' && !quoted) {
      out.push(field); field = ''
    } else {
      field += ch
    }
  }
  out.push(field)
  return out
}

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
    expect(csv).toContain('NOT PROCESSED')
    expect(csv).toContain('unreadable')
  })

  it('keeps every row the same width as the header', () => {
    // Error rows were once built from a hardcoded list of blanks, so adding a
    // column silently shifted their values into the wrong ones.
    const csv = resultsToCsv([result()], [{ filename: 'bad.png', message: 'unreadable' }])
    const widths = new Set(rows(csv).map((line) => cells(line).length))
    expect(widths.size).toBe(1)
  })

  it('carries the application side of the comparison', () => {
    const csv = resultsToCsv([result({
      application: { filename: 'cola.pdf', serial_number: '24-0417', extraction_source: 'form_fields', brand_name: 'OLD TOM DISTILLERY' },
      pairing: { rule: 'sole_pair' },
    })], [])
    expect(csv).toContain('24-0417')
    expect(csv).toContain('form_fields')
    expect(csv).toContain('sole_pair')
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
