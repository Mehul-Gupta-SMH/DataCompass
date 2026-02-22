import React, { useState, useEffect } from 'react'
import QueryInput from './components/QueryInput.jsx'
import SQLResult from './components/SQLResult.jsx'
import QueryHistory from './components/QueryHistory.jsx'
import SchemaERD from './components/SchemaERD.jsx'

const tabStyle = (active) => ({
  padding: '6px 16px',
  border: 'none',
  background: 'none',
  cursor: 'pointer',
  fontWeight: active ? 600 : 400,
  color: active ? '#2563eb' : '#555',
  borderBottom: active ? '2px solid #2563eb' : '2px solid transparent',
  fontSize: 14,
})

export default function App() {
  const [activeTab, setActiveTab] = useState('query')
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
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #e5e7eb',
          paddingBottom: 0,
          marginBottom: 16,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 20 }}>SQLCoder</h1>
        <nav style={{ display: 'flex', gap: 4 }}>
          <button style={tabStyle(activeTab === 'query')} onClick={() => setActiveTab('query')}>
            Query
          </button>
          <button style={tabStyle(activeTab === 'schema')} onClick={() => setActiveTab('schema')}>
            Schema / ERD
          </button>
        </nav>
      </div>

      {activeTab === 'query' && (
        <>
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
        </>
      )}

      {activeTab === 'schema' && <SchemaERD />}
    </div>
  )
}
