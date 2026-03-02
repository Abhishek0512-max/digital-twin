import { useState, useRef, useEffect, useCallback } from "react";
import { streamChat, StreamMeta, SourceInfo } from "../api";
import MessageBubble from "./MessageBubble";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  conversationId?: string;
  sources?: SourceInfo[];
  isStreaming?: boolean;
}

const SUGGESTIONS = [
  "Tell me about yourself",
  "What was your experience at Juume AI?",
  "Why are you interested in AI?",
  "What kind of role are you looking for?",
  "How does your electronics background influence your AI work?",
  "What do you do outside of work?",
];

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, []);

  const sendMessage = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || isStreaming) return;
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: msg,
    };
    const assistantMsg: Message = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      sources: [],
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    let currentId = assistantMsg.id;

    await streamChat(
      msg,
      conversationId,
      (meta: StreamMeta) => {
        currentId = meta.message_id;
        setConversationId(meta.conversation_id);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? { ...m, id: meta.message_id, conversationId: meta.conversation_id }
              : m
          )
        );
      },
      (token: string) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === currentId
              ? { ...m, content: m.content + token }
              : m
          )
        );
      },
      (sources: SourceInfo[]) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === currentId ? { ...m, sources } : m
          )
        );
      },
      () => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === currentId ? { ...m, isStreaming: false } : m
          )
        );
        setIsStreaming(false);
      },
      (err: Error) => {
        console.error("Stream error:", err);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === currentId
              ? { ...m, content: "Sorry, something went wrong. Please try again.", isStreaming: false }
              : m
          )
        );
        setIsStreaming(false);
      }
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-container">
      <div className="messages-area">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-avatar">AV</div>
            <h2>Hey, I'm Abhishek's Digital Twin</h2>
            <p>
              I can answer questions about my background, skills, projects, career goals, and more.
              Powered by RAG with hybrid retrieval and LLM reranking.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  className="suggestion-btn"
                  onClick={() => sendMessage(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            conversationId={conversationId || ""}
            showDebug={showDebug}
          />
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="input-area">
        <button
          className={`debug-toggle ${showDebug ? "active" : ""}`}
          onClick={() => setShowDebug(!showDebug)}
          title={showDebug ? "Hide retrieval debug info" : "Show retrieval debug info"}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4M12 8h.01" />
          </svg>
        </button>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            autoResize();
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask Abhishek's twin something..."
          rows={1}
          disabled={isStreaming}
        />
        <button
          className="send-btn"
          onClick={() => sendMessage()}
          disabled={!input.trim() || isStreaming}
        >
          {isStreaming ? (
            <span className="spinner" />
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
