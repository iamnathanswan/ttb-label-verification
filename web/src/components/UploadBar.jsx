import { useState } from 'react'

// Past a handful, one chip per file stops being a summary and becomes the page.
// At the 300 Sarah describes, the chips grew the bar to 2,309px on a 900px screen
// and pushed "Check 300 labels" to y=1207 — the control that starts the job was
// off screen, behind three hundred things the agent did not need to read.
const CHIP_LIMIT = 8

/**
 * The upload controls once files are chosen.
 *
 * Two 400px drop zones earn their space while they are the task. Once documents
 * are loaded the task is reading them, so the controls shrink to a bar and give
 * the room to the work.
 *
 * A peak-season batch is reviewed through its results, not its inputs, so a large
 * queue collapses to its counts. The full list stays one click away — an agent
 * who needs to drop one wrong file from 300 still can — but it opens into a
 * bounded, scrolling panel rather than displacing the actions.
 */
export default function UploadBar({
  labels, applications, onAddLabels, onAddApplications, onRemove, onClear, onCheck, busy, dragging,
}) {
  const [listOpen, setListOpen] = useState(false)
  const total = labels.length + applications.length
  const collapsed = total > CHIP_LIMIT

  const chip = (file, kind) => (
    <span className={`chip chip--${kind}`} key={`${file.name}-${file.size}`}>
      <span className="chip__name" title={file.name}>{file.name}</span>
      <button type="button" onClick={() => onRemove(kind, file)} disabled={busy}
              aria-label={`Remove ${file.name}`}>×</button>
    </span>
  )

  const row = (file, kind) => (
    <li key={`${file.name}-${file.size}`}>
      <span className={`filelist__dot filelist__dot--${kind}`} aria-hidden="true" />
      <span className="filelist__name">{file.name}</span>
      <button type="button" onClick={() => onRemove(kind, file)} disabled={busy}
              aria-label={`Remove ${file.name}`}>Remove</button>
    </li>
  )

  const count = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

  return (
    <div className={`bar${dragging ? ' bar--over' : ''}`}>
      <div className="bar__files">
        {collapsed ? (
          <button
            type="button"
            className="bar__summary"
            onClick={() => setListOpen((open) => !open)}
            aria-expanded={listOpen}
            aria-controls="queued-files"
          >
            {[
              labels.length && count(labels.length, 'label'),
              applications.length && count(applications.length, 'application'),
            ].filter(Boolean).join(' · ')}
            <span className="bar__summary-toggle">{listOpen ? 'Hide list' : 'Show list'}</span>
          </button>
        ) : (
          <>
            {labels.map((f) => chip(f, 'label'))}
            {applications.map((f) => chip(f, 'application'))}
          </>
        )}
        {dragging && <span className="bar__hint">release to add</span>}
      </div>

      <div className="bar__actions">
        <label className="bar__add" htmlFor="bar-labels">
          Add labels
          <input id="bar-labels" type="file" multiple accept="image/*,application/pdf"
                 disabled={busy} className="sr-only"
                 onChange={(e) => { onAddLabels(Array.from(e.target.files || [])); e.target.value = '' }} />
        </label>
        <label className="bar__add" htmlFor="bar-applications">
          Add applications
          <input id="bar-applications" type="file" multiple accept="application/pdf"
                 disabled={busy} className="sr-only"
                 onChange={(e) => { onAddApplications(Array.from(e.target.files || [])); e.target.value = '' }} />
        </label>
        <button type="button" className="bar__clear" onClick={onClear} disabled={busy}>Clear</button>
        <button type="button" className="primary" onClick={onCheck} disabled={busy || !labels.length}>
          {busy ? 'Checking…' : `Check ${labels.length || ''} label${labels.length === 1 ? '' : 's'}`.trim()}
        </button>
      </div>

      {collapsed && listOpen && (
        <ul className="filelist" id="queued-files">
          {labels.map((f) => row(f, 'label'))}
          {applications.map((f) => row(f, 'application'))}
        </ul>
      )}
    </div>
  )
}
