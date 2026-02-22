import { useEffect, useState } from 'react'
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

export default function SchemaERD() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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
    <div style={{ height: 'calc(100vh - 100px)' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  )
}
