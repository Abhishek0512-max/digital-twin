import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { sendFeedback, SourceInfo } from "../api";

interface Props {
  message: {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources?: SourceInfo[];
    isStreaming?: boolean;
  };
  conversationId: string;
  showDebug: boolean;
}

export default function MessageBubble({ message, conversationId, showDebug }: Props) {
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const handleFeedback = async (rating: "up" | "down") => {
    if (feedback) return;
    setFeedback(rating);
    try {
      await sendFeedback({
        message_id: message.id,
        conversation_id: conversationId,
        question: "",
        response: message.content,
        rating,
      });
    } catch (err) {
      console.error("Feedback error:", err);
    }
  };

  const isUser = message.role === "user";
  const sources = message.sources || [];
  const isDone = !message.isStreaming && message.content.length > 0;

  return (
    <div className={`message-row ${isUser ? "user-row" : "assistant-row"}`}>
      {!isUser && <div className="msg-avatar">AV</div>}
      <div className={`message-bubble ${isUser ? "user-bubble" : "assistant-bubble"}`}>
        <div className="message-content">
          {!message.content && !isUser ? (
            <div className="thinking-state">
              <span className="thinking-dots">
                <span /><span /><span />
              </span>
              <span className="thinking-text">Thinking...</span>
            </div>
          ) : isUser ? (
            message.content
          ) : (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          )}
        </div>

        {!isUser && isDone && sources.length > 0 && (
          <div className="sources-row">
            <span className="sources-label">Sources:</span>
            {sources.map((s, i) => (
              <span key={i} className="source-tag">
                {s.file}{s.section ? ` > ${s.section}` : ""}
              </span>
            ))}
          </div>
        )}

        {!isUser && isDone && showDebug && sources.length > 0 && (
          <div className="debug-panel">
            <div className="debug-title">Retrieval Debug</div>
            {sources.map((s, i) => (
              <div key={i} className="debug-item">
                <span className="debug-file">{s.file}</span>
                <span className="debug-section">{s.section || "—"}</span>
                <span className="debug-score">RRF: {s.score}</span>
              </div>
            ))}
          </div>
        )}

        {!isUser && isDone && (
          <div className="feedback-row">
            <button
              className={`fb-btn ${feedback === "up" ? "active-up" : ""}`}
              onClick={() => handleFeedback("up")}
              title="Good response"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
              </svg>
            </button>
            <button
              className={`fb-btn ${feedback === "down" ? "active-down" : ""}`}
              onClick={() => handleFeedback("down")}
              title="Poor response"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10zM17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
              </svg>
            </button>
          </div>
        )}
      </div>
      {isUser && <div className="msg-avatar user-avatar">You</div>}
    </div>
  );
}
