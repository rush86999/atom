import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";

interface AgentDetailProps {
  agentId: string;
  agentName: string;
  agentDescription?: string;
  maturityLevel: string;
  confidenceScore: number;
  capabilities: string[];
  recentExecutions: Array<{
    id: string;
    timestamp: Date;
    duration: number;
    success: boolean;
  }>;
  onClose: () => void;
  onQuickChat?: (message: string, agentId: string) => void;
}

export default function AgentDetail({
  agentId,
  agentName,
  agentDescription,
  maturityLevel,
  confidenceScore,
  capabilities,
  recentExecutions,
  onClose,
  onQuickChat,
}: AgentDetailProps) {
  const [isFavorite, setIsFavorite] = useState(false);
  const [chatMessage, setChatMessage] = useState("");
  const [showSettings, setShowSettings] = useState(false);

  const successRate = recentExecutions.length > 0
    ? (recentExecutions.filter((e) => e.success).length / recentExecutions.length) * 100
    : 0;

  const avgDuration = recentExecutions.length > 0
    ? recentExecutions.reduce((sum, e) => sum + e.duration, 0) / recentExecutions.length
    : 0;

  const getMaturityColor = () => {
    switch (maturityLevel) {
      case "AUTONOMOUS":
        return "#4caf50";
      case "SUPERVISED":
        return "#2196f3";
      case "INTERN":
        return "#ff9800";
      case "STUDENT":
        return "#f44336";
      default:
        return "#888";
    }
  };

  const getMaturityLabel = () => {
    switch (maturityLevel) {
      case "AUTONOMOUS":
        return "Autonomous";
      case "SUPERVISED":
        return "Supervised";
      case "INTERN":
        return "Intern";
      case "STUDENT":
        return "Student";
      default:
        return maturityLevel;
    }
  };

  const handleQuickChat = () => {
    if (chatMessage.trim() && onQuickChat) {
      onQuickChat(chatMessage, agentId);
      setChatMessage("");
      onClose();
    }
  };

  const formatTimeAgo = (timestamp: Date) => {
    const seconds = Math.floor((Date.now() - timestamp.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    const seconds = Math.floor(ms / 1000);
    return `${seconds}s`;
  };

  return (
    <>
      <div
        className="agent-detail-modal"
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          background: "#1e1e1e",
          border: "1px solid #444",
          borderRadius: "8px",
          minWidth: "550px",
          maxWidth: "650px",
          maxHeight: "80vh",
          zIndex: 1000,
          boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
          display: "flex",
          flexDirection: "column",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid #444",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
          }}
        >
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>{agentName}</h3>
              <button
                onClick={() => setIsFavorite(!isFavorite)}
                style={{
                  background: "none",
                  border: "none",
                  fontSize: "16px",
                  cursor: "pointer",
                  padding: "0",
                  opacity: isFavorite ? 1 : 0.3,
                }}
              >
                {isFavorite ? "⭐" : "☆"}
              </button>
            </div>
            {agentDescription && (
              <div style={{ fontSize: "12px", color: "#888", marginTop: "4px" }}>
                {agentDescription}
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={() => setShowSettings(!showSettings)}
              style={{
                background: "none",
                border: "none",
                color: "#888",
                fontSize: "16px",
                cursor: "pointer",
                padding: "4px",
              }}
              title="Agent Settings"
            >
              ⚙️
            </button>
            <button
              onClick={onClose}
              style={{
                background: "none",
                border: "none",
                color: "#888",
                fontSize: "20px",
                cursor: "pointer",
                padding: "0",
                width: "24px",
                height: "24px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
          {/* Status Badges */}
          <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
            <div
              style={{
                padding: "4px 10px",
                background: `${getMaturityColor()}20`,
                border: `1px solid ${getMaturityColor()}`,
                borderRadius: "4px",
                fontSize: "11px",
                fontWeight: 600,
                color: getMaturityColor(),
              }}
            >
              {getMaturityLabel()}
            </div>
            <div
              style={{
                padding: "4px 10px",
                background: "#2a2a2a",
                border: "1px solid #444",
                borderRadius: "4px",
                fontSize: "11px",
                color: "#888",
              }}
            >
              Confidence: {(confidenceScore * 100).toFixed(0)}%
            </div>
          </div>

          {/* Capabilities */}
          <div style={{ marginBottom: "20px" }}>
            <div
              style={{
                fontSize: "12px",
                color: "#888",
                textTransform: "uppercase",
                marginBottom: "8px",
                fontWeight: 600,
              }}
            >
              Capabilities
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
              {capabilities.map((capability, index) => (
                <div
                  key={index}
                  style={{
                    padding: "4px 10px",
                    background: "#2a2a2a",
                    border: "1px solid #444",
                    borderRadius: "4px",
                    fontSize: "11px",
                    color: "#ccc",
                  }}
                >
                  {capability}
                </div>
              ))}
            </div>
          </div>

          {/* Stats */}
          <div style={{ marginBottom: "20px", display: "flex", gap: "12px" }}>
            <div style={{ flex: 1, padding: "12px", background: "#2a2a2a", borderRadius: "6px" }}>
              <div style={{ fontSize: "11px", color: "#888", marginBottom: "4px" }}>Success Rate</div>
              <div style={{ fontSize: "20px", fontWeight: 600, color: "#4caf50" }}>
                {successRate.toFixed(0)}%
              </div>
            </div>
            <div style={{ flex: 1, padding: "12px", background: "#2a2a2a", borderRadius: "6px" }}>
              <div style={{ fontSize: "11px", color: "#888", marginBottom: "4px" }}>Avg Duration</div>
              <div style={{ fontSize: "20px", fontWeight: 600, color: "#2196f3" }}>
                {formatDuration(avgDuration)}
              </div>
            </div>
          </div>

          {/* Recent Executions */}
          <div style={{ marginBottom: "20px" }}>
            <div
              style={{
                fontSize: "12px",
                color: "#888",
                textTransform: "uppercase",
                marginBottom: "8px",
                fontWeight: 600,
              }}
            >
              Recent Executions ({recentExecutions.length})
            </div>
            <div
              style={{
                background: "#2a2a2a",
                borderRadius: "6px",
                padding: "8px",
                maxHeight: "200px",
                overflowY: "auto",
              }}
            >
              {recentExecutions.length === 0 ? (
                <div style={{ padding: "12px", color: "#888", fontSize: "12px", textAlign: "center" }}>
                  No recent executions
                </div>
              ) : (
                recentExecutions.map((execution) => (
                  <div
                    key={execution.id}
                    style={{
                      padding: "8px",
                      borderBottom: "1px solid #444",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <div
                        style={{
                          width: "8px",
                          height: "8px",
                          borderRadius: "50%",
                          backgroundColor: execution.success ? "#4caf50" : "#f44336",
                        }}
                      />
                      <span style={{ fontSize: "12px" }}>
                        {execution.success ? "Success" : "Failed"}
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span style={{ fontSize: "11px", color: "#888" }}>
                        {formatDuration(execution.duration)}
                      </span>
                      <span style={{ fontSize: "11px", color: "#888" }}>
                        {formatTimeAgo(execution.timestamp)}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Quick Chat */}
          {onQuickChat && (
            <div>
              <div
                style={{
                  fontSize: "12px",
                  color: "#888",
                  textTransform: "uppercase",
                  marginBottom: "8px",
                  fontWeight: 600,
                }}
              >
                Quick Chat
              </div>
              <textarea
                value={chatMessage}
                onChange={(e) => setChatMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    handleQuickChat();
                  }
                }}
                placeholder="Ask this agent something... (⌘+Enter to send)"
                style={{
                  width: "100%",
                  minHeight: "80px",
                  padding: "8px 12px",
                  background: "#2a2a2a",
                  border: "1px solid #444",
                  borderRadius: "6px",
                  color: "#fff",
                  fontSize: "12px",
                  boxSizing: "border-box",
                  resize: "vertical",
                }}
              />
            </div>
          )}

          {/* Episodes Link */}
          <div style={{ marginTop: "16px", textAlign: "center" }}>
            <button
              onClick={() => {
                const url = `http://localhost:8000/agents/${agentId}/episodes`;
                window.open(url, "_blank");
              }}
              style={{
                background: "none",
                border: "none",
                color: "#2196f3",
                fontSize: "12px",
                cursor: "pointer",
                textDecoration: "underline",
              }}
            >
              View Agent Episodes →
            </button>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 20px",
            borderTop: "1px solid #444",
            display: "flex",
            justifyContent: "flex-end",
            gap: "8px",
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "8px 16px",
              background: "#444",
              border: "none",
              borderRadius: "6px",
              color: "#fff",
              fontSize: "12px",
              cursor: "pointer",
            }}
          >
            Close
          </button>
          {onQuickChat && (
            <button
              onClick={handleQuickChat}
              disabled={!chatMessage.trim()}
              className="button"
              style={{
                padding: "8px 16px",
                fontSize: "12px",
                opacity: chatMessage.trim() ? 1 : 0.5,
                cursor: chatMessage.trim() ? "pointer" : "not-allowed",
              }}
            >
              Send Message
            </button>
          )}
        </div>
      </div>

      {/* Overlay */}
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,0.5)",
          zIndex: 999,
        }}
        onClick={onClose}
      />
    </>
  );
}
