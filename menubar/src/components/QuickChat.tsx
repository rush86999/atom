import { useState } from "react";

interface QuickChatProps {
  onSend: (message: string, agentId?: string) => Promise<string | undefined>;
  agents: Array<{ id: string; name: string; maturity_level: string }>;
}

export default function QuickChat({ onSend, agents }: QuickChatProps) {
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | undefined>(
    agents.find((a) => a.maturity_level === "AUTONOMOUS")?.id
  );

  const handleSend = async () => {
    if (!message.trim() || isLoading) return;

    setError(null);
    setResponse(null);
    setIsLoading(true);

    try {
      const responseText = await onSend(message, selectedAgentId);
      setResponse(responseText || "Message sent successfully");
      setMessage("");
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to send message";
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="quick-chat">
      <div className="section-title">Quick Chat</div>

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

      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        placeholder="Ask Atom anything... (⌘+Enter to send)"
      />

      {error && <div className="error">{error}</div>}

      {response && (
        <div
          style={{
            marginTop: "8px",
            padding: "8px 12px",
            background: "#2a2a2a",
            borderRadius: "6px",
            fontSize: "12px",
            color: "#4caf50",
          }}
        >
          {response}
        </div>
      )}

      <button
        onClick={handleSend}
        disabled={isLoading || !message.trim()}
        className="button"
      >
        {isLoading ? "Sending..." : "Send"}
      </button>
    </div>
  );
}
