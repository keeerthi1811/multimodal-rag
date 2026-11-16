import React, { useState, useEffect } from 'react';

export default function SettingsModal({ isOpen, onClose, onKeyUpdated }) {
  const [apiKey, setApiKey] = useState('');
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchSettings();
      setStatusMsg(null);
    }
  }, [isOpen]);

  const fetchSettings = async () => {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
      }
    } catch (e) {
      console.error('Failed to load settings:', e);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setLoading(true);
    setStatusMsg(null);
    try {
      const res = await fetch('/api/settings/api-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatusMsg({ type: 'success', text: data.message });
        setApiKey('');
        fetchSettings();
        if (onKeyUpdated) onKeyUpdated();
      } else {
        setStatusMsg({ type: 'error', text: data.detail || 'Failed to save key' });
      }
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/70">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-sm">
              ⚙
            </div>
            <div>
              <h3 className="font-semibold text-slate-900 text-base">API & Model Settings</h3>
              <p className="text-xs text-slate-500">Configure Groq API key and multimodal reasoning models</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Status badge */}
          <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200 bg-slate-50/50">
            <div className="text-xs">
              <span className="text-slate-500 block">Current Groq Status:</span>
              <span className="font-semibold text-slate-800 text-sm">
                {settings?.groq_configured ? '🟢 Live Groq API Active' : '🟡 Simulated Fallback Active'}
              </span>
            </div>
            <span className={`text-xs px-2.5 py-1 rounded-full font-medium border ${
              settings?.groq_configured 
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-amber-50 text-amber-700 border-amber-200'
            }`}>
              {settings?.groq_configured ? 'Connected' : 'Offline / Mock'}
            </span>
          </div>

          {/* Model info list */}
          <div className="grid grid-cols-2 gap-2.5 text-xs">
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-slate-400 block mb-0.5">LLM Reasoning</span>
              <span className="font-mono text-slate-700 font-medium truncate block">
                {settings?.groq_model || 'llama-3.3-70b-versatile'}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-slate-400 block mb-0.5">Vision Model</span>
              <span className="font-mono text-slate-700 font-medium truncate block">
                {settings?.vision_model || 'llama-3.2-11b-vision-preview'}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-slate-400 block mb-0.5">Audio Model</span>
              <span className="font-mono text-slate-700 font-medium truncate block">
                {settings?.audio_model || 'whisper-large-v3-turbo'}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
              <span className="text-slate-400 block mb-0.5">Embeddings</span>
              <span className="font-mono text-slate-700 font-medium truncate block">
                {settings?.embedding_model || 'BAAI/bge-base-en-v1.5'}
              </span>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSave} className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Update Groq API Key
              </label>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  placeholder="gsk_..."
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="w-full px-3.5 py-2.5 pr-20 text-xs font-mono rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 bg-white text-slate-900 placeholder-slate-400"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-700 px-1.5 py-0.5"
                >
                  {showKey ? 'Hide' : 'Show'}
                </button>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Keys start with <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-600">gsk_</code>. Saved directly to local configuration.
              </p>
            </div>

            {statusMsg && (
              <div className={`text-xs p-3 rounded-xl border ${
                statusMsg.type === 'success'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : 'bg-rose-50 text-rose-800 border-rose-200'
              }`}>
                {statusMsg.text}
              </div>
            )}

            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-colors"
              >
                Close
              </button>
              <button
                type="submit"
                disabled={loading || !apiKey.trim()}
                className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl shadow-xs transition-colors"
              >
                {loading ? 'Saving...' : 'Save & Connect'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
