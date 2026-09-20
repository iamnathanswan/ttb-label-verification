export default function DropZone({ onBrowse, disabled, maxFiles, dragging }) {
  return (
    <div className={`drop${dragging ? ' drop--over' : ''}${disabled ? ' drop--disabled' : ''}`}>
      <input
        id="label-files"
        type="file"
        multiple
        accept="image/*,application/pdf"
        disabled={disabled}
        onChange={(e) => {
          onBrowse(Array.from(e.target.files || []))
          e.target.value = ''
        }}
        className="sr-only"
      />
      {/* The label is the keyboard-reachable control; the input stays visually
          hidden but focusable, so keyboard and pointer share one path (UX-05). */}
      <label htmlFor="label-files" className="drop__label">
        <strong>Choose label files</strong>
        <span>{dragging ? 'release to add them' : 'or drag them anywhere on this page'}</span>
      </label>
      <p className="drop__hint">
        JPEG, PNG, WebP, TIFF or PDF · up to {maxFiles} labels at once
      </p>
    </div>
  )
}
