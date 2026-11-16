import React, { useRef } from "react";
import {
  Upload,
  FileText,
  Image as ImageIcon,
  Film,
  Headphones,
  X,
  Loader2,
  Layers,
  Sparkles,
  Database
} from "lucide-react";

export default function Sidebar({
  sources = [],
  activeScope,
  setActiveScope,
  onUpload,
  onDeleteSource,
  onClearAll,
  uploading,
  totalChunks = 0,
  onQuickLoadSampleData,
  isBenchmarking
}) {
  const fileInputRef = useRef(null);

  const handleFiles = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      onUpload(files);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files || []);
    if (files.length > 0) {
      onUpload(files);
    }
  };

  const getModalityIcon = (modality) => {
    switch (modality?.toLowerCase()) {
      case "image":
        return <ImageIcon size={15} className="doc-icon text-sky-700" />;
      case "video":
        return <Film size={15} className="doc-icon text-purple-700" />;
      case "audio":
        return <Headphones size={15} className="doc-icon text-amber-700" />;
      default:
        return <FileText size={15} className="doc-icon text-emerald-800" />;
    }
  };

  return (
    <aside className="sidebar">
      <div>
        {/* Brand Header */}
        <div className="brand-section">
          <div className="brand-icon">
            Ω
          </div>
          <div className="brand-title-wrap">
            <span className="brand-name">NexusRAG</span>
            <span className="brand-sub">Multimodal Knowledge Studio</span>
          </div>
        </div>

        {/* Upload Zone */}
        <div
          className="upload-dropzone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
        >
          <input
            type="file"
            ref={fileInputRef}
            accept=".pdf,.txt,.png,.jpg,.jpeg,.mp3,.wav,.mp4,.mov,.mkv"
            multiple
            onChange={handleFiles}
            disabled={uploading}
          />
          <div className="upload-icon-wrap">
            {uploading ? (
              <Loader2 size={16} className="spin" />
            ) : (
              <Upload size={16} />
            )}
          </div>
          <span className="upload-prompt">
            {uploading ? "Indexing Sources..." : "Upload Multimodal Files"}
          </span>
          <span className="upload-hint">PDF, Images, Audio, Video, TXT</span>
        </div>

        {/* Scope Selector & Sources Management */}
        <div className="scope-header-row">
          <span className="section-label">Library ({sources.length})</span>
          {sources.length > 0 && (
            <button className="clear-btn" onClick={onClearAll} title="Clear all indexed files">
              Clear All
            </button>
          )}
        </div>

        {/* "All Sources" Scope Pill */}
        <button
          className={`scope-all-pill ${activeScope === "all" ? "active" : ""}`}
          onClick={() => setActiveScope("all")}
          disabled={sources.length === 0}
        >
          <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Layers size={14} />
            All Sources (Cross-Modal)
          </span>
          <span className="badge-count">{sources.length}</span>
        </button>

        {/* Sources Chips List */}
        <div className="doc-list">
          {sources.map((src) => {
            const sid = src.source_id || src.filename;
            const modality = src.modality || "document";
            const chunkCount = src.chunk_count || src.chunks || 1;
            const isActive = activeScope === sid;

            return (
              <div
                key={sid}
                className={`doc-chip ${isActive ? "active" : ""}`}
                onClick={() => setActiveScope(sid)}
              >
                <div className="doc-chip-left">
                  {getModalityIcon(modality)}
                  <div className="doc-info">
                    <span className="doc-title" title={sid}>
                      {sid}
                    </span>
                    <span className="doc-meta">
                      {modality} • {chunkCount} chunk{chunkCount > 1 ? "s" : ""}
                    </span>
                  </div>
                </div>
                <button
                  className="doc-delete-btn"
                  title={`Delete ${sid}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSource(sid);
                  }}
                >
                  <X size={14} />
                </button>
              </div>
            );
          })}

          {sources.length === 0 && !uploading && (
            <div style={{ textAlign: "center", padding: "20px 8px", color: "var(--text-muted)", fontSize: "0.78rem" }}>
              No sources loaded yet. Upload documents, charts, audio, or video files.
            </div>
          )}
        </div>

        {/* Quick Sample Benchmark Data */}
        <div className="sample-load-card">
          <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase" }}>
            Benchmark Dataset
          </span>
          <button
            className="sample-load-btn"
            onClick={onQuickLoadSampleData}
            disabled={isBenchmarking}
            title="Ingests standard sample report, chart, and audio"
          >
            {isBenchmarking ? (
              <>
                <Loader2 size={13} className="spin" /> Indexing Benchmarks...
              </>
            ) : (
              <>
                <Sparkles size={13} /> Load Sample Benchmark Data
              </>
            )}
          </button>
        </div>
      </div>

      {/* Footer Stats */}
      <div className="sidebar-footer">
        <span>{sources.length} Sources • {totalChunks} Chunks</span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.68rem" }}>Vector + Graph</span>
      </div>
    </aside>
  );
}
