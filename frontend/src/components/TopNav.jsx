import React from "react";
import { MessageSquare, Share2, BarChart3, Settings } from "lucide-react";

export default function TopNav({
  activeTab,
  setActiveTab,
  activeScope,
  sourcesCount = 0,
  onOpenSettings
}) {
  const tabs = [
    { id: "chat", label: "Chat & Synthesis", icon: MessageSquare },
    { id: "graph", label: "Evidence Graph", icon: Share2 },
    { id: "eval", label: "Evaluation & Benchmarks", icon: BarChart3 },
  ];

  const scopeLabel =
    activeScope === "all"
      ? `Cross-Modal (${sourcesCount} sources)`
      : activeScope;

  return (
    <header className="top-nav">
      <nav className="tab-switcher">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              className={`tab-button ${isActive ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={15} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="top-nav-right">
        <div className="nav-scope-badge" title="Active Retrieval Scope">
          <span className="scope-dot" />
          <span>{scopeLabel}</span>
        </div>

        <button
          className="nav-settings-btn"
          onClick={onOpenSettings}
          title="Configure Groq API Key & Models"
        >
          <Settings size={14} />
          <span>Settings</span>
        </button>
      </div>
    </header>
  );
}
