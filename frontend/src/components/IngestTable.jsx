import React, { useState } from 'react'

const s = {
  card: {
    background: '#fff',
    border: '1px solid #ddd',
    borderRadius: 8,
    padding: '1.25rem',
    marginBottom: '1.25rem',
  },
  label: { fontWeight: 600, fontSize: 13, marginBottom: 4, display: 'block' },
  textarea: {
    width: '100%',
    minHeight: 200,
    padding: '0.6rem 0.75rem',
    fontSize: '0.85rem',
    border: '1px solid #ccc',
    borderRadius: 6,
    resize: 'vertical',
    fontFamily: 'monospace',
    marginBottom: '0.75rem',
    boxSizing: 'border-box',
  },
  input: {
    padding: '0.45rem 0.7rem',
    fontSize: '0.88rem',
    border: '1px solid #ccc',
    borderRadius: 6,
    fontFamily: 'inherit',
    width: '100%',
    boxSizing: 'border-box',
  },
  select: {
    padding: '0.5rem 0.75rem',
    fontSize: '0.9rem',
    border: '1px solid #ccc',
    borderRadius: 6,
    background: '#fff',
  },
  row: { display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap' },
  btn: (color = '#2563eb') => ({
    padding: '0.5rem 1.25rem',
    fontSize: '0.9rem',
    background: color,
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    fontWeight: 600,
    cursor: 'pointer',
    flex: '0 0 auto',
  }),
  btnSm: (color = '#6b7280') => ({
    padding: '0.3rem 0.8rem',
    fontSize: '0.8rem',
    background: color,
    color: '#fff',
    border: 'none',
    borderRadius: 5,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  }),
  error: { color: '#b91c1c', fontSize: '0.85rem', marginTop: '0.5rem' },
  success: {
    color: '#065f46',
    background: '#d1fae5',
    border: '1px solid #6ee7b7',
    borderRadius: 6,
    padding: '0.75rem 1rem',
    fontSize: '0.9rem',
    marginTop: '0.75rem',
  },
  sectionTitle: { margin: '1.1rem 0 0.4rem', fontSize: 14, fontWeight: 700, color: '#1e1e2e' },
  chip: (color = '#e5e7eb', text = '#374151') => ({
    display: 'inline-block',
    background: color,
    color: text,
    borderRadius: 12,
    padding: '2px 10px',
    fontSize: 12,
    fontWeight: 600,
    marginRight: 4,
    marginBottom: 4,
  }),
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12.5, marginTop: 6 },
  th: {
    background: '#f3f4f6',
    border: '1px solid #e5e7eb',
    padding: '5px 8px',
    textAlign: 'left',
    fontWeight: 600,
    color: '#374151',
    whiteSpace: 'nowrap',
  },
  td: { border: '1px solid #e5e7eb', padding: '4px 6px', verticalAlign: 'top' },
  codeCell: {
    border: '1px solid #e5e7eb',
    padding: '4px 6px',
    verticalAlign: 'top',
    fontFamily: 'monospace',
    fontSize: 11,
    color: '#4b5563',
    maxWidth: 260,
    wordBreak: 'break-word',
  },
  descInput: {
    width: '100%',
    padding: '4px 6px',
    fontSize: 12,
    border: '1px solid #d1d5db',
    borderRadius: 4,
    fontFamily: 'inherit',
    boxSizing: 'border-box',
    minWidth: 180,
  },
  relGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1.5fr auto',
    gap: '0.4rem',
    alignItems: 'center',
    marginBottom: '0.35rem',
  },
  notice: {
    padding: '0.6rem 1rem',
    background: '#eff6ff',
    border: '1px solid #bfdbfe',
    borderRadius: 6,
    fontSize: 13,
    color: '#1e40af',
    marginBottom: '0.75rem',
  },
  infoBox: {
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
    borderRadius: 6,
    padding: '0.6rem 0.9rem',
    marginBottom: '0.75rem',
    fontSize: 13,
  },
}

const PLACEHOLDER = `-- Example: INSERT ... SELECT pipeline
INSERT INTO customer_monthly_summary (customer_id, customer_name, order_month, total_orders, revenue)
SELECT
    c.customer_id,
    c.customer_name,
    DATE_TRUNC('month', o.order_date) AS order_month,
    COUNT(o.order_id)                 AS total_orders,
    SUM(o.total_amount)               AS revenue
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name, DATE_TRUNC('month', o.order_date);

-- Or: CREATE TABLE AS SELECT (CTAS)
-- CREATE TABLE sales_summary AS
-- SELECT region, SUM(amount) AS total_sales FROM sales GROUP BY region;`

