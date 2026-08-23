/**
 * Shared inline styles for MenuBar panels — matches the SettingsModal
 * dark theme (#1e1e1e background, #444 borders, #fff text, blue accents).
 *
 * Round 80r-80v panels use these via the `styles` export so they render
 * consistently inside SettingsModal without a CSS file.
 */

export const panelStyles = {
  container: {
    display: "flex" as const,
    flexDirection: "column" as const,
    gap: "8px",
    marginBottom: "16px",
  },
  header: {
    display: "flex" as const,
    alignItems: "center" as const,
    justifyContent: "space-between" as const,
    marginBottom: "4px",
  },
  title: {
    fontSize: "12px",
    fontWeight: 600,
    color: "#888",
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
  },
  count: {
    fontSize: "12px",
    color: "#aaa",
  },
  refreshButton: {
    background: "none",
    border: "none",
    color: "#2196F3",
    cursor: "pointer",
    fontSize: "12px",
    padding: "2px 6px",
  },
  error: {
    fontSize: "12px",
    color: "#f44336",
    padding: "6px 0",
  },
  loading: {
    fontSize: "12px",
    color: "#888",
    padding: "8px 0",
    textAlign: "center" as const,
  },
  empty: {
    fontSize: "12px",
    color: "#666",
    padding: "12px 0",
    textAlign: "center" as const,
    fontStyle: "italic" as const,
  },
  list: {
    listStyle: "none" as const,
    margin: 0,
    padding: 0,
    maxHeight: "240px",
    overflowY: "auto" as const,
  },
  row: {
    display: "flex" as const,
    alignItems: "center" as const,
    justifyContent: "space-between" as const,
    padding: "8px 10px",
    borderBottom: "1px solid #333",
    gap: "8px",
  },
  rowLast: {
    borderBottom: "none",
  },
  name: {
    fontSize: "13px",
    color: "#ddd",
    flex: 1,
    textTransform: "capitalize" as const,
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  badge: {
    fontSize: "10px",
    fontWeight: 600,
    padding: "2px 8px",
    borderRadius: "10px",
    textTransform: "uppercase" as const,
  },
  badgeHealthy: {
    background: "#1b3a28",
    color: "#4caf50",
  },
  badgeUnhealthy: {
    background: "#3a1b1b",
    color: "#f44336",
  },
  actionButton: {
    background: "#2a2a2a",
    border: "1px solid #444",
    borderRadius: "4px",
    color: "#ccc",
    cursor: "pointer",
    fontSize: "11px",
    fontWeight: 600,
    padding: "4px 10px",
    whiteSpace: "nowrap" as const,
  },
  actionButtonDisabled: {
    opacity: 0.5,
    cursor: "default" as const,
  },
  approveButton: {
    background: "#1b3a28",
    borderColor: "#4caf50",
    color: "#4caf50",
  },
  rejectButton: {
    background: "#3a1b1b",
    borderColor: "#f44336",
    color: "#f44336",
  },
  connectButton: {
    background: "#1b283a",
    borderColor: "#2196F3",
    color: "#2196F3",
  },
  confirmation: {
    fontSize: "12px",
    color: "#4caf50",
    padding: "6px 0",
  },
  metaText: {
    fontSize: "11px",
    color: "#777",
  },
};
