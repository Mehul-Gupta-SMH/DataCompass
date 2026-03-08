import React from 'react'

const styles = {
  form: {
    background: '#fff',
    border: '1px solid #ddd',
    borderRadius: '8px',
    padding: '1.25rem',
    marginBottom: '1.25rem',
  },
  textarea: {
    width: '100%',
    minHeight: '100px',
    padding: '0.6rem 0.75rem',
    fontSize: '0.95rem',
    border: '1px solid #ccc',
    borderRadius: '6px',
    resize: 'vertical',
    fontFamily: 'inherit',
    marginBottom: '0.75rem',
  },
  row: {
    display: 'flex',
    gap: '0.75rem',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  select: {
    padding: '0.5rem 0.75rem',
    fontSize: '0.9rem',
    border: '1px solid #ccc',
    borderRadius: '6px',
    background: '#fff',
    flex: '0 0 auto',
  },
  submitBtn: {
    padding: '0.5rem 1.25rem',
    fontSize: '0.95rem',
    background: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontWeight: 600,
    flex: '0 0 auto',
  },
  spinner: {
    marginLeft: '0.5rem',
    fontSize: '0.85rem',
    color: '#555',
  },
  error: {
    marginTop: '0.75rem',
    color: '#b91c1c',
    fontSize: '0.9rem',
  },
}

export default function QueryInput({
  query,
  setQuery,
  provider,
  setProvider,
  providers,
  loading,
  error,
  onSubmit,
  queryType,
  setQueryType,
}) {
  function handleSubmit(e) {
    e.preventDefault()
    onSubmit()
  }

  const btnLabel = loading
    ? 'Generating…'
    : queryType === 'dataframe_api'
    ? 'Generate DataFrame Code'
    : queryType === 'spark_sql'
    ? 'Generate Spark SQL'
    : 'Generate SQL'

  return (
    <form style={styles.form} onSubmit={handleSubmit}>
      <textarea
        style={styles.textarea}
        placeholder="Ask a question about your data…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={loading}
      />
      <div style={styles.row}>
        <select
          style={styles.select}
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          disabled={loading}
        >
          {providers.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          style={styles.select}
          value={queryType}
          onChange={(e) => setQueryType(e.target.value)}
          disabled={loading}
        >
          <option value="sql">SQL</option>
          <option value="spark_sql">Spark SQL</option>
          <option value="dataframe_api">DataFrame API</option>
        </select>
        <button style={styles.submitBtn} type="submit" disabled={loading}>
          {btnLabel}
        </button>
        {loading && <span style={styles.spinner}>Please wait…</span>}
      </div>
      {error && <div style={styles.error}>{error}</div>}
    </form>
  )
}
