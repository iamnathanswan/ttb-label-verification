import { useState } from 'react'

const STATUS_ICON = { PASS: '✓', REVIEW: '!', FAIL: '✕' }

function Check({ check }) {
  return (
    <li className={`check check--${check.status.toLowerCase()}`}>
      <span className="check__status" aria-hidden="true">{STATUS_ICON[check.status]}</span>
      <div>
        <p className="check__name">
          <span className="sr-only">{check.status}: </span>
          {check.name}
          {check.advisory && <span className="check__tag">advisory</span>}
        </p>
        <p className="check__detail">{check.detail}</p>
        {check.expected && check.observed && (
          <p className="check__compare">
            <span>application: <code>{check.expected}</code></span>
            <span>label: <code>{check.observed}</code></span>
          </p>
        )}
        {check.citation && <p className="check__cite">{check.citation}</p>}
      </div>
    </li>
  )
}

export default function App() {
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true); setError(null); setResult(null)
    try {
      const res = await fetch('/api/verify', { method: 'POST', body: new FormData(e.target) })
      const body = await res.json()
      if (!res.ok) throw new Error(body.detail || 'Verification failed.')
      setResult(body)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const decidable = result?.checks.filter((c) => !c.advisory) ?? []
  const advisory = result?.checks.filter((c) => c.advisory) ?? []

  return (
    <main>
      <h1>TTB Label Verification</h1>
      <p className="lede">
        Check an alcohol beverage label against TTB requirements under 27 CFR Parts 5 and 16.
      </p>

      <form onSubmit={onSubmit}>
        <label className="field">
          <span>Label image or PDF</span>
          <input type="file" name="file" accept="image/*,application/pdf" required />
        </label>
        <details>
          <summary>Compare against application values (optional)</summary>
          <label className="field"><span>Brand name</span><input name="brand_name" /></label>
          <label className="field"><span>Class / type</span><input name="class_type" /></label>
          <label className="field"><span>Alcohol content (% by volume)</span>
            <input name="alcohol_content_pct" type="number" step="0.1" /></label>
          <label className="field"><span>Net contents</span><input name="net_contents" /></label>
        </details>
        <button type="submit" disabled={busy}>{busy ? 'Checking…' : 'Check label'}</button>
      </form>

      <div aria-live="polite">
        {error && <p className="error" role="alert">{error}</p>}

        {result && (
          <section className="result">
            <h2 className={`verdict verdict--${result.overall.toLowerCase()}`}>
              <span aria-hidden="true">{STATUS_ICON[result.overall]}</span> {result.overall}
              <span className="verdict__meta">{result.filename} · {result.elapsed_ms} ms</span>
            </h2>

            <ul className="checks">
              {decidable.map((c, i) => <Check key={i} check={c} />)}
            </ul>

            {advisory.length > 0 && (
              <>
                <h3>Requires physical inspection</h3>
                <p className="note">
                  These depend on measurement an image cannot supply, so they apply to every
                  label alike and do not affect the verdict above.
                </p>
                <ul className="checks">
                  {advisory.map((c, i) => <Check key={i} check={c} />)}
                </ul>
              </>
            )}
          </section>
        )}
      </div>
    </main>
  )
}
