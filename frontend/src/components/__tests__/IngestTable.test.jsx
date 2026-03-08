import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'

import IngestTable from '../IngestTable.jsx'

describe('IngestTable provider dropdown', () => {
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

  it('shows provider labels + availability status', async () => {
    render(<IngestTable providers={['open_ai', 'google']} />)

    await waitFor(() => {
      const unavailable = screen.getByRole('option', { name: /OpenAI\s+—\s+\$5\.00/ })
      expect(unavailable).toBeDisabled()
      expect(screen.getByRole('option', { name: /Google Gemini\s+—\s+N\/A/ })).toBeEnabled()
    })
  })
})

describe('IngestTable Codex option', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      json: () => Promise.resolve({
        balances: {
          codex: { label: '$0.03', available: true },
        },
      }),
    })))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the Codex provider label', async () => {
    render(<IngestTable providers={['codex']} />)

    await waitFor(() => {
      const option = screen.getByRole('option', { name: /OpenAI Codex/ })
      expect(option).toBeInTheDocument()
      expect(option).toHaveTextContent('OpenAI Codex')
      expect(option).toHaveTextContent('$0.03')
    })
  })
})
