import { useRef, useState } from 'react'

export default function DropZone({ onFiles, disabled, maxFiles }) {
  const inputRef = useRef(null)
  const [over, setOver] = useState(false)

  const accept = (list) => {
    const files = Array.from(list || []).filter((f) => f.size > 0)
    if (files.length) onFiles(files)
  }

  return (
    <div
      className={`drop${over ? ' drop--over' : ''}${disabled ? ' drop--disabled' : ''}`}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); if (!disabled) accept(e.dataTransfer.files) }}
    >
      <input
        ref={inputRef}
        id="label-files"
        type="file"
        multiple
        accept="image/*,application/pdf"
        disabled={disabled}
        onChange={(e) => { accept(e.target.files); e.target.value = '' }}
        className="sr-only"
      />
      {/* The label is the keyboard-reachable control; the input stays visually
          hidden but focusable, so keyboard and pointer share one path (UX-05). */}
      <label htmlFor="label-files" className="drop__label">
        <strong>Choose label files</strong>
        <span>or drag them here</span>
      </label>
      <p className="drop__hint">
        JPEG, PNG, WebP, TIFF or PDF · up to {maxFiles} labels at once
      </p>
    </div>
  )
}
