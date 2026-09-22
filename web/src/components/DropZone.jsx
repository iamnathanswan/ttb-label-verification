import { useEffect, useState } from 'react'
import Lightbox from './Lightbox.jsx'
import { makePreview } from '../lib/preview.js'

/**
 * Show what was dropped, where it was dropped.
 *
 * A filename is not enough to tell whether the right scan was picked up, and
 * finding out after a check has run is too late. Beyond a handful of files
 * thumbnails stop helping, so a large batch falls back to a plain list.
 */
function Thumbnail({ file, onRemove, onExpand, disabled }) {
  const [preview, setPreview] = useState({ url: null, kind: null })

  useEffect(() => {
    let live = true
    let created = null
    makePreview(file).then((result) => {
      if (!live) {
        if (result.url) URL.revokeObjectURL(result.url)
        return
      }
      created = result.url
      setPreview(result)
    })
    return () => {
      live = false
      if (created) URL.revokeObjectURL(created)
    }
  }, [file])

  return (
    <figure className="thumb">
      <button
        type="button"
        className="thumb__frame"
        onClick={() => onExpand(file)}
        disabled={!preview.url}
        aria-label={`Enlarge ${file.name}`}
      >
        {preview.url ? (
          <img src={preview.url} alt={`First page of ${file.name}`} />
        ) : (
          <span className="thumb__placeholder" aria-hidden="true">
            {preview.kind === 'pdf' ? 'PDF' : '…'}
          </span>
        )}
      </button>
      <figcaption title={file.name}>{file.name}</figcaption>
      <button type="button" className="thumb__remove" onClick={() => onRemove(file)} disabled={disabled}>
        Remove<span className="sr-only"> {file.name}</span>
      </button>
    </figure>
  )
}

export default function DropZone({
  id, title, hint, files, onBrowse, onRemove, disabled, dragging, accept, previewLimit = 6,
}) {
  const [expanded, setExpanded] = useState(null)
  const showThumbnails = files.length > 0 && files.length <= previewLimit

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

      {showThumbnails && (
        <div className="thumbs">
          {files.map((f) => (
            <Thumbnail key={`${f.name}-${f.size}`} file={f} onRemove={onRemove}
                       onExpand={setExpanded} disabled={disabled} />
          ))}
        </div>
      )}

      {files.length > previewLimit && (
        <>
          <p className="note">{files.length} files — too many to preview individually.</p>
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
        </>
      )}

      <Lightbox file={expanded} onClose={() => setExpanded(null)} />
    </div>
  )
}
