import { useState } from 'react'
import Lightbox from './Lightbox.jsx'
import { previewKey } from '../lib/usePreviews.js'

/**
 * The documents, large, beside the findings.
 *
 * A finding is checked by looking at the document it came from. Below the results
 * that meant scrolling away from the thing being verified; here the pane stays
 * put while the findings scroll, which is the motion an agent actually makes.
 *
 * Only for a single review — a batch is read through its results, and three
 * hundred documents in a pane would be a filing cabinet, not a workspace.
 */
export default function DocumentPane({ label, application, previews }) {
  const tabs = [
    label && { id: 'label', title: 'Label', file: label },
    application && { id: 'application', title: 'Application', file: application },
  ].filter(Boolean)

  const [active, setActive] = useState('label')
  const [expanded, setExpanded] = useState(null)
  const current = tabs.find((t) => t.id === active) || tabs[0]
  if (!current) return null

  const preview = previews[previewKey(current.file)]

  return (
    <aside className="pane" aria-label="Source documents">
      {tabs.length > 1 && (
        <div className="pane__tabs" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={tab.id === current.id}
              className={`pane__tab${tab.id === current.id ? ' pane__tab--on' : ''}`}
              onClick={() => setActive(tab.id)}
            >
              {tab.title}
            </button>
          ))}
        </div>
      )}

      {/* The preview is a button: clicking the document to enlarge it is what
          anyone tries first, so the affordance sits on the document itself. */}
      <button
        type="button"
        className="pane__frame"
        onClick={() => setExpanded(current.file)}
        disabled={!preview?.url}
        aria-label={`Enlarge ${current.file.name}`}
      >
        {preview?.url ? (
          <>
            <img src={preview.url} alt={`${current.title}: ${current.file.name}`} />
            <span className="pane__zoom" aria-hidden="true">Click to enlarge</span>
          </>
        ) : (
          <span className="pane__loading">Rendering {current.file.name}…</span>
        )}
      </button>

      <p className="pane__caption">
        <span title={current.file.name}>{current.file.name}</span>
        <button type="button" className="linkish" onClick={() => setExpanded(current.file)}
                disabled={!preview?.url}>
          Enlarge
        </button>
      </p>

      <Lightbox file={expanded} onClose={() => setExpanded(null)} />
    </aside>
  )
}
