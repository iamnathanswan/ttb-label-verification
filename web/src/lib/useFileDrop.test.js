import { describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useFileDrop } from './useFileDrop.js'

/**
 * Regression: dropping a file outside the drop zone used to hit the browser
 * default, which opens the file and replaces the application — losing whatever
 * was already queued.
 */

const dragEvent = (type, { files = [], types = ['Files'] } = {}) => {
  const event = new Event(type, { bubbles: true, cancelable: true })
  event.dataTransfer = { types, files, dropEffect: '' }
  return event
}

/** Dispatch inside act() so the state update is flushed before assertions. */
const fire = (type, options) => {
  const event = dragEvent(type, options)
  act(() => {
    window.dispatchEvent(event)
  })
  return event
}

describe('useFileDrop', () => {
  it('accepts a file dropped anywhere on the page, not only on the zone', () => {
    const onFiles = vi.fn()
    renderHook(() => useFileDrop(onFiles))

    const file = new File(['x'], 'dropped.png', { type: 'image/png' })
    window.dispatchEvent(dragEvent('drop', { files: [file] }))

    expect(onFiles).toHaveBeenCalledTimes(1)
    expect(onFiles.mock.calls[0][0][0].name).toBe('dropped.png')
  })

  it('prevents the browser default so a stray drop cannot navigate away', () => {
    renderHook(() => useFileDrop(vi.fn()))
    const event = dragEvent('drop', { files: [] })
    window.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
  })

  it('prevents the default on dragover, or the drop never fires', () => {
    renderHook(() => useFileDrop(vi.fn()))
    const event = dragEvent('dragover')
    window.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
  })

  it('reports dragging state while a file is over the window', () => {
    const { result } = renderHook(() => useFileDrop(vi.fn()))
    expect(result.current).toBe(false)

    fire('dragenter')
    expect(result.current).toBe(true)

    fire('dragleave')
    expect(result.current).toBe(false)
  })

  it('does not flicker when the pointer crosses child elements', () => {
    const { result } = renderHook(() => useFileDrop(vi.fn()))
    fire('dragenter')   // page
    fire('dragenter')   // a child
    fire('dragleave')   // leaving that child
    expect(result.current).toBe(true)   // still over the page
    fire('dragleave')
    expect(result.current).toBe(false)
  })

  it('ignores drags that carry no files, such as selected text', () => {
    const onFiles = vi.fn()
    const { result } = renderHook(() => useFileDrop(onFiles))
    fire('dragenter', { types: ['text/plain'] })
    expect(result.current).toBe(false)
    expect(onFiles).not.toHaveBeenCalled()
  })

  it('survives a caller that passes a new function every render', () => {
    const onFiles = vi.fn()
    const { rerender, result } = renderHook(() => useFileDrop((f) => onFiles(f)))

    fire('dragenter')
    rerender()
    expect(result.current).toBe(true) // the drag is not interrupted by a re-render

    const file = new File(['x'], 'kept.png', { type: 'image/png' })
    fire('drop', { files: [file] })
    expect(onFiles).toHaveBeenCalledTimes(1)
  })

  it('stops listening while a batch is running', () => {
    const onFiles = vi.fn()
    renderHook(() => useFileDrop(onFiles, { disabled: true }))
    const file = new File(['x'], 'late.png', { type: 'image/png' })
    window.dispatchEvent(dragEvent('drop', { files: [file] }))
    expect(onFiles).not.toHaveBeenCalled()
  })
})
