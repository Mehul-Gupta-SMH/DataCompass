import React, { useState } from 'react'

const styles = {
  container: {
    background: '#fff',
    border: '1px solid #ddd',
    borderRadius: '8px',
    padding: '1.25rem',
    marginBottom: '1.25rem',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '0.75rem',
  },
  pre: {
    background: '#1e1e2e',
    color: '#cdd6f4',
    padding: '1rem',
    borderRadius: '6px',
    overflowX: 'auto',
    fontSize: '0.88rem',
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  copyBtn: {
    padding: '0.35rem 0.85rem',
    fontSize: '0.85rem',
    background: '#e5e7eb',
    border: '1px solid #ccc',
    borderRadius: '5px',
    cursor: 'pointer',
  },
  copied: {
    padding: '0.35rem 0.85rem',
    fontSize: '0.85rem',
    background: '#d1fae5',
    border: '1px solid #6ee7b7',
    borderRadius: '5px',
    color: '#065f46',
  },
  execSection: {
    marginTop: '1rem',
  },
  connRow: {
    display: 'flex',
    gap: '0.5rem',
    alignItems: 'center',
    marginBottom: '0.5rem',
    flexWrap: 'wrap',
  },
  connInput: {
    flex: 1,
    minWidth: '240px',
    padding: '0.45rem 0.7rem',
    fontSize: '0.88rem',
    border: '1px solid #ccc',
    borderRadius: '6px',
    fontFamily: 'monospace',
  },
  runBtn: {
    padding: '0.45rem 1rem',
    fontSize: '0.88rem',
    background: '#16a34a',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontWeight: 600,
    cursor: 'pointer',
    flex: '0 0 auto',
  },
  execError: {
    color: '#b91c1c',
    fontSize: '0.85rem',
    marginTop: '0.4rem',
  },
  notice: {
    marginTop: '1rem',
    padding: '0.75rem 1rem',
    background: '#fffbeb',
    border: '1px solid #fcd34d',
    borderRadius: '6px',
    color: '#92400e',
    fontSize: '0.88rem',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '0.85rem',
    marginTop: '0.75rem',
  },
  th: {
    background: '#f3f4f6',
    border: '1px solid #e5e7eb',
    padding: '0.4rem 0.6rem',
    textAlign: 'left',
    fontWeight: 600,
  },
  td: {
    border: '1px solid #e5e7eb',
    padding: '0.4rem 0.6rem',
  },
  tdAlt: {
    border: '1px solid #e5e7eb',
    padding: '0.4rem 0.6rem',
    background: '#f9fafb',
  },
  nullVal: {
    fontStyle: 'italic',
    color: '#9ca3af',
  },
  emptyMsg: {
    color: '#6b7280',
    fontSize: '0.88rem',
    marginTop: '0.5rem',
  },
}

function ResultsTable({ columns, rows }) {
  if (!columns || columns.length === 0) {
    return <div style={styles.emptyMsg}>Query returned no results.</div>
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={styles.table}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col} style={styles.th}>
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} style={{ ...styles.td, textAlign: 'center', color: '#9ca3af' }}>
                No rows returned.
              </td>
            </tr>
          ) : (
            rows.map((row, i) =>
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j} style={i % 2 === 0 ? styles.td : styles.tdAlt}>
                    {cell === null ? <em style={styles.nullVal}>NULL</em> : String(cell)}
                  </td>
                ))}
              </tr>
            )
          )}
        </tbody>
      </table>
    </div>
  )
}

export default function SQLResult({
  sql,
  queryType,
  connString,
  setConnString,
  onExecute,
  execLoading,
  execResult,
  execError,
}) {
  const [copied, setCopied] = useState(false)

  if (!sql) return null

  const heading =
    queryType === 'dataframe_api'
      ? 'Generated DataFrame Code'
      : queryType === 'spark_sql'
      ? 'Generated Spark SQL'
      : 'Generated SQL'

  function handleCopy() {
    navigator.clipboard.writeText(sql).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={{ margin: 0 }}>{heading}</h2>
        <button style={copied ? styles.copied : styles.copyBtn} onClick={handleCopy}>
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre style={styles.pre}>{sql}</pre>

      {queryType !== 'dataframe_api' ? (
        <div style={styles.execSection}>
          <div style={styles.connRow}>
            <input
              style={styles.connInput}
              type="text"
              placeholder="Connection string (e.g. sqlite:///path/to/db.sqlite)"
              value={connString}
              onChange={(e) => setConnString(e.target.value)}
              disabled={execLoading}
            />
            <button
              style={styles.runBtn}
              onClick={onExecute}
              disabled={execLoading || !connString.trim()}
            >
              {execLoading ? 'Running…' : 'Run Query'}
            </button>
          </div>
          {execError && <div style={styles.execError}>{execError}</div>}
          {execResult && (
            <ResultsTable columns={execResult.columns} rows={execResult.rows} />
          )}
        </div>
      ) : (
        <div style={styles.notice}>
          DataFrame API requires a PySpark environment — copy and run in your notebook/shell.
        </div>
      )}
    </div>
  )
}
