// @vitest-environment jsdom
/**
 * First real component test for ChatView (round-8).
 *
 * We deliberately test the SIMPLEST stable behaviors instead of mocking the
 * whole component (api calls, SSE streaming, sessionStorage, ResizeObserver…):
 *   - MessageRow is a memoized component (round-5 regression guard).
 *   - MessageRow renders user and assistant messages faithfully.
 *   - The *[stopped]* marker (round-3 regression guard) is rendered as text.
 *
 * The virtual-list windowing math itself is covered by pure unit tests in
 * lib/virtualList.test.ts (node env, no DOM required).
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MessageRow } from './ChatView'
import type { MessageRecord } from '../lib/api/conversations'

function makeMessage(overrides: Partial<MessageRecord>): MessageRecord {
  return {
    id: 'm1',
    conversation_id: 'conv-1',
    role: 'assistant',
    content: '',
    status: 'completed',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    attachments: [],
    ...overrides,
  }
}

describe('MessageRow', () => {
  it('is wrapped in React.memo (round-5 regression guard)', () => {
    // React.memo returns an element with $$typeof === Symbol.for('react.memo').
    expect((MessageRow as unknown as { $$typeof: symbol }).$$typeof).toBe(Symbol.for('react.memo'))
  })

  it('renders a user message with its prompt glyph and content', () => {
    const message = makeMessage({ id: 'u1', role: 'user', content: 'Build me a todo app' })
    render(<MessageRow message={message} />)
    expect(screen.getByText('Build me a todo app')).toBeTruthy()
    expect(screen.getByText('❯')).toBeTruthy()
  })

  it('renders an assistant message content', () => {
    const message = makeMessage({ id: 'a1', role: 'assistant', content: 'Here is the plan.' })
    render(<MessageRow message={message} />)
    expect(screen.getByText('Here is the plan.')).toBeTruthy()
  })

  it('renders the *[stopped]* marker when content ends with it', () => {
    const message = makeMessage({ id: 'a2', role: 'assistant', content: 'Partial answer\n\n*[stopped]*' })
    render(<MessageRow message={message} />)
    expect(screen.getByText('Partial answer')).toBeTruthy()
    expect(screen.getByText('*[stopped]*')).toBeTruthy()
  })

  it('renders a streaming placeholder when assistant state is streaming with no content', () => {
    const message = makeMessage({ id: 'a3', role: 'assistant', content: '', status: 'streaming' })
    render(
      <MessageRow
        message={message}
        state={{ content: '', toolCalls: [], fileDiffs: [], shellOutputs: new Map(), todos: [], filesModified: [], isStreaming: true }}
      />,
    )
    expect(screen.getByText(/thinking…/)).toBeTruthy()
  })
})