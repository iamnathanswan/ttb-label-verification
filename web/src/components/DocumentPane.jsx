import { useState } from 'react'
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

      <div className="pane__frame">
        {preview?.url ? (
          <img src={preview.url} alt={`${current.title}: ${current.file.name}`} />
        ) : (
          <p className="pane__loading">Rendering {current.file.name}…</p>
        )}
      </div>

      <p className="pane__caption">
        <span title={current.file.name}>{current.file.name}</span>
        {preview?.url && (
          <a href={preview.url} target="_blank" rel="noreferrer">Open full size</a>
        )}
      </p>
    </aside>
  )
}
