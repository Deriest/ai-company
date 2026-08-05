/**
 * Lightweight virtual-list windowing for the chat message list.
 *
 * ChatView renders every message in a conversation (1000+ rows possible), which
 * makes the initial render of a long conversation expensive. This module
 * computes the "window" of messages that should actually be rendered for a
 * given scroll position, plus the heights of the top/bottom spacer divs that
 * preserve the total scroll height — so the scrollbar, auto-scroll-to-bottom,
 * and stick-to-bottom-while-streaming behavior stay identical to a fully
 * rendered list.
 *
 * Implementation is a fixed-estimate row-height window (no dependency): rows
 * are assumed to be `rowHeight` px tall, and the caller may refine the estimate
 * over time by measuring the rendered slice (see ChatView).
 */
export interface MessageWindow {
  /** First index to render (inclusive). */
  start: number;
  /** Index after the last rendered row (exclusive). */
  end: number;
  /** Height in px of the top spacer (rows [0, start) are off-screen). */
  spacerTop: number;
  /** Height in px of the bottom spacer (rows [end, total) are off-screen). */
  spacerBottom: number;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Compute the visible window of a `total`-row list.
 *
 * - `scrollTop` is clamped to the valid range: a stale/large scrollTop (e.g.
 *   after switching to a shorter conversation, or after the content shrinks)
 *   must never push the window past the end of the list, which would render a
 *   blank view.
 * - `overscan` adds extra rows above/below the viewport so slightly taller
 *   rows don't produce empty gaps while scrolling.
 */
export function computeMessageWindow(
  total: number,
  scrollTop: number,
  containerHeight: number,
  rowHeight: number,
  overscan: number,
): MessageWindow {
  if (total <= 0 || rowHeight <= 0) {
    return { start: 0, end: 0, spacerTop: 0, spacerBottom: 0 };
  }

  const safeContainer = Math.max(containerHeight, 0);
  const safeOverscan = Math.max(overscan, 0);

  const contentHeight = total * rowHeight;
  const maxScrollTop = Math.max(0, contentHeight - safeContainer);
  const clampedScrollTop = clamp(scrollTop, 0, maxScrollTop);

  let start = Math.floor(clampedScrollTop / rowHeight) - safeOverscan;
  let end = Math.ceil((clampedScrollTop + safeContainer) / rowHeight) + safeOverscan;

  start = clamp(start, 0, total);
  end = clamp(end, start, total);

  return {
    start,
    end,
    spacerTop: start * rowHeight,
    spacerBottom: (total - end) * rowHeight,
  };
}