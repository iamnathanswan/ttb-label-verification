/**
 * A thumbnail for a queued document.
 *
 * Images are previewed straight from an object URL — no round trip. A PDF needs
 * rasterising, which the browser cannot do without a viewer or a library, so the
 * server renders its first page; it already does this on the ingest path.
 *
 * Previews are a convenience, so a failure is silent: the file still uploads and
 * the queue still shows its name.
 */

const isPdf = (file) =>
  file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')

export async function makePreview(file) {
  if (!isPdf(file)) return { url: URL.createObjectURL(file), kind: 'image' }

  try {
    const body = new FormData()
    body.append('file', file, file.name)
    const response = await fetch('/api/preview', { method: 'POST', body })
    if (!response.ok) return { url: null, kind: 'pdf' }
    return { url: URL.createObjectURL(await response.blob()), kind: 'pdf' }
  } catch {
    return { url: null, kind: 'pdf' }
  }
}
