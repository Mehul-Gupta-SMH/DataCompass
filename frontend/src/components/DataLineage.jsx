import { useState, useCallback, useEffect } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'

// ---------------------------------------------------------------------------
// Custom node
// ---------------------------------------------------------------------------
function LineageNode({ data }) {
  const bg =
    data.role === 'center'
      ? '#2563eb'
      : '#374151'
  return (
    <div
      style={{
        background: bg,
        color: '#fff',
        padding: '10px 20px',
        borderRadius: 8,
        fontWeight: 600,
        fontSize: 13,
        fontFamily: 'sans-serif',
        minWidth: 120,
        textAlign: 'center',
        boxShadow: data.role === 'center' ? '0 0 0 3px #bfdbfe' : 'none',
        border: data.role === 'center' ? '2px solid #93c5fd' : '1px solid #6b7280',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      {data.label}
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  )
}

const nodeTypes = { lineageNode: LineageNode }
const NODE_W = 160
const NODE_H = 44

function buildFlow(lineageData) {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', nodesep: 60, ranksep: 180 })

  const rfNodes = lineageData.nodes.map((n) => ({
    id: n.id,
    type: 'lineageNode',
    position: { x: 0, y: 0 },
    data: { label: n.id, role: n.role },
  }))

  rfNodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }))

  const rfEdges = lineageData.edges.map((e, i) => {
    const label = e.joinKeys
      ? e.joinKeys.length > 40 ? e.joinKeys.slice(0, 37) + '…' : e.joinKeys
      : ''
    return {
      id: `e-${i}`,
      source: e.source,
      target: e.target,
      label,
      labelStyle: { fontSize: 10, fill: '#444' },
      labelBgStyle: { fill: '#fff', fillOpacity: 0.9 },
      labelBgPadding: [4, 6],
      labelBgBorderRadius: 4,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 14,
        height: 14,
        color: '#94a3b8',
      },
      style: { stroke: '#94a3b8', strokeWidth: 1.5 },
    }
  })

  rfEdges.forEach((e) => g.setEdge(e.source, e.target))
  dagre.layout(g)

  const layoutedNodes = rfNodes.map((n) => {
    const pos = g.node(n.id)
    return { ...n, position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 } }
  })

  return { nodes: layoutedNodes, edges: rfEdges }
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------
function Legend() {
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 16,
        left: 16,
        background: 'rgba(255,255,255,0.92)',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        padding: '8px 14px',
        fontSize: 12,
        zIndex: 10,
        display: 'flex',
        gap: 16,
        alignItems: 'center',
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ background: '#2563eb', borderRadius: 4, width: 14, height: 14, display: 'inline-block' }} />
        Selected table
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ background: '#374151', borderRadius: 4, width: 14, height: 14, display: 'inline-block' }} />
        Related table
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function DataLineage({ tables }) {
  const [selected, setSelected] = useState('')
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [noRelations, setNoRelations] = useState(false)

  async function loadLineage(tableName) {
    if (!tableName) return
    setLoading(true)
    setError('')
    setNoRelations(false)
    setNodes([])
    setEdges([])
    try {
      const res = await fetch(`/api/lineage/${encodeURIComponent(tableName)}`)
      const data = await res.json()
      if (!res.ok) { setError(data.detail ?? 'Failed to load lineage.'); return }
      if (data.nodes.length <= 1) { setNoRelations(true); return }
      const { nodes: n, edges: e } = buildFlow(data)
      setNodes(n)
      setEdges(e)
    } catch {
      setError('Network error — is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  function handleSelect(e) {
    const val = e.target.value
    setSelected(val)
    loadLineage(val)
  }

  return (
    <div>
      {/* Table selector */}
      <div
        style={{
          background: '#fff',
          border: '1px solid #ddd',
          borderRadius: 8,
          padding: '1rem 1.25rem',
          marginBottom: '1.25rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <label style={{ fontWeight: 600, fontSize: 14 }}>Select a table</label>
        <select
          style={{
            padding: '0.45rem 0.7rem',
            fontSize: '0.9rem',
            border: '1px solid #ccc',
            borderRadius: 6,
            background: '#fff',
            minWidth: 200,
          }}
          value={selected}
          onChange={handleSelect}
          disabled={loading}
        >
          <option value="">— choose table —</option>
          {tables.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        {loading && <span style={{ fontSize: 13, color: '#555' }}>Loading lineage…</span>}
      </div>

      {/* Error */}
      {error && (
        <div
          style={{
            padding: '0.75rem 1rem',
            background: '#fee2e2',
            border: '1px solid #fca5a5',
            borderRadius: 6,
            color: '#991b1b',
            marginBottom: '1rem',
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {/* No relations notice */}
      {noRelations && (
        <div
          style={{
            padding: '0.75rem 1rem',
            background: '#fffbeb',
            border: '1px solid #fcd34d',
            borderRadius: 6,
            color: '#92400e',
            fontSize: 13,
          }}
        >
          No relationships found for <strong>{selected}</strong>. Add relationships when ingesting tables.
        </div>
      )}

      {/* React Flow lineage graph */}
      {nodes.length > 0 && (
        <div
          style={{
            height: 'calc(100vh - 260px)',
            border: '1px solid #e5e7eb',
            borderRadius: 8,
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.3 }}
          >
            <Background />
            <Controls />
            <MiniMap />
            <Legend />
          </ReactFlow>
        </div>
      )}

      {/* Empty state */}
      {!selected && !loading && (
        <div style={{ textAlign: 'center', padding: 60, color: '#9ca3af', fontSize: 14 }}>
          Select a table above to view its lineage graph.
        </div>
      )}
    </div>
  )
}
