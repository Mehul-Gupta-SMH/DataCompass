import React from 'react'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App.jsx'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch({ providersPayload, queryPayload, providersFails, queryFails } = {}) {
  const fetchMock = vi.fn()

  // First call: GET /api/providers
  if (providersFails) {
    fetchMock.mockRejectedValueOnce(new Error('network'))
  } else {
    const providers = providersPayload ?? ['anthropic', 'open_ai']
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ providers }),
    })
  }

  // Second call: POST /api/query (only set up when needed)
  if (queryPayload !== undefined) {
    fetchMock.mockResolvedValueOnce(queryPayload)
  } else if (queryFails) {
    fetchMock.mockRejectedValueOnce(new Error('network'))
  }

  global.fetch = fetchMock
  return fetchMock
}

async function waitForProviders() {
  await waitFor(() => expect(screen.getByRole('combobox')).toBeInTheDocument())
  // wait until at least one option is rendered
  await waitFor(() => expect(screen.getAllByRole('option').length).toBeGreaterThan(0))
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('App', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches /api/providers on mount', async () => {
    const fetchMock = mockFetch()
    render(<App />)
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/api/providers'),
    )
  })

  it('populates the provider dropdown after mount', async () => {
    mockFetch({ providersPayload: ['anthropic', 'open_ai'] })
    render(<App />)
    await waitForProviders()
    const options = screen.getAllByRole('option')
    expect(options.map((o) => o.value)).toEqual(['anthropic', 'open_ai'])
  })

  it('shows an error when the provider fetch fails', async () => {
    mockFetch({ providersFails: true })
    render(<App />)
    await waitFor(() =>
      expect(
        screen.getByText(/failed to load providers from backend/i),
      ).toBeInTheDocument(),
    )
  })

  it('shows "Please enter a query." and makes no query fetch when query is empty', async () => {
    const fetchMock = mockFetch()
    render(<App />)
    // textarea is empty by default — click submit without typing
    await userEvent.click(screen.getByRole('button', { name: /generate sql/i }))
    expect(screen.getByText('Please enter a query.')).toBeInTheDocument()
    // Only the initial providers fetch; no second call for /api/query
    expect(fetchMock).not.toHaveBeenCalledWith(
      '/api/query',
      expect.anything(),
    )
  })

  it('shows the SQL result on a successful query', async () => {
    mockFetch({
      providersPayload: ['open_ai'],
      queryPayload: {
        ok: true,
        json: () => Promise.resolve({ sql: 'SELECT 1' }),
      },
    })
    render(<App />)
    await waitForProviders()

    await userEvent.type(screen.getByRole('textbox'), 'show me orders')
    await userEvent.click(screen.getByRole('button', { name: /generate sql/i }))

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /generated sql/i })).toBeInTheDocument(),
    )
  })

  it('shows the detail field as an error when the API returns a non-ok response', async () => {
    mockFetch({
      providersPayload: ['open_ai'],
      queryPayload: {
        ok: false,
        json: () => Promise.resolve({ detail: 'Invalid query input.' }),
      },
    })
    render(<App />)
    await waitForProviders()

    await userEvent.type(screen.getByRole('textbox'), 'bad query')
    await userEvent.click(screen.getByRole('button', { name: /generate sql/i }))

    await waitFor(() =>
      expect(screen.getByText('Invalid query input.')).toBeInTheDocument(),
    )
  })

  it('shows a network error message when fetch throws', async () => {
    mockFetch({
      providersPayload: ['open_ai'],
      queryFails: true,
    })
    render(<App />)
    await waitForProviders()

    await userEvent.type(screen.getByRole('textbox'), 'show me orders')
    await userEvent.click(screen.getByRole('button', { name: /generate sql/i }))

    await waitFor(() =>
      expect(screen.getByText(/network error/i)).toBeInTheDocument(),
    )
  })

  it('appends a new entry to the history list after a successful query', async () => {
    mockFetch({
      providersPayload: ['open_ai'],
      queryPayload: {
        ok: true,
        json: () => Promise.resolve({ sql: 'SELECT 1' }),
      },
    })
    render(<App />)
    await waitForProviders()

    await userEvent.type(screen.getByRole('textbox'), 'show me orders')
    await userEvent.click(screen.getByRole('button', { name: /generate sql/i }))

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /session history/i })).toBeInTheDocument(),
    )
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })

  it('restores the textarea value when a history item is clicked', async () => {
    mockFetch({
      providersPayload: ['open_ai'],
      queryPayload: {
        ok: true,
        json: () => Promise.resolve({ sql: 'SELECT 1' }),
      },
    })
    render(<App />)
    await waitForProviders()

    await userEvent.type(screen.getByRole('textbox'), 'show me orders')
    await userEvent.click(screen.getByRole('button', { name: /generate sql/i }))

    // Wait for the history item to appear
    await waitFor(() => screen.getByText('show me orders', { selector: 'div' }))

    // Clear the textarea by clicking the history item
    await userEvent.clear(screen.getByRole('textbox'))
    await userEvent.click(screen.getByText('show me orders', { selector: 'div' }))

    expect(screen.getByRole('textbox')).toHaveValue('show me orders')
  })
})
