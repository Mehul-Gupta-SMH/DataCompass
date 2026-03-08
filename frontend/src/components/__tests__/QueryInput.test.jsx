import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QueryInput from '../QueryInput.jsx'

function renderQueryInput(overrides = {}) {
  const props = {
    query: '',
    setQuery: vi.fn(),
    provider: 'open_ai',
    setProvider: vi.fn(),
    providers: ['open_ai', 'anthropic'],
    loading: false,
    error: '',
    onSubmit: vi.fn(),
    ...overrides,
  }
  return { ...render(<QueryInput {...props} />), props }
}

describe('QueryInput', () => {
  it('renders a textarea', () => {
    renderQueryInput()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('renders a provider select', () => {
    renderQueryInput()
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('renders a submit button', () => {
    renderQueryInput()
    expect(screen.getByRole('button', { name: /generate sql/i })).toBeInTheDocument()
  })

  it('calls onSubmit when the form is submitted', async () => {
    const { props } = renderQueryInput()
    await userEvent.click(screen.getByRole('button', { name: /generate sql/i }))
    expect(props.onSubmit).toHaveBeenCalledTimes(1)
  })

  it('calls setQuery when the textarea changes', () => {
    const { props } = renderQueryInput()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'hello' } })
    expect(props.setQuery).toHaveBeenCalledWith('hello')
  })

  it('calls setProvider when the select changes', () => {
    const { props } = renderQueryInput()
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'anthropic' } })
    expect(props.setProvider).toHaveBeenCalledWith('anthropic')
  })

  it('disables textarea and button when loading is true', () => {
    renderQueryInput({ loading: true })
    expect(screen.getByRole('textbox')).toBeDisabled()
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('shows "Generating…" button text when loading', () => {
    renderQueryInput({ loading: true })
    expect(screen.getByRole('button')).toHaveTextContent('Generating\u2026')
  })

  it('shows error text when error prop is non-empty', () => {
    renderQueryInput({ error: 'Something went wrong' })
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('does not show error element when error is empty', () => {
    renderQueryInput({ error: '' })
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument()
  })
})
