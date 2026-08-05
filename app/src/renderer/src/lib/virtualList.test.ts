import { describe, it, expect } from 'vitest'
import { clamp, computeMessageWindow } from './virtualList'

/**
 * Unit tests for the virtual-list windowing helper (round-8).
 *
 * The helper is a pure function: (total, scrollTop, containerHeight, rowHeight,
 * overscan) -> { start, end, spacerTop, spacerBottom }. These tests pin down the
 * edge cases that matter for the chat view: empty lists, exact row boundaries,
 * bottom-of-list anchoring, overscan clamping, and stale scroll positions.
 */
describe('computeMessageWindow', () => {
  it('returns an empty window for an empty list', () => {
    expect(computeMessageWindow(0, 0, 400, 60, 6)).toEqual({ start: 0, end: 0, spacerTop: 0, spacerBottom: 0 })
    expect(computeMessageWindow(0, 5000, 400, 60, 6)).toEqual({ start: 0, end: 0, spacerTop: 0, spacerBottom: 0 })
    expect(computeMessageWindow(-1, 0, 400, 60, 6)).toEqual({ start: 0, end: 0, spacerTop: 0, spacerBottom: 0 })
  })

  it('returns an empty window when rowHeight is invalid', () => {
    expect(computeMessageWindow(100, 0, 400, 0, 6)).toEqual({ start: 0, end: 0, spacerTop: 0, spacerBottom: 0 })
    expect(computeMessageWindow(100, 0, 400, -10, 6)).toEqual({ start: 0, end: 0, spacerTop: 0, spacerBottom: 0 })
  })

  it('renders the first rows at the top of the list', () => {
    const w = computeMessageWindow(100, 0, 400, 40, 0)
    expect(w).toEqual({ start: 0, end: 10, spacerTop: 0, spacerBottom: 90 * 40 })
  })

  it('renders the visible rows in the middle of the list', () => {
    const w = computeMessageWindow(100, 2000, 400, 40, 0)
    expect(w).toEqual({ start: 50, end: 60, spacerTop: 50 * 40, spacerBottom: 40 * 40 })
  })

  it('handles a scrollTop that lands exactly on a row boundary', () => {
    const w = computeMessageWindow(100, 400, 400, 40, 0)
    expect(w).toEqual({ start: 10, end: 20, spacerTop: 400, spacerBottom: 80 * 40 })
  })

  it('handles fractional (mid-row) scroll positions', () => {
    const w = computeMessageWindow(100, 2137, 400, 40, 0)
    expect(w).toEqual({ start: 53, end: 64, spacerTop: 53 * 40, spacerBottom: 36 * 40 })
  })

  it('anchors the window to the bottom of the list at max scroll', () => {
    const w = computeMessageWindow(100, 3600, 400, 40, 0)
    expect(w).toEqual({ start: 90, end: 100, spacerTop: 90 * 40, spacerBottom: 0 })
  })

  it('clamps overscan at the top of the list', () => {
    const w = computeMessageWindow(100, 0, 400, 40, 6)
    expect(w.start).toBe(0)
    expect(w.end).toBe(16)
    expect(w.spacerTop).toBe(0)
  })

  it('clamps overscan at the bottom of the list', () => {
    const w = computeMessageWindow(100, 3600, 400, 40, 6)
    expect(w.end).toBe(100)
    expect(w.start).toBe(84)
    expect(w.spacerBottom).toBe(0)
  })

  it('clamps a stale scrollTop that exceeds the content height', () => {
    // 10 rows x 40px = 400px content, viewport 400px -> max scroll is 0.
    const w = computeMessageWindow(10, 100000, 400, 40, 0)
    expect(w).toEqual({ start: 0, end: 10, spacerTop: 0, spacerBottom: 0 })
  })

  it('renders every row when the container is taller than the content', () => {
    const w = computeMessageWindow(5, 500, 1000, 40, 0)
    expect(w).toEqual({ start: 0, end: 5, spacerTop: 0, spacerBottom: 0 })
  })

  it('clamps a negative scrollTop to the top of the list', () => {
    const w = computeMessageWindow(100, -50, 400, 40, 0)
    expect(w).toEqual({ start: 0, end: 10, spacerTop: 0, spacerBottom: 90 * 40 })
  })

  it('clamps a huge overscan so the window never exceeds the list', () => {
    const w = computeMessageWindow(3, 0, 400, 40, 100)
    expect(w).toEqual({ start: 0, end: 3, spacerTop: 0, spacerBottom: 0 })
  })

  it('preserves the total scroll height invariant across scroll positions', () => {
    // spacerTop + rendered rows + spacerBottom must always equal total * rowHeight
    // (at or below the true max scroll), so the scrollbar stays honest.
    for (const scrollTop of [0, 1, 333, 1999, 2000, 3600, 99999]) {
      const w = computeMessageWindow(100, scrollTop, 400, 40, 3)
      const rendered = (w.end - w.start) * 40
      expect(w.spacerTop + rendered + w.spacerBottom).toBe(100 * 40)
      expect(w.start).toBeGreaterThanOrEqual(0)
      expect(w.end).toBeLessThanOrEqual(100)
      expect(w.start).toBeLessThanOrEqual(w.end)
    }
  })
})

describe('clamp', () => {
  it('clamps values into [min, max]', () => {
    expect(clamp(5, 0, 10)).toBe(5)
    expect(clamp(-1, 0, 10)).toBe(0)
    expect(clamp(11, 0, 10)).toBe(10)
    expect(clamp(0, 0, 0)).toBe(0)
  })
})