import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import QuickChat from "./components/QuickChat";
import AgentList from "./components/AgentList";
import CanvasList from "./components/CanvasList";
import type { User, AgentSummary, CanvasSummary, ConnectionStatus } from "./types";

interface MenuBarProps {
  user: User | null;
  token: string | null;
  onLogout: () => void;
}

export default function MenuBar({ user, token, onLogout }: MenuBarProps) {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [canvases, setCanvases] = useState<CanvasSummary[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    status: "disconnected",
    server_time: new Date().toISOString(),
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Load initial data
    loadRecentData();

    // Set up connection status polling
    const statusInterval = setInterval(checkConnectionStatus, 30000); // 30 seconds

    // Listen for global hotkey
    const unlisten = listen("quick-chat-hotkey", () => {
      console.log("Quick chat hotkey triggered");
      // Focus on quick chat input
    });

    return () => {
      clearInterval(statusInterval);
      unlisten.then((fn) => fn());
    };
  }, [token]);

  const loadRecentData = async () => {
    if (!token) return;

    try {
      setIsLoading(true);
      const data = await invoke<{ agents: AgentSummary[]; canvases: CanvasSummary[] }>(
        "get_recent_items",
        { token }
      );
      setAgents(data.agents);
      setCanvases(data.canvases);
    } catch (error) {
      console.error("Failed to load recent data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const checkConnectionStatus = async () => {
    if (!token) return;

    try {
      const status = await invoke<ConnectionStatus>("get_connection_status", { token });
      setConnectionStatus(status);
    } catch (error) {
      console.error("Failed to check connection status:", error);
      setConnectionStatus({
        status: "error",
        server_time: new Date().toISOString(),
      });
    }
  };

  const handleQuickChat = async (message: string, agentId?: string) => {
    if (!token) return;

    try {
      const response = await invoke<{ success: boolean; response?: string; error?: string }>(
        "quick_chat",
        { token, message, agentId }
      );

      if (response.success) {
        return response.response;
      } else {
        throw new Error(response.error || "Chat failed");
      }
    } catch (error) {
      console.error("Quick chat failed:", error);
      throw error;
    }
  };

  const getMaturityColor = (maturity: string): string => {
    switch (maturity) {
      case "AUTONOMOUS":
        return "autonomous";
      case "SUPERVISED":
        return "supervised";
      case "INTERN":
        return "intern";
      case "STUDENT":
        return "student";
      default:
        return "student";
    }
  };

  return (
    <div className="menubar-container">
      {/* Header */}
      <div className="header">
        <div>
          <h1>Atom</h1>
          <div style={{ fontSize: "11px", color: "#888" }}>
            {user?.first_name} {user?.last_name}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            className={`status-indicator ${connectionStatus.status !== "connected" ? "offline" : ""}`}
            title={connectionStatus.status}
          />
          <button
            onClick={onLogout}
            style={{
              background: "none",
              border: "none",
              color: "#888",
              fontSize: "11px",
              cursor: "pointer",
            }}
          >
            Logout
          </button>
        </div>
      </div>

      {/* Quick Chat */}
      <QuickChat onSend={handleQuickChat} agents={agents} />

      {/* Recent Agents */}
      <div style={{ marginTop: "20px" }}>
        <div className="section-title">Recent Agents</div>
        {isLoading ? (
          <div className="loading">Loading...</div>
        ) : (
          <AgentList agents={agents} getMaturityColor={getMaturityColor} />
        )}
      </div>

      {/* Recent Canvases */}
      <div style={{ marginTop: "20px" }}>
        <div className="section-title">Recent Canvases</div>
        {isLoading ? (
          <div className="loading">Loading...</div>
        ) : (
          <CanvasList canvases={canvases} />
        )}
      </div>

      {/* Keyboard Shortcut Hint */}
      <div
        style={{
          marginTop: "20px",
          padding: "8px 12px",
          background: "#2a2a2a",
          borderRadius: "6px",
          fontSize: "11px",
          color: "#888",
          textAlign: "center",
        }}
      >
        Press <kbd style={{ background: "#444", padding: "2px 6px", borderRadius: "3px" }}>
          ⌘⇧A
        </kbd>{" "}
        to open quick chat
      </div>
    </div>
  );
}
