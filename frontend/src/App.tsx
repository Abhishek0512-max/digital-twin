import { useState, useEffect, useCallback } from "react";
import ChatWindow from "./components/ChatWindow";
import EvalPanel from "./components/EvalPanel";
import "./App.css";

function App() {
  const [activeTab, setActiveTab] = useState<"chat" | "eval">("chat");
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const [chatKey, setChatKey] = useState(0);
  const [showEvalAccess, setShowEvalAccess] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("http://localhost:8000/health");
        if (res.ok) setBackendStatus("online");
        else setBackendStatus("offline");
      } catch {
        setBackendStatus("offline");
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "e") {
      e.preventDefault();
      setShowEvalAccess(true);
      setActiveTab("eval");
    }
  }, []);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <div className="avatar">AV</div>
          <div>
            <h1>Abhishek's Digital Twin</h1>
            <div className="subtitle-row">
              <span className={`status-dot ${backendStatus}`} />
              <p className="subtitle">
                {backendStatus === "online"
                  ? "Ask me anything about my background, experience, and interests"
                  : backendStatus === "checking"
                  ? "Connecting..."
                  : "Backend offline — start the server on port 8000"}
              </p>
            </div>
          </div>
        </div>
        <div className="header-actions">
          <button
            className="new-chat-btn"
            onClick={() => { setActiveTab("chat"); setChatKey((k) => k + 1); }}
            title="New conversation"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14" />
            </svg>
            New Chat
          </button>
          {showEvalAccess && (
            <nav className="header-nav">
              <button
                className={`tab-btn ${activeTab === "chat" ? "active" : ""}`}
                onClick={() => setActiveTab("chat")}
              >
                Chat
              </button>
              <button
                className={`tab-btn ${activeTab === "eval" ? "active" : ""}`}
                onClick={() => setActiveTab("eval")}
              >
                Eval
              </button>
            </nav>
          )}
        </div>
      </header>
      <main className="app-main">
        {activeTab === "chat" ? <ChatWindow key={chatKey} /> : <EvalPanel />}
      </main>
    </div>
  );
}

export default App;