export default function IngestTable({ providers }) {
  const [sql, setSql] = useState('')
  const [provider, setProvider] = useState(providers[0] ?? '')
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Preview state
  const [tableName, setTableName] = useState('')
  const [tableDesc, setTableDesc] = useState('')
  const [columns, setColumns] = useState([])
  const [sourceTables, setSourceTables] = useState([])
  const [relationships, setRelationships] = useState([])

  async function handleAnalyze() {
    if (!sql.trim()) { setError('Please paste a pipeline SQL statement.'); return }
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/api/ingest/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql, provider }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail ?? 'Analysis failed.'); return }
      setTableName(data.table_name)
      setTableDesc(data.table_desc)
      setColumns(data.columns)
      setSourceTables(data.source_tables ?? [])
      setRelationships(data.relationships ?? [])
      setStep(2)
    } catch {
      setError('Network error — is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  async function handleCommit() {
    if (!tableDesc.trim()) { setError('Table description cannot be empty.'); return }
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/api/ingest/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ table_name: tableName, table_desc: tableDesc, columns, relationships }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail ?? 'Commit failed.'); return }
      setSuccess(`"${tableName}" added to schema — data dictionary and lineage stored.`)
      setStep(1)
      setSql('')
    } catch {
      setError('Network error — is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  function updateColDesc(idx, value) {
    setColumns((prev) => prev.map((c, i) => i === idx ? { ...c, desc: value } : c))
  }

  function addRelationship() {
    setRelationships((prev) => [...prev, { source: '', target: tableName, join_keys: '' }])
  }

  function updateRel(idx, field, value) {
    setRelationships((prev) => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r))
  }

  function removeRel(idx) {
    setRelationships((prev) => prev.filter((_, i) => i !== idx))
  }

  // ---- Step 1: SQL input --------------------------------------------------
  if (step === 1) {
    return (
      <div style={s.card}>
        <h2 style={{ marginTop: 0 }}>Ingest Pipeline Table</h2>
        <div style={s.notice}>
          Paste a data pipeline SQL query (<code>INSERT INTO … SELECT</code> or{' '}
          <code>CREATE TABLE … AS SELECT</code>). The system will detect source tables,
          look up their column metadata, and generate a data dictionary for the output table.
        </div>
        <label style={s.label}>Pipeline SQL</label>
        <textarea
          style={s.textarea}
          placeholder={PLACEHOLDER}
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          disabled={loading}
        />
        <div style={s.row}>
          <select
            style={s.select}
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            disabled={loading}
          >
            {providers.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <button style={s.btn()} onClick={handleAnalyze} disabled={loading}>
            {loading ? 'Analyzing…' : 'Analyze Pipeline'}
          </button>
        </div>
        {error && <div style={s.error}>{error}</div>}
        {success && <div style={s.success}>{success}</div>}
      </div>
    )
  }

  // ---- Step 2: Preview + edit + commit ------------------------------------
  return (
    <div style={s.card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.9rem' }}>
        <h2 style={{ margin: 0 }}>Review Data Dictionary</h2>
        <button style={s.btnSm('#6b7280')} onClick={() => { setStep(1); setError('') }}>
          ← Back
        </button>
      </div>

      {/* Detected info */}
      <div style={s.infoBox}>
        <span style={{ fontWeight: 600 }}>Target table: </span>
        <code style={{ background: '#e5e7eb', padding: '1px 6px', borderRadius: 4 }}>{tableName}</code>
        &emsp;
        <span style={{ fontWeight: 600 }}>Source tables: </span>
        {sourceTables.length
          ? sourceTables.map((t) => (
              <span key={t} style={s.chip('#dbeafe', '#1e40af')}>{t}</span>
            ))
          : <span style={{ color: '#9ca3af', fontSize: 12 }}>none detected</span>}
      </div>

      {/* Table name + description */}
      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
        <div>
          <label style={s.label}>Target Table Name</label>
          <input style={s.input} value={tableName} onChange={(e) => setTableName(e.target.value)} />
        </div>
        <div>
          <label style={s.label}>Table Description</label>
          <input
            style={s.input}
            value={tableDesc}
            onChange={(e) => setTableDesc(e.target.value)}
            placeholder="Generated by LLM — edit if needed"
          />
        </div>
      </div>

      {/* Column mapping table */}
      <div style={s.sectionTitle}>Column Mappings &amp; Descriptions</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>Target Column</th>
              <th style={s.th}>Source Expression</th>
              <th style={{ ...s.th, minWidth: 220 }}>Description (editable)</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((col, i) => (
              <tr key={col.name} style={{ background: i % 2 === 0 ? '#fff' : '#f9fafb' }}>
                <td style={{ ...s.td, fontWeight: 600 }}>{col.name}</td>
                <td style={s.codeCell}>{col.source_expr || '—'}</td>
                <td style={s.td}>
                  <input
                    style={s.descInput}
                    value={col.desc}
                    onChange={(e) => updateColDesc(i, e.target.value)}
                    placeholder="Describe this column…"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Relationships */}
      <div style={s.sectionTitle}>Lineage Relationships</div>
      <p style={{ fontSize: 12, color: '#6b7280', margin: '0 0 8px' }}>
        Auto-detected from source tables. Edit join keys or remove as needed.
      </p>
      {relationships.length > 0 && (
        <div style={{ marginBottom: 6 }}>
          <div style={{ ...s.relGrid, fontWeight: 600, fontSize: 12, color: '#374151', marginBottom: 4 }}>
            <span>Source Table</span>
            <span>Target Table</span>
            <span>Join Keys (optional)</span>
            <span />
          </div>
          {relationships.map((rel, i) => (
            <div key={i} style={s.relGrid}>
              <input style={s.input} value={rel.source} placeholder="source_table"
                onChange={(e) => updateRel(i, 'source', e.target.value)} />
              <input style={s.input} value={rel.target} placeholder="target_table"
                onChange={(e) => updateRel(i, 'target', e.target.value)} />
              <input style={s.input} value={rel.join_keys}
                placeholder="e.g. orders.customer_id = customers.id"
                onChange={(e) => updateRel(i, 'join_keys', e.target.value)} />
              <button style={s.btnSm('#dc2626')} onClick={() => removeRel(i)}>✕</button>
            </div>
          ))}
        </div>
      )}
      <button style={s.btnSm('#4b5563')} onClick={addRelationship}>+ Add Relationship</button>

      {/* Commit */}
      <div style={{ marginTop: '1.25rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <button style={s.btn('#16a34a')} onClick={handleCommit} disabled={loading}>
          {loading ? 'Saving…' : 'Add to Schema'}
        </button>
      </div>
      {error && <div style={s.error}>{error}</div>}
    </div>
  )
}
