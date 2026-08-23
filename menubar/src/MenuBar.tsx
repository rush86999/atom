import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import QuickChat from "./components/QuickChat";
import AgentList from "./components/AgentList";
import CanvasList from "./components/CanvasList";
import StatusIndicator from "./components/StatusIndicator";
import NotificationBadge from "./components/NotificationBadge";
import SettingsModal from "./components/SettingsModal";
import IntegrationsPanel from "./components/IntegrationsPanel";
import WorkflowsPanel from "./components/WorkflowsPanel";
import AnalyticsPanel from "./components/AnalyticsPanel";
import ApprovalsPanel from "./components/ApprovalsPanel";

type MenuTab = "chat" | "agents" | "canvases" | "workflows" | "approvals" | "integrations" | "analytics";
import { getIntegrationHealth } from "../src/services/integrationService";
// Approvals badge: poll count so supervisors see pending HITL items

import AgentDetail from "./components/AgentDetail";
import { useHotkeys } from "./hooks/useHotkeys";
import type { User, AgentSummary, CanvasSummary, ConnectionStatus } from "./types";

interface MenuBarProps {
  user: User | null;
  token: string | null;
  onLogout: () => void;
}

interface Notification {
  id: string;
  type: "message" | "alert" | "update";
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  actionUrl?: string;
}

