import { useCallback, useEffect, useRef, useState } from 'react'
import DropZone from './components/DropZone.jsx'
import ResultCard from './components/ResultCard.jsx'
import { downscale } from './lib/downscale.js'
import { readEventStream } from './lib/sse.js'
import { downloadCsv, resultsToCsv } from './lib/csv.js'
import { useFileDrop } from './lib/useFileDrop.js'

const EMPTY = { results: [], errors: [], progress: null, elapsed: null }

const same = (a, b) => a.name === b.name && a.size === b.size
const isPdf = (file) => file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')

export default function App() {
  const [labels, setLabels] = useState([])
  const [applications, setApplications] = useState([])
  const [run, setRun] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [fatal, setFatal] = useState(null)
  const [limits, setLimits] = useState({ max_batch_files: 300 })
  const resultsRef = useRef(null)

  useEffect(() => {
    fetch('/api/config').then((r) => r.json()).then(setLimits).catch(() => {})
  }, [])

  const addTo = useCallback((setter, incoming) => {
    setter((current) => {
      const merged = [...current]
      for (const file of incoming) if (!merged.some((e) => same(e, file))) merged.push(file)
      return merged.slice(0, limits.max_batch_files)
    })
  }, [limits.max_batch_files])

  const addLabels = useCallback((files) => addTo(setLabels, files), [addTo])
  const addApplications = useCallback((files) => addTo(setApplications, files), [addTo])

  // A file dropped on the page rather than a zone is routed by type: a COLA
  // application is always a PDF, and a label is almost always an image. Anything
  // routed wrongly can be moved with Remove, so the guess is never trapping.
  const routeDropped = useCallback((files) => {
    const pdfs = files.filter(isPdf)
    const images = files.filter((f) => !isPdf(f))
    if (images.length) addLabels(images)
    if (pdfs.length) addApplications(pdfs)
  }, [addLabels, addApplications])

  const dragging = useFileDrop(routeDropped, { disabled: busy })

  async function verify() {
    if (!labels.length) return
    setBusy(true); setFatal(null); setRun({ ...EMPTY, progress: { completed: 0, total: labels.length } })

    try {
      const form = new FormData()
      for (const file of labels) form.append('files', await downscale(file), file.name)
      for (const file of applications) form.append('applications', file, file.name)

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
  const fileFor = (list, name) => list.find((f) => f.name === name)

  return (
    <>
      <a href="#results" className="skip">Skip to results</a>
      <main>
        <header>
          <h1>TTB Label Verification</h1>
          <p className="lede">
            Check a label against its COLA application and against the requirements in
            27 CFR Parts 5 and 16. Both documents are read for you — nothing is retyped.
          </p>
        </header>

        <section aria-labelledby="upload-heading">
          <h2 id="upload-heading" className="sr-only">Upload documents</h2>
          <div className="zones">
            <DropZone
              id="label-files"
              title="Labels"
              hint="JPEG, PNG, WebP, TIFF or PDF"
              accept="image/*,application/pdf"
              files={labels}
              onBrowse={addLabels}
              onRemove={(file) => setLabels((c) => c.filter((f) => !same(f, file)))}
              disabled={busy}
              dragging={dragging}
            />
            <DropZone
              id="application-files"
              title="Applications"
              hint="COLA applications, TTB F 5100.31 (PDF). Optional."
              accept="application/pdf"
              files={applications}
              onBrowse={addApplications}
              onRemove={(file) => setApplications((c) => c.filter((f) => !same(f, file)))}
              disabled={busy}
              dragging={dragging}
            />
          </div>

          {labels.length > 1 && applications.length > 0 && (
            <p className="note">
              Labels are paired to applications by serial number in the filename, then by a
              shared filename, then by brand. Anything that cannot be matched confidently is
              reported rather than guessed.
            </p>
          )}

          <button type="button" className="primary" onClick={verify} disabled={busy || !labels.length}>
            {busy ? 'Checking…' : `Check ${labels.length || ''} label${labels.length === 1 ? '' : 's'}`.trim()}
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
                    {errors.length > 0 && <span className="pill pill--error">{errors.length} not processed</span>}
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
            <ResultCard
              key={r.filename}
              result={r}
              defaultOpen={i === 0}
              labelFile={fileFor(labels, r.filename)}
              applicationFile={fileFor(applications, r.pairing?.application_filename)}
            />
          ))}
        </section>
      </main>
    </>
  )
}
