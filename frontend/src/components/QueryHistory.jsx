import React from 'react'

const styles = {
  container: {
    background: '#fff',
    border: '1px solid #ddd',
    borderRadius: '8px',
    padding: '1.25rem',
  },
  list: {
    listStyle: 'none',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  item: {
    border: '1px solid #e5e7eb',
    borderRadius: '6px',
    padding: '0.75rem 1rem',
    cursor: 'pointer',
    background: '#fafafa',
    transition: 'background 0.15s',
  },
  itemHover: {
    background: '#eff6ff',
  },
  queryText: {
    fontWeight: 600,
    marginBottom: '0.25rem',
    fontSize: '0.9rem',
  },
  meta: {
    fontSize: '0.78rem',
    color: '#6b7280',
    marginBottom: '0.4rem',
  },
  sqlPreview: {
    background: '#1e1e2e',
    color: '#cdd6f4',
    borderRadius: '4px',
    padding: '0.4rem 0.6rem',
    fontSize: '0.78rem',
    overflowX: 'auto',
    whiteSpace: 'nowrap',
  },
  empty: {
    color: '#9ca3af',
    fontSize: '0.9rem',
  },
}

export default function QueryHistory({ history, onSelect }) {
  if (!history.length) return null

  return (
    <div style={styles.container}>
      <h2>Session History</h2>
      <ul style={styles.list}>
        {history.map((entry, idx) => (
          <HistoryItem key={idx} entry={entry} onSelect={onSelect} />
        ))}
      </ul>
    </div>
  )
}

function HistoryItem({ entry, onSelect }) {
  const [hovered, setHovered] = React.useState(false)

  return (
    <li
      style={{ ...styles.item, ...(hovered ? styles.itemHover : {}) }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onSelect(entry)}
      title="Click to restore this query"
    >
      <div style={styles.queryText}>{entry.query}</div>
      <div style={styles.meta}>Provider: {entry.provider}</div>
      <pre style={styles.sqlPreview}>{entry.sql}</pre>
    </li>
  )
}
