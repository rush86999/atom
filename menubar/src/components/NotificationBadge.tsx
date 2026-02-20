import { useState } from "react";

interface Notification {
  id: string;
  type: "message" | "alert" | "update";
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  actionUrl?: string;
}

interface NotificationBadgeProps {
  count: number;
  notifications: Notification[];
  onMarkRead?: (id: string) => void;
  onMarkAllRead?: () => void;
  onDismiss?: (id: string) => void;
}

export default function NotificationBadge({
  count,
  notifications,
  onMarkRead,
  onMarkAllRead,
  onDismiss,
}: NotificationBadgeProps) {
  const [showList, setShowList] = useState(false);

  const getBadgeColor = () => {
    const unreadTypes = new Set(
      notifications.filter((n) => !n.read).map((n) => n.type)
    );
    if (unreadTypes.has("alert")) return "#f44336"; // red for alerts
    if (unreadTypes.has("message")) return "#2196f3"; // blue for messages
    return "#ff9800"; // orange for updates
  };

  const getDisplayCount = () => {
    return count > 99 ? "99+" : count.toString();
  };

  const groupedNotifications = {
    messages: notifications.filter((n) => n.type === "message"),
    alerts: notifications.filter((n) => n.type === "alert"),
    updates: notifications.filter((n) => n.type === "update"),
  };

  const handleNotificationClick = (notification: Notification) => {
    if (!notification.read && onMarkRead) {
      onMarkRead(notification.id);
    }
    if (notification.actionUrl) {
      // Open URL in browser
      window.open(notification.actionUrl, "_blank");
    }
    setShowList(false);
  };

  const handleDismiss = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (onDismiss) {
      onDismiss(id);
    }
  };

  const formatTimeAgo = (timestamp: Date) => {
    const seconds = Math.floor((Date.now() - timestamp.getTime()) / 1000);
    if (seconds < 60) return "Just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <>
      {/* Badge */}
      {unreadCount > 0 && (
        <div
          className="notification-badge"
          style={{
            position: "relative",
            display: "inline-block",
            cursor: "pointer",
          }}
          onClick={() => setShowList(!showList)}
        >
          {/* Bell Icon */}
          <div
            style={{
              fontSize: "18px",
              color: "#888",
              padding: "4px",
            }}
          >
            🔔
          </div>

          {/* Badge Count */}
          <div
            style={{
              position: "absolute",
              top: "-4px",
              right: "-4px",
              background: getBadgeColor(),
              color: "#fff",
              fontSize: "10px",
              fontWeight: "bold",
              minWidth: "16px",
              height: "16px",
              borderRadius: "8px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 4px",
            }}
          >
            {getDisplayCount()}
          </div>
        </div>
      )}

      {/* Notification List Modal */}
      {showList && (
        <>
          <div
            className="notification-list-modal"
            style={{
              position: "fixed",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              background: "#1e1e1e",
              border: "1px solid #444",
              borderRadius: "8px",
              minWidth: "380px",
              maxWidth: "450px",
              maxHeight: "600px",
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
                padding: "16px",
                borderBottom: "1px solid #444",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>
                Notifications ({unreadCount})
              </h3>
              <div style={{ display: "flex", gap: "8px" }}>
                {onMarkAllRead && unreadCount > 0 && (
                  <button
                    onClick={() => {
                      onMarkAllRead();
                      setShowList(false);
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#2196f3",
                      fontSize: "12px",
                      cursor: "pointer",
                      padding: "4px 8px",
                    }}
                  >
                    Mark all read
                  </button>
                )}
                <button
                  onClick={() => setShowList(false)}
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

            {/* Notification List */}
            <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
              {notifications.length === 0 ? (
                <div
                  style={{
                    padding: "32px",
                    textAlign: "center",
                    color: "#888",
                    fontSize: "12px",
                  }}
                >
                  No notifications
                </div>
              ) : (
                Object.entries(groupedNotifications).map(([type, notifs]) =>
                  notifs.length > 0 ? (
                    <div key={type} style={{ marginBottom: "16px" }}>
                      {/* Group Header */}
                      <div
                        style={{
                          fontSize: "11px",
                          color: "#888",
                          textTransform: "uppercase",
                          padding: "4px 8px",
                          fontWeight: 600,
                        }}
                      >
                        {type === "messages" ? "Messages" : type === "alerts" ? "Alerts" : "Updates"}
                      </div>

                      {/* Notifications */}
                      {notifs.map((notification) => (
                        <div
                          key={notification.id}
                          onClick={() => handleNotificationClick(notification)}
                          style={{
                            padding: "12px",
                            background: notification.read ? "#1e1e1e" : "#2a2a2a",
                            borderRadius: "6px",
                            marginBottom: "8px",
                            cursor: "pointer",
                            border: notification.read ? "none" : "1px solid #444",
                            position: "relative",
                          }}
                        >
                          {/* Dismiss Button */}
                          {onDismiss && (
                            <button
                              onClick={(e) => handleDismiss(e, notification.id)}
                              style={{
                                position: "absolute",
                                top: "8px",
                                right: "8px",
                                background: "none",
                                border: "none",
                                color: "#888",
                                fontSize: "16px",
                                cursor: "pointer",
                                padding: "0",
                                width: "20px",
                                height: "20px",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                              }}
                            >
                                ×
                            </button>
                          )}

                          {/* Type Indicator */}
                          <div
                            style={{
                              display: "inline-block",
                              width: "6px",
                              height: "6px",
                              borderRadius: "50%",
                              backgroundColor:
                                notification.type === "alert"
                                  ? "#f44336"
                                  : notification.type === "message"
                                  ? "#2196f3"
                                  : "#ff9800",
                              marginRight: "8px",
                            }}
                          />

                          {/* Title */}
                          <div
                            style={{
                              fontSize: "13px",
                              fontWeight: notification.read ? "normal" : "600",
                              marginBottom: "4px",
                              paddingRight: "20px",
                            }}
                          >
                            {notification.title}
                          </div>

                          {/* Message */}
                          <div
                            style={{
                              fontSize: "12px",
                              color: "#aaa",
                              marginBottom: "6px",
                              lineHeight: "1.4",
                            }}
                          >
                            {notification.message}
                          </div>

                          {/* Timestamp */}
                          <div style={{ fontSize: "11px", color: "#888" }}>
                            {formatTimeAgo(notification.timestamp)}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null
                )
              )}
            </div>

            {/* Footer */}
            <div
              style={{
                padding: "12px 16px",
                borderTop: "1px solid #444",
                display: "flex",
                justifyContent: "center",
              }}
            >
              <button
                onClick={() => setShowList(false)}
                className="button"
                style={{ padding: "8px 24px", fontSize: "12px" }}
              >
                Close
              </button>
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
            onClick={() => setShowList(false)}
          />
        </>
      )}
    </>
  );
}
