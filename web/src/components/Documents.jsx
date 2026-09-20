import { useEffect, useState } from 'react'

/**
 * Show the source documents beside the findings.
 *
 * A verification tool has to be checkable. An agent who cannot see what was read
 * has only the tool's word for it, and the whole point is to replace their manual
 * comparison with one they can audit in a glance.
 *
 * Both are rendered from object URLs; browsers display PDFs natively, so no
 * client-side PDF library is needed.
 */
export default function Documents({ labelFile, applicationFile }) {
  const [urls, setUrls] = useState({ label: null, application: null })

  useEffect(() => {
    const next = {
      label: labelFile ? URL.createObjectURL(labelFile) : null,
      application: applicationFile ? URL.createObjectURL(applicationFile) : null,
    }
    setUrls(next)
    return () => {
      for (const url of Object.values(next)) if (url) URL.revokeObjectURL(url)
    }
  }, [labelFile, applicationFile])

  if (!labelFile && !applicationFile) return null

  return (
    <div className="documents">
      {urls.label && (
        <figure>
          <figcaption>Label — {labelFile.name}</figcaption>
          {labelFile.type === 'application/pdf' ? (
            <embed src={urls.label} type="application/pdf" title={`Label: ${labelFile.name}`} />
          ) : (
            <img src={urls.label} alt={`The label submitted as ${labelFile.name}`} />
          )}
        </figure>
      )}
      {urls.application && (
        <figure>
          <figcaption>Application — {applicationFile.name}</figcaption>
          <embed
            src={urls.application}
            type="application/pdf"
            title={`Application: ${applicationFile.name}`}
          />
        </figure>
      )}
    </div>
  )
}
