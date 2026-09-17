import { useEffect, useState } from 'react'

export default function App() {
  const [health, setHealth] = useState('checking…')

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => setHealth(d.status === 'ok' ? `ok · v${d.version}` : 'unexpected response'))
      .catch(() => setHealth('unreachable'))
  }, [])

  return (
    <main>
      <h1>TTB Label Verification</h1>
      <p className="lede">
        Upload alcohol beverage labels to check required information against TTB
        requirements under 27 CFR Parts 5 and 16.
      </p>
      <p className="status" role="status">
        API: <strong>{health}</strong>
      </p>
      <p className="note">Phase 0 — deployment scaffold. Verification lands in Phase 3.</p>
    </main>
  )
}
