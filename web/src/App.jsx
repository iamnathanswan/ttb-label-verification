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
  const [expected, setExpected] = useState({
    brand_name: '', fanciful_name: '', source_of_product: '', type_of_product: '',
    net_contents: '', alcohol_content_pct: '', producer_name: '',
  })
  const setExpectedField = (name, value) => setExpected((e) => ({ ...e, [name]: value }))
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

      // A single label takes typed values; a batch takes them from the CSV.
      if (files.length === 1) {
        const filled = Object.entries(expected).filter(([, v]) => String(v).trim())
        if (filled.length) {
          const header = filled.map(([k]) => k).join(',')
          const row = filled.map(([, v]) => `"${String(v).replace(/"/g, '""')}"`).join(',')
          const csv = `filename,${header}\n"${files[0].name}",${row}\n`
          form.append('expected_csv', new Blob([csv], { type: 'text/csv' }), 'typed.csv')
        }
      }

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
              Values declared on the COLA application (TTB F 5100.31). Supplying them
              checks the label against what was submitted; without them, labels are still
              checked against the regulations.
            </p>

            {files.length > 1 ? (
              <>
                <p className="note">
                  For a batch, upload a CSV with a <code>filename</code> column plus any of{' '}
                  <code>brand_name</code>, <code>fanciful_name</code>,{' '}
                  <code>source_of_product</code>, <code>type_of_product</code>,{' '}
                  <code>net_contents</code>, <code>alcohol_content_pct</code>,{' '}
                  <code>producer_name</code>.
                </p>
                <label className="field">
                  <span>Application values (CSV)</span>
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    disabled={busy}
                    onChange={(e) => setExpectedCsv(e.target.files?.[0] || null)}
                  />
                </label>
              </>
            ) : (
              <div className="fields">
                <label className="field">
                  <span>Brand name <small>(field 6)</small></span>
                  <input name="brand_name" value={expected.brand_name}
                         onChange={(e) => setExpectedField('brand_name', e.target.value)} disabled={busy} />
                </label>
                <label className="field">
                  <span>Fanciful name <small>(field 7)</small></span>
                  <input name="fanciful_name" value={expected.fanciful_name}
                         onChange={(e) => setExpectedField('fanciful_name', e.target.value)} disabled={busy} />
                </label>
                <label className="field">
                  <span>Source of product <small>(field 3)</small></span>
                  <select name="source_of_product" value={expected.source_of_product}
                          onChange={(e) => setExpectedField('source_of_product', e.target.value)} disabled={busy}>
                    <option value="">Not specified</option>
                    <option value="domestic">Domestic</option>
                    <option value="imported">Imported</option>
                  </select>
                </label>
                <label className="field">
                  <span>Type of product <small>(field 5)</small></span>
                  <select name="type_of_product" value={expected.type_of_product}
                          onChange={(e) => setExpectedField('type_of_product', e.target.value)} disabled={busy}>
                    <option value="">Not specified</option>
                    <option value="wine">Wine</option>
                    <option value="distilled_spirits">Distilled spirits</option>
                    <option value="malt_beverage">Malt beverages</option>
                  </select>
                </label>
                <label className="field">
                  <span>Net contents <small>(field 12)</small></span>
                  <input name="net_contents" placeholder="750 mL" value={expected.net_contents}
                         onChange={(e) => setExpectedField('net_contents', e.target.value)} disabled={busy} />
                </label>
                <label className="field">
                  <span>Alcohol content <small>(field 13)</small></span>
                  <input name="alcohol_content_pct" type="number" step="0.1" placeholder="45.0"
                         value={expected.alcohol_content_pct}
                         onChange={(e) => setExpectedField('alcohol_content_pct', e.target.value)} disabled={busy} />
                </label>
                <label className="field field--wide">
                  <span>Producer name and address <small>(field 8)</small></span>
                  <input name="producer_name" value={expected.producer_name}
                         onChange={(e) => setExpectedField('producer_name', e.target.value)} disabled={busy} />
                </label>
              </div>
            )}
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
