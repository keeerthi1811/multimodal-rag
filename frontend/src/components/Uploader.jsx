import React, { useState, useRef } from 'react';

export default function Uploader({ ingestedFiles, onFileUploadSuccess, onQuickLoadSampleData, onDeleteSource }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      await uploadFiles(files);
    }
  };

  const handleFileInputChange = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      await uploadFiles(files);
    }
  };

  const uploadFiles = async (files) => {
    setIsUploading(true);
    setUploadError(null);

    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || 'Upload failed');
        }

        const data = await response.json();
        onFileUploadSuccess(data);
      } catch (err) {
        console.error('Upload error:', err);
        setUploadError(`Failed to upload ${file.name}: ${err.message}`);
      }
    }

    setIsUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDelete = async (sourceId, filename) => {
    if (!window.confirm(`Permanently delete "${filename || sourceId}"?`)) return;
    setDeletingId(sourceId);
    try {
      const res = await fetch(`/api/source/${encodeURIComponent(sourceId)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        if (onDeleteSource) onDeleteSource(sourceId);
      } else {
        alert('Failed to delete file.');
      }
    } catch (e) {
      alert(`Delete failed: ${e.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const getModalityMeta = (modality) => {
    switch ((modality || '').toLowerCase()) {
      case 'document':
        return { label: 'Document', icon: '📄', bg: 'bg-[#EAF2ED] text-[#1B4332] border-[#C3D9CB]' };
      case 'image':
        return { label: 'Image (OCR+Vision)', icon: '🖼️', bg: 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]' };
      case 'video':
        return { label: 'Video (Frames+Audio)', icon: '🎬', bg: 'bg-[#FEE2E2] text-[#991B1B] border-[#FECACA]' };
      case 'audio':
        return { label: 'Audio (Whisper)', icon: '🎙️', bg: 'bg-[#EDE9FE] text-[#5B21B6] border-[#DDD6FE]' };
      default:
        return { label: modality || 'Media', icon: '📦', bg: 'bg-stone-100 text-stone-700 border-stone-200' };
    }
  };

  return (
    <div className="bg-white border border-[#E5E1D8] rounded-2xl p-5 shadow-2xs space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-[#1C1917] flex items-center gap-2">
            <span>📥</span> Multimodal Ingestion Pipeline
          </h2>
          <p className="text-xs text-[#57534E] mt-0.5">
            Accepts PDFs, images (with OCR & Vision), video frames, and audio into Weaviate and Neo4j.
          </p>
        </div>

        <button
          onClick={onQuickLoadSampleData}
          className="self-start sm:self-auto px-3 py-1.5 text-xs font-semibold text-[#1B4332] bg-[#EAF2ED] hover:bg-[#D7E8DC] border border-[#C3D9CB] rounded-xl transition-colors flex items-center gap-1.5 shadow-2xs"
        >
          <span>✨</span> Load Sample Benchmark Data
        </button>
      </div>

      {/* Drag & Drop Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-[#1B4332] bg-[#EAF2ED]/40'
            : 'border-[#E5E1D8] hover:border-[#1B4332]/60 bg-[#FAF9F6] hover:bg-[#EAF2ED]/20'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.png,.jpg,.jpeg,.webp,.mp4,.mov,.mp3,.wav"
          className="hidden"
          onChange={handleFileInputChange}
        />
        <div className="flex flex-col items-center justify-center space-y-1.5">
          <div className="w-10 h-10 rounded-xl bg-white border border-[#E5E1D8] shadow-2xs flex items-center justify-center text-lg text-stone-700">
            {isUploading ? '⏳' : '☁️'}
          </div>
          <div>
            <p className="text-xs font-semibold text-[#1C1917]">
              {isUploading ? 'Ingesting and vectorizing files...' : 'Click to browse or drop multimodal files here'}
            </p>
            <p className="text-[11px] text-stone-400 mt-0.5">
              Supported: <strong className="text-stone-600 font-medium">.pdf, .txt, .png, .jpg, .mp4, .mov, .mp3, .wav</strong>
            </p>
          </div>
        </div>
      </div>

      {uploadError && (
        <div className="text-xs p-3 rounded-xl bg-rose-50 text-rose-800 border border-rose-200 flex items-center gap-2">
          <span>⚠️</span> {uploadError}
        </div>
      )}

      {/* Active Ingested Files List */}
      {ingestedFiles && ingestedFiles.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-[#F0ECE1]">
          <div className="flex items-center justify-between text-xs text-stone-500 px-1 font-medium">
            <span>Library Sources ({ingestedFiles.length})</span>
            <span className="text-[11px] text-stone-400">Click 🗑️ to delete any item</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {ingestedFiles.map((file, idx) => {
              const meta = getModalityMeta(file.modality);
              const sid = file.source_id || file.filename;
              const isDeleting = deletingId === sid;

              return (
                <div
                  key={`${sid}-${idx}`}
                  className="bg-[#FAF9F6] border border-[#E5E1D8] rounded-xl p-3 flex items-center justify-between gap-2.5 transition-all hover:border-stone-300"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="text-base">{meta.icon}</span>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-[#1C1917] truncate">
                        {file.filename || file.source_id}
                      </p>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className={`text-[10px] px-1.5 py-0.2 rounded font-medium border ${meta.bg}`}>
                          {meta.label}
                        </span>
                        <span className="text-[10px] text-stone-400 font-mono">
                          {file.chunks_count || 1} chunks
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(sid, file.filename);
                    }}
                    disabled={isDeleting}
                    title="Delete this uploaded file"
                    className="p-1.5 text-stone-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg border border-transparent hover:border-rose-200 transition-colors"
                  >
                    {isDeleting ? '⌛' : '🗑️'}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
