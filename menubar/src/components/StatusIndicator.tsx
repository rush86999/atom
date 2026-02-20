import { useState } from "react";

interface StatusIndicatorProps {
  status: "connected" | "connecting" | "disconnected" | "error";
  agentStatus?: "online" | "busy" | "offline";
  latency?: number;
  onClick?: () => void;
}

interface StatusHistoryEntry {
  status: string;
  timestamp: Date;
  latency?: number;
}

export default function StatusIndicator({
  status,
  agentStatus = "offline",
  latency,
  onClick,
}: StatusIndicatorProps) {
  const [showDetails, setShowDetails] = useState(false);
  const [history] = useState<StatusHistoryEntry[]>([
    { status: "connected", timestamp: new Date(Date.now() - 60000), latency: 45 },
    { status: "connected", timestamp: new Date(Date.now() - 120000), latency: 52 },
    { status: "connecting", timestamp: new Date(Date.now() - 180000) },
    { status: "disconnected", timestamp: new Date(Date.now() - 240000) },
    { status: "connected", timestamp: new Date(Date.now() - 300000), latency: 38 },
  ]);

  const getStatusColor = () => {
    switch (status) {
      case "connected":
        return "#4caf50";
      case "connecting":
        return "#ff9800";
      case "disconnected":
        return "#f44336";
      case "error":
        return "#d32f2f";
      default:
        return "#888";
    }
  };

  const getLatencyColor = () => {
    if (!latency) return "#888";
    if (latency < 100) return "#4caf50"; // good
    if (latency < 300) return "#ff9800"; // degraded
    return "#f44336"; // poor
  };

  const getLatencyLabel = () => {
    if (!latency) return "Unknown";
    if (latency < 100) return "Good";
    if (latency < 300) return "Degraded";
    return "Poor";
  };

  const getAgentStatusColor = () => {
    switch (agentStatus) {
      case "online":
        return "#4caf50";
      case "busy":
        return "#ff9800";
      case "offline":
        return "#888";
      default:
        return "#888";
    }
  };

  const handleHealthCheck = async () => {
    // Trigger health check - this would call the backend
    console.log("Triggering health check...");
    setShowDetails(false);
  };

  const formatTimeAgo = (timestamp: Date) => {
    const seconds = Math.floor((Date.now() - timestamp.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  return (
    <>
      <div
        className="status-indicator-wrapper"
        style={{ position: "relative", display: "inline-block" }}
      >
        {/* Status Dot */}
        <div
          className={`status-indicator status-${status}`}
          style={{
            width: "10px",
            height: "10px",
            borderRadius: "50%",
            backgroundColor: getStatusColor(),
            cursor: onClick ? "pointer" : "default",
            display: "inline-block",
            animation: status === "connecting" ? "pulse 1.5s infinite" : "none",
          }}
          onClick={() => {
            if (onClick) onClick();
            setShowDetails(!showDetails);
          }}
          title={`${status.charAt(0).toUpperCase() + status.slice(1)} - Click for details`}
        />

        {/* Animated pulse for connecting state */}
        {status === "connecting" && (
          <style>{`
            @keyframes pulse {
              0% {
                box-shadow: 0 0 0 0 rgba(255, 152, 0, 0.7);
              }
              70% {
                box-shadow: 0 0 0 6px rgba(255, 152, 0, 0);
              }
              100% {
                box-shadow: 0 0 0 0 rgba(255, 152, 0, 0);
              }
            }
          `}</style>
        )}
      </div>

      {/* Status Details Modal */}
      {showDetails && (
        <div
          className="status-details-modal"
          style={{
            position: "fixed",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            background: "#1e1e1e",
            border: "1px solid #444",
            borderRadius: "8px",
            padding: "20px",
            minWidth: "350px",
            maxWidth: "450px",
            zIndex: 1000,
            boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>Connection Status</h3>
            <button
              onClick={() => setShowDetails(false)}
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

          {/* Current Status */}
          <div style={{ marginBottom: "16px", padding: "12px", background: "#2a2a2a", borderRadius: "6px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
              <div
                style={{
                  width: "12px",
                  height: "12px",
                  borderRadius: "50%",
                  backgroundColor: getStatusColor(),
                }}
              />
              <span style={{ fontWeight: 600, fontSize: "14px" }}>
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </span>
            </div>

            {latency && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "8px" }}>
                <span style={{ fontSize: "12px", color: "#888" }}>Latency:</span>
                <span style={{ color: getLatencyColor(), fontWeight: 600 }}>
                  {latency}ms ({getLatencyLabel()})
                </span>
              </div>
            )}

            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "8px" }}>
              <span style={{ fontSize: "12px", color: "#888" }}>Agent Status:</span>
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  backgroundColor: getAgentStatusColor(),
                }}
              />
              <span style={{ fontWeight: 600, fontSize: "12px" }}>
                {agentStatus.charAt(0).toUpperCase() + agentStatus.slice(1)}
              </span>
            </div>
          </div>

          {/* Status History */}
          <div style={{ marginBottom: "16px" }}>
            <div style={{ fontSize: "12px", color: "#888", marginBottom: "8px" }}>Status History</div>
            <div style={{ background: "#2a2a2a", borderRadius: "6px", padding: "8px" }}>
              {history.map((entry, index) => (
                <div
                  key={index}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "6px 0",
                    borderBottom: index < history.length - 1 ? "1px solid #444" : "none",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div
                      style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "50%",
                        backgroundColor:
                          entry.status === "connected"
                            ? "#4caf50"
                            : entry.status === "connecting"
                            ? "#ff9800"
                            : entry.status === "error"
                            ? "#d32f2f"
                            : "#f44336",
                      }}
                    />
                    <span style={{ fontSize: "12px" }}>
                      {entry.status.charAt(0).toUpperCase() + entry.status.slice(1)}
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    {entry.latency && (
                      <span style={{ fontSize: "11px", color: "#888" }}>{entry.latency}ms</span>
                    )}
                    <span style={{ fontSize: "11px", color: "#888" }}>
                      {formatTimeAgo(entry.timestamp)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={handleHealthCheck}
              className="button"
              style={{ flex: 1, padding: "8px 16px", fontSize: "12px" }}
            >
              Run Health Check
            </button>
            <button
              onClick={() => setShowDetails(false)}
              className="button"
              style={{
                flex: 1,
                padding: "8px 16px",
                fontSize: "12px",
                background: "#444",
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Overlay */}
      {showDetails && (
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
          onClick={() => setShowDetails(false)}
        />
      )}
    </>
  );
}
