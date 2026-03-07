import { useState } from 'react'

// ---------------------------------------------------------------------------
// Run-query section embedded inside SQL messages
// ---------------------------------------------------------------------------
function ResultsTable({ columns, rows }) {
  if (!columns?.length) return <p style={{ color: '#9ca3af', fontSize: 12 }}>No results.</p>
  return (
    <div style={{ overflowX: 'auto', marginTop: 8 }}>
      <table style={{ borderCollapse: 'collapse', fontSize: 12, width: '100%' }}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c} style={{ background: '#f3f4f6', border: '1px solid #e5e7eb', padding: '4px 8px', textAlign: 'left', fontWeight: 600 }}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} style={{ border: '1px solid #e5e7eb', padding: '3px 8px', background: i % 2 ? '#f9fafb' : '#fff' }}>
                  {cell === null ? <em style={{ color: '#9ca3af' }}>NULL</em> : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RunQueryPanel({ content, queryType }) {
  const [open, setOpen] = useState(false)
  const [connStr, setConnStr] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function handleRun() {
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const res = await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ generated_query: content, query_type: queryType, connection_string: connStr }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail ?? 'Execution failed.'); return }
      setResult(data)
    } catch {
      setError('Network error.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ marginTop: 10 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          background: 'none', border: '1px solid #d1d5db', borderRadius: 5,
          padding: '3px 10px', fontSize: 12, cursor: 'pointer', color: '#374151',
          display: 'flex', alignItems: 'center', gap: 4,
        }}
      >
        <span style={{ fontSize: 10 }}>{open ? '▼' : '▶'}</span> Run Query
      </button>

      {open && (
        <div style={{ marginTop: 8 }}>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              style={{
                flex: 1, minWidth: 200, padding: '5px 8px', fontSize: 12,
                border: '1px solid #d1d5db', borderRadius: 5, fontFamily: 'monospace',
              }}
              placeholder="sqlite:///path/to/db.sqlite"
              value={connStr}
              onChange={(e) => setConnStr(e.target.value)}
              disabled={loading}
            />
            <button
              onClick={handleRun}
              disabled={loading || !connStr.trim()}
              style={{
                background: '#16a34a', color: '#fff', border: 'none', borderRadius: 5,
                padding: '5px 14px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}
            >
              {loading ? 'Running…' : 'Execute'}
            </button>
          </div>
          {error && <p style={{ color: '#b91c1c', fontSize: 12, marginTop: 6 }}>{error}</p>}
          {result && <ResultsTable columns={result.columns} rows={result.rows} />}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Individual message bubble
// ---------------------------------------------------------------------------
export default function ChatMessage({ msg, onRetry }) {
  const [copied, setCopied] = useState(false)

  const isUser = msg.role === 'user'

  function handleCopy() {
    navigator.clipboard.writeText(msg.content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  // ---- User bubble --------------------------------------------------------
  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 14 }}>
        <div
          style={{
            background: '#2563eb',
            color: '#fff',
            borderRadius: '16px 16px 4px 16px',
            padding: '10px 16px',
            maxWidth: '70%',
            fontSize: 14,
            lineHeight: 1.5,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {msg.content}
        </div>
      </div>
    )
  }

  // ---- Clarify bubble -----------------------------------------------------
  if (msg.type === 'clarify') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 14 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', maxWidth: '72%' }}>
          <div style={{
            width: 28, height: 28, borderRadius: '50%', background: '#f3f4f6',
            border: '1px solid #e5e7eb', display: 'flex', alignItems: 'center',
            justifyContent: 'center', fontSize: 14, flexShrink: 0, marginTop: 2,
          }}>
            ?
          </div>
          <div
            style={{
              background: '#f9fafb',
              border: '1px solid #e5e7eb',
              borderRadius: '4px 16px 16px 16px',
              padding: '10px 16px',
              fontSize: 14,
              lineHeight: 1.5,
              color: '#1f2937',
            }}
          >
            {msg.content}
          </div>
        </div>
      </div>
    )
  }

  // ---- Error bubble --------------------------------------------------------
  if (msg.type === 'error') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 14 }}>
        <div
          style={{
            background: '#fee2e2',
            border: '1px solid #fca5a5',
            borderRadius: '4px 16px 16px 16px',
            padding: '10px 16px',
            fontSize: 13,
            color: '#991b1b',
            maxWidth: '72%',
          }}
        >
          {msg.content}
          {onRetry && msg.retryQuery && (
            <button
              onClick={() => onRetry(msg)}
              style={{
                display: 'block',
                marginTop: 8,
                background: 'none',
                border: '1px solid #fca5a5',
                borderRadius: 5,
                padding: '3px 10px',
                fontSize: 12,
                color: '#991b1b',
                cursor: 'pointer',
              }}
            >
              ↺ Retry
            </button>
          )}
        </div>
      </div>
    )
  }

  // ---- SQL / Code bubble --------------------------------------------------
  const label =
    msg.queryType === 'dataframe_api' ? 'Generated DataFrame Code'
    : msg.queryType === 'spark_sql'   ? 'Generated Spark SQL'
    : 'Generated SQL'

  const canRun = msg.queryType !== 'dataframe_api'

  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 14 }}>
      <div style={{ maxWidth: '80%', minWidth: 280 }}>
        <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4, marginLeft: 2 }}>
          {label}
        </div>
        <div
          style={{
            background: '#1e1e2e',
            borderRadius: '4px 12px 12px 12px',
            overflow: 'hidden',
          }}
        >
          {/* header bar */}
          <div style={{
            display: 'flex', justifyContent: 'flex-end',
            padding: '6px 10px', borderBottom: '1px solid #2d2d3f',
          }}>
            <button
              onClick={handleCopy}
              style={{
                background: copied ? '#166534' : 'transparent',
                border: '1px solid ' + (copied ? '#166534' : '#4b5563'),
                borderRadius: 4, padding: '2px 10px', fontSize: 11,
                color: copied ? '#d1fae5' : '#9ca3af', cursor: 'pointer',
              }}
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
          <pre
            style={{
              margin: 0,
              padding: '14px 16px',
              color: '#cdd6f4',
              fontSize: 13,
              lineHeight: 1.6,
              overflowX: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {msg.content}
          </pre>
        </div>

        {/* DataFrame API notice */}
        {!canRun && (
          <div style={{
            marginTop: 8, padding: '6px 12px', background: '#fffbeb',
            border: '1px solid #fcd34d', borderRadius: 6, fontSize: 12, color: '#92400e',
          }}>
            DataFrame API requires a live PySpark environment — copy and run in your notebook.
          </div>
        )}

        {/* Run query panel */}
        {canRun && <RunQueryPanel content={msg.content} queryType={msg.queryType} />}
      </div>
    </div>
  )
}
