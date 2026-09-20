import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Accept dropped files anywhere on the page.
 *
 * A drop zone that only listens on its own rectangle has a trap: a file dropped
 * anywhere else hits the browser default, which is to open that file — replacing
 * the application with a picture of a bottle and losing whatever was queued.
 * Missing a target by a few pixels should not cost someone their work, so the
 * window handles the drop and the zone becomes an affordance rather than a
 * requirement.
 *
 * `dragenter` and `dragleave` fire again for every child element the pointer
 * crosses, so a depth counter tracks whether the pointer is still over the
 * window at all; comparing against the event target alone makes the highlight
 * flicker.
 */
export function useFileDrop(onFiles, { disabled = false } = {}) {
  const [dragging, setDragging] = useState(false)

  // The counter lives in a ref, not the effect closure: if the effect re-runs
  // mid-drag — because a dependency changed — a local variable would reset to
  // zero and the highlight would stick on or clear early.
  const depthRef = useRef(0)

  // Likewise the callback, so a caller passing an unstable function does not
  // tear the listeners down and rebuild them on every render.
  const onFilesRef = useRef(onFiles)
  useEffect(() => {
    onFilesRef.current = onFiles
  }, [onFiles])

  useEffect(() => {
    if (disabled) {
      depthRef.current = 0
      setDragging(false)
      return undefined
    }
    const carriesFiles = (e) => Array.from(e.dataTransfer?.types || []).includes('Files')

    const onDragEnter = (e) => {
      if (!carriesFiles(e)) return
      e.preventDefault()
      depthRef.current += 1
      setDragging(true)
    }

    const onDragOver = (e) => {
      if (!carriesFiles(e)) return
      e.preventDefault() // required, or the drop event never fires
      e.dataTransfer.dropEffect = 'copy'
    }

    const onDragLeave = (e) => {
      if (!carriesFiles(e)) return
      depthRef.current = Math.max(0, depthRef.current - 1)
      if (depthRef.current === 0) setDragging(false)
    }

    const onDrop = (e) => {
      // Prevent the default even when the drag carried no files: dropping a URL
      // or a folder would otherwise navigate away just as destructively.
      e.preventDefault()
      depthRef.current = 0
      setDragging(false)
      const files = Array.from(e.dataTransfer?.files || [])
      if (files.length) onFilesRef.current(files)
    }

    window.addEventListener('dragenter', onDragEnter)
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('dragleave', onDragLeave)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragenter', onDragEnter)
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('dragleave', onDragLeave)
      window.removeEventListener('drop', onDrop)
    }
  }, [disabled])

  return dragging
}
