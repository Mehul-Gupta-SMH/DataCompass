import React from 'react'
import { render, screen, fireEvent, act } from '@testing-library/react'
import SQLResult from '../SQLResult.jsx'

describe('SQLResult', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
      configurable: true,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders nothing when sql is empty string', () => {
    const { container } = render(<SQLResult sql="" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when sql is null', () => {
    const { container } = render(<SQLResult sql={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the SQL text', () => {
    render(<SQLResult sql="SELECT 1" />)
    expect(screen.getByText('SELECT 1')).toBeInTheDocument()
  })

  it('renders "Generated SQL" heading', () => {
    render(<SQLResult sql="SELECT 1" />)
    expect(screen.getByRole('heading', { name: /generated sql/i })).toBeInTheDocument()
  })

  it('renders a copy button', () => {
    render(<SQLResult sql="SELECT 1" />)
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
  })

  it('calls clipboard.writeText with the sql string on copy click', async () => {
    render(<SQLResult sql="SELECT 42" />)
    fireEvent.click(screen.getByRole('button', { name: /copy/i }))
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('SELECT 42')
  })

  it('shows "Copied!" after copy button is clicked', async () => {
    render(<SQLResult sql="SELECT 1" />)
    fireEvent.click(screen.getByRole('button', { name: /copy/i }))
    // flush the resolved clipboard promise
    await act(async () => {})
    expect(screen.getByRole('button')).toHaveTextContent('Copied!')
  })

  it('reverts button label back to "Copy" after 2 s', async () => {
    vi.useFakeTimers()
    render(<SQLResult sql="SELECT 1" />)
    fireEvent.click(screen.getByRole('button', { name: /copy/i }))
    await act(async () => {})
    expect(screen.getByRole('button')).toHaveTextContent('Copied!')
    act(() => vi.advanceTimersByTime(2001))
    expect(screen.getByRole('button')).toHaveTextContent('Copy')
  })
})
