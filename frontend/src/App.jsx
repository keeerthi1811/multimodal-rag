import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TopNav from './components/TopNav';
import ChatTab from './components/ChatTab';
import EvidenceGraph from './components/EvidenceGraph';
import EvaluationDashboard from './components/EvaluationDashboard';
import SettingsModal from './components/SettingsModal';
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [sources, setSources] = useState([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [activeScope, setActiveScope] = useState('all');
  const [uploading, setUploading] = useState(false);

  // Chat State
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);

  // Graph & Evaluation Data
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [metricsData, setMetricsData] = useState(null);
  const [isBenchmarking, setIsBenchmarking] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // 1. Initial Data Fetch on Mount
  useEffect(() => {
    fetchHealth();
    fetchSources();
    fetchMetrics();
    fetchInitialGraph();
  }, []);

  const fetchHealth = async () => {
    try {
      await fetch('/api/health');
    } catch (e) {
      console.warn('Health check error:', e);
    }
  };

  const fetchSources = async () => {
    try {
      const res = await fetch('/api/sources');
      if (res.ok) {
        const data = await res.json();
        const srcList = data.sources || [];
        setSources(srcList);
        const total = srcList.reduce((sum, s) => sum + (s.chunks_count || s.chunks || 1), 0);
        setTotalChunks(total);
        if (srcList.length > 0 && messages.length === 0) {
          setMessages([
            {
              role: 'assistant',
              text: `Welcome to **NexusRAG**. Currently loaded **${srcList.length}** source(s) across your multimodal library (${total} semantic chunks). Ask any question or click a suggested prompt to synthesize knowledge.`,
              citations: [],
            },
          ]);
        }
      }
    } catch (e) {
      console.warn('Sources fetch error:', e);
    }
  };

  const fetchMetrics = async () => {
    try {
      const res = await fetch('/api/metrics');
      if (res.ok) {
        const data = await res.json();
        setMetricsData(data);
      }
    } catch (e) {
      console.warn('Metrics fetch error:', e);
    }
  };

  const fetchInitialGraph = async () => {
    try {
      const res = await fetch('/api/graph?limit=80');
      if (res.ok) {
        const data = await res.json();
        if (data.nodes && data.nodes.length > 0) {
          setGraphData(data);
        }
      }
    } catch (e) {
      console.warn('Initial graph fetch error:', e);
    }
  };

  // 2. Handle Multi-File Upload
  const handleUpload = async (files) => {
    if (!files || files.length === 0) return;
    setUploading(true);

    const uploadedNames = [];
    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('source_id', file.name);

        const res = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        });

        if (res.ok) {
          uploadedNames.push(file.name);
        }
      }

      await fetchSources();
      await fetchInitialGraph();

      if (uploadedNames.length > 0) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: `Successfully ingested and indexed **${uploadedNames.join(', ')}**. Multimodal features and entity relations have been persisted into the Vector Store and Knowledge Graph. Ask me anything!`,
            citations: [],
          },
        ]);
      }
    } catch (err) {
      console.error('Upload error:', err);
      alert('Failed to process upload. Please check backend server.');
    } finally {
      setUploading(false);
    }
  };

  // 3. Handle Source Deletion
  const handleDeleteSource = async (sourceId) => {
    try {
      const res = await fetch(`/api/source/${encodeURIComponent(sourceId)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setSources((prev) => prev.filter((s) => s.source_id !== sourceId && s.filename !== sourceId));
        if (activeScope === sourceId) {
          setActiveScope('all');
        }
        await fetchSources();
        await fetchInitialGraph();
      }
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  // 4. Handle Clear All
  const handleClearAll = async () => {
    if (!window.confirm('Clear all indexed multimodal sources and graph data?')) return;
    try {
      const res = await fetch('/api/sources', { method: 'DELETE' });
      if (res.ok) {
        setSources([]);
        setTotalChunks(0);
        setActiveScope('all');
        setMessages([]);
        setGraphData({ nodes: [], edges: [] });
      }
    } catch (err) {
      console.error('Clear all error:', err);
    }
  };

  // 5. Handle Query Submission
  const handleQuerySubmit = async (queryText) => {
    if (!queryText.trim() || isQuerying) return;

    // Append user message
    setMessages((prev) => [...prev, { role: 'user', text: queryText }]);
    setQuestion('');
    setIsQuerying(true);

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: queryText,
          top_k: 5,
          similarity_weight: 0.5,
          graph_weight: 0.5,
          enable_mmr: true,
          mmr_lambda: 0.7,
          source_filter: activeScope !== 'all' ? activeScope : null,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Query failed');
      }

      const result = await res.json();

      // Append assistant answer
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: result.answer,
          citations: result.citations || [],
          latency_breakdown: result.latency_breakdown,
          has_conflict: result.has_conflict,
        },
      ]);

      if (result.evidence_graph && result.evidence_graph.nodes?.length > 0) {
        setGraphData(result.evidence_graph);
      }
    } catch (err) {
      console.error('Query submit error:', err);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `An error occurred while answering your question: ${err.message}`,
          citations: [],
        },
      ]);
    } finally {
      setIsQuerying(false);
    }
  };

  // 6. Handle Quick Load Sample Benchmark Data
  const handleQuickLoadSampleData = async () => {
    setIsBenchmarking(true);
    try {
      const res = await fetch('/api/evaluate', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setMetricsData(data);
        await fetchSources();
        await fetchInitialGraph();

        // Run sample question
        handleQuerySubmit('What is the approved fiscal budget and allocation for Project Alpha?');
      }
    } catch (e) {
      console.error('Quick load error:', e);
    } finally {
      setIsBenchmarking(false);
    }
  };

  // 7. Handle Live Benchmark Execution
  const handleRunBenchmark = async () => {
    setIsBenchmarking(true);
    try {
      const res = await fetch('/api/evaluate', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setMetricsData(data);
      }
    } catch (err) {
      console.error('Benchmark error:', err);
      alert(`Benchmark failed: ${err.message}`);
    } finally {
      setIsBenchmarking(false);
    }
  };

  return (
    <div className="app-layout">
      {/* Left Sidebar / Sources Rail */}
      <Sidebar
        sources={sources}
        activeScope={activeScope}
        setActiveScope={setActiveScope}
        onUpload={handleUpload}
        onDeleteSource={handleDeleteSource}
        onClearAll={handleClearAll}
        uploading={uploading}
        totalChunks={totalChunks}
        onQuickLoadSampleData={handleQuickLoadSampleData}
        isBenchmarking={isBenchmarking}
      />

      {/* Main Canvas Viewport */}
      <div className="main-canvas">
        <TopNav
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          activeScope={activeScope}
          sourcesCount={sources.length}
          onOpenSettings={() => setIsSettingsOpen(true)}
        />

        <div className="viewport">
          <ErrorBoundary>
            {activeTab === 'chat' && (
              <ChatTab
                messages={messages}
                question={question}
                setQuestion={setQuestion}
                onAsk={handleQuerySubmit}
                asking={isQuerying}
                activeScope={activeScope}
                sourcesCount={sources.length}
                onNavigateToGraph={() => setActiveTab('graph')}
              />
            )}

            {activeTab === 'graph' && (
              <div style={{ padding: '24px', height: '100%', boxSizing: 'border-box' }}>
                <EvidenceGraph graphData={graphData} />
              </div>
            )}

            {activeTab === 'eval' && (
              <div style={{ padding: '32px 24px', overflowY: 'auto', flex: 1 }}>
                <EvaluationDashboard
                  metricsData={metricsData}
                  onRunBenchmark={handleRunBenchmark}
                  isBenchmarking={isBenchmarking}
                />
              </div>
            )}
          </ErrorBoundary>
        </div>
      </div>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onKeyUpdated={() => { fetchHealth(); }}
      />
    </div>
  );
}
