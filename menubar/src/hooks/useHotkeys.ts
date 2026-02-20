import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";

interface HotkeyConfig {
  toggle_window: string;
  quick_chat_focus: string;
  show_recent_agents: string;
  show_notifications: string;
}

interface HotkeyConflict {
  hotkey: string;
  existing_action: string;
  new_action: string;
}

export function useHotkeys() {
  const [config, setConfig] = useState<HotkeyConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadHotkeys();

    // Listen for hotkey events from Tauri backend
    const unbindFocusQuickChat = listen("focus-quick-chat", () => {
      console.log("Focus quick chat hotkey triggered");
      // Focus on quick chat input
      const textarea = document.querySelector("textarea[placeholder*='Ask Atom']");
      if (textarea instanceof HTMLTextAreaElement) {
        textarea.focus();
      }
    });

    const unbindShowRecentAgents = listen("show-recent-agents", () => {
      console.log("Show recent agents hotkey triggered");
      // Scroll to recent agents section
      const agentsSection = document.querySelector(".section-title")?.parentElement
        ?.querySelectorAll("div")?.[1];
      agentsSection?.scrollIntoView({ behavior: "smooth" });
    });

    const unbindShowNotifications = listen("show-notifications", () => {
      console.log("Show notifications hotkey triggered");
      // Trigger notification badge click
      const notificationBadge = document.querySelector(".notification-badge");
      if (notificationBadge) {
        (notificationBadge as HTMLElement).click();
      }
    });

    return () => {
      unbindFocusQuickChat.then((fn) => fn());
      unbindShowRecentAgents.then((fn) => fn());
      unbindShowNotifications.then((fn) => fn());
    };
  }, []);

  const loadHotkeys = async () => {
    try {
      setIsLoading(true);
      const hotkeyConfig = await invoke<HotkeyConfig>("get_hotkeys");
      setConfig(hotkeyConfig);
    } catch (error) {
      console.error("Failed to load hotkeys:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const updateHotkeys = async (
    newConfig: HotkeyConfig
  ): Promise<{ success: boolean; conflicts?: HotkeyConflict[] }> => {
    try {
      const conflicts = await invoke<HotkeyConflict[]>("update_hotkeys", {
        config: newConfig,
      });

      if (conflicts.length > 0) {
        return { success: false, conflicts };
      }

      setConfig(newConfig);
      return { success: true };
    } catch (error) {
      console.error("Failed to update hotkeys:", error);
      return { success: false };
    }
  };

  const triggerHotkey = async (action: string) => {
    try {
      await invoke("trigger_hotkey", { action });
    } catch (error) {
      console.error("Failed to trigger hotkey:", error);
    }
  };

  const formatHotkeyForDisplay = (hotkey: string): string => {
    return hotkey
      .replace("Cmd", "⌘")
      .replace("Shift", "⇧")
      .replace("Ctrl", "⌃")
      .replace("Alt", "⌥")
      .replace("+", "");
  };

  const getHotkeyLabel = (action: keyof HotkeyConfig): string => {
    if (!config) return "";
    return formatHotkeyForDisplay(config[action]);
  };

  return {
    config,
    isLoading,
    updateHotkeys,
    triggerHotkey,
    formatHotkeyForDisplay,
    getHotkeyLabel,
  };
}

// Hook for listening to specific hotkey events
export function useHotkeyListener(
  event: string,
  callback: () => void,
  deps: React.DependencyList = []
) {
  useEffect(() => {
    let unbind: (() => void) | null = null;

    listen(event, () => {
      callback();
    }).then((fn) => {
      unbind = fn;
    });

    return () => {
      if (unbind) {
        unbind();
      }
    };
  }, deps);
}
