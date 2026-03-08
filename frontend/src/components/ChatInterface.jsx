import { useState, useRef, useEffect } from 'react'
import ChatMessage from './ChatMessage.jsx'
import { PROVIDER_LABELS, formatProviderLabel } from '../constants/providerLabels.js'

const QUERY_TYPE_LABELS = {
  sql: 'SQL',
  spark_sql: 'Spark SQL',
  dataframe_api: 'DataFrame API',
  pandas: 'Pandas',
}

const STORAGE_KEY = 'data_compass_sessions'
const MAX_SESSIONS = 30

let _msgId = 0
function nextId() { return ++_msgId }

function loadSessions() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') } catch { return [] }
}

function saveSessions(sessions) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions)) } catch {}
}

function formatTimestamp(ts) {
  const d = new Date(ts)
  const now = new Date()
  if (d.toDateString() === now.toDateString())
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

// ---------------------------------------------------------------------------
// Left pane — session list
// ---------------------------------------------------------------------------
function SessionPane({ sessions, currentId, onSelect, onNew, onDelete }) {
  const [hoverId, setHoverId] = useState(null)

  return (
    <div style={{
      width: 220, flexShrink: 0,
      borderRight: '1px solid #e5e7eb',
      display: 'flex', flexDirection: 'column',
      background: '#f9fafb',
      overflowY: 'auto',
    }}>
      <div style={{ padding: '10px 10px 6px' }}>
        <button
          onClick={onNew}
          style={{
            width: '100%', padding: '7px 12px', fontSize: 13, fontWeight: 600,
            background: '#2563eb', color: '#fff', border: 'none',
            borderRadius: 7, cursor: 'pointer', textAlign: 'left',
          }}
        >
          + New Chat
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '2px 6px 8px' }}>
        {sessions.length === 0 && (
          <p style={{ fontSize: 12, color: '#9ca3af', textAlign: 'center', marginTop: 24 }}>
            No conversations yet
          </p>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            onMouseEnter={() => setHoverId(s.id)}
            onMouseLeave={() => setHoverId(null)}
            style={{
              position: 'relative',
              borderRadius: 6,
              marginBottom: 2,
              background: s.id === currentId ? '#e0e7ff' : hoverId === s.id ? '#f3f4f6' : 'transparent',
              cursor: 'pointer',
            }}
          >
            <div
              onClick={() => onSelect(s)}
              style={{ padding: '7px 28px 7px 10px' }}
            >
              <div style={{
                fontSize: 13, fontWeight: s.id === currentId ? 600 : 400,
                color: '#1f2937',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {s.title}
              </div>
              <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>
                {formatTimestamp(s.timestamp)} · {PROVIDER_LABELS[s.provider] ?? s.provider}
              </div>
            </div>
            {hoverId === s.id && (
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(s.id) }}
                style={{
                  position: 'absolute', top: 6, right: 6,
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: '#9ca3af', fontSize: 14, lineHeight: 1, padding: 2,
                }}
                title="Delete"
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main chat component
// ---------------------------------------------------------------------------
export default function ChatInterface({ providers }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [provider, setProvider] = useState(providers[0] ?? '')
  const [queryType, setQueryType] = useState('sql')
  const [loading, setLoading] = useState(false)
  const [balances, setBalances] = useState({})
  const [sessions, setSessions] = useState(() => loadSessions())
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const bottomRef = useRef(null)
  const sessionIdRef = useRef(null)   // stable ref avoids stale closure issues

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Sync provider when list first loads
  useEffect(() => {
    if (providers.length && !provider) setProvider(providers[0])
  }, [providers])

  // Fetch provider balances
  useEffect(() => {
    if (!providers.length) return
    fetch('/api/providers/balance')
      .then((r) => r.json())
      .then((data) => setBalances(data.balances ?? {}))
      .catch(() => {})
  }, [providers])

  // Auto-save session whenever messages change
  useEffect(() => {
    if (!messages.length || !sessionIdRef.current) return
    const title = (messages.find((m) => m.role === 'user')?.content ?? 'Conversation').slice(0, 55)
    setSessions((prev) => {
      const existing = prev.find((s) => s.id === sessionIdRef.current)
      const entry = {
        id: sessionIdRef.current,
        title,
        timestamp: existing?.timestamp ?? Date.now(),
        messages,
        provider,
        queryType,
      }
      const others = prev.filter((s) => s.id !== sessionIdRef.current)
      const next = [entry, ...others].slice(0, MAX_SESSIONS)
      saveSessions(next)
      return next
    })
  }, [messages])

  // ---- Session management -----------------------------------------------

  function handleNewChat() {
    setMessages([])
    setCurrentSessionId(null)
    sessionIdRef.current = null
    setInput('')
  }

  function handleSelectSession(session) {
    setMessages(session.messages)
    setProvider(session.provider)
    setQueryType(session.queryType)
    setCurrentSessionId(session.id)
    sessionIdRef.current = session.id
  }

  function handleDeleteSession(id) {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id)
      saveSessions(next)
      return next
    })
    if (sessionIdRef.current === id) handleNewChat()
  }

  // ---- Message helpers ---------------------------------------------------

  function pushMsg(msg) {
    setMessages((prev) => [...prev, { id: nextId(), ...msg }])
  }

  // Conversation history for /api/chat — only dialogue turns, not SQL blobs
  function buildHistory(msgs) {
    return msgs
      .filter((m) => m.type === 'text' || m.type === 'clarify')
      .map((m) => ({ role: m.role, content: m.content }))
  }

  // ---- API call ----------------------------------------------------------

  async function _callApi(history, prov, qType, retryLabel) {
    setLoading(true)
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history, provider: prov, query_type: qType }),
      })
      const data = await res.json()

      if (!res.ok) {
        pushMsg({ role: 'assistant', type: 'error', content: data.detail ?? 'An error occurred.', retryQuery: retryLabel })
        return
      }

      const msgType = data.type === 'clarify' ? 'clarify' : 'sql'
      const msg = { role: 'assistant', type: msgType, content: data.sql, queryType: qType }
      if (data.options?.length) msg.options = data.options
      pushMsg(msg)
    } catch {
      pushMsg({ role: 'assistant', type: 'error', content: 'Network error — is the backend running?', retryQuery: retryLabel })
    } finally {
      setLoading(false)
    }
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')

    // Start a new session on the first message
    if (!sessionIdRef.current) {
      const newId = Date.now().toString()
      sessionIdRef.current = newId
      setCurrentSessionId(newId)
    }

    const userEntry = { id: nextId(), role: 'user', type: 'text', content: text }
    const updated = [...messages, userEntry]
    setMessages(updated)

    await _callApi(buildHistory(updated), provider, queryType, text)
  }

  function handleRetry(failedMsg) {
    if (loading) return
    const prior = messages.filter((m) => m.id !== failedMsg.id)
    setMessages(prior)
    // Exclude previous assistant clarify messages so the requirement gathering
    // agent re-evaluates fresh from user messages only (not its own prior questions).
    const retryHistory = prior
      .filter((m) => m.type === 'text')
      .map((m) => ({ role: m.role, content: m.content }))
    _callApi(retryHistory, provider, queryType, failedMsg.retryQuery)
  }

  async function handleOptionSelect(optionText) {
    if (loading) return
    setInput('')
    if (!sessionIdRef.current) {
      const newId = Date.now().toString()
      sessionIdRef.current = newId
      setCurrentSessionId(newId)
    }
    const userEntry = { id: nextId(), role: 'user', type: 'text', content: optionText }
    const updated = [...messages, userEntry]
    setMessages(updated)
    await _callApi(buildHistory(updated), provider, queryType, optionText)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const isEmpty = messages.length === 0

  // ---- Render ------------------------------------------------------------

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 110px)' }}>

      {/* ── Left pane: session history ── */}
      <SessionPane
        sessions={sessions}
        currentId={currentSessionId}
        onSelect={handleSelectSession}
        onNew={handleNewChat}
        onDelete={handleDeleteSession}
      />

      {/* ── Right: chat area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, paddingLeft: 16 }}>

        {/* Toolbar */}
        <div style={{
          display: 'flex', gap: 8, alignItems: 'center',
          padding: '6px 0 10px',
          borderBottom: '1px solid #e5e7eb',
          flexShrink: 0,
        }}>
          <span style={{ fontSize: 12, color: '#6b7280', fontWeight: 500 }}>Provider</span>
          <select
            style={{ padding: '4px 10px', fontSize: 13, border: '1px solid #d1d5db', borderRadius: 6, background: '#fff' }}
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            disabled={loading}
          >
            {providers.map((p) => {
              const bal = balances[p]
              const unavailable = bal?.available === false
              const label = formatProviderLabel(p, balances)
              return (
                <option key={p} value={p} disabled={unavailable}>
                  {label}{unavailable ? ' (unavailable)' : ''}
                </option>
              )
            })}
          </select>

          <span style={{ fontSize: 12, color: '#6b7280', fontWeight: 500, marginLeft: 8 }}>Mode</span>
          <select
            style={{ padding: '4px 10px', fontSize: 13, border: '1px solid #d1d5db', borderRadius: 6, background: '#fff' }}
            value={queryType}
            onChange={(e) => setQueryType(e.target.value)}
            disabled={loading}
          >
            {Object.entries(QUERY_TYPE_LABELS).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>

          {messages.length > 0 && (
            <button
              onClick={handleNewChat}
              style={{
                marginLeft: 'auto', background: 'none', border: '1px solid #e5e7eb',
                borderRadius: 5, padding: '3px 10px', fontSize: 12,
                color: '#6b7280', cursor: 'pointer',
              }}
            >
              Clear chat
            </button>
          )}
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 0 8px' }}>
          {isEmpty && (
            <div style={{ textAlign: 'center', marginTop: '15%', color: '#9ca3af' }}>
              <div style={{ marginBottom: 12 }}>
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="#d1d5db" strokeWidth="1.2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M16.24 7.76l-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z" fill="#e5e7eb" stroke="none" />
                  <circle cx="12" cy="12" r="1.5" fill="#9ca3af" stroke="none" />
                </svg>
              </div>
              <p style={{ fontSize: 15, fontWeight: 600, color: '#6b7280', margin: '0 0 6px' }}>
                Ask a question about your data
              </p>
              <p style={{ fontSize: 13, color: '#9ca3af', margin: 0 }}>
                Type below — the assistant will gather requirements then generate {QUERY_TYPE_LABELS[queryType]}.
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessage key={msg.id} msg={msg} onRetry={handleRetry} onOptionSelect={handleOptionSelect} />
          ))}

          {loading && (
            <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 14 }}>
              <div style={{
                background: '#f3f4f6', borderRadius: '4px 16px 16px 16px',
                padding: '10px 18px', fontSize: 14, color: '#6b7280',
                display: 'flex', gap: 4, alignItems: 'center',
              }}>
                <span style={{ animation: 'pulse 1s infinite' }}>●</span>
                <span style={{ opacity: 0.6 }}>●</span>
                <span style={{ opacity: 0.3 }}>●</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div style={{
          borderTop: '1px solid #e5e7eb', paddingTop: 12,
          flexShrink: 0, display: 'flex', gap: 8, alignItems: 'flex-end',
        }}>
          <textarea
            rows={2}
            style={{
              flex: 1, resize: 'none', padding: '10px 14px', fontSize: 14,
              border: '1px solid #d1d5db', borderRadius: 10, fontFamily: 'inherit',
              lineHeight: 1.5, outline: 'none', boxSizing: 'border-box',
            }}
            placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            style={{
              padding: '10px 18px',
              background: loading || !input.trim() ? '#e5e7eb' : '#2563eb',
              color: loading || !input.trim() ? '#9ca3af' : '#fff',
              border: 'none', borderRadius: 10, fontWeight: 700, fontSize: 14,
              cursor: loading || !input.trim() ? 'default' : 'pointer',
              flexShrink: 0, alignSelf: 'flex-end', height: 44,
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
