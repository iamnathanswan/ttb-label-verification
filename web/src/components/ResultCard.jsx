import { useState } from 'react'

const ICON = { PASS: '✓', REVIEW: '!', FAIL: '✕' }
const WORD = { PASS: 'Passed', REVIEW: 'Needs review', FAIL: 'Failed' }

function Check({ check }) {
  return (
    <li className={`check check--${check.status.toLowerCase()}`}>
      <span className="check__icon" aria-hidden="true">{ICON[check.status]}</span>
      <div className="check__body">
        <p className="check__name">
          {/* Status is announced in text, not conveyed by colour alone (UX-04). */}
          <span className="sr-only">{WORD[check.status]}: </span>
          {check.name}
          {check.advisory && <span className="tag">advisory</span>}
        </p>
        <p className="check__detail">{check.detail}</p>
        {(check.expected || check.observed) && (
          <dl className="compare">
            {check.expected && (<><dt>Application</dt><dd><code>{check.expected}</code></dd></>)}
            {check.observed && (<><dt>Label</dt><dd><code>{check.observed}</code></dd></>)}
          </dl>
        )}
        {check.citation && <p className="cite">{check.citation}</p>}
      </div>
    </li>
  )
}

export default function ResultCard({ result, defaultOpen }) {
  const [open, setOpen] = useState(Boolean(defaultOpen))
  const decidable = result.checks.filter((c) => !c.advisory)
  const advisory = result.checks.filter((c) => c.advisory)
  const failed = decidable.filter((c) => c.status === 'FAIL')
  const review = decidable.filter((c) => c.status === 'REVIEW')

  const summary =
    failed.length ? `${failed.length} rule${failed.length > 1 ? 's' : ''} failed`
    : review.length ? `${review.length} item${review.length > 1 ? 's' : ''} need review`
    : 'No issues found in the checks that can be made from an image'

  return (
    <article className={`card card--${result.overall.toLowerCase()}`}>
      <button
        type="button"
        className="card__head"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="card__icon" aria-hidden="true">{ICON[result.overall]}</span>
        <span className="card__title">
          <span className="card__file">{result.filename}</span>
          <span className="card__summary">
            <strong>{WORD[result.overall]}</strong> — {summary}
          </span>
        </span>
        <span className="card__meta">{result.elapsed_ms} ms</span>
        <span className="card__chevron" aria-hidden="true">{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div className="card__detail">
          <ul className="checks">
            {decidable.map((c, i) => <Check key={`${c.id}-${i}`} check={c} />)}
          </ul>
          {advisory.length > 0 && (
            <>
              <h4>Requires physical inspection</h4>
              <p className="note">
                These depend on measurement a photograph cannot supply, so they apply to
                every label alike and do not affect the result above.
              </p>
              <ul className="checks">
                {advisory.map((c, i) => <Check key={`adv-${c.id}-${i}`} check={c} />)}
              </ul>
            </>
          )}
        </div>
      )}
    </article>
  )
}
