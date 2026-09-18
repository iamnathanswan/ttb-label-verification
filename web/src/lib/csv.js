/** Export batch results (BAT-05). Janet in Seattle has been asking for years. */

const COLUMNS = [
  ['File', (r) => r.filename],
  ['Result', (r) => r.overall],
  ['Failed rules', (r) => r.checks.filter((c) => c.status === 'FAIL').map((c) => c.id).join(' ')],
  ['Needs review', (r) => r.checks.filter((c) => c.status === 'REVIEW' && !c.advisory).map((c) => c.id).join(' ')],
  ['Brand name', (r) => r.fields.brand_name],
  ['Class/type', (r) => r.fields.class_type],
  ['Alcohol content', (r) => (r.fields.alcohol_content_pct ?? '') && `${r.fields.alcohol_content_pct}%`],
  ['Net contents', (r) => r.fields.net_contents_raw],
  ['Producer', (r) => r.fields.producer_name],
  ['Findings', (r) => r.checks.filter((c) => c.status !== 'PASS' && !c.advisory).map((c) => c.detail).join(' | ')],
  ['Milliseconds', (r) => r.elapsed_ms],
]

/**
 * Spreadsheets treat a leading =, +, -, @, tab or CR as the start of a formula.
 * Label text reaches this file from whatever is printed on an uploaded image, so
 * a brand name of `=cmd|'/c calc'!A1` would execute on open. Prefixing with an
 * apostrophe forces the cell to be read as text; Excel and Sheets both hide it.
 */
const neutralise = (text) => (/^[=+\-@\t\r]/.test(text) ? `'${text}` : text)

const escape = (value) => {
  const text = neutralise(value == null ? '' : String(value))
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function resultsToCsv(results, errors) {
  const lines = [COLUMNS.map(([h]) => escape(h)).join(',')]
  for (const r of results) lines.push(COLUMNS.map(([, get]) => escape(get(r))).join(','))
  for (const e of errors) lines.push([escape(e.filename), 'ERROR', '', '', '', '', '', '', '', escape(e.message), ''].join(','))
  return lines.join('\n')
}

export function downloadCsv(filename, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
