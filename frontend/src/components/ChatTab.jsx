import React, { useRef, useEffect } from "react";
import { Send, Loader2, Sparkles, Share2, Layers } from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer";

export default function ChatTab({
  messages = [],
  question = "",
  setQuestion,
  onAsk,
  asking = false,
  activeScope = "all",
  sourcesCount = 0,
  onNavigateToGraph
}) {
  const bottomRef = useRef(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!question.trim() || asking) return;
    onAsk(question);
  };

  const samplePrompts = [
    "What is the approved fiscal budget and timeline for Project Alpha?",
    "Summarize the key findings, speakers, and action items from the sources.",
    "Compare the accuracy and precision figures reported across all modalities."
  ];

  return (
    <div className="chat-container">
      {/* Scrollable Message History */}
      <div className="chat-history">
        {messages.length === 0 ? (
          <div className="editorial-empty-state">
            <h2 className="empty-headline">Multimodal Knowledge Synthesis</h2>
            <p className="empty-description">
              Inquire across your uploaded PDF reports, diagram images, audio briefings, and video recordings.
              NexusRAG fuses semantic vectors and knowledge graph neighborhoods into articulate, verifiable answers with exact source citations.
            </p>
            {sourcesCount > 0 && (
              <div className="prompt-suggestions">
                <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Suggested Cross-Modal Inquiries
                </span>
                {samplePrompts.map((prompt, idx) => (
                  <button
                    key={idx}
                    className="prompt-chip"
                    onClick={() => {
                      setQuestion(prompt);
                    }}
                  >
                    <span>{prompt}</span>
                    <Sparkles size={14} style={{ opacity: 0.6 }} />
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isUser = msg.role === "user";

            return (
              <div key={idx} className={`message-row ${msg.role}`}>
                <div className={`message-bubble ${msg.role}`}>
                  {isUser ? (
                    <div>{msg.text}</div>
                  ) : (
                    <>
                      <MarkdownRenderer content={msg.text} />

                      {/* Source Citations & Telemetry */}
                      <div className="message-meta">
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="citations-group">
                            {msg.citations.map((c, cIdx) => {
                              const mod = (c.modality || "DOC").toUpperCase();
                              const sid = c.source_id || c.file_name || "source";
                              let label = `[${mod}: ${sid}`;
                              if (c.page_num) label += `, p.${c.page_num}`;
                              else if (c.timestamp) label += `, ${c.timestamp}s`;
                              else if (c.start_time !== undefined && c.start_time !== null) label += `, ${c.start_time.toFixed(1)}s`;
                              label += `]`;

                              return (
                                <span
                                  key={cIdx}
                                  className="citation-chip"
                                  title={`Source: ${sid} (${mod})`}
                                >
                                  📌 {label}
                                </span>
                              );
                            })}
                          </div>
                        )}

                        {msg.latency_breakdown?.total_query_ms && (
                          <span className="latency-tag">
                            ⏱ {msg.latency_breakdown.total_query_ms}ms
                          </span>
                        )}

                        {onNavigateToGraph && (
                          <button
                            onClick={onNavigateToGraph}
                            style={{
                              marginLeft: "auto",
                              background: "none",
                              border: "none",
                              color: "var(--accent-primary)",
                              cursor: "pointer",
                              fontSize: "0.72rem",
                              fontWeight: 600,
                              display: "flex",
                              alignItems: "center",
                              gap: "4px"
                            }}
                            title="Inspect in Evidence Graph"
                          >
                            <Share2 size={13} />
                            <span>Evidence Subgraph</span>
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}

        {asking && (
          <div className="message-row assistant">
            <div className="message-bubble assistant" style={{ display: "flex", alignItems: "center", gap: "10px", color: "var(--text-secondary)" }}>
              <Loader2 size={16} className="spin" style={{ color: "var(--accent-primary)" }} />
              <span style={{ fontSize: "0.85rem" }}>
                Retrieving multimodal vectors, traversing graph triples, and synthesizing response...
              </span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Chat Input Bar */}
      <div className="chat-input-bar">
        <form onSubmit={handleSubmit} className="input-box-wrapper">
          <input
            type="text"
            className="input-field"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={
              sourcesCount === 0
                ? "Upload multimodal files to begin asking questions..."
                : activeScope === "all"
                ? `Ask anything across all ${sourcesCount} sources...`
                : `Ask a question specific to ${activeScope}...`
            }
            disabled={asking}
          />
          <button
            type="submit"
            className="submit-btn"
            disabled={asking || !question.trim()}
            title="Submit query"
          >
            {asking ? <Loader2 size={16} className="spin" /> : <Send size={15} />}
          </button>
        </form>
      </div>
    </div>
  );
}
