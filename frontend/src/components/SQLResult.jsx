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
  },
  copied: {
    padding: '0.35rem 0.85rem',
    fontSize: '0.85rem',
    background: '#d1fae5',
    border: '1px solid #6ee7b7',
    borderRadius: '5px',
    color: '#065f46',
  },
}

export default function SQLResult({ sql }) {
  const [copied, setCopied] = useState(false)

  if (!sql) return null

  function handleCopy() {
    navigator.clipboard.writeText(sql).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={{ margin: 0 }}>Generated SQL</h2>
        <button
          style={copied ? styles.copied : styles.copyBtn}
          onClick={handleCopy}
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre style={styles.pre}>{sql}</pre>
    </div>
  )
}
