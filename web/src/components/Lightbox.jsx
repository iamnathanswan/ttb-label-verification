import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

const isPdf = (file) =>
  file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')

/**
 * Show a document at its own size.
 *
 * The preview beside the findings is a 480px render — enough to confirm the right
 * file was picked up, not enough to read six-point warning text or a hand-written
 * form field. This opens the *original* file rather than the thumbnail: an image
 * at full resolution, and a PDF in the browser's own viewer, which brings zoom,
 * page navigation and text selection for free.
 *
 * A PDF goes through the server first. Browser PDF viewers execute whatever
 * JavaScript a document carries, and these documents come from applicants. The
 * official TTB form is itself an example — it fires an alert about LEGAL paper on
 * open — so the bytes are scrubbed before the viewer ever sees them (OPS-07).
 *
 * Modal behaviour is hand-rolled rather than borrowed: Escape closes, focus moves
 * in and returns to whatever opened it, and Tab is kept inside while it is open.
 *
 * Rendered through a portal to <body>. The document pane it is opened from is
 * sticky, which makes it a stacking context, and a z-index set inside one is only
 * ever compared against its siblings — so the overlay was painting *underneath*
 * the sticky upload bar and hiding its own close button. A modal belongs at the
 * top of the document, not wherever it happened to be triggered from.
 */
export default function Lightbox({ file, onClose }) {
  const [url, setUrl] = useState(null)
  const [error, setError] = useState(null)
  const dialogRef = useRef(null)
  const closeRef = useRef(null)
  const openerRef = useRef(null)

  useEffect(() => {
    if (!file) return undefined
    setError(null)

    // An image is inert and is shown straight from the local file. A PDF is not,
    // so it is sanitised server-side first.
    if (!isPdf(file)) {
      const objectUrl = URL.createObjectURL(file)
      setUrl(objectUrl)
      return () => { URL.revokeObjectURL(objectUrl); setUrl(null) }
    }

    let objectUrl = null
    let cancelled = false
    const body = new FormData()
    body.append('file', file)

    fetch('/api/document', { method: 'POST', body })
      .then((res) => (res.ok ? res.blob() : Promise.reject(new Error(String(res.status)))))
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => { if (!cancelled) setError('This PDF could not be prepared for viewing.') })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      setUrl(null)
    }
  }, [file])

  useEffect(() => {
    if (!file) return undefined

    openerRef.current = document.activeElement
    closeRef.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        onClose()
        return
      }
      if (event.key !== 'Tab') return
      // Keep focus inside: a dialog you can tab out of is a dialog that has
      // stranded a keyboard user behind an overlay they cannot see past.
      const focusable = dialogRef.current?.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      if (!focusable?.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      openerRef.current?.focus?.()
    }
  }, [file, onClose])

  if (!file) return null

  return createPortal(
    <div className="lightbox" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div
        className="lightbox__panel"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Full size: ${file.name}`}
      >
        <header className="lightbox__bar">
          <span className="lightbox__name" title={file.name}>{file.name}</span>
          {url && <a href={url} target="_blank" rel="noreferrer">Open in a new tab</a>}
          <button type="button" ref={closeRef} onClick={onClose} className="lightbox__close">
            Close<span className="sr-only"> full size view</span>
          </button>
        </header>

        <div className="lightbox__body">
          {error && <p className="lightbox__fallback" role="alert">{error}</p>}
          {!url && !error && <p className="lightbox__fallback">Preparing {file.name}…</p>}
          {url && (isPdf(file) ? (
            <object data={url} type="application/pdf" aria-label={`Document: ${file.name}`}>
              <p className="lightbox__fallback">
                This browser cannot display the PDF inline.{' '}
                <a href={url} target="_blank" rel="noreferrer">Open {file.name} in a new tab</a>.
              </p>
            </object>
          ) : (
            <img src={url} alt={`${file.name} at full size`} />
          ))}
        </div>
      </div>
    </div>,
    document.body,
  )
}
