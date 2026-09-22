import { useState } from 'react'
import Comparison from './Comparison.jsx'

const ICON = { PASS: '✓', REVIEW: '!', FAIL: '✕' }
const WORD = { PASS: 'Passed', REVIEW: 'Needs review', FAIL: 'Failed' }

/** A compact tally so each section states its own outcome. */
function Count({ checks }) {
  if (!checks.length) return <span className="count count--none">not checked</span>
  const failed = checks.filter((c) => c.status === 'FAIL').length
  const review = checks.filter((c) => c.status === 'REVIEW').length
  if (failed) return <span className="count count--fail">{failed} failed</span>
  if (review) return <span className="count count--review">{review} to check</span>
  return <span className="count count--pass">all clear</span>
}

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

export default function ResultCard({ result, defaultOpen, stacked = false }) {
  const [open, setOpen] = useState(Boolean(defaultOpen))

  // Two different questions, answered differently. Compliance asks whether the
  // label is lawful on its own terms; matching asks whether it agrees with the
  // application, which is as often fixed by correcting the form as the label.
  const decidable = result.checks.filter((c) => !c.advisory)
  const matching = decidable.filter((c) => c.category === 'matching')
  const compliance = decidable.filter((c) => c.category !== 'matching')
  const advisory = result.checks.filter((c) => c.advisory)

  const count = (list, status) => list.filter((c) => c.status === status).length
  const parts = []
  if (count(compliance, 'FAIL')) parts.push(`${count(compliance, 'FAIL')} rule${count(compliance, 'FAIL') > 1 ? 's' : ''} failed`)
  if (count(matching, 'FAIL')) parts.push(`${count(matching, 'FAIL')} mismatch${count(matching, 'FAIL') > 1 ? 'es' : ''}`)
  const reviews = count(compliance, 'REVIEW') + count(matching, 'REVIEW')
  if (reviews) parts.push(`${reviews} to check`)
  const summary = parts.join(' · ') || 'No issues found in the checks that can be made from an image'

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
        <span className="card__meta">
          {result.application?.serial_number && (
            <span className="card__serial">{result.application.serial_number}</span>
          )}
          {result.elapsed_ms} ms
        </span>
        <span className="card__chevron" aria-hidden="true">{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div className="card__detail">
          {/* Side by side: the two questions are read together, and seeing one
              clear while the other is not is the comparison an agent makes. */}
          <div className={stacked ? 'columns columns--stacked' : 'columns'}>
          <section className="group">
            <h4>
              Against the application
              <Count checks={matching} />
            </h4>
            <p className="note">
              Does the label say what was declared on the COLA application? A disagreement
              here is as often corrected on the form as on the label.
            </p>
            <Comparison result={result} />
            {matching.length > 0 && (
              <ul className="checks">
                {matching.map((c, i) => <Check key={`m-${c.id}-${i}`} check={c} />)}
              </ul>
            )}
          </section>

          <section className="group">
            <h4>
              Against the regulations
              <Count checks={compliance} />
            </h4>
            <p className="note">
              Is the label lawful on its own terms? Answered from the label and 27 CFR
              alone — a label can match its application exactly and still fail here.
            </p>
            <ul className="checks">
              {compliance.map((c, i) => <Check key={`c-${c.id}-${i}`} check={c} />)}
            </ul>
          </section>
          </div>

          {advisory.length > 0 && (
            <section className="group">
              <h4>Requires physical inspection</h4>
              <p className="note">
                These depend on measurement a photograph cannot supply, so they apply to
                every label alike and do not affect the result above.
              </p>
              <ul className="checks">
                {advisory.map((c, i) => <Check key={`adv-${c.id}-${i}`} check={c} />)}
              </ul>
            </section>
          )}

        </div>
      )}
    </article>
  )
}
