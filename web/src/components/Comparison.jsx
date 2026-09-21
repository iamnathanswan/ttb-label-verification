const ICON = { PASS: '✓', REVIEW: '!', FAIL: '✕' }
const WORD = { PASS: 'Match', REVIEW: 'Check', FAIL: 'Mismatch' }

const TYPE_LABEL = {
  wine: 'Wine',
  distilled_spirits: 'Distilled spirits',
  malt_beverage: 'Malt beverages',
  unknown: '—',
}

const titled = (value) => (value ? value[0].toUpperCase() + value.slice(1) : '')

/**
 * The comparison an agent came here for (MCH-07, MCH-09): what the application
 * declared, what the label says, and whether they agree. Values on both sides were
 * extracted, so this is the tool showing its work rather than asking for it.
 *
 * Laid out as stacked rows rather than a four-column table so it reads in a
 * half-width column beside the regulation findings.
 */
export default function Comparison({ result }) {
  const { application, pairing, fields, checks } = result
  if (!application) {
    return (
      <p className="note">
        {pairing?.detail
          || 'No application was paired with this label, so only the regulations were checked.'}
      </p>
    )
  }

  const outcomeFor = (name) =>
    checks.find((c) => c.id.startsWith('MCH') && c.name.toLowerCase().includes(name))

  const rows = [
    {
      label: 'Brand name', field: 6,
      application: application.brand_name, onLabel: fields.brand_name,
      check: outcomeFor('brand'),
    },
    {
      label: 'Fanciful name', field: 7,
      application: application.fanciful_name, onLabel: fields.brand_name,
      check: outcomeFor('fanciful'),
    },
    {
      label: 'Producer', field: 8,
      application: application.applicant_name,
      onLabel: [fields.producer_name, fields.producer_address].filter(Boolean).join(', '),
      check: outcomeFor('producer'),
    },
    {
      label: 'Source of product', field: 3,
      application: titled(application.source_of_product),
      onLabel: fields.country_of_origin || '—',
      check: checks.find((c) => c.id === 'VAL-13'),
      note: 'Declares which rules apply',
    },
    {
      label: 'Type of product', field: 5,
      application: TYPE_LABEL[application.type_of_product] || '',
      onLabel: TYPE_LABEL[fields.beverage_type] || '—',
      check: outcomeFor('product type')
        || (application.type_of_product && application.type_of_product === fields.beverage_type
          ? { status: 'PASS' } : null),
      note: 'Selects Part 4, 5 or 7',
    },
  ].filter((row) => row.application)

  return (
    <div className="comparison">
      <div className="comparison__head">
        <h5>
          Application {application.serial_number && <code>{application.serial_number}</code>}
        </h5>
        <span className={`tag tag--${application.extraction_source}`}>
          {application.extraction_source === 'form_fields'
            ? 'read from form fields'
            : 'read by sight — scanned form'}
        </span>
      </div>
      {pairing?.detail && <p className="note">{pairing.detail}</p>}

      <ul className="fieldrows">
        {rows.map((row) => (
          <li key={row.label} className={`fieldrow${row.check ? ` fieldrow--${row.check.status.toLowerCase()}` : ''}`}>
            <p className="fieldrow__head">
              <span className="fieldrow__name">
                {row.label} <small>field {row.field}</small>
              </span>
              {row.check && (
                <span className={`outcome outcome--${row.check.status.toLowerCase()}`}>
                  <span aria-hidden="true">{ICON[row.check.status]}</span>{' '}
                  <span className="sr-only">Result: </span>{WORD[row.check.status]}
                </span>
              )}
            </p>
            {row.note && <p className="fieldrow__note">{row.note}</p>}
            <dl className="fieldrow__values">
              <dt>Application</dt>
              <dd><code>{row.application || '—'}</code></dd>
              <dt>Label</dt>
              <dd><code>{row.onLabel || '—'}</code></dd>
            </dl>
          </li>
        ))}
      </ul>

      <p className="note">
        Net contents and alcohol content are not fields on TTB F 5100.31 — they are
        verified against the label&rsquo;s own requirements.
      </p>
    </div>
  )
}
