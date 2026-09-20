export default function DropZone({ id, title, hint, files, onBrowse, onRemove, disabled, dragging, accept }) {
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

      {files.length > 0 && (
        <ul className="queue">
          {files.map((f) => (
            <li key={`${f.name}-${f.size}`}>
              <span className="queue__name">{f.name}</span>
              <button type="button" onClick={() => onRemove(f)} disabled={disabled}>
                Remove<span className="sr-only"> {f.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
