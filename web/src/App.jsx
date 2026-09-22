import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import DocumentPane from './components/DocumentPane.jsx'
import DropZone from './components/DropZone.jsx'
import DropOverlay from './components/DropOverlay.jsx'
import ResultCard from './components/ResultCard.jsx'
import UploadBar from './components/UploadBar.jsx'
import { downscale } from './lib/downscale.js'
import { readEventStream } from './lib/sse.js'
import { downloadCsv, resultsToCsv } from './lib/csv.js'
import { useFileDrop } from './lib/useFileDrop.js'
import { usePreviews } from './lib/usePreviews.js'

const EMPTY = { results: [], errors: [], progress: null, elapsed: null }

const same = (a, b) => a.name === b.name && a.size === b.size
const isPdf = (file) => file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')

export default function App() {
  const [labels, setLabels] = useState([])
  const [applications, setApplications] = useState([])
  const [run, setRun] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [fatal, setFatal] = useState(null)
  const [limits, setLimits] = useState({ max_batch_files: 300, preview_limit: 6 })
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
  // application is always a PDF, and a label is almost always an image.
  const routeDropped = useCallback((files) => {
    const images = files.filter((f) => !isPdf(f))
    const pdfs = files.filter(isPdf)
    if (images.length) addLabels(images)
    if (pdfs.length) addApplications(pdfs)
  }, [addLabels, addApplications])

  const dragging = useFileDrop(routeDropped, { disabled: busy })

  const { results, errors, progress, elapsed } = run
  const singleReview = labels.length === 1
  const mode = labels.length === 0 && applications.length === 0 ? 'upload' : 'workspace'

  // Only a single review gets a document pane; previews for a batch would be
  // three hundred uploads to render a filing cabinet.
  const paneFiles = useMemo(
    () => (singleReview ? [...labels, ...applications] : []),
    [singleReview, labels, applications],
  )
  const previews = usePreviews(paneFiles, { enabled: singleReview })

  const removeFile = (kind, file) => {
    const setter = kind === 'label' ? setLabels : setApplications
    setter((current) => current.filter((f) => !same(f, file)))
  }

  const clearAll = () => {
    setLabels([]); setApplications([]); setRun(EMPTY); setFatal(null)
  }

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
      <main className={mode === 'upload' ? '' : 'main--workspace'}>
        <header>
          <h1>TTB Label Verification</h1>
          {mode === 'upload' && (
            <p className="lede">
              Check a label against its COLA application and against the requirements in
              27 CFR Parts 5 and 16. Both documents are read for you — nothing is retyped.
            </p>
          )}
        </header>

        {mode === 'upload' ? (
          <section aria-labelledby="upload-heading">
            <h2 id="upload-heading" className="sr-only">Upload documents</h2>
            <div className="zones">
              <DropZone
                id="label-files" title="Labels"
                hint="JPEG, PNG, WebP, TIFF or PDF"
                accept="image/*,application/pdf"
                onBrowse={addLabels}
                disabled={busy} dragging={dragging}
              />
              <DropZone
                id="application-files" title="Applications"
                hint="COLA applications, TTB F 5100.31 (PDF). Optional."
                accept="application/pdf"
                onBrowse={addApplications}
                disabled={busy} dragging={dragging}
              />
            </div>
          </section>
        ) : (
          <UploadBar
            labels={labels} applications={applications}
            onAddLabels={addLabels} onAddApplications={addApplications}
            onRemove={removeFile} onClear={clearAll} onCheck={verify}
            busy={busy} dragging={dragging}
          />
        )}

        {/* The zones already highlight themselves, so the overlay is for the
            workspace, where nothing else says a drop would land. */}
        <DropOverlay visible={dragging && mode === 'workspace'} />

        {fatal && <p className="error" role="alert">{fatal}</p>}

        {mode === 'workspace' && (
          <div className={`workspace${singleReview ? '' : ' workspace--wide'}`}>
            {singleReview && (
              <DocumentPane
                label={labels[0]}
                application={applications[0]}
                previews={previews}
              />
            )}

            <section id="results" aria-labelledby="results-heading" tabIndex={-1} ref={resultsRef}>
              <h2 id="results-heading" className="sr-only">Results</h2>

              {/* Streaming updates are announced politely rather than on every card. */}
              <p className="sr-only" aria-live="polite">
                {busy && progress ? `Checked ${done} of ${progress.total} labels.`
                  : elapsed != null ? `Finished. ${counts.FAIL} failed, ${counts.REVIEW} need review, ${counts.PASS} passed.`
                  : ''}
              </p>

              {!progress && !busy && (
                <div className="waiting">
                  <h2>Ready to check</h2>
                  <p>
                    {labels.length} label{labels.length === 1 ? '' : 's'}
                    {applications.length
                      ? ` and ${applications.length} application${applications.length === 1 ? '' : 's'}`
                      : ', with no application — the regulation checks will still run'}.
                  </p>
                  <p className="note">
                    The label is read for its brand, class/type, alcohol content, net contents,
                    producer and government warning; the application for what was declared on
                    TTB F 5100.31.
                  </p>
                </div>
              )}

              {progress && (
                <div className="summary">
                  <div className="progress">
                    <div className="progress__bar" style={{ width: `${(done / progress.total) * 100}%` }} />
                  </div>
                  <p className="summary__line">
                    <strong>{done} of {progress.total}</strong> checked
                    {elapsed != null && <> · {(elapsed / 1000).toFixed(1)} s</>}
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
                  immediately; the rest stay collapsed to keep a batch scannable. */}
              {sorted.map((r, i) => (
                <ResultCard key={r.filename} result={r} defaultOpen={i === 0} stacked={singleReview} />
              ))}
            </section>
          </div>
        )}
      </main>
    </>
  )
}
