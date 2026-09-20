import { useCallback, useEffect, useRef, useState } from 'react'
import DropZone from './components/DropZone.jsx'
import ResultCard from './components/ResultCard.jsx'
import { downscale } from './lib/downscale.js'
import { readEventStream } from './lib/sse.js'
import { downloadCsv, resultsToCsv } from './lib/csv.js'
import { useFileDrop } from './lib/useFileDrop.js'

const EMPTY = { results: [], errors: [], progress: null, elapsed: null }

export default function App() {
  const [files, setFiles] = useState([])
  const [expectedCsv, setExpectedCsv] = useState(null)
  const [run, setRun] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [fatal, setFatal] = useState(null)
  const [limits, setLimits] = useState({ max_batch_files: 300 })
  const resultsRef = useRef(null)

  useEffect(() => {
    fetch('/api/config').then((r) => r.json()).then(setLimits).catch(() => {})
  }, [])

  const addFiles = useCallback((incoming) => {
    setFiles((current) => {
      const merged = [...current]
      for (const f of incoming) {
        if (!merged.some((e) => e.name === f.name && e.size === f.size)) merged.push(f)
      }
      return merged.slice(0, limits.max_batch_files)
    })
  }, [limits.max_batch_files])

  // Files may be dropped anywhere on the page, not only on the zone.
  const dragging = useFileDrop(addFiles, { disabled: busy })

  const removeFile = (target) =>
    setFiles((current) => current.filter((f) => !(f.name === target.name && f.size === target.size)))

  async function verify() {
    if (!files.length) return
    setBusy(true); setFatal(null); setRun({ ...EMPTY, progress: { completed: 0, total: files.length } })

    try {
      const form = new FormData()
      for (const file of files) form.append('files', await downscale(file), file.name)
      if (expectedCsv) form.append('expected_csv', expectedCsv, expectedCsv.name)

      const response = await fetch('/api/verify/batch', { method: 'POST', body: form })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `Verification failed (HTTP ${response.status}).`)
      }

      await readEventStream(response, (event, payload) => {
        if (event === 'result') {
          setRun((s) => ({ ...s, results: [...s.results, payload], progress: payload.progress }))
        } else if (event === 'error') {
          setRun((s) => ({ ...s, errors: [...s.errors, payload], progress: payload.progress }))
        } else if (event === 'done') {
          setRun((s) => ({ ...s, elapsed: payload.elapsed_ms }))
        }
      })
      resultsRef.current?.focus()
    } catch (err) {
      setFatal(err.message)
    } finally {
      setBusy(false)
    }
  }

  const { results, errors, progress, elapsed } = run
  const done = results.length + errors.length
  const counts = {
    FAIL: results.filter((r) => r.overall === 'FAIL').length,
    REVIEW: results.filter((r) => r.overall === 'REVIEW').length,
    PASS: results.filter((r) => r.overall === 'PASS').length,
  }
  // Worst first: an agent works the rejections, not the passes.
  const order = { FAIL: 0, REVIEW: 1, PASS: 2 }
  const sorted = [...results].sort((a, b) => order[a.overall] - order[b.overall])

  return (
    <>
      <a href="#results" className="skip">Skip to results</a>
      <main>
        <header>
          <h1>TTB Label Verification</h1>
          <p className="lede">
            Check alcohol beverage labels against the requirements in 27 CFR Parts 5 and 16.
            Upload one label or a whole batch.
          </p>
        </header>

        <section aria-labelledby="upload-heading">
          <h2 id="upload-heading" className="sr-only">Upload labels</h2>
          <DropZone
            onBrowse={addFiles}
            disabled={busy}
            maxFiles={limits.max_batch_files}
            dragging={dragging}
          />

          {files.length > 0 && (
            <div className="queue">
              <h3>{files.length} label{files.length > 1 ? 's' : ''} ready</h3>
              <ul>
                {files.map((f) => (
                  <li key={`${f.name}-${f.size}`}>
                    <span className="queue__name">{f.name}</span>
                    <button type="button" onClick={() => removeFile(f)} disabled={busy}>
                      Remove<span className="sr-only"> {f.name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <details className="panel">
            <summary>Compare against application values (optional)</summary>
            <p className="note">
              Upload a CSV with a <code>filename</code> column plus any of{' '}
              <code>brand_name</code>, <code>class_type</code>, <code>alcohol_content_pct</code>,{' '}
              <code>net_contents</code>, <code>producer_name</code>, <code>country_of_origin</code>.
              Without it, labels are still checked against the regulations.
            </p>
            <label className="field">
              <span>Application values (CSV)</span>
              <input type="file" accept=".csv,text/csv" disabled={busy}
                     onChange={(e) => setExpectedCsv(e.target.files?.[0] || null)} />
            </label>
          </details>

          <button type="button" className="primary" onClick={verify} disabled={busy || !files.length}>
            {busy ? 'Checking…' : `Check ${files.length || ''} label${files.length === 1 ? '' : 's'}`.trim()}
          </button>
        </section>

        {fatal && <p className="error" role="alert">{fatal}</p>}

        <section id="results" aria-labelledby="results-heading" tabIndex={-1} ref={resultsRef}>
          <h2 id="results-heading" className="sr-only">Results</h2>

          {/* Streaming updates are announced politely rather than on every card. */}
          <p className="sr-only" aria-live="polite">
            {busy && progress ? `Checked ${done} of ${progress.total} labels.`
              : elapsed != null ? `Finished. ${counts.FAIL} failed, ${counts.REVIEW} need review, ${counts.PASS} passed.`
              : ''}
          </p>

          {progress && (
            <div className="summary">
              <div className="progress">
                <div className="progress__bar" style={{ width: `${(done / progress.total) * 100}%` }} />
              </div>
              <p className="summary__line">
                <strong>{done} of {progress.total}</strong> checked
                {elapsed != null && <> · {(elapsed / 1000).toFixed(1)} s total</>}
                {done > 0 && (
                  <>
                    {' · '}
                    <span className="pill pill--fail">{counts.FAIL} failed</span>
                    <span className="pill pill--review">{counts.REVIEW} review</span>
                    <span className="pill pill--pass">{counts.PASS} passed</span>
                    {errors.length > 0 && <span className="pill pill--error">{errors.length} could not be read</span>}
                  </>
                )}
              </p>
              {!busy && done > 0 && (
                <button type="button" onClick={() =>
                  downloadCsv(`ttb-verification-${new Date().toISOString().slice(0, 10)}.csv`,
                              resultsToCsv(results, errors))}>
                  Download results as CSV
                </button>
              )}
            </div>
          )}

          {errors.map((e, i) => (
            <div className="card card--error" key={`err-${i}`}>
              <p className="card__file">{e.filename}</p>
              <p>{e.message}</p>
            </div>
          ))}

          {/* The worst result opens on arrival so an agent sees a finding
              immediately; the rest stay collapsed to keep a 300-label run scannable. */}
          {sorted.map((r, i) => (
            <ResultCard key={r.filename} result={r} defaultOpen={i === 0} />
          ))}
        </section>
      </main>
    </>
  )
}
