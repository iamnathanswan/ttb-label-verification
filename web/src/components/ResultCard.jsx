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

export default function ResultCard({ result, defaultOpen }) {
  const [open, setOpen] = useState(Boolean(defaultOpen))
  const [tab, setTab] = useState(null)

  // Two different questions, answered differently. Compliance asks whether the
  // label is lawful on its own terms; matching asks whether it agrees with the
  // application, which is as often fixed by correcting the form as the label.
  const decidable = result.checks.filter((c) => !c.advisory)
  const matching = decidable.filter((c) => c.category === 'matching')
  const compliance = decidable.filter((c) => c.category !== 'matching')
  const advisory = result.checks.filter((c) => c.advisory)

  const count = (list, status) => list.filter((c) => c.status === status).length

  // Three questions, not one list. Which is open by default is decided by the
  // findings: an agent opening a failed result wants the failure, and hunting for
  // it behind a tab would be worse than the single scroll this replaced.
  const sections = [
    {
      id: 'matching',
      title: 'Against the application',
      checks: matching,
      note: 'Does the label say what was declared on the COLA application? A disagreement '
        + 'here is as often corrected on the form as on the label.',
    },
    {
      id: 'compliance',
      title: 'Against the regulations',
      checks: compliance,
      note: 'Is the label lawful on its own terms? Answered from the label and 27 CFR '
        + 'alone — a label can match its application exactly and still fail here.',
    },
    {
      id: 'advisory',
      title: 'Requires physical inspection',
      checks: advisory,
      note: 'These depend on measurement a photograph cannot supply, so they apply to '
        + 'every label alike and do not affect the result above.',
    },
  ].filter((s) => s.checks.length > 0 || s.id === 'matching')

  const worst = (s) => (count(s.checks, 'FAIL') ? 0 : count(s.checks, 'REVIEW') ? 1 : 2)
  const defaultTab = [...sections].sort((a, b) => worst(a) - worst(b))[0]?.id
  const active = tab && sections.some((s) => s.id === tab) ? tab : defaultTab

  const onTabKey = (event) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key]
    if (!step) return
    event.preventDefault()
    const i = sections.findIndex((s) => s.id === active)
    const next = sections[(i + step + sections.length) % sections.length]
    setTab(next.id)
    event.currentTarget.parentElement.querySelector(`[data-tab="${next.id}"]`)?.focus()
  }
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
          <div className="tabs" role="tablist" aria-label={`Findings for ${result.filename}`}>
            {sections.map((s) => (
              <button
                key={s.id}
                type="button"
                role="tab"
                data-tab={s.id}
                aria-selected={s.id === active}
                tabIndex={s.id === active ? 0 : -1}
                className={`tabs__tab${s.id === active ? ' tabs__tab--on' : ''}`}
                onClick={() => setTab(s.id)}
                onKeyDown={onTabKey}
              >
                {s.title}
                <Count checks={s.checks} />
              </button>
            ))}
          </div>

          {sections.map((s) => (
            s.id === active && (
              <section className="group" key={s.id} role="tabpanel" tabIndex={-1}>
                <p className="note">{s.note}</p>
                {s.id === 'matching' && <Comparison result={result} />}
                {s.checks.length > 0 && (
                  <ul className="checks">
                    {s.checks.map((c, i) => <Check key={`${s.id}-${c.id}-${i}`} check={c} />)}
                  </ul>
                )}
              </section>
            )
          ))}
        </div>
      )}
    </article>
  )
}
