import { useEffect, useState, useCallback } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import TableNode from './TableNode.jsx'

const NODE_WIDTH = 260
const nodeTypes = { tableNode: TableNode }

function getLayoutedElements(nodes, edges) {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', nodesep: 60, ranksep: 220 })

  nodes.forEach((node) => {
    const colCount = node.data.columns.length
    g.setNode(node.id, { width: NODE_WIDTH, height: 60 + colCount * 28 })
  })

  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target)
  })

  dagre.layout(g)

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id)
    return {
      ...node,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - (60 + node.data.columns.length * 28) / 2 },
    }
  })

  return { nodes: layoutedNodes, edges }
}

function TableDetailPane({ table, onClose }) {
  const hasPK = (c) => /primary\s*key/i.test(c.constraints)
  const hasFK = (c) => /foreign\s*key/i.test(c.constraints)

  return (
    <div
      style={{
        width: 360,
        flexShrink: 0,
        background: '#fff',
        borderLeft: '1px solid #e5e7eb',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 16px',
          background: '#1e1e2e',
          color: '#fff',
          flexShrink: 0,
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 14 }}>{table.label}</span>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#cdd6f4',
            fontSize: 18,
            cursor: 'pointer',
            lineHeight: 1,
            padding: '0 2px',
          }}
          title="Close"
        >
          ×
        </button>
      </div>

      {/* Body */}
      <div style={{ overflowY: 'auto', padding: '12px 16px', flex: 1 }}>
        {table.description && (
          <p style={{ margin: '0 0 12px', color: '#555', fontSize: 13, fontStyle: 'italic' }}>
            {table.description}
          </p>
        )}

        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: 12,
          }}
        >
          <thead>
            <tr>
              {['Column', 'Type', 'Tags', 'Description'].map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: 'left',
                    padding: '5px 6px',
                    background: '#f3f4f6',
                    border: '1px solid #e5e7eb',
                    fontWeight: 600,
                    color: '#374151',
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.columns.map((col, i) => (
              <tr key={col.name} style={{ background: i % 2 === 0 ? '#fff' : '#f9fafb' }}>
                <td style={{ padding: '5px 6px', border: '1px solid #e5e7eb', fontWeight: 500 }}>
                  {col.name}
                </td>
                <td style={{ padding: '5px 6px', border: '1px solid #e5e7eb', color: '#6b7280', fontStyle: 'italic' }}>
                  {col.type || '—'}
                </td>
                <td style={{ padding: '5px 6px', border: '1px solid #e5e7eb' }}>
                  <span style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                    {hasPK(col) && (
                      <span style={{ background: '#fbbf24', color: '#78350f', borderRadius: 3, padding: '0 4px', fontSize: 10, fontWeight: 700 }}>PK</span>
                    )}
                    {hasFK(col) && (
                      <span style={{ background: '#93c5fd', color: '#1e3a5f', borderRadius: 3, padding: '0 4px', fontSize: 10, fontWeight: 700 }}>FK</span>
                    )}
                    {!hasPK(col) && !hasFK(col) && <span style={{ color: '#d1d5db' }}>—</span>}
                  </span>
                </td>
                <td style={{ padding: '5px 6px', border: '1px solid #e5e7eb', color: '#374151' }}>
                  {col.description || <span style={{ color: '#d1d5db' }}>—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function SchemaERD() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedTable, setSelectedTable] = useState(null)

  useEffect(() => {
    fetch('/api/schema')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data) => {
        if (!data.tables.length) {
          setLoading(false)
          return
        }

        const rfNodes = data.tables.map((t) => ({
          id: t.name,
          type: 'tableNode',
          position: { x: 0, y: 0 },
          width: NODE_WIDTH,
          data: {
            label: t.name,
            description: t.description,
            columns: t.columns,
          },
        }))

        const rfEdges = data.relations.map((r, i) => {
          const firstKey = r.joinKeys[0] || ''
          const label = firstKey.length > 38 ? firstKey.slice(0, 35) + '…' : firstKey
          return {
            id: `e-${i}`,
            source: r.source,
            target: r.target,
            type: 'default',
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

        const { nodes: ln, edges: le } = getLayoutedElements(rfNodes, rfEdges)
        setNodes(ln)
        setEdges(le)
        setLoading(false)
      })
      .catch((err) => {
        setError(`Failed to load schema: ${err.message}`)
        setLoading(false)
      })
  }, [])

  const onNodeClick = useCallback((_, node) => {
    setSelectedTable(node.data)
    // Highlight selected node
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, selected: n.id === node.id },
      }))
    )
  }, [setNodes])

  const handleClose = useCallback(() => {
    setSelectedTable(null)
    setNodes((nds) =>
      nds.map((n) => ({ ...n, data: { ...n.data, selected: false } }))
    )
  }, [setNodes])

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 40, color: '#555' }}>
        Loading schema…
      </div>
    )
  }

  if (error) {
    return (
      <div
        style={{
          margin: 20,
          padding: 16,
          background: '#fee2e2',
          border: '1px solid #fca5a5',
          borderRadius: 6,
          color: '#991b1b',
        }}
      >
        {error}
      </div>
    )
  }

  if (!nodes.length) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 40, color: '#888' }}>
        No schema data available. Import relations and table metadata first.
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 100px)' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          fitView
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>

      {selectedTable && (
        <TableDetailPane table={selectedTable} onClose={handleClose} />
      )}
    </div>
  )
}
