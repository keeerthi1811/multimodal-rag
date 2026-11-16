import React from 'react';

export default function LatencyBar({ latencyData }) {
  if (!latencyData) return null;

  const {
    retrieval_ms = 0,
    rerank_mmr_ms = 0,
    conflict_graph_ms = 0,
    llm_generation_ms = 0,
    total_query_ms = 0,
  } = latencyData;

  const safeTotal = Math.max(1, total_query_ms || (retrieval_ms + rerank_mmr_ms + conflict_graph_ms + llm_generation_ms));

  const pctRetrieval = Math.max(5, (retrieval_ms / safeTotal) * 100);
  const pctRerank = Math.max(5, (rerank_mmr_ms / safeTotal) * 100);
  const pctConflict = Math.max(5, (conflict_graph_ms / safeTotal) * 100);
  const pctLLM = Math.max(5, (llm_generation_ms / safeTotal) * 100);

  return (
    <div className="bg-[#FAF9F6] border border-[#E5E1D8] rounded-xl p-3.5 space-y-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-bold text-[#1C1917]">
          <span>⏱️</span>
          <span>Stage Latency Instrumentation Telemetry</span>
        </div>
        <span className="font-mono text-xs font-bold text-[#1B4332] bg-[#EAF2ED] px-2 py-0.5 rounded-full border border-[#C3D9CB]">
          {total_query_ms}ms total
        </span>
      </div>

      {/* Segmented Bar */}
      <div className="h-2 w-full bg-[#E5E1D8] rounded-full overflow-hidden flex p-0.5">
        <div
          style={{ width: `${pctRetrieval}%` }}
          className="h-full bg-sky-500 rounded-l-full transition-all"
          title={`Retrieval: ${retrieval_ms}ms`}
        />
        <div
          style={{ width: `${pctRerank}%` }}
          className="h-full bg-[#1B4332] transition-all"
          title={`Rerank + MMR: ${rerank_mmr_ms}ms`}
        />
        <div
          style={{ width: `${pctConflict}%` }}
          className="h-full bg-amber-500 transition-all"
          title={`Conflict & Graph: ${conflict_graph_ms}ms`}
        />
        <div
          style={{ width: `${pctLLM}%` }}
          className="h-full bg-emerald-600 rounded-r-full transition-all"
          title={`LLM Generation: ${llm_generation_ms}ms`}
        />
      </div>

      {/* Stage Legend */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-[#57534E]">
        <div className="flex items-center gap-1.5 bg-white p-1 rounded-lg border border-[#E5E1D8]">
          <div className="w-2 h-2 rounded-full bg-sky-500 shrink-0" />
          <span className="truncate">Retrieval:</span>
          <span className="font-mono text-[#1C1917] font-bold">{retrieval_ms}ms</span>
        </div>
        <div className="flex items-center gap-1.5 bg-white p-1 rounded-lg border border-[#E5E1D8]">
          <div className="w-2 h-2 rounded-full bg-[#1B4332] shrink-0" />
          <span className="truncate">Rerank/MMR:</span>
          <span className="font-mono text-[#1C1917] font-bold">{rerank_mmr_ms}ms</span>
        </div>
        <div className="flex items-center gap-1.5 bg-white p-1 rounded-lg border border-[#E5E1D8]">
          <div className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
          <span className="truncate">Conflict/Graph:</span>
          <span className="font-mono text-[#1C1917] font-bold">{conflict_graph_ms}ms</span>
        </div>
        <div className="flex items-center gap-1.5 bg-white p-1 rounded-lg border border-[#E5E1D8]">
          <div className="w-2 h-2 rounded-full bg-emerald-600 shrink-0" />
          <span className="truncate">LLM Synth:</span>
          <span className="font-mono text-[#1C1917] font-bold">{llm_generation_ms}ms</span>
        </div>
      </div>
    </div>
  );
}
