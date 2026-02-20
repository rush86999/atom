import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import QuickChat from "./components/QuickChat";
import AgentList from "./components/AgentList";
import CanvasList from "./components/CanvasList";
import StatusIndicator from "./components/StatusIndicator";
import NotificationBadge from "./components/NotificationBadge";
import SettingsModal from "./components/SettingsModal";
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
          {/* Status Indicator */}
          <StatusIndicator
            status={connectionStatus.status as any}
            agentStatus={agentStatus}
            latency={latency}
          />

          {/* Notification Badge */}
          <NotificationBadge
            count={unreadCount}
            notifications={notifications}
            onMarkRead={handleMarkNotificationRead}
            onMarkAllRead={handleMarkAllNotificationsRead}
            onDismiss={handleDismissNotification}
          />

          {/* Settings Button */}
          <button
            onClick={() => setShowSettings(true)}
            style={{
              background: "none",
              border: "none",
              color: "#888",
              fontSize: "16px",
              cursor: "pointer",
              padding: "4px",
            }}
            title="Settings"
          >
            ⚙️
          </button>

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
      <QuickChat
        onSend={handleQuickChat}
        agents={agents}
        autoFocus={false}
      />

      {/* Recent Agents */}
      <div style={{ marginTop: "20px" }}>
        <div className="section-title">Recent Agents</div>
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
        Press{" "}
        <kbd style={{ background: "#444", padding: "2px 6px", borderRadius: "3px" }}>
          {hotkeys.getHotkeyLabel("toggle_window") || "⌘⇧A"}
        </kbd>{" "}
        to toggle •{" "}
        <kbd style={{ background: "#444", padding: "2px 6px", borderRadius: "3px" }}>
          {hotkeys.getHotkeyLabel("quick_chat_focus") || "⌘⇧C"}
        </kbd>{" "}
        for chat
      </div>

      {/* Settings Modal */}
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
