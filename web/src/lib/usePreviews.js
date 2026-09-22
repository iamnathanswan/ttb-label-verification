import { useEffect, useState } from 'react'
import { makePreview } from './preview.js'

/**
 * Keep a rendered preview for each queued file.
 *
 * Held above the components that show them, because the same render is wanted in
 * two places — the upload bar and the document pane — and fetching a PDF
 * thumbnail twice would double the work for no benefit.
 *
 * Object URLs are revoked when a file leaves the queue, so dropping and removing
 * files repeatedly does not accumulate them.
 */
export function usePreviews(files, { enabled = true } = {}) {
  const [previews, setPreviews] = useState({})

  useEffect(() => {
    if (!enabled) return undefined

    let live = true
    const wanted = new Set(files.map((f) => `${f.name}-${f.size}`))

    setPreviews((current) => {
      const kept = {}
      for (const [key, value] of Object.entries(current)) {
        if (wanted.has(key)) kept[key] = value
        else if (value.url) URL.revokeObjectURL(value.url)
      }
      return kept
    })

    for (const file of files) {
      const key = `${file.name}-${file.size}`
      setPreviews((current) => {
        if (current[key]) return current
        makePreview(file).then((result) => {
          if (!live) {
            if (result.url) URL.revokeObjectURL(result.url)
            return
          }
          setPreviews((now) => (now[key] ? now : { ...now, [key]: result }))
        })
        return current
      })
    }

    return () => {
      live = false
    }
  }, [files, enabled])

  return previews
}

export const previewKey = (file) => `${file.name}-${file.size}`
