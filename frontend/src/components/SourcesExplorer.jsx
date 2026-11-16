import React, { useState, useEffect } from 'react';

export default function SourcesExplorer({ onDeleteSource, onRefresh }) {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterModality, setFilterModality] = useState('all');
  const [selectedSource, setSelectedSource] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    fetchSources();
  }, []);

  const fetchSources = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/sources');
      if (res.ok) {
        const data = await res.json();
        setSources(data.sources || []);
      }
    } catch (e) {
      console.error('Failed to fetch sources:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (sourceId, filename) => {
    if (!window.confirm(`Permanently delete "${filename || sourceId}" from vector storage, knowledge graph, and disk?`)) {
      return;
    }

    setDeletingId(sourceId);
    try {
      const res = await fetch(`/api/source/${encodeURIComponent(sourceId)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setSources(prev => prev.filter(s => s.source_id !== sourceId));
        if (selectedSource?.source_id === sourceId) {
          setSelectedSource(null);
        }
        if (onDeleteSource) onDeleteSource(sourceId);
        if (onRefresh) onRefresh();
      } else {
        alert('Failed to delete source');
      }
    } catch (e) {
      console.error('Delete error:', e);
      alert(`Delete error: ${e.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const filteredSources = sources.filter(s => {
    if (filterModality === 'all') return true;
    return (s.modality || '').toLowerCase() === filterModality.toLowerCase();
  });

  const getModalityBadge = (modality) => {
    switch ((modality || '').toLowerCase()) {
      case 'document':
        return { label: 'Document', bg: 'bg-[#EAF2ED] text-[#1B4332] border-[#C3D9CB]', icon: '📄' };
      case 'image':
        return { label: 'Image (OCR+Vision)', bg: 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]', icon: '🖼️' };
      case 'video':
        return { label: 'Video (Frames+Audio)', bg: 'bg-[#FEE2E2] text-[#991B1B] border-[#FECACA]', icon: '🎬' };
      case 'audio':
        return { label: 'Audio (Whisper)', bg: 'bg-[#EDE9FE] text-[#5B21B6] border-[#DDD6FE]', icon: '🎙️' };
      default:
        return { label: modality || 'Media', bg: 'bg-stone-100 text-stone-700 border-stone-200', icon: '📦' };
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Stats */}
      <div className="bg-white rounded-2xl p-5 border border-[#E5E1D8] shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-[#1C1917] tracking-tight flex items-center gap-2">
            <span>🗂️</span> Library & Media Sources
          </h2>
          <p className="text-xs text-[#57534E] mt-0.5">
            Manage all ingested multimodal files, review extracted text and transcripts, and delete items.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-[#FAF9F6] border border-[#E5E1D8] rounded-xl px-3 py-1.5 text-xs text-[#57534E]">
            <span className="font-semibold text-[#1C1917]">{sources.length}</span> Active Sources
          </div>
          <button
            onClick={() => { fetchSources(); if (onRefresh) onRefresh(); }}
            className="px-3 py-1.5 text-xs font-semibold text-[#1C1917] bg-[#F5F3EF] hover:bg-[#EAF2ED] rounded-xl transition-colors flex items-center gap-1.5"
          >
            <span>↻</span> Refresh
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-[#E5E1D8] pb-2">
        {['all', 'document', 'image', 'video', 'audio'].map((mod) => (
          <button
            key={mod}
            onClick={() => setFilterModality(mod)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
              filterModality === mod
                ? 'bg-[#1B4332] text-white shadow-2xs'
                : 'text-[#57534E] hover:text-[#1C1917] hover:bg-[#F5F3EF]'
            }`}
          >
            {mod === 'all' ? 'All Modalities' : mod}
          </button>
        ))}
      </div>

      {/* Source Grid and Preview Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Source Cards List */}
        <div className="lg:col-span-2 space-y-3">
          {loading ? (
            <div className="bg-white rounded-2xl p-12 border border-[#E5E1D8] text-center text-stone-400 text-sm">
              Loading sources...
            </div>
          ) : filteredSources.length === 0 ? (
            <div className="bg-white rounded-2xl p-12 border border-[#E5E1D8] text-center space-y-2">
              <div className="text-3xl text-stone-300">📂</div>
              <h3 className="font-semibold text-[#1C1917] text-sm">No sources found</h3>
              <p className="text-xs text-[#57534E] max-w-sm mx-auto">
                No uploaded files match this filter. Upload files in the Studio tab to index them here.
              </p>
            </div>
          ) : (
            filteredSources.map((src) => {
              const badge = getModalityBadge(src.modality);
              const isSelected = selectedSource?.source_id === src.source_id;
              const isDeleting = deletingId === src.source_id;

              return (
                <div
                  key={src.source_id}
                  onClick={() => setSelectedSource(src)}
                  className={`bg-white rounded-xl p-4 border transition-all cursor-pointer ${
                    isSelected
                      ? 'border-[#1B4332] ring-2 ring-[#1B4332]/10 shadow-xs'
                      : 'border-[#E5E1D8] hover:border-stone-400 hover:shadow-2xs'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="text-xl p-2 rounded-xl bg-[#FAF9F6] border border-[#E5E1D8] shrink-0">
                        {badge.icon}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="font-semibold text-[#1C1917] text-sm truncate max-w-xs md:max-w-md">
                            {src.filename || src.source_id}
                          </h4>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${badge.bg}`}>
                            {badge.label}
                          </span>
                        </div>
                        <p className="text-xs text-stone-400 line-clamp-1 mt-0.5 font-mono">
                          ID: {src.source_id}
                        </p>
                        {src.sample_content && (
                          <p className="text-xs text-[#57534E] line-clamp-2 mt-1.5 bg-[#FAF9F6] p-2 rounded-lg border border-[#E5E1D8]">
                            {src.sample_content}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[11px] text-stone-500 bg-[#F5F3EF] px-2 py-1 rounded-md font-mono">
                        {src.chunks_count || 1} chunks
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(src.source_id, src.filename);
                        }}
                        disabled={isDeleting}
                        title="Permanently delete from vector store and graph"
                        className="p-1.5 text-stone-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors border border-transparent hover:border-rose-200"
                      >
                        {isDeleting ? '⌛' : '🗑️'}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Detail / Inspector Panel */}
        <div className="bg-white rounded-2xl p-5 border border-[#E5E1D8] shadow-2xs h-fit space-y-4">
          <h3 className="font-bold text-[#1C1917] text-sm border-b border-[#F0ECE1] pb-3 flex items-center justify-between">
            <span>Inspector Preview</span>
            {selectedSource && (
              <span className="text-xs font-normal text-stone-400 font-mono">
                {selectedSource.source_id}
              </span>
            )}
          </h3>

          {selectedSource ? (
            <div className="space-y-4 text-xs">
              <div>
                <span className="text-stone-400 block mb-1">File Name</span>
                <span className="font-semibold text-[#1C1917] break-all">
                  {selectedSource.filename || selectedSource.source_id}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded-lg bg-[#FAF9F6] border border-[#E5E1D8]">
                  <span className="text-stone-400 block mb-0.5">Modality</span>
                  <span className="font-medium text-[#1C1917] capitalize">
                    {selectedSource.modality}
                  </span>
                </div>
                <div className="p-2.5 rounded-lg bg-[#FAF9F6] border border-[#E5E1D8]">
                  <span className="text-stone-400 block mb-0.5">Indexed Chunks</span>
                  <span className="font-medium text-[#1C1917] font-mono">
                    {selectedSource.chunks_count || 1} chunks
                  </span>
                </div>
              </div>

              <div>
                <span className="text-stone-400 block mb-1">Extracted Content Preview</span>
                <div className="bg-[#FAF9F6] border border-[#E5E1D8] rounded-xl p-3 text-[#1C1917] font-mono text-[11px] leading-relaxed max-h-64 overflow-y-auto whitespace-pre-wrap">
                  {selectedSource.sample_content || 'No text snippet preview available.'}
                </div>
              </div>

              <div className="pt-2">
                <button
                  onClick={() => handleDelete(selectedSource.source_id, selectedSource.filename)}
                  className="w-full py-2 px-3 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-xl transition-colors flex items-center justify-center gap-1.5"
                >
                  <span>🗑️</span> Delete This Source Permanently
                </button>
              </div>
            </div>
          ) : (
            <div className="py-8 text-center text-stone-400 text-xs">
              Select any file on the left to inspect its details, extracted OCR/transcription chunks, and metadata.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
