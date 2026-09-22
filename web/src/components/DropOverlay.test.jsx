import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import DropOverlay from './DropOverlay.jsx'

afterEach(cleanup)

describe('DropOverlay', () => {
  it('shows nothing when no drag is in flight', () => {
    render(<DropOverlay visible={false} />)
    expect(document.querySelector('.dropover')).toBeNull()
  })

  it('names where each kind of file will land', () => {
    render(<DropOverlay visible />)
    expect(screen.getByText('Drop to add')).toBeTruthy()
    // The routing is not guessable from the overlay's presence alone.
    expect(document.querySelector('.dropover__hint').textContent).toMatch(/labels/)
    expect(document.querySelector('.dropover__hint').textContent).toMatch(/applications/)
  })

  it('stays out of the accessibility tree', () => {
    // Dragging a file is a pointer-only gesture. The keyboard and screen-reader
    // path is the file inputs in the bar, which are always present, so announcing
    // a drag overlay to someone who cannot be dragging is noise.
    //
    // The other half of not interfering — pointer-events: none, without which the
    // overlay fires its own dragenter/dragleave under the cursor and the
    // highlight flickers — lives in CSS and is verified in a real browser, not
    // here: happy-dom does not apply stylesheets.
    render(<DropOverlay visible />)
    expect(document.querySelector('.dropover').getAttribute('aria-hidden')).toBe('true')
  })
})
