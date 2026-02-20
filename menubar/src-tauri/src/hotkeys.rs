use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, Listener, Manager};

// ============================================================================
// Data Models
// ============================================================================

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct HotkeyConfig {
    pub toggle_window: String,
    pub quick_chat_focus: String,
    pub show_recent_agents: String,
    pub show_notifications: String,
}

impl Default for HotkeyConfig {
    fn default() -> Self {
        Self {
            toggle_window: "Cmd+Shift+A".to_string(),
            quick_chat_focus: "Cmd+Shift+C".to_string(),
            show_recent_agents: "Cmd+Shift+R".to_string(),
            show_notifications: "Cmd+Shift+N".to_string(),
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct HotkeyConflict {
    pub hotkey: String,
    pub existing_action: String,
    pub new_action: String,
}

// ============================================================================
// Hotkey Manager
// ============================================================================

pub struct HotkeyManager {
    config: Mutex<HotkeyConfig>,
    registered_hotkeys: Mutex<HashMap<String, String>>, // hotkey -> action
}

impl HotkeyManager {
    pub fn new() -> Self {
        Self {
            config: Mutex::new(HotkeyConfig::default()),
            registered_hotkeys: Mutex::new(HashMap::new()),
        }
    }

    pub fn load_config(&self, config: HotkeyConfig) {
        *self.config.lock().unwrap() = config;
    }

    pub fn get_config(&self) -> HotkeyConfig {
        self.config.lock().unwrap().clone()
    }

    pub fn detect_conflicts(&self, new_config: &HotkeyConfig) -> Vec<HotkeyConflict> {
        let mut conflicts = Vec::new();
        let mut hotkey_map: HashMap<String, String> = HashMap::new();

        // Build mapping of hotkeys to actions
        let config = self.config.lock().unwrap();
        hotkey_map.insert(config.toggle_window.clone(), "toggle_window".to_string());
        hotkey_map.insert(config.quick_chat_focus.clone(), "quick_chat_focus".to_string());
        hotkey_map.insert(config.show_recent_agents.clone(), "show_recent_agents".to_string());
        hotkey_map.insert(config.show_notifications.clone(), "show_notifications".to_string());

        // Check for conflicts in new config
        if let Some(existing) = hotkey_map.get(&new_config.toggle_window) {
            if existing != "toggle_window" {
                conflicts.push(HotkeyConflict {
                    hotkey: new_config.toggle_window.clone(),
                    existing_action: existing.clone(),
                    new_action: "toggle_window".to_string(),
                });
            }
        }

        if let Some(existing) = hotkey_map.get(&new_config.quick_chat_focus) {
            if existing != "quick_chat_focus" {
                conflicts.push(HotkeyConflict {
                    hotkey: new_config.quick_chat_focus.clone(),
                    existing_action: existing.clone(),
                    new_action: "quick_chat_focus".to_string(),
                });
            }
        }

        if let Some(existing) = hotkey_map.get(&new_config.show_recent_agents) {
            if existing != "show_recent_agents" {
                conflicts.push(HotkeyConflict {
                    hotkey: new_config.show_recent_agents.clone(),
                    existing_action: existing.clone(),
                    new_action: "show_recent_agents".to_string(),
                });
            }
        }

        if let Some(existing) = hotkey_map.get(&new_config.show_notifications) {
            if existing != "show_notifications" {
                conflicts.push(HotkeyConflict {
                    hotkey: new_config.show_notifications.clone(),
                    existing_action: existing.clone(),
                    new_action: "show_notifications".to_string(),
                });
            }
        }

        conflicts
    }

    pub fn parse_hotkey(hotkey: &str) -> Option<(String, Vec<String>)> {
        let parts: Vec<&str> = hotkey.split('+').collect();
        if parts.is_empty() {
            return None;
        }

        let key = parts.last()?.to_string();
        let mut modifiers = Vec::new();

        for part in parts.iter().take(parts.len() - 1) {
            match part.trim().to_uppercase().as_str() {
                "CMD" | "COMMAND" | "META" => modifiers.push("CMD".to_string()),
                "SHIFT" => modifiers.push("SHIFT".to_string()),
                "CTRL" | "CONTROL" => modifiers.push("CTRL".to_string()),
                "ALT" | "OPTION" => modifiers.push("ALT".to_string()),
                _ => {}
            }
        }

        Some((key, modifiers))
    }

    pub fn register_hotkeys(&self, app: &AppHandle) -> Result<(), String> {
        let config = self.config.lock().unwrap();

        // Note: Tauri 2.0 uses global shortcut plugin
        // This is a placeholder for actual global shortcut registration
        // In production, you'd use tauri-plugin-global-shortcut

        // Emit events for each hotkey action
        // The frontend will listen for these events

        Ok(())
    }
}

impl Default for HotkeyManager {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Tauri Commands
// ============================================================================

#[tauri::command]
pub async fn get_hotkeys() -> HotkeyConfig {
    // In production, load from persistent storage
    HotkeyConfig::default()
}

#[tauri::command]
pub async fn update_hotkeys(config: HotkeyConfig) -> Result<Vec<HotkeyConflict>, String> {
    // Validate for conflicts
    let manager = HotkeyManager::new();
    let conflicts = manager.detect_conflicts(&config);

    if conflicts.is_empty() {
        // In production, save to persistent storage
        Ok(vec![])
    } else {
        Ok(conflicts)
    }
}

#[tauri::command]
pub async fn trigger_hotkey(action: String, app: AppHandle) -> Result<(), String> {
    match action.as_str() {
        "toggle_window" => {
            if let Some(window) = app.get_webview_window("main") {
                if window.is_visible().unwrap_or(false) {
                    window.hide().map_err(|e| e.to_string())?;
                } else {
                    window.show().map_err(|e| e.to_string())?;
                    window.set_focus().map_err(|e| e.to_string())?;
                }
            }
        }
        "quick_chat_focus" => {
            if let Some(window) = app.get_webview_window("main") {
                window.show().map_err(|e| e.to_string())?;
                window.set_focus().map_err(|e| e.to_string())?;
                // Emit event to frontend to focus chat input
                app.emit("focus-quick-chat", ())
                    .map_err(|e| e.to_string())?;
            }
        }
        "show_recent_agents" => {
            if let Some(window) = app.get_webview_window("main") {
                window.show().map_err(|e| e.to_string())?;
                window.set_focus().map_err(|e| e.to_string())?;
                // Emit event to frontend to show recent agents
                app.emit("show-recent-agents", ())
                    .map_err(|e| e.to_string())?;
            }
        }
        "show_notifications" => {
            if let Some(window) = app.get_webview_window("main") {
                window.show().map_err(|e| e.to_string())?;
                window.set_focus().map_err(|e| e.to_string())?;
                // Emit event to frontend to show notifications
                app.emit("show-notifications", ())
                    .map_err(|e| e.to_string())?;
            }
        }
        _ => {
            return Err(format!("Unknown hotkey action: {}", action));
        }
    }

    Ok(())
}
