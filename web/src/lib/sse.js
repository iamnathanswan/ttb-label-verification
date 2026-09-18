/**
 * Read a server-sent event stream from a POST response.
 *
 * EventSource cannot issue POST requests or send multipart bodies, so the stream
 * is parsed from the fetch body directly. Events are delivered as they arrive so
 * the first result renders inside the single-label budget (PRF-02).
 */

export async function readEventStream(response, onEvent) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let split
    while ((split = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, split)
      buffer = buffer.slice(split + 2)

      let name = 'message'
      const dataLines = []
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) name = line.slice(7)
        else if (line.startsWith('data: ')) dataLines.push(line.slice(6))
      }
      if (dataLines.length) {
        try {
          onEvent(name, JSON.parse(dataLines.join('\n')))
        } catch {
          // A malformed frame should not tear down a 300-label run.
        }
      }
    }
  }
}
