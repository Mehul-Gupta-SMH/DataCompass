import { useState, useRef, useEffect } from 'react'
import ChatMessage from './ChatMessage.jsx'

const QUERY_TYPE_LABELS = {
  sql: 'SQL',
  spark_sql: 'Spark SQL',
  dataframe_api: 'DataFrame API',
}

let _msgId = 0
function nextId() { return ++_msgId }

export default function ChatInterface({ providers }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [provider, setProvider] = useState(providers[0] ?? '')
  const [queryType, setQueryType] = useState('sql')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  // Scroll to bottom whenever messages update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Keep provider in sync if providers list loads after mount
  useEffect(() => {
    if (providers.length && !provider) setProvider(providers[0])
  }, [providers])

  function pushMsg(msg) {
    setMessages((prev) => [...prev, { id: nextId(), ...msg }])
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return

    pushMsg({ role: 'user', type: 'text', content: text })
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text, provider, query_type: queryType }),
      })
      const data = await res.json()

      if (!res.ok) {
        pushMsg({ role: 'assistant', type: 'error', content: data.detail ?? 'An error occurred.' })
        return
      }

      // data.type: "sql" | "code" | "clarify"
      const msgType = data.type === 'clarify' ? 'clarify' : 'sql'
      pushMsg({
        role: 'assistant',
        type: msgType,
        content: data.sql,       // backend sends content under "sql" key
        queryType,
      })
    } catch {
      pushMsg({ role: 'assistant', type: 'error', content: 'Network error — is the backend running?' })
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 110px)' }}>

      {/* Toolbar */}
      <div style={{
        display: 'flex', gap: 8, alignItems: 'center',
        padding: '6px 0 10px',
        borderBottom: '1px solid #e5e7eb',
        marginBottom: 0, flexShrink: 0,
      }}>
        <span style={{ fontSize: 12, color: '#6b7280', fontWeight: 500 }}>Provider</span>
        <select
          style={{ padding: '4px 10px', fontSize: 13, border: '1px solid #d1d5db', borderRadius: 6, background: '#fff' }}
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          disabled={loading}
        >
          {providers.map((p) => <option key={p} value={p}>{p}</option>)}
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
            onClick={() => setMessages([])}
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
            <div style={{ fontSize: 40, marginBottom: 12 }}>
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
              Type below — the assistant will generate {QUERY_TYPE_LABELS[queryType]} or ask for clarification.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage key={msg.id} msg={msg} />
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
        borderTop: '1px solid #e5e7eb',
        paddingTop: 12,
        flexShrink: 0,
        display: 'flex',
        gap: 8,
        alignItems: 'flex-end',
      }}>
        <textarea
          ref={textareaRef}
          rows={2}
          style={{
            flex: 1,
            resize: 'none',
            padding: '10px 14px',
            fontSize: 14,
            border: '1px solid #d1d5db',
            borderRadius: 10,
            fontFamily: 'inherit',
            lineHeight: 1.5,
            outline: 'none',
            boxSizing: 'border-box',
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
            border: 'none',
            borderRadius: 10,
            fontWeight: 700,
            fontSize: 14,
            cursor: loading || !input.trim() ? 'default' : 'pointer',
            flexShrink: 0,
            alignSelf: 'flex-end',
            height: 44,
          }}
        >
          Send
        </button>
      </div>
    </div>
  )
}
