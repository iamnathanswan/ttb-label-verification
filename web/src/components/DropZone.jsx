/**
 * The empty-state chooser for one kind of document.
 *
 * Only ever rendered with nothing uploaded — the first file switches the whole
 * screen to the workspace, where the upload bar and the document pane take over
 * showing what is queued and what it looks like. So this shows no file list and
 * no thumbnails: it previously carried both, and neither could render.
 */
export default function DropZone({ id, title, hint, onBrowse, disabled, dragging, accept }) {
  return (
    <div className={`drop${dragging ? ' drop--over' : ''}${disabled ? ' drop--disabled' : ''}`}>
      <h3 className="drop__title">{title}</h3>
      <input
        id={id}
        type="file"
        multiple
        accept={accept}
        disabled={disabled}
        onChange={(e) => {
          onBrowse(Array.from(e.target.files || []))
          e.target.value = ''
        }}
        className="sr-only"
      />
      {/* The label is the keyboard-reachable control; the input stays visually
          hidden but focusable, so keyboard and pointer share one path (UX-05). */}
      <label htmlFor={id} className="drop__label">
        <strong>Choose files</strong>
        <span>{dragging ? 'release to add' : 'or drag them here'}</span>
      </label>
      <p className="drop__hint">{hint}</p>
    </div>
  )
}
