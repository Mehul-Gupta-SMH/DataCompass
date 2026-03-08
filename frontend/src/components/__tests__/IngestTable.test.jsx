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
