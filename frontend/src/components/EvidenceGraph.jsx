import React, { useState, useMemo } from 'react';

export default function EvidenceGraph({ graphData }) {
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [filterConflictsOnly, setFilterConflictsOnly] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);

  const { nodes = [], edges = [] } = graphData || {};

  const getNodeName = (node) => {
    return String(node?.name || node?.properties?.name || node?.label || node?.id || 'Node');
  };

  const getNodeModality = (node) => {
    return String(node?.modality || node?.properties?.modality || node?.type || '').toLowerCase();
  };

  // Radial / Force layout for SVG
  const layout = useMemo(() => {
    if (!nodes || nodes.length === 0) return { positionedNodes: [], positionedEdges: [] };

    const width = 800;
    const height = 550;
    const centerX = width / 2;
    const centerY = height / 2;

    const queryNode = nodes.find(n => n.type === 'query');
    const evidenceNodes = nodes.filter(n => n.type === 'evidence' || n.modality);
    const placedIds = new Set();
    const positions = {};

    // 1. Query Node at center
    if (queryNode) {
      positions[queryNode.id] = { x: centerX, y: centerY };
      placedIds.add(queryNode.id);
    }

    // 2. Evidence Nodes in inner circle
    const rEvidence = 160;
    evidenceNodes.forEach((node, idx) => {
      const angle = (idx / Math.max(1, evidenceNodes.length)) * 2 * Math.PI - Math.PI / 2;
      positions[node.id] = {
        x: centerX + rEvidence * Math.cos(angle),
        y: centerY + rEvidence * Math.sin(angle),
      };
      placedIds.add(node.id);
    });

    // 3. Entity Nodes in outer circle
    const otherNodes = nodes.filter(n => !placedIds.has(n.id));
    const rEntity = 230;
    otherNodes.forEach((node, idx) => {
      const angle = (idx / Math.max(1, otherNodes.length)) * 2 * Math.PI - Math.PI / 4;
      positions[node.id] = {
        x: centerX + rEntity * Math.cos(angle),
        y: centerY + rEntity * Math.sin(angle),
      };
    });

    const positionedNodes = nodes.map(n => ({
      ...n,
      ...(positions[n.id] || { x: centerX, y: centerY }),
    }));

    const filteredEdges = filterConflictsOnly
      ? edges.filter(e => e.relationship === 'CONTRADICTS')
      : edges;

    return { positionedNodes, positionedEdges: filteredEdges };
  }, [nodes, edges, filterConflictsOnly]);

  const getNodeColor = (node) => {
    if (node?.type === 'query') return { bg: '#1B4332', border: '#143225', text: '#ffffff' }; // Deep forest
    const mod = getNodeModality(node);
    switch (mod) {
      case 'document':
        return { bg: '#2D6A4F', border: '#1B4332', text: '#ffffff' }; // Sage/Forest
      case 'image':
        return { bg: '#D97706', border: '#B45309', text: '#ffffff' }; // Amber
      case 'video':
        return { bg: '#E11D48', border: '#BE123C', text: '#ffffff' }; // Rose
      case 'audio':
        return { bg: '#7C3AED', border: '#6D28D9', text: '#ffffff' }; // Violet
      default:
        return { bg: '#0284C7', border: '#0369A1', text: '#ffffff' }; // Sky
    }
  };

  const getEdgeStyle = (edge) => {
    switch (edge.relationship) {
      case 'CONTRADICTS':
        return { stroke: '#E11D48', strokeWidth: 2.5, strokeDasharray: '6,4', labelColor: 'text-rose-700 bg-rose-50 border-rose-200' };
      case 'SUPPORTS':
        return { stroke: '#2D6A4F', strokeWidth: 2, strokeDasharray: 'none', labelColor: 'text-[#1B4332] bg-[#EAF2ED] border-[#C3D9CB]' };
      case 'MENTIONS':
        return { stroke: '#A8A29E', strokeWidth: 1.5, strokeDasharray: 'none', labelColor: 'text-stone-600 bg-stone-100 border-stone-200' };
      default:
        return { stroke: '#D6D3D1', strokeWidth: 1.5, strokeDasharray: 'none', labelColor: 'text-stone-600 bg-stone-100 border-stone-200' };
    }
  };

  const nodeMap = useMemo(() => {
    const map = {};
    layout.positionedNodes.forEach(n => {
      map[n.id] = n;
    });
    return map;
  }, [layout.positionedNodes]);

  return (
    <div className="space-y-6">
      {/* Top Controls Header */}
      <div className="bg-white rounded-2xl p-5 border border-[#E5E1D8] shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-[#1C1917] tracking-tight flex items-center gap-2">
            <span>🕸️</span> Evidence Graph Explorer
          </h2>
          <p className="text-xs text-[#57534E] mt-0.5">
            Stage 6 temporary in-memory subgraph mapping cross-modal connections, support links, and semantic entities.
          </p>
        </div>

        {/* Toolbar Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setFilterConflictsOnly(!filterConflictsOnly)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all flex items-center gap-1.5 ${
              filterConflictsOnly
                ? 'bg-rose-50 text-rose-700 border-rose-300 shadow-2xs'
                : 'bg-white text-stone-700 border-[#E5E1D8] hover:bg-[#FAF9F6]'
            }`}
          >
            <span>⚠️</span> {filterConflictsOnly ? 'Showing Conflicts Only' : 'Filter Conflicts'}
          </button>

          <div className="flex items-center bg-[#F5F3EF] rounded-xl p-1 border border-[#E5E1D8]">
            <button
              onClick={() => setZoomLevel(prev => Math.min(prev + 0.15, 1.8))}
              className="px-2 py-1 text-xs font-bold text-stone-700 hover:bg-white rounded-lg transition-colors"
              title="Zoom In"
            >
              +
            </button>
            <span className="text-[11px] font-mono px-2 text-stone-500">
              {Math.round(zoomLevel * 100)}%
            </span>
            <button
              onClick={() => setZoomLevel(prev => Math.max(prev - 0.15, 0.6))}
              className="px-2 py-1 text-xs font-bold text-stone-700 hover:bg-white rounded-lg transition-colors"
              title="Zoom Out"
            >
              -
            </button>
            <button
              onClick={() => { setZoomLevel(1); setSelectedNode(null); setSelectedEdge(null); }}
              className="px-2 py-1 text-xs font-medium text-stone-500 hover:text-stone-800 hover:bg-white rounded-lg transition-colors ml-1"
              title="Reset View"
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      {/* Main Canvas & Inspector Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* SVG Graph Viewport */}
        <div className="lg:col-span-3 bg-white border border-[#E5E1D8] rounded-2xl shadow-2xs overflow-hidden relative flex flex-col items-center justify-center min-h-[550px]">
          {/* Subtle Grid Background Pattern */}
          <div
            className="absolute inset-0 opacity-40 pointer-events-none"
            style={{
              backgroundImage: 'radial-gradient(#D6D3D1 1px, transparent 1px)',
              backgroundSize: '20px 20px',
            }}
          />

          {layout.positionedNodes.length === 0 ? (
            <div className="text-center p-12 space-y-3 z-10">
              <div className="text-4xl text-stone-300">🕸️</div>
              <h3 className="text-sm font-semibold text-[#1C1917]">No active evidence graph</h3>
              <p className="text-xs text-[#57534E] max-w-sm mx-auto">
                Ask a question in Studio or click "Load Sample Benchmark Data" to generate an interactive query-centric evidence subgraph.
              </p>
            </div>
          ) : (
            <div className="w-full h-full overflow-auto flex items-center justify-center p-4">
              <svg
                width={800 * zoomLevel}
                height={550 * zoomLevel}
                viewBox="0 0 800 550"
                className="transition-transform duration-100 ease-out select-none"
              >
                <defs>
                  <marker
                    id="arrowhead-default"
                    markerWidth="8"
                    markerHeight="8"
                    refX="14"
                    refY="4"
                    orient="auto"
                  >
                    <polygon points="0 0, 8 4, 0 8" fill="#A8A29E" />
                  </marker>
                  <marker
                    id="arrowhead-conflict"
                    markerWidth="8"
                    markerHeight="8"
                    refX="14"
                    refY="4"
                    orient="auto"
                  >
                    <polygon points="0 0, 8 4, 0 8" fill="#E11D48" />
                  </marker>
                  <marker
                    id="arrowhead-support"
                    markerWidth="8"
                    markerHeight="8"
                    refX="14"
                    refY="4"
                    orient="auto"
                  >
                    <polygon points="0 0, 8 4, 0 8" fill="#2D6A4F" />
                  </marker>
                </defs>

                {/* Edges */}
                {layout.positionedEdges.map((edge, idx) => {
                  const s = nodeMap[edge.source];
                  const t = nodeMap[edge.target];
                  if (!s || !t) return null;

                  const style = getEdgeStyle(edge);
                  const midX = (s.x + t.x) / 2;
                  const midY = (s.y + t.y) / 2;

                  const markerId = edge.relationship === 'CONTRADICTS'
                    ? 'url(#arrowhead-conflict)'
                    : edge.relationship === 'SUPPORTS'
                    ? 'url(#arrowhead-support)'
                    : 'url(#arrowhead-default)';

                  const isSelected = selectedEdge === edge;

                  return (
                    <g key={`edge-${idx}`} className="cursor-pointer" onClick={() => setSelectedEdge(edge)}>
                      <line
                        x1={s.x}
                        y1={s.y}
                        x2={t.x}
                        y2={t.y}
                        stroke={style.stroke}
                        strokeWidth={isSelected ? style.strokeWidth + 2 : style.strokeWidth}
                        strokeDasharray={style.strokeDasharray}
                        markerEnd={markerId}
                        opacity={isSelected ? 1 : 0.75}
                      />
                      {/* Edge Label Badge */}
                      <rect
                        x={midX - 32}
                        y={midY - 10}
                        width="64"
                        height="20"
                        rx="6"
                        fill="#ffffff"
                        stroke={style.stroke}
                        strokeWidth="1"
                      />
                      <text
                        x={midX}
                        y={midY + 3.5}
                        fontSize="9"
                        fontWeight="700"
                        fontFamily="monospace"
                        textAnchor="middle"
                        fill={edge.relationship === 'CONTRADICTS' ? '#dc2626' : '#475569'}
                      >
                        {edge.relationship || 'RELATES'}
                      </text>
                    </g>
                  );
                })}

                {/* Nodes */}
                {layout.positionedNodes.map((node) => {
                  const colors = getNodeColor(node);
                  const isSelected = selectedNode?.id === node.id;
                  const nodeName = getNodeName(node);
                  const isQuery = node.type === 'query';
                  const radius = isQuery ? 26 : 20;

                  return (
                    <g
                      key={`node-${node.id}`}
                      className="cursor-pointer transition-transform hover:scale-110"
                      onClick={() => setSelectedNode(node)}
                    >
                      {/* Selection Ring */}
                      {isSelected && (
                        <circle
                          cx={node.x}
                          cy={node.y}
                          r={radius + 6}
                          fill="none"
                          stroke="#1B4332"
                          strokeWidth="2.5"
                          strokeDasharray="4,3"
                        />
                      )}

                      {/* Main Node Circle */}
                      <circle
                        cx={node.x}
                        cy={node.y}
                        r={radius}
                        fill={colors.bg}
                        stroke={colors.border}
                        strokeWidth="2"
                        className="shadow-md"
                      />

                      {/* Icon or Monogram */}
                      <text
                        x={node.x}
                        y={node.y + 4}
                        fontSize={isQuery ? '14' : '11'}
                        fontWeight="bold"
                        fill={colors.text}
                        textAnchor="middle"
                      >
                        {isQuery ? '❓' : node.modality === 'image' ? '🖼️' : node.modality === 'video' ? '🎬' : node.modality === 'audio' ? '🎙️' : '📄'}
                      </text>

                      {/* Text Label Below Node */}
                      <rect
                        x={node.x - Math.min(80, nodeName.length * 4)}
                        y={node.y + radius + 4}
                        width={Math.min(160, nodeName.length * 8)}
                        height="18"
                        rx="4"
                        fill="#ffffff"
                        stroke="#E5E1D8"
                        strokeWidth="1"
                        opacity="0.95"
                      />
                      <text
                        x={node.x}
                        y={node.y + radius + 16}
                        fontSize="10"
                        fontWeight="600"
                        fontFamily="sans-serif"
                        textAnchor="middle"
                        fill="#1C1917"
                      >
                        {nodeName.length > 18 ? nodeName.substring(0, 16) + '...' : nodeName}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}

          {/* Graph Legend Floating at Bottom */}
          <div className="absolute bottom-3 left-3 bg-white/95 backdrop-blur-md px-3.5 py-2 rounded-xl border border-[#E5E1D8] shadow-2xs flex items-center gap-3 text-[11px] font-medium text-[#57534E]">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#1B4332] inline-block" />
              <span>Query</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#2D6A4F] inline-block" />
              <span>Document</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#D97706] inline-block" />
              <span>Image</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#E11D48] inline-block" />
              <span>Video</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#7C3AED] inline-block" />
              <span>Audio</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#0284C7] inline-block" />
              <span>Entity</span>
            </div>
          </div>
        </div>

        {/* Node / Edge Inspector Drawer */}
        <div className="bg-white rounded-2xl p-5 border border-[#E5E1D8] shadow-2xs h-fit space-y-4">
          <h3 className="font-bold text-[#1C1917] text-sm border-b border-[#F0ECE1] pb-3 flex items-center justify-between">
            <span>Graph Inspector</span>
            {selectedNode && (
              <span className="text-[11px] font-mono text-[#1B4332] bg-[#EAF2ED] px-2 py-0.5 rounded border border-[#C3D9CB]">
                Selected
              </span>
            )}
          </h3>

          {selectedNode ? (
            <div className="space-y-4 text-xs">
              <div>
                <span className="text-stone-400 block mb-1">Node Identifier</span>
                <span className="font-bold text-[#1C1917] break-all text-sm">
                  {getNodeName(selectedNode)}
                </span>
                <span className="text-[11px] text-stone-400 font-mono block mt-0.5">
                  ID: {selectedNode.id}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded-xl bg-[#FAF9F6] border border-[#E5E1D8]">
                  <span className="text-stone-400 block mb-0.5">Type / Role</span>
                  <span className="font-semibold text-[#1C1917] capitalize">
                    {selectedNode.type || 'Entity'}
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-[#FAF9F6] border border-[#E5E1D8]">
                  <span className="text-stone-400 block mb-0.5">Modality</span>
                  <span className="font-semibold text-[#1C1917] capitalize">
                    {getNodeModality(selectedNode) || 'Concept'}
                  </span>
                </div>
              </div>

              {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
                <div>
                  <span className="text-stone-400 block mb-1">Properties</span>
                  <div className="bg-[#FAF9F6] border border-[#E5E1D8] rounded-xl p-3 text-[11px] font-mono text-[#1C1917] leading-relaxed max-h-48 overflow-y-auto">
                    {JSON.stringify(selectedNode.properties, null, 2)}
                  </div>
                </div>
              )}

              {selectedNode.content && (
                <div>
                  <span className="text-stone-400 block mb-1">Associated Content</span>
                  <p className="bg-[#FAF9F6] border border-[#E5E1D8] rounded-xl p-3 text-[#1C1917] leading-relaxed max-h-48 overflow-y-auto font-mono text-[11px]">
                    {selectedNode.content}
                  </p>
                </div>
              )}

              <button
                onClick={() => setSelectedNode(null)}
                className="w-full py-2 text-xs font-semibold text-stone-700 bg-stone-100 hover:bg-stone-200 rounded-xl transition-colors"
              >
                Clear Selection
              </button>
            </div>
          ) : selectedEdge ? (
            <div className="space-y-3 text-xs">
              <div>
                <span className="text-stone-400 block mb-1">Relationship</span>
                <span className="font-bold text-[#1C1917] text-sm font-mono">
                  {selectedEdge.relationship}
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-[#FAF9F6] border border-[#E5E1D8]">
                <span className="text-stone-400 block mb-0.5">Source Node</span>
                <span className="font-mono text-[#1C1917]">{selectedEdge.source}</span>
              </div>
              <div className="p-2.5 rounded-xl bg-[#FAF9F6] border border-[#E5E1D8]">
                <span className="text-stone-400 block mb-0.5">Target Node</span>
                <span className="font-mono text-[#1C1917]">{selectedEdge.target}</span>
              </div>
              <button
                onClick={() => setSelectedEdge(null)}
                className="w-full py-2 text-xs font-semibold text-stone-700 bg-stone-100 hover:bg-stone-200 rounded-xl transition-colors"
              >
                Clear Selection
              </button>
            </div>
          ) : (
            <div className="py-12 text-center text-stone-400 text-xs">
              Click on any node or edge in the graph canvas to inspect its semantic properties, modalities, and connections.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
