import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import ChatInterface from '../ChatInterface.jsx'
import ChatMessage from '../ChatMessage.jsx'

let originalScrollIntoView

beforeAll(() => {
  originalScrollIntoView = window.HTMLElement.prototype.scrollIntoView
  window.HTMLElement.prototype.scrollIntoView = vi.fn()
})

afterAll(() => {
  window.HTMLElement.prototype.scrollIntoView = originalScrollIntoView
})

describe('ChatInterface Claude Code label handling', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      json: () => Promise.resolve({
        balances: {
          claude_code: { label: 'CLI 1.2.3', available: true },
        },
      }),
    })))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the dropdown option with the backend-provided CLI label', async () => {
    render(<ChatInterface providers={['claude_code']} />)

    await waitFor(() => {
      expect(
        screen.getByRole('option', { name: /Claude Code\s+—\s+CLI 1\.2\.3/ }),
      ).toBeInTheDocument()
    })
  })
})

describe('ChatInterface provider balance display', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      json: () => Promise.resolve({
        balances: {
          open_ai: { label: '$5.00', available: false },
          google: { label: 'N/A', available: true },
        },
      }),
    })))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('disables options when the backend marks the provider unavailable', async () => {
    render(<ChatInterface providers={['open_ai', 'google']} />)

    await waitFor(() => {
      const unavailable = screen.getByRole('option', { name: /OpenAI\s+—\s+\$5\.00/ })
      expect(unavailable).toBeDisabled()
      expect(screen.getByRole('option', { name: /Google Gemini\s+—\s+N\/A/ })).toBeEnabled()
    })
  })
})

describe('ChatMessage clarify options', () => {
  it('shows clarify options as pills and forwards clicks', async () => {
    const handleOptionSelect = vi.fn()

    render(
      <ChatMessage
        msg={{
          role: 'assistant',
          type: 'clarify',
          content: 'Need more detail',
          options: ['Use Claude Code', 'Try another provider'],
        }}
        onOptionSelect={handleOptionSelect}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Use Claude Code' }))

    expect(handleOptionSelect).toHaveBeenCalledTimes(1)
    expect(handleOptionSelect).toHaveBeenCalledWith('Use Claude Code')
  })
})
