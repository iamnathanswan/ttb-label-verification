/**
 * Shrink images before upload (PRF-04).
 *
 * A 4000px phone photo costs several times the tokens and upload time of a
 * 1600px one with no gain in legibility for label text. Doing it in the browser
 * also means a 300-label batch uploads in a fraction of the bytes.
 *
 * PDFs pass through untouched — the server rasterises them.
 */

const MAX_EDGE = 1600
const QUALITY = 0.88

export async function downscale(file) {
  if (!file.type.startsWith('image/')) return file

  try {
    const bitmap = await createImageBitmap(file)
    const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height))
    if (scale === 1) return file

    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    bitmap.close?.()

    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY))
    if (!blob || blob.size >= file.size) return file
    return new File([blob], file.name, { type: 'image/jpeg' })
  } catch {
    // A browser that cannot decode the image should still be able to upload it;
    // the server will report the problem with a message the agent can act on.
    return file
  }
}
