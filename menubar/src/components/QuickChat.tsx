import { useState, useEffect, useRef } from "react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  agentId?: string;
  streaming?: boolean;
  feedback?: "up" | "down" | null;
}

interface QuickChatProps {
  onSend: (message: string, agentId?: string) => Promise<string | undefined>;
  onSendFeedback?: (messageId: string, feedback: "up" | "down") => void;
  agents: Array<{ id: string; name: string; maturity_level: string }>;
  autoFocus?: boolean;
}

const MAX_HISTORY = 20;

export default function QuickChat({
  onSend,
  onSendFeedback,
  agents,
  autoFocus = false,
}: QuickChatProps) {
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [streamingResponse, setStreamingResponse] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | undefined>(
    agents.find((a) => a.maturity_level === "AUTONOMOUS")?.id
  );
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Auto-focus on mount if enabled
  useEffect(() => {
    if (autoFocus && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [autoFocus]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [history, streamingResponse]);

  const handleSend = async () => {
    if (!message.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: message.trim(),
      timestamp: new Date(),
      agentId: selectedAgentId,
    };

    // Add user message to history
    setHistory((prev) => [...prev.slice(-MAX_HISTORY + 1), userMessage]);
    setError(null);
    setIsLoading(true);
    setIsTyping(true);
    setStreamingResponse("");
    setMessage("");

    try {
      // Simulate streaming response (in real implementation, use WebSocket)
      const responseText = await onSend(userMessage.content, selectedAgentId);

      if (responseText) {
        // Add assistant message to history
        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: responseText,
          timestamp: new Date(),
          agentId: selectedAgentId,
        };
        setHistory((prev) => [...prev.slice(-MAX_HISTORY + 1), assistantMessage]);
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to send message";
      setError(errorMessage);
    } finally {
      setIsLoading(false);
      setIsTyping(false);
      setStreamingResponse("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearHistory = () => {
    setHistory([]);
    setError(null);
  };

  const handleCopyResponse = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const handleFeedback = (messageId: string, feedback: "up" | "down") => {
    setHistory((prev) =>
      prev.map((msg) => (msg.id === messageId ? { ...msg, feedback } : msg))
    );
    if (onSendFeedback) {
      onSendFeedback(messageId, feedback);
    }
  };

  const formatTime = (timestamp: Date) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="quick-chat">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "8px",
        }}
      >
        <div className="section-title" style={{ margin: 0 }}>
          Quick Chat
        </div>
        {history.length > 0 && (
          <button
            onClick={handleClearHistory}
            style={{
              background: "none",
              border: "none",
              color: "#888",
              fontSize: "11px",
              cursor: "pointer",
              padding: "4px 8px",
            }}
          >
            Clear History
          </button>
        )}
      </div>

      {agents.length > 0 && (
        <select
          value={selectedAgentId || ""}
          onChange={(e) => setSelectedAgentId(e.target.value || undefined)}
          style={{
            width: "100%",
            padding: "8px 12px",
            background: "#2a2a2a",
            border: "1px solid #444",
            borderRadius: "6px",
            color: "#fff",
            fontSize: "12px",
            marginBottom: "8px",
            boxSizing: "border-box",
          }}
        >
          <option value="">Auto-select Agent</option>
          {agents.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name} ({agent.maturity_level})
            </option>
          ))}
        </select>
      )}

      {/* Chat History */}
      {history.length > 0 && (
        <div
          ref={chatContainerRef}
          style={{
            maxHeight: "300px",
            overflowY: "auto",
            marginBottom: "12px",
            paddingRight: "4px",
          }}
        >
          {history.map((msg) => (
            <div
              key={msg.id}
              style={{
                marginBottom: "12px",
                padding: "8px 12px",
                background: msg.role === "user" ? "#2a2a2a" : "#1e1e1e",
                border: msg.role === "user" ? "1px solid #444" : "none",
                borderRadius: "6px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                <span style={{ fontSize: "11px", fontWeight: 600, color: "#888" }}>
                  {msg.role === "user" ? "You" : "Agent"}
                </span>
                <span style={{ fontSize: "10px", color: "#666" }}>{formatTime(msg.timestamp)}</span>
              </div>
              <div style={{ fontSize: "13px", lineHeight: "1.4", whiteSpace: "pre-wrap" }}>
                {msg.content}
              </div>
              {msg.role === "assistant" && (
                <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                  <button
                    onClick={() => handleCopyResponse(msg.content)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#888",
                      fontSize: "11px",
                      cursor: "pointer",
                      padding: "2px 4px",
                    }}
                    title="Copy response"
                  >
                    📋 Copy
                  </button>
                  <button
                    onClick={() => handleFeedback(msg.id, msg.feedback === "up" ? null : "up")}
                    style={{
                      background: "none",
                      border: "none",
                      fontSize: "11px",
                      cursor: "pointer",
                      padding: "2px 4px",
                      opacity: msg.feedback === "up" ? 1 : 0.5,
                    }}
                    title="Helpful"
                  >
                    👍 {msg.feedback === "up" ? "Liked" : "Like"}
                  </button>
                  <button
                    onClick={() => handleFeedback(msg.id, msg.feedback === "down" ? null : "down")}
                    style={{
                      background: "none",
                      border: "none",
                      fontSize: "11px",
                      cursor: "pointer",
                      padding: "2px 4px",
                      opacity: msg.feedback === "down" ? 1 : 0.5,
                    }}
                    title="Not helpful"
                  >
                    👎 {msg.feedback === "down" ? "Disliked" : "Dislike"}
                  </button>
                </div>
              )}
            </div>
          ))}

          {/* Typing Indicator */}
          {isTyping && (
            <div
              style={{
                padding: "8px 12px",
                background: "#1e1e1e",
                borderRadius: "6px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <div style={{ display: "flex", gap: "4px" }}>
                <div
                  style={{
                    width: "6px",
                    height: "6px",
                    borderRadius: "50%",
                    background: "#888",
                    animation: "typing-bounce 1.4s infinite ease-in-out",
                  }}
                />
                <div
                  style={{
                    width: "6px",
                    height: "6px",
                    borderRadius: "50%",
                    background: "#888",
                    animation: "typing-bounce 1.4s infinite ease-in-out 0.2s",
                  }}
                />
                <div
                  style={{
                    width: "6px",
                    height: "6px",
                    borderRadius: "50%",
                    background: "#888",
                    animation: "typing-bounce 1.4s infinite ease-in-out 0.4s",
                  }}
                />
              </div>
              <span style={{ fontSize: "11px", color: "#888" }}>Agent is typing...</span>
              <style>{`
                @keyframes typing-bounce {
                  0%, 80%, 100% { transform: translateY(0); }
                  40% { transform: translateY(-6px); }
                }
              `}</style>
            </div>
          )}
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {/* Auto-growing textarea */}
      <div style={{ position: "relative" }}>
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => {
            setMessage(e.target.value);
            // Auto-resize textarea
            if (textareaRef.current) {
              textareaRef.current.style.height = "auto";
              textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
            }
          }}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder="Ask Atom anything... (⌘+Enter to send, Shift+Enter for newline)"
          style={{
            width: "100%",
            minHeight: "60px",
            maxHeight: "150px",
            padding: "8px 12px",
            background: "#2a2a2a",
            border: "1px solid #444",
            borderRadius: "6px",
            color: "#fff",
            fontSize: "12px",
            boxSizing: "border-box",
            resize: "none",
            overflowY: "auto",
          }}
        />
      </div>

      <button
        onClick={handleSend}
        disabled={isLoading || !message.trim()}
        className="button"
        style={{ marginTop: "8px", width: "100%" }}
      >
        {isLoading ? "Sending..." : "Send"}
      </button>
    </div>
  );
}
