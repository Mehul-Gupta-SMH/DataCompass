import React, { useState, useEffect } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext.jsx'
import LoginPage from './components/LoginPage.jsx'
import ChatInterface from './components/ChatInterface.jsx'
import SchemaERD from './components/SchemaERD.jsx'
import IngestTable from './components/IngestTable.jsx'
import DataLineage from './components/DataLineage.jsx'

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

function CompassIcon() {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#2563eb" strokeWidth="1.4">
      <circle cx="12" cy="12" r="10" />
      <polygon points="12,5 14.5,12 12,19 9.5,12" fill="#2563eb" stroke="none" opacity="0.25" />
      <polygon points="5,12 12,9.5 19,12 12,14.5" fill="#2563eb" stroke="none" />
      <circle cx="12" cy="12" r="1.2" fill="#fff" stroke="none" />
    </svg>
  )
}

function AppContent() {
  const { user, logout } = useAuth()
  const [activeTab, setActiveTab]     = useState('query')
  const [providers, setProviders]     = useState([])
  const [schemaTables, setSchemaTables] = useState([])

  useEffect(() => {
    if (!user) return
    fetch('/api/providers')
      .then((r) => r.json())
      .then((data) => setProviders(data.providers ?? []))
      .catch(() => {})
  }, [user])

  useEffect(() => {
    if (!user) return
    if (activeTab === 'lineage') {
      fetch('/api/schema')
        .then((r) => r.json())
        .then((data) => setSchemaTables((data.tables ?? []).map((t) => t.name)))
        .catch(() => {})
    }
  }, [activeTab, user])

  // Redirect to login if not authenticated
  if (!user) return <LoginPage />

  return (
    <div style={{ maxWidth: '98vw', margin: '0 auto', padding: '0 24px' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderBottom: '1px solid #e5e7eb', paddingBottom: 0, marginBottom: 0, paddingTop: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingBottom: 10 }}>
          <CompassIcon />
          <span style={{ fontSize: 20, fontWeight: 700, color: '#1e1e2e', letterSpacing: '-0.3px' }}>
            Data Compass
          </span>
        </div>

        <nav style={{ display: 'flex', gap: 2 }}>
          <button style={tabStyle(activeTab === 'query')}   onClick={() => setActiveTab('query')}>Query</button>
          <button style={tabStyle(activeTab === 'schema')}  onClick={() => setActiveTab('schema')}>Schema / ERD</button>
          <button style={tabStyle(activeTab === 'ingest')}  onClick={() => setActiveTab('ingest')}>Ingest Table</button>
          <button style={tabStyle(activeTab === 'lineage')} onClick={() => setActiveTab('lineage')}>Join Path</button>
        </nav>

        {/* User info + logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 10 }}>
          <span style={{ fontSize: 13, color: '#6b7280' }}>
            {user.username}
          </span>
          <button
            onClick={logout}
            style={{
              background: 'none', border: '1px solid #e5e7eb', borderRadius: 6,
              padding: '4px 12px', fontSize: 12, color: '#6b7280', cursor: 'pointer',
            }}
          >
            Sign out
          </button>
        </div>
      </div>

      {/* Tab content */}
      <div style={{ paddingTop: 16 }}>
        {activeTab === 'query'   && <ChatInterface providers={providers} />}
        {activeTab === 'schema'  && <SchemaERD />}
        {activeTab === 'ingest'  && <IngestTable providers={providers} />}
        {activeTab === 'lineage' && <DataLineage tables={schemaTables} />}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}