export default function MenuBar({ user, token, onLogout }: MenuBarProps) {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [canvases, setCanvases] = useState<CanvasSummary[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    status: "disconnected",
    server_time: new Date().toISOString(),
  });
  const [isLoading, setIsLoading] = useState(true);
  const [agentStatus, setAgentStatus] = useState<"online" | "busy" | "offline">("offline");
  const [latency, setLatency] = useState<number | undefined>(undefined);

  // New component states
  const [showSettings, setShowSettings] = useState(false);
  const [pendingApprovalCount, setPendingApprovalCount] = useState(0);
  const [activeTab, setActiveTab] = useState<MenuTab>("agents");
  const [selectedAgent, setSelectedAgent] = useState<AgentSummary | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const hotkeys = useHotkeys();

  useEffect(() => {
    // Load initial data
    loadRecentData();
    loadNotifications();

    // Set up connection status polling
    const statusInterval = setInterval(checkConnectionStatus, 30000); // 30 seconds

    // Listen for global hotkey
    const unlisten = listen("quick-chat-hotkey", () => {
      console.log("Quick chat hotkey triggered");
      // Focus on quick chat input
    });

    // Listen for notification badge updates
    const unlistenBadge = listen<number>("notification-badge", (event) => {
      setUnreadCount(event.payload);
    });

    // Listen for new notifications
    const unlistenNotif = listen<Notification>("notification", (event) => {
      setNotifications((prev) => [event.payload, ...prev].slice(0, 50));
      setUnreadCount((prev) => prev + 1);
    });

    return () => {
      clearInterval(statusInterval);
      unlisten.then((fn) => fn());
      unlistenBadge.then((fn) => fn());
      unlistenNotif.then((fn) => fn());
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
      const startTime = Date.now();
      const status = await invoke<ConnectionStatus>("get_connection_status", { token });
      const endTime = Date.now();

      setConnectionStatus(status);
      setLatency(endTime - startTime);
      setAgentStatus("online");
    } catch (error) {
      console.error("Failed to check connection status:", error);
      setConnectionStatus({
        status: "error",
        server_time: new Date().toISOString(),
      });
      setAgentStatus("offline");
    }
  };

  const loadNotifications = async () => {
    if (!token) return;

    try {
      const notifs = await invoke<Notification[]>("get_unread_notifications");
      setNotifications(notifs);
      setUnreadCount(notifs.filter((n) => !n.read).length);
    } catch (error) {
      console.error("Failed to load notifications:", error);
    }
  };

  const handleMarkNotificationRead = async (id: string) => {
    try {
      await invoke("mark_notification_read", { id });
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (error) {
      console.error("Failed to mark notification as read:", error);
    }
  };

  const handleMarkAllNotificationsRead = async () => {
    try {
      await invoke("mark_all_notifications_read");
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error("Failed to mark all notifications as read:", error);
    }
  };

  const handleDismissNotification = async (id: string) => {
    try {
      await invoke("dismiss_notification", { id });
      setNotifications((prev) => {
        const notification = prev.find((n) => n.id === id);
        const wasUnread = notification?.read === false;
        const updated = prev.filter((n) => n.id !== id);
        if (wasUnread) {
          setUnreadCount((count) => Math.max(0, count - 1));
        }
        return updated;
      });
    } catch (error) {
      console.error("Failed to dismiss notification:", error);
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

  const handleAgentClick = (agent: AgentSummary) => {
    setSelectedAgent(agent);
  };


  // Round 80v: poll pending approvals so the settings button shows a badge
  useEffect(() => {
    let cancelled = false;
    const checkPending = async () => {
      try {
        const session = await invoke<{ token: string } | null>("get_session");
        if (!session?.token || cancelled) return;
        const res = await fetch(
          `${localStorage.getItem("atom_server_url") || "http://localhost:8000"}/api/agent-governance/pending-approvals`,
          { headers: { Authorization: `Bearer ${session.token}` } }
        );
        if (!res.ok || cancelled) return;
        const data = await res.json();
        setPendingApprovalCount(data.count ?? 0);
      } catch {
        // non-fatal — badge stays at current value
      }
    };
    checkPending();
    const interval = setInterval(checkPending, 60_000); // every minute
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  const serverUrl = localStorage.getItem("atom_server_url") || "http://localhost:8000";
  const tabs: Array<{ id: MenuTab; label: string; icon: string; badge?: number }> = [
    { id: "chat", label: "Chat", icon: "💬" },
    { id: "agents", label: "Agents", icon: "🤖" },
    { id: "canvases", label: "Canvas", icon: "🎨" },
    { id: "workflows", label: "Workflows", icon: "⚙️" },
    { id: "approvals", label: "Approvals", icon: "✅", badge: pendingApprovalCount },
    { id: "integrations", label: "Integrations", icon: "🔗" },
    { id: "analytics", label: "Analytics", icon: "📊" },
  ];

  return (
    <div className="menubar-container">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", borderBottom: "1px solid #333" }}>
        <div>
          <div style={{ fontSize: "14px", fontWeight: 700, color: "#fff" }}>Atom</div>
          <div style={{ fontSize: "11px", color: "#888" }}>
            {connectionStatus === ConnectionStatus.CONNECTED ? "Connected" : connectionStatus}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <StatusIndicator status={connectionStatus} />
          <NotificationBadge
            count={unreadCount}
            notifications={notifications}
            onMarkRead={handleMarkNotificationRead}
            onMarkAllRead={handleMarkAllNotificationsRead}
            onDismiss={handleDismissNotification}
          />
          <button
            onClick={() => setShowSettings(true)}
            style={{
              background: "none",
              border: "none",
              color: "#888",
              fontSize: "16px",
              cursor: "pointer",
              padding: "4px",
              position: "relative",
            }}
            title="Settings"
          >
            ⚙️
            {pendingApprovalCount > 0 && (
              <span style={{
                position: "absolute",
                top: "-2px",
                right: "-4px",
                background: "#f44336",
                color: "#fff",
                borderRadius: "50%",
                width: "16px",
                height: "16px",
                fontSize: "10px",
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }} data-testid="approval-badge">{pendingApprovalCount}</span>
            )}
          </button>
        </div>
      </div>

      {/* Tab Bar */}
      <div style={{
        display: "flex",
        overflowX: "auto",
        borderBottom: "1px solid #333",
        background: "#1a1a1a",
      }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1,
              background: activeTab === tab.id ? "#2a2a2a" : "transparent",
              border: "none",
              borderBottom: activeTab === tab.id ? "2px solid #2196F3" : "2px solid transparent",
              color: activeTab === tab.id ? "#fff" : "#888",
              fontSize: "11px",
              fontWeight: activeTab === tab.id ? 600 : 400,
              padding: "8px 4px",
              cursor: "pointer",
              position: "relative",
              whiteSpace: "nowrap",
            }}
            data-testid={`tab-${tab.id}`}
          >
            {tab.icon} {tab.label}
            {tab.badge != null && tab.badge > 0 && (
              <span style={{
                position: "absolute",
                top: "2px",
                right: "2px",
                background: "#f44336",
                color: "#fff",
                borderRadius: "50%",
                width: "14px",
                height: "14px",
                fontSize: "9px",
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}>{tab.badge}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{ padding: "12px", flex: 1, overflowY: "auto" }}>
        {/* Chat Tab */}
        {activeTab === "chat" && (
          <QuickChat
            autoFocus={true}
            onSend={handleQuickChat}
          />
        )}

        {/* Agents Tab */}
        {activeTab === "agents" && (
          <div>
            {isLoading ? (
              <div className="loading">Loading...</div>
            ) : (
              <AgentList
                agents={agents}
                getMaturityColor={getMaturityColor}
                onAgentClick={handleAgentClick}
              />
            )}
          </div>
        )}

        {/* Canvases Tab */}
        {activeTab === "canvases" && (
          <div>
            {isLoading ? (
              <div className="loading">Loading...</div>
            ) : (
              <CanvasList canvases={canvases} />
            )}
          </div>
        )}

        {/* Workflows Tab */}
        {activeTab === "workflows" && (
          <WorkflowsPanel serverUrl={serverUrl} token={token} />
        )}

        {/* Approvals Tab */}
        {activeTab === "approvals" && (
          <ApprovalsPanel serverUrl={serverUrl} token={token} />
        )}

        {/* Integrations Tab */}
        {activeTab === "integrations" && (
          <IntegrationsPanel serverUrl={serverUrl} token={token} />
        )}

        {/* Analytics Tab */}
        {activeTab === "analytics" && (
          <AnalyticsPanel serverUrl={serverUrl} token={token} />
        )}
      </div>

      {/* Keyboard Shortcut Hint */}
      <div style={{
        padding: "6px 12px",
        background: "#2a2a2a",
        borderRadius: "6px",
        fontSize: "10px",
        color: "#666",
        textAlign: "center",
      }}>
        Press{" "}
        <kbd style={{ background: "#444", padding: "2px 5px", borderRadius: "3px" }}>
          {hotkeys.getHotkeyLabel("toggle_window") || "⌘⇧A"}
        </kbd>{" "}
        toggle •{" "}
        <kbd style={{ background: "#444", padding: "2px 5px", borderRadius: "3px" }}>
          {hotkeys.getHotkeyLabel("quick_chat_focus") || "⌘⇧C"}
        </kbd>{" "}
        chat
      </div>

      {/* Settings Modal (config only — feature tabs are above) */}
      <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} onLogout={onLogout} />

      {/* Agent Detail Modal */}
      {selectedAgent && (
        <AgentDetail
          agentId={selectedAgent.id}
          agentName={selectedAgent.name}
          maturityLevel={selectedAgent.maturity_level}
          confidenceScore={0.85}
          capabilities={["Chat", "Automation", "Canvas Presentation", "Workflow Execution"]}
          recentExecutions={[]}
          onClose={() => setSelectedAgent(null)}
          onQuickChat={handleQuickChat}
        />
      )}
    </div>
  );
}
