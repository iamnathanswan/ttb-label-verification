const ICON = { PASS: '✓', REVIEW: '!', FAIL: '✕' }
const WORD = { PASS: 'Match', REVIEW: 'Check', FAIL: 'Mismatch' }

const TYPE_LABEL = {
  wine: 'Wine',
  distilled_spirits: 'Distilled spirits',
  malt_beverage: 'Malt beverages',
  unknown: '—',
}

/**
 * The comparison an agent came here for (MCH-07, MCH-09): what the application
 * declared, what the label says, and whether they agree. Values on both sides were
 * extracted, so this is the tool showing its work rather than asking for it.
 */
export default function Comparison({ result }) {
  const { application, pairing, fields, checks } = result
  if (!application) {
    return (
      <p className="note">
        {pairing?.detail || 'No application was paired with this label, so only the regulations were checked.'}
      </p>
    )
  }

  const outcomeFor = (name) => checks.find((c) => c.id.startsWith('MCH') && c.name.toLowerCase().includes(name))

  const rows = [
    { label: 'Brand name', field: 6, application: application.brand_name, onLabel: fields.brand_name, check: outcomeFor('brand') },
    { label: 'Fanciful name', field: 7, application: application.fanciful_name, onLabel: fields.brand_name, check: outcomeFor('fanciful') },
    { label: 'Producer', field: 8, application: application.applicant_name, onLabel: [fields.producer_name, fields.producer_address].filter(Boolean).join(', '), check: outcomeFor('producer') },
    { label: 'Source of product', field: 3, application: application.source_of_product ? application.source_of_product[0].toUpperCase() + application.source_of_product.slice(1) : '', onLabel: fields.country_of_origin || '—', check: checks.find((c) => c.id === 'VAL-13'), note: 'Declares which rules apply' },
    {
      label: 'Type of product', field: 5,
      application: TYPE_LABEL[application.type_of_product] || '',
      onLabel: TYPE_LABEL[fields.beverage_type] || '—',
      // A mismatch produces a finding; agreement produces none, so say so rather
      // than leaving a dash an agent has to interpret.
      check: outcomeFor('product type')
        || (application.type_of_product && application.type_of_product === fields.beverage_type
            ? { status: 'PASS' } : null),
      note: 'Selects Part 4, 5 or 7',
    },
  ].filter((row) => row.application)

  return (
    <div className="comparison">
      <div className="comparison__head">
        <h4>Application {application.serial_number && <code>{application.serial_number}</code>}</h4>
        <span className={`tag tag--${application.extraction_source}`}>
          {application.extraction_source === 'form_fields'
            ? 'read from form fields'
            : 'read by sight — scanned form'}
        </span>
      </div>
      {pairing?.detail && <p className="note">{pairing.detail}</p>}

      <table>
        <caption className="sr-only">Application values compared with the label</caption>
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Application</th>
            <th scope="col">Label</th>
            <th scope="col">Result</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">
                {row.label} <small>field {row.field}</small>
                {row.note && <em>{row.note}</em>}
              </th>
              <td><code>{row.application || '—'}</code></td>
              <td><code>{row.onLabel || '—'}</code></td>
              <td>
                {row.check ? (
                  <span className={`outcome outcome--${row.check.status.toLowerCase()}`}>
                    <span aria-hidden="true">{ICON[row.check.status]}</span> {WORD[row.check.status]}
                  </span>
                ) : (
                  <span className="outcome outcome--none">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="note">
        Net contents and alcohol content are not fields on TTB F 5100.31 — they are
        verified against the label&rsquo;s own requirements below.
      </p>
    </div>
  )
}
