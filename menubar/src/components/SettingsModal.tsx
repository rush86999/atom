import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogout: () => void;
}

interface Settings {
  serverUrl: string;
  autoLaunch: boolean;
  startMinimized: boolean;
  notificationsEnabled: boolean;
  notificationSound: boolean;
  theme: "light" | "dark" | "auto";
  hotkeyToggle: string;
  hotkeyQuickChat: string;
  defaultAgent: string;
}

export default function SettingsModal({ isOpen, onClose, onLogout }: SettingsModalProps) {
  const [settings, setSettings] = useState<Settings>({
    serverUrl: "http://localhost:8000",
    autoLaunch: false,
    startMinimized: false,
    notificationsEnabled: true,
    notificationSound: true,
    theme: "dark",
    hotkeyToggle: "Cmd+Shift+A",
    hotkeyQuickChat: "Cmd+Shift+C",
    defaultAgent: "",
  });

  const [hasChanges, setHasChanges] = useState(false);
  const [cacheCleared, setCacheCleared] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadSettings();
    }
  }, [isOpen]);

  const loadSettings = async () => {
    try {
      // Load settings from Tauri backend or localStorage
      const savedSettings = localStorage.getItem("atom_settings");
      if (savedSettings) {
        setSettings(JSON.parse(savedSettings));
      }
    } catch (error) {
      console.error("Failed to load settings:", error);
    }
  };

  const saveSettings = async () => {
    try {
      // Save to localStorage and Tauri backend
      localStorage.setItem("atom_settings", JSON.stringify(settings));

      // Invoke Tauri command to update settings
      await invoke("update_settings", { settings });
      setHasChanges(false);
      onClose();
    } catch (error) {
      console.error("Failed to save settings:", error);
    }
  };

  const handleSettingChange = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleClearCache = async () => {
    try {
      await invoke("clear_cache");
      setCacheCleared(true);
      setTimeout(() => setCacheCleared(false), 2000);
    } catch (error) {
      console.error("Failed to clear cache:", error);
    }
  };

  const handleLogout = () => {
    onLogout();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <>
      <div
        className="settings-modal"
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          background: "#1e1e1e",
          border: "1px solid #444",
          borderRadius: "8px",
          minWidth: "500px",
          maxWidth: "600px",
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
            alignItems: "center",
          }}
        >
          <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>Settings</h3>
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

        {/* Settings Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
          {/* Server Configuration */}
          <div style={{ marginBottom: "24px" }}>
            <div
              style={{
                fontSize: "12px",
                color: "#888",
                textTransform: "uppercase",
                marginBottom: "8px",
                fontWeight: 600,
              }}
            >
              Server
            </div>
            <div>
              <label style={{ fontSize: "12px", display: "block", marginBottom: "4px" }}>
                Server URL
              </label>
              <input
                type="text"
                value={settings.serverUrl}
                onChange={(e) => handleSettingChange("serverUrl", e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "#2a2a2a",
                  border: "1px solid #444",
                  borderRadius: "6px",
                  color: "#fff",
                  fontSize: "12px",
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>

          {/* Startup */}
          <div style={{ marginBottom: "24px" }}>
            <div
              style={{
                fontSize: "12px",
                color: "#888",
                textTransform: "uppercase",
                marginBottom: "8px",
                fontWeight: 600,
              }}
            >
              Startup
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}>
                <input
                  type="checkbox"
                  checked={settings.autoLaunch}
                  onChange={(e) => handleSettingChange("autoLaunch", e.target.checked)}
                  style={{ cursor: "pointer" }}
                />
                Launch automatically on system startup
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}>
                <input
                  type="checkbox"
                  checked={settings.startMinimized}
                  onChange={(e) => handleSettingChange("startMinimized", e.target.checked)}
                  style={{ cursor: "pointer" }}
                />
                Start minimized to menu bar
              </label>
            </div>
          </div>

          {/* Notifications */}
          <div style={{ marginBottom: "24px" }}>
            <div
              style={{
                fontSize: "12px",
                color: "#888",
                textTransform: "uppercase",
                marginBottom: "8px",
                fontWeight: 600,
              }}
            >
              Notifications
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}>
                <input
                  type="checkbox"
                  checked={settings.notificationsEnabled}
                  onChange={(e) => handleSettingChange("notificationsEnabled", e.target.checked)}
                  style={{ cursor: "pointer" }}
                />
                Enable notifications
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}>
                <input
                  type="checkbox"
                  checked={settings.notificationSound}
                  onChange={(e) => handleSettingChange("notificationSound", e.target.checked)}
                  style={{ cursor: "pointer" }}
                />
                Play notification sound
              </label>
            </div>
          </div>

          {/* Appearance */}
          <div style={{ marginBottom: "24px" }}>
            <div
              style={{
                fontSize: "12px",
                color: "#888",
                textTransform: "uppercase",
                marginBottom: "8px",
                fontWeight: 600,
              }}
            >
              Appearance
            </div>
            <div>
              <label style={{ fontSize: "12px", display: "block", marginBottom: "4px" }}>
                Theme
              </label>
              <select
                value={settings.theme}
                onChange={(e) => handleSettingChange("theme", e.target.value as "light" | "dark" | "auto")}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "#2a2a2a",
                  border: "1px solid #444",
                  borderRadius: "6px",
                  color: "#fff",
                  fontSize: "12px",
                  boxSizing: "border-box",
                }}
              >
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="auto">Auto (System)</option>
              </select>
            </div>
          </div>

          {/* Hotkeys */}
          <div style={{ marginBottom: "24px" }}>
            <div
              style={{
                fontSize: "12px",
                color: "#888",
                textTransform: "uppercase",
                marginBottom: "8px",
                fontWeight: 600,
              }}
            >
              Keyboard Shortcuts
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <div>
                <label style={{ fontSize: "12px", display: "block", marginBottom: "4px" }}>
                  Toggle Menu Bar
                </label>
                <input
                  type="text"
                  value={settings.hotkeyToggle}
                  onChange={(e) => handleSettingChange("hotkeyToggle", e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "#2a2a2a",
                    border: "1px solid #444",
                    borderRadius: "6px",
                    color: "#fff",
                    fontSize: "12px",
                    boxSizing: "border-box",
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: "12px", display: "block", marginBottom: "4px" }}>
                  Quick Chat Focus
                </label>
                <input
                  type="text"
                  value={settings.hotkeyQuickChat}
                  onChange={(e) => handleSettingChange("hotkeyQuickChat", e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "#2a2a2a",
                    border: "1px solid #444",
                    borderRadius: "6px",
                    color: "#fff",
                    fontSize: "12px",
                    boxSizing: "border-box",
                  }}
                />
              </div>
            </div>
          </div>

          {/* Agent */}
          <div style={{ marginBottom: "24px" }}>
            <div
              style={{
                fontSize: "12px",
                color: "#888",
                textTransform: "uppercase",
                marginBottom: "8px",
                fontWeight: 600,
              }}
            >
              Agent
            </div>
            <div>
              <label style={{ fontSize: "12px", display: "block", marginBottom: "4px" }}>
                Default Agent
              </label>
              <input
                type="text"
                value={settings.defaultAgent}
                onChange={(e) => handleSettingChange("defaultAgent", e.target.value)}
                placeholder="Auto-select"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "#2a2a2a",
                  border: "1px solid #444",
                  borderRadius: "6px",
                  color: "#fff",
                  fontSize: "12px",
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>

          {/* Data Management */}
          <div style={{ marginBottom: "24px" }}>
            <div
              style={{
                fontSize: "12px",
                color: "#888",
                textTransform: "uppercase",
                marginBottom: "8px",
                fontWeight: 600,
              }}
            >
              Data
            </div>
            <button
              onClick={handleClearCache}
              style={{
                padding: "8px 16px",
                background: cacheCleared ? "#4caf50" : "#444",
                border: "1px solid #555",
                borderRadius: "6px",
                color: "#fff",
                fontSize: "12px",
                cursor: "pointer",
              }}
            >
              {cacheCleared ? "Cache Cleared!" : "Clear Cache"}
            </button>
          </div>

          {/* About */}
          <div style={{ marginBottom: "24px", padding: "12px", background: "#2a2a2a", borderRadius: "6px" }}>
            <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>
              Atom Menu Bar
            </div>
            <div style={{ fontSize: "11px", color: "#888" }}>
              Version 1.0.0
            </div>
            <div style={{ fontSize: "11px", color: "#888", marginTop: "4px" }}>
              MIT License
            </div>
          </div>

          {/* Logout */}
          <div>
            <button
              onClick={handleLogout}
              style={{
                padding: "8px 16px",
                background: "#d32f2f",
                border: "none",
                borderRadius: "6px",
                color: "#fff",
                fontSize: "12px",
                cursor: "pointer",
                width: "100%",
              }}
            >
              Logout
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
            Cancel
          </button>
          <button
            onClick={saveSettings}
            disabled={!hasChanges}
            className="button"
            style={{
              padding: "8px 16px",
              fontSize: "12px",
              opacity: hasChanges ? 1 : 0.5,
              cursor: hasChanges ? "pointer" : "not-allowed",
            }}
          >
            Save Changes
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
        onClick={onClose}
      />
    </>
  );
}
