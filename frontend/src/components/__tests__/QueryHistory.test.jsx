import React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QueryHistory from '../QueryHistory.jsx'

const SAMPLE_HISTORY = [
  { query: 'show me orders', provider: 'open_ai', sql: 'SELECT * FROM orders' },
  { query: 'top products', provider: 'anthropic', sql: 'SELECT * FROM products' },
]

describe('QueryHistory', () => {
  it('renders nothing when history is empty', () => {
    const { container } = render(<QueryHistory history={[]} onSelect={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders "Session History" heading when entries are present', () => {
    render(<QueryHistory history={SAMPLE_HISTORY} onSelect={vi.fn()} />)
    expect(screen.getByRole('heading', { name: /session history/i })).toBeInTheDocument()
  })

  it('renders one list item per history entry', () => {
    render(<QueryHistory history={SAMPLE_HISTORY} onSelect={vi.fn()} />)
    expect(screen.getAllByRole('listitem')).toHaveLength(SAMPLE_HISTORY.length)
  })

  it('shows query text for each entry', () => {
    render(<QueryHistory history={SAMPLE_HISTORY} onSelect={vi.fn()} />)
    expect(screen.getByText('show me orders')).toBeInTheDocument()
    expect(screen.getByText('top products')).toBeInTheDocument()
  })

  it('shows provider for each entry', () => {
    render(<QueryHistory history={SAMPLE_HISTORY} onSelect={vi.fn()} />)
    expect(screen.getByText(/open_ai/)).toBeInTheDocument()
    expect(screen.getByText(/anthropic/)).toBeInTheDocument()
  })

  it('shows SQL preview for each entry', () => {
    render(<QueryHistory history={SAMPLE_HISTORY} onSelect={vi.fn()} />)
    expect(screen.getByText('SELECT * FROM orders')).toBeInTheDocument()
    expect(screen.getByText('SELECT * FROM products')).toBeInTheDocument()
  })

  it('calls onSelect with the clicked entry object', async () => {
    const onSelect = vi.fn()
    render(<QueryHistory history={SAMPLE_HISTORY} onSelect={onSelect} />)
    await userEvent.click(screen.getByText('show me orders'))
    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith(SAMPLE_HISTORY[0])
  })
})
