import React, { useState, useEffect } from 'react'
import QueryInput from './components/QueryInput.jsx'
import SQLResult from './components/SQLResult.jsx'
import QueryHistory from './components/QueryHistory.jsx'

export default function App() {
  const [providers, setProviders] = useState([])
  const [provider, setProvider] = useState('')
  const [query, setQuery] = useState('')
  const [sql, setSql] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])

  useEffect(() => {
    fetch('/api/providers')
      .then((r) => r.json())
      .then((data) => {
        setProviders(data.providers)
        if (data.providers.length > 0) setProvider(data.providers[0])
      })
      .catch(() => setError('Failed to load providers from backend.'))
  }, [])

  async function handleSubmit() {
    if (!query.trim()) {
      setError('Please enter a query.')
      return
    }
    setError('')
    setSql('')
    setLoading(true)
    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, provider }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail ?? 'An error occurred.')
      } else {
        setSql(data.sql)
        setHistory((prev) => [{ query, provider, sql: data.sql }, ...prev])
      }
    } catch {
      setError('Network error — is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  function handleHistorySelect(entry) {
    setQuery(entry.query)
    setProvider(entry.provider)
    setSql(entry.sql)
    setError('')
  }

  return (
    <div>
      <h1>SQLCoder</h1>
      <QueryInput
        query={query}
        setQuery={setQuery}
        provider={provider}
        setProvider={setProvider}
        providers={providers}
        loading={loading}
        error={error}
        onSubmit={handleSubmit}
      />
      <SQLResult sql={sql} />
      <QueryHistory history={history} onSelect={handleHistorySelect} />
    </div>
  )
}
