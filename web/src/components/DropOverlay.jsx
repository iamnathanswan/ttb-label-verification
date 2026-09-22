import { createPortal } from 'react-dom'

/**
 * Show, while a drag is in flight, that the whole window will accept it.
 *
 * Files can be dropped anywhere on the page at any time — `useFileDrop` listens on
 * the window precisely so that missing a target by a few pixels does not open the
 * file and destroy the queue. But once the first document is added the screen
 * switches to the workspace, the two large drop zones are replaced by a compact
 * bar, and nothing on screen says dropping still works. The capability stayed;
 * the affordance left with the zones.
 *
 * Rather than spend permanent screen space on a zone that is only relevant during
 * a drag, this appears for the duration of one. The routing rule is stated,
 * because it is not guessable: the type of the file decides which side it joins.
 *
 * Hidden from assistive technology, and deliberately. Dragging a file is a
 * pointer-only gesture; the keyboard and screen-reader path is the file inputs in
 * the bar, which are always present. Announcing a drag overlay to someone who
 * cannot be dragging is noise.
 *
 * `pointer-events: none` matters: an element appearing under the cursor
 * mid-drag fires its own dragenter and dragleave, and the highlight flickers.
 */
export default function DropOverlay({ visible }) {
  if (!visible) return null

  return createPortal(
    <div className="dropover" aria-hidden="true">
      <div className="dropover__card">
        <p className="dropover__title">Drop to add</p>
        <p className="dropover__hint">
          Images and label PDFs join the labels · COLA application PDFs join the applications
        </p>
      </div>
    </div>,
    document.body,
  )
}
