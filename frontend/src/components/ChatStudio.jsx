import React, { useState } from 'react';
import MarkdownRenderer from './MarkdownRenderer';
import LatencyBar from './LatencyBar';

export default function ChatStudio({ onQuerySubmit, isQuerying, currentResult, onNavigateToGraph }) {
  const [queryText, setQueryText] = useState('');
  const [similarityWeight, setSimilarityWeight] = useState(0.5);
  const [graphWeight, setGraphWeight] = useState(0.5);
  const [topK, setTopK] = useState(4);
  const [enableMMR, setEnableMMR] = useState(true);
  const [mmrLambda, setMmrLambda] = useState(0.7);
  const [showSettings, setShowSettings] = useState(false);
  const [activeChunkModal, setActiveChunkModal] = useState(null);

  const sampleQueries = [
    "Who is the President according to the uploaded schedule image?",
    "Explain the multimodal ingestion and representation process",
    "What is the approved fiscal budget for Project Alpha in 2026?",
    "Summarize the key findings and speaker takeaways"
  ];

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!queryText.trim() || isQuerying) return;

    onQuerySubmit({
      query: queryText.trim(),
      top_k: topK,
      similarity_weight: similarityWeight,
      graph_weight: graphWeight,
      enable_mmr: enableMMR,
      mmr_lambda: mmrLambda,
    });
  };

  const getModalityBadge = (modality) => {
    switch ((modality || '').toLowerCase()) {
      case 'document':
        return { label: 'Doc', icon: '📄', bg: 'bg-[#EAF2ED] text-[#1B4332] border-[#C3D9CB]' };
      case 'image':
        return { label: 'Image', icon: '🖼️', bg: 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]' };
      case 'video':
        return { label: 'Video', icon: '🎬', bg: 'bg-[#FEE2E2] text-[#991B1B] border-[#FECACA]' };
      case 'audio':
        return { label: 'Audio', icon: '🎙️', bg: 'bg-[#EDE9FE] text-[#5B21B6] border-[#DDD6FE]' };
      default:
        return { label: modality || 'Media', icon: '📦', bg: 'bg-stone-100 text-stone-700 border-stone-200' };
    }
  };

  return (
    <div className="space-y-5">
      {/* Query Bar Card */}
      <div className="bg-white border border-[#E5E1D8] rounded-2xl p-5 shadow-2xs space-y-3.5">
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="relative">
            <textarea
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              placeholder="Ask any question across your uploaded documents, images, video, or audio..."
              rows={3}
              className="w-full bg-[#FAF9F6] border border-[#E5E1D8] rounded-xl px-4 py-3 text-xs md:text-sm text-[#1C1917] placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-[#1B4332]/15 focus:border-[#1B4332] focus:bg-white resize-none transition-all"
            />
            <div className="absolute right-3 bottom-3 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowSettings(!showSettings)}
                className="px-2.5 py-1.5 rounded-lg border border-[#E5E1D8] bg-white text-[#57534E] hover:text-[#1C1917] text-xs font-medium transition-colors"
                title="Configure retrieval parameters"
              >
                ⚙️ {showSettings ? 'Hide Options' : 'Tune Weights'}
              </button>
              <button
                type="submit"
                disabled={!queryText.trim() || isQuerying}
                className="px-4 py-1.5 rounded-lg bg-[#1B4332] hover:bg-[#143225] text-white text-xs font-semibold shadow-2xs flex items-center gap-1.5 disabled:opacity-50 transition-colors"
              >
                {isQuerying ? (
                  <>
                    <span className="animate-spin text-sm">⏳</span>
                    <span>Synthesizing...</span>
                  </>
                ) : (
                  <>
                    <span>Ask Nexus ↵</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Quick Query Pill Suggestions */}
          <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
            <span className="text-[11px] font-semibold text-stone-400">Suggested:</span>
            {sampleQueries.map((sample, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setQueryText(sample)}
                className="text-[11px] px-2.5 py-1 rounded-full bg-[#F5F3EF] hover:bg-[#EAF2ED] hover:text-[#1B4332] text-[#57534E] border border-[#E5E1D8] transition-colors truncate max-w-xs"
              >
                {sample}
              </button>
            ))}
          </div>

          {/* Tunable Pipeline Weights Drawer */}
          {showSettings && (
            <div className="p-4 rounded-xl bg-[#FAF9F6] border border-[#E5E1D8] space-y-3 animate-in fade-in duration-150 text-xs">
              <div className="flex items-center justify-between font-semibold text-[#1C1917]">
                <span>Hybrid Vector-Graph Retrieval Weights</span>
                <span className="text-[11px] text-stone-400 font-normal">Stage 1-4 Scoring Parameters</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                {/* Similarity Weight */}
                <div>
                  <div className="flex justify-between text-stone-600 mb-1">
                    <span>Vector Similarity:</span>
                    <span className="font-mono font-bold text-[#1C1917]">{similarityWeight}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={similarityWeight}
                    onChange={(e) => setSimilarityWeight(parseFloat(e.target.value))}
                    className="w-full accent-[#1B4332] cursor-pointer"
                  />
                </div>

                {/* Graph Weight */}
                <div>
                  <div className="flex justify-between text-stone-600 mb-1">
                    <span>Graph Cypher:</span>
                    <span className="font-mono font-bold text-[#1C1917]">{graphWeight}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={graphWeight}
                    onChange={(e) => setGraphWeight(parseFloat(e.target.value))}
                    className="w-full accent-[#1B4332] cursor-pointer"
                  />
                </div>

                {/* Top-K */}
                <div>
                  <div className="flex justify-between text-stone-600 mb-1">
                    <span>Top-K Candidates:</span>
                    <span className="font-mono font-bold text-[#1C1917]">{topK}</span>
                  </div>
                  <input
                    type="range"
                    min="2"
                    max="10"
                    step="1"
                    value={topK}
                    onChange={(e) => setTopK(parseInt(e.target.value))}
                    className="w-full accent-[#1B4332] cursor-pointer"
                  />
                </div>

                {/* MMR Diversity */}
                <div>
                  <div className="flex justify-between text-stone-600 mb-1">
                    <span>MMR Diversity (λ):</span>
                    <span className="font-mono font-bold text-[#1C1917]">{enableMMR ? mmrLambda : 'Off'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={enableMMR}
                      onChange={(e) => setEnableMMR(e.target.checked)}
                      className="rounded accent-[#1B4332] cursor-pointer"
                    />
                    <input
                      type="range"
                      min="0.1"
                      max="0.9"
                      step="0.1"
                      disabled={!enableMMR}
                      value={mmrLambda}
                      onChange={(e) => setMmrLambda(parseFloat(e.target.value))}
                      className="w-full accent-[#1B4332] cursor-pointer disabled:opacity-40"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </form>
      </div>

      {/* Grounded Results & Answer View */}
      {currentResult && (
        <div className="space-y-5 animate-in fade-in duration-200">
          {/* Grounded Answer Card (Notice: Yellow alert box is COMPLETELY REMOVED per user request) */}
          <div className="bg-white border border-[#E5E1D8] rounded-2xl p-6 shadow-2xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#F0ECE1] pb-3">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-[#EAF2ED] text-[#1B4332] border border-[#C3D9CB] flex items-center justify-center font-bold text-xs">
                  Ω
                </div>
                <h3 className="font-bold text-[#1C1917] text-sm">Grounded Multimodal Answer</h3>
              </div>
              <span className="text-[11px] text-stone-400 font-mono">
                {currentResult.evidence_chunks?.length || 0} evidence sources fused
              </span>
            </div>

            {/* Answer Text Rendered with Polished Markdown */}
            <div className="bg-[#FAF9F6] p-4 rounded-xl border border-[#ECE8E1] text-[#1C1917]">
              <MarkdownRenderer content={currentResult.answer} />
            </div>

            {/* Inline Citations Row */}
            {currentResult.citations && currentResult.citations.length > 0 && (
              <div className="pt-2">
                <span className="text-xs font-bold text-[#57534E] block mb-2">
                  Traceable Inline Citations:
                </span>
                <div className="flex items-center gap-2 flex-wrap">
                  {currentResult.citations.map((cite, idx) => {
                    const badge = getModalityBadge(cite.modality);
                    return (
                      <button
                        key={idx}
                        onClick={() => {
                          const matchingChunk = currentResult.evidence_chunks?.find(
                            c => c.source_id === cite.source_id || c.metadata?.file_name === cite.source_id
                          );
                          setActiveChunkModal(matchingChunk || {
                            source_id: cite.source_id,
                            modality: cite.modality,
                            content: `Citation referenced from source ${cite.source_id}.`,
                            metadata: cite
                          });
                        }}
                        className={`text-xs px-2.5 py-1 rounded-lg border font-mono font-medium flex items-center gap-1.5 transition-all hover:scale-102 hover:shadow-2xs ${badge.bg}`}
                        title="Click to view raw evidence excerpt"
                      >
                        <span>{badge.icon}</span>
                        <span>{cite.source_id}</span>
                        {cite.page_num && <span className="font-bold opacity-80">p.{cite.page_num}</span>}
                        {cite.start_time !== undefined && (
                          <span className="font-bold opacity-80">{cite.start_time}s</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Latency Bar */}
            {currentResult.latency_breakdown && (
              <div className="pt-2">
                <LatencyBar latencyData={currentResult.latency_breakdown} />
              </div>
            )}
          </div>

          {/* Retrieved Evidence Chunks Grid */}
          <div className="bg-white border border-[#E5E1D8] rounded-2xl p-6 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-bold text-[#1C1917] text-sm">
                  Retrieved Multimodal Chunks ({currentResult.evidence_chunks?.length || 0})
                </h3>
                <p className="text-xs text-stone-500">
                  Ranked by Hybrid Search (Weaviate + Neo4j) + Cross-Encoder Reranker + MMR
                </p>
              </div>

              {onNavigateToGraph && (
                <button
                  onClick={onNavigateToGraph}
                  className="px-3 py-1.5 text-xs font-semibold text-[#1B4332] bg-[#EAF2ED] hover:bg-[#D7E8DC] border border-[#C3D9CB] rounded-xl transition-colors flex items-center gap-1 shadow-2xs"
                >
                  <span>🕸️</span> Open Full Evidence Graph ↗
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              {currentResult.evidence_chunks?.map((chunk, idx) => {
                const badge = getModalityBadge(chunk.modality);
                const score = chunk.score !== undefined ? (chunk.score * 100).toFixed(1) : null;

                return (
                  <div
                    key={chunk.chunk_id || idx}
                    onClick={() => setActiveChunkModal(chunk)}
                    className="p-3.5 rounded-xl border border-[#E5E1D8] bg-[#FAF9F6] hover:bg-white hover:border-[#1B4332]/40 hover:shadow-2xs transition-all cursor-pointer space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">{badge.icon}</span>
                        <span className="font-semibold text-[#1C1917] text-xs truncate max-w-44">
                          {chunk.source_id}
                        </span>
                        <span className={`text-[10px] px-1.5 py-0.2 rounded-md font-medium border ${badge.bg}`}>
                          {badge.label}
                        </span>
                      </div>
                      {score && (
                        <span className="font-mono text-[10px] font-bold text-[#1B4332] bg-[#EAF2ED] px-1.5 py-0.5 rounded border border-[#C3D9CB]">
                          {score}%
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[#57534E] line-clamp-3 leading-relaxed">
                      {chunk.content}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Chunk Detail Modal */}
      {activeChunkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl shadow-xl border border-[#E5E1D8] w-full max-w-xl overflow-hidden space-y-4 p-6">
            <div className="flex items-center justify-between border-b border-[#F0ECE1] pb-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">
                  {getModalityBadge(activeChunkModal.modality).icon}
                </span>
                <div>
                  <h4 className="font-bold text-[#1C1917] text-sm">
                    {activeChunkModal.source_id}
                  </h4>
                  <span className="text-[11px] text-stone-400 font-mono">
                    Chunk ID: {activeChunkModal.chunk_id || 'N/A'}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setActiveChunkModal(null)}
                className="text-stone-400 hover:text-stone-700 p-1.5 rounded-lg hover:bg-stone-100 transition-colors"
              >
                ✕
              </button>
            </div>

            <div>
              <span className="text-xs font-semibold text-stone-500 block mb-1">
                Extracted Chunk Content
              </span>
              <div className="bg-[#FAF9F6] border border-[#E5E1D8] rounded-xl p-3.5 text-xs text-[#1C1917] leading-relaxed max-h-72 overflow-y-auto whitespace-pre-wrap font-mono">
                {activeChunkModal.content}
              </div>
            </div>

            {activeChunkModal.metadata && (
              <div>
                <span className="text-xs font-semibold text-stone-500 block mb-1">
                  Metadata Provenance
                </span>
                <div className="bg-[#FAF9F6] p-2.5 rounded-xl border border-[#E5E1D8] text-[11px] font-mono text-[#57534E] overflow-x-auto">
                  {JSON.stringify(activeChunkModal.metadata, null, 2)}
                </div>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setActiveChunkModal(null)}
                className="px-4 py-2 text-xs font-semibold text-stone-700 bg-stone-100 hover:bg-stone-200 rounded-xl transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
