import React from 'react';

export default function Header({ activeTab, setActiveTab, healthData, onOpenSettings }) {
  const groqConfigured = healthData?.connectors?.groq?.configured;
  const vectorBackend = healthData?.connectors?.vector_store?.backend || 'local_disk_persisted';
  const graphBackend = healthData?.connectors?.graph_store?.backend || 'local_disk_persisted';

  const tabs = [
    { id: 'studio', label: 'Studio & Q&A', icon: '⚡' },
    { id: 'graph', label: 'Evidence Graph', icon: '🕸️' },
    { id: 'sources', label: 'Library & Sources', icon: '📂' },
    { id: 'eval', label: 'Evaluation & Benchmarks', icon: '📊' },
  ];

  return (
    <header className="border-b border-[#E5E1D8] bg-[#FAF9F6] sticky top-0 z-40 px-6 py-3 shadow-2xs">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#1B4332] text-white flex items-center justify-center font-bold text-base shadow-2xs">
            Ω
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-[#1C1917]">
                NexusRAG
              </h1>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-[#EAF2ED] text-[#1B4332] border border-[#C3D9CB]">
                Multimodal Studio
              </span>
            </div>
            <p className="text-xs text-[#57534E] font-normal">
              Hybrid Vector-Graph Retrieval & Contextual Synthesis
            </p>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav className="flex items-center bg-[#F5F3EF] p-1 rounded-xl border border-[#E5E1D8]">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === tab.id
                  ? 'bg-white text-[#1B4332] shadow-2xs border border-[#E5E1D8]'
                  : 'text-[#57534E] hover:text-[#1C1917] hover:bg-stone-200/50'
              }`}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Status Indicators & Settings */}
        <div className="flex items-center gap-2 text-xs">
          <div className="hidden lg:flex items-center gap-1.5">
            <span className={`px-2.5 py-1 rounded-full text-[11px] font-medium border flex items-center gap-1 ${
              groqConfigured
                ? 'bg-[#EAF2ED] text-[#1B4332] border-[#C3D9CB]'
                : 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${groqConfigured ? 'bg-[#166534]' : 'bg-[#D97706]'}`} />
              Groq: {groqConfigured ? 'Live API' : 'Synthesized'}
            </span>

            <span className="px-2.5 py-1 rounded-full text-[11px] font-medium border bg-white text-[#57534E] border-[#E5E1D8] flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#1B4332]" />
              {vectorBackend === 'weaviate_cloud' ? 'Weaviate' : 'VectorStore'}
            </span>

            <span className="px-2.5 py-1 rounded-full text-[11px] font-medium border bg-white text-[#57534E] border-[#E5E1D8] flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#0284C7]" />
              {graphBackend === 'neo4j_native' ? 'Neo4j' : 'GraphStore'}
            </span>
          </div>

          <button
            onClick={onOpenSettings}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#E5E1D8] bg-white hover:bg-[#F5F3EF] text-[#1C1917] text-xs font-semibold shadow-2xs transition-colors"
          >
            <span>⚙️</span> API Config
          </button>
        </div>
      </div>
    </header>
  );
}
