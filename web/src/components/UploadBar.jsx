/**
 * The upload controls once files are chosen.
 *
 * Two 400px drop zones earn their space while they are the task. Once documents
 * are loaded the task is reading them, so the controls shrink to a bar and give
 * the room to the work.
 */
export default function UploadBar({
  labels, applications, onAddLabels, onAddApplications, onRemove, onClear, onCheck, busy, dragging,
}) {
  const chip = (file, kind) => (
    <span className={`chip chip--${kind}`} key={`${file.name}-${file.size}`}>
      <span className="chip__name" title={file.name}>{file.name}</span>
      <button type="button" onClick={() => onRemove(kind, file)} disabled={busy}
              aria-label={`Remove ${file.name}`}>×</button>
    </span>
  )

  return (
    <div className={`bar${dragging ? ' bar--over' : ''}`}>
      <div className="bar__files">
        {labels.map((f) => chip(f, 'label'))}
        {applications.map((f) => chip(f, 'application'))}
        {dragging && <span className="bar__hint">release to add</span>}
      </div>

      <div className="bar__actions">
        <label className="bar__add">
          Add labels
          <input type="file" multiple accept="image/*,application/pdf" disabled={busy}
                 className="sr-only"
                 onChange={(e) => { onAddLabels(Array.from(e.target.files || [])); e.target.value = '' }} />
        </label>
        <label className="bar__add">
          Add applications
          <input type="file" multiple accept="application/pdf" disabled={busy}
                 className="sr-only"
                 onChange={(e) => { onAddApplications(Array.from(e.target.files || [])); e.target.value = '' }} />
        </label>
        <button type="button" className="bar__clear" onClick={onClear} disabled={busy}>Clear</button>
        <button type="button" className="primary" onClick={onCheck} disabled={busy || !labels.length}>
          {busy ? 'Checking…' : `Check ${labels.length || ''} label${labels.length === 1 ? '' : 's'}`.trim()}
        </button>
      </div>
    </div>
  )
}
