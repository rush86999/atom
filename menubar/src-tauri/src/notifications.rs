use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, Listener};
use chrono::{DateTime, Utc};

// ============================================================================
// Data Models
// ============================================================================

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Notification {
    pub id: String,
    pub category: NotificationCategory,
    pub title: String,
    pub message: String,
    pub timestamp: DateTime<Utc>,
    pub read: bool,
    pub action_url: Option<String>,
    pub sound: Option<String>,
    pub persistent: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "snake_case")]
pub enum NotificationCategory {
    Agent,
    Workflow,
    System,
    Message,
    Alert,
    Update,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub enum NotificationAction {
    Open,
    Dismiss,
    Snooze { duration_minutes: u64 },
}

#[derive(Debug, Serialize, Deserialize)]
pub struct NotificationStats {
    pub total: usize,
    pub unread: usize,
    pub by_category: HashMap<String, usize>,
}

// ============================================================================
// Notification Store
// ============================================================================

pub struct NotificationStore {
    notifications: Mutex<Vec<Notification>>,
}

impl NotificationStore {
    pub fn new() -> Self {
        Self {
            notifications: Mutex::new(Vec::new()),
        }
    }

    pub fn add(&self, notification: Notification) {
        let mut notifications = self.notifications.lock().unwrap();
        notifications.push(notification);

        // Keep only last 100 notifications
        if notifications.len() > 100 {
            notifications.drain(0..notifications.len() - 100);
        }
    }

    pub fn get_all(&self) -> Vec<Notification> {
        self.notifications.lock().unwrap().clone()
    }

    pub fn get_unread(&self) -> Vec<Notification> {
        self.notifications
            .lock()
            .unwrap()
            .iter()
            .filter(|n| !n.read)
            .cloned()
            .collect()
    }

    pub fn mark_read(&self, id: &str) -> Option<Notification> {
        let mut notifications = self.notifications.lock().unwrap();
        notifications
            .iter_mut()
            .find(|n| n.id == id)
            .map(|n| {
                n.read = true;
                n.clone()
            })
    }

    pub fn mark_all_read(&self) {
        let mut notifications = self.notifications.lock().unwrap();
        for notification in notifications.iter_mut() {
            notification.read = true;
        }
    }

    pub fn remove(&self, id: &str) -> Option<Notification> {
        let mut notifications = self.notifications.lock().unwrap();
        notifications
            .iter()
            .position(|n| n.id == id)
            .map(|pos| notifications.remove(pos))
    }

    pub fn get_stats(&self) -> NotificationStats {
        let notifications = self.notifications.lock().unwrap();
        let total = notifications.len();
        let unread = notifications.iter().filter(|n| !n.read).count();

        let mut by_category: HashMap<String, usize> = HashMap::new();
        for notification in notifications.iter() {
            let category = format!("{:?}", notification.category);
            *by_category.entry(category).or_insert(0) += 1;
        }

        NotificationStats {
            total,
            unread,
            by_category,
        }
    }
}

impl Default for NotificationStore {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Notification Manager
// ============================================================================

pub struct NotificationManager {
    store: NotificationStore,
}

impl NotificationManager {
    pub fn new() -> Self {
        Self {
            store: NotificationStore::new(),
        }
    }

    pub fn store(&self) -> &NotificationStore {
        &self.store
    }

    pub fn notify(
        &self,
        app: &AppHandle,
        notification: Notification,
    ) -> Result<(), String> {
        // Add to store
        self.store.add(notification.clone());

        // Emit notification event to frontend
        app.emit("notification", &notification)
            .map_err(|e| format!("Failed to emit notification event: {}", e))?;

        // Show native notification
        self.show_native_notification(app, &notification)?;

        // Update badge count
        self.update_badge_count(app);

        Ok(())
    }

    pub fn handle_action(
        &self,
        app: &AppHandle,
        id: &str,
        action: NotificationAction,
    ) -> Result<(), String> {
        match action {
            NotificationAction::Open => {
                if let Some(notification) = self.store.mark_read(id) {
                    if let Some(url) = notification.action_url {
                        // Open URL in default browser
                        self.open_url(&url)?;
                    }
                }
            }
            NotificationAction::Dismiss => {
                self.store.remove(id);
            }
            NotificationAction::Snooze { duration_minutes } => {
                // Snooze notification - remove from store and schedule re-delivery
                if let Some(notification) = self.store.remove(id) {
                    // In production, you'd schedule a task to re-deliver after duration
                    // For now, just log it
                    println!(
                        "Snoozed notification {} for {} minutes",
                        id, duration_minutes
                    );
                }
            }
        }

        // Update badge count
        self.update_badge_count(app);

        Ok(())
    }

    fn show_native_notification(
        &self,
        app: &AppHandle,
        notification: &Notification,
    ) -> Result<(), String> {
        // Use Tauri's notification plugin or native OS APIs
        // For now, emit event that frontend can handle
        app.emit("native-notification", notification)
            .map_err(|e| format!("Failed to emit native notification: {}", e))?;

        // Play sound if specified
        if let Some(sound) = &notification.sound {
            self.play_sound(sound)?;
        }

        Ok(())
    }

    fn update_badge_count(&self, app: &AppHandle) {
        let stats = self.store.get_stats();
        app.emit("notification-badge", stats.unread)
            .ok();
    }

    fn play_sound(&self, sound: &str) -> Result<(), String> {
        // Play notification sound
        // In production, use rodio or similar audio library
        println!("Playing sound: {}", sound);
        Ok(())
    }

    fn open_url(&self, url: &str) -> Result<(), String> {
        // Open URL in default browser
        #[cfg(target_os = "macos")]
        {
            std::process::Command::new("open")
                .arg(url)
                .spawn()
                .map_err(|e| format!("Failed to open URL: {}", e))?;
        }

        #[cfg(target_os = "windows")]
        {
            std::process::Command::new("cmd")
                .args(&["/C", "start", "", url])
                .spawn()
                .map_err(|e| format!("Failed to open URL: {}", e))?;
        }

        #[cfg(target_os = "linux")]
        {
            std::process::Command::new("xdg-open")
                .arg(url)
                .spawn()
                .map_err(|e| format!("Failed to open URL: {}", e))?;
        }

        Ok(())
    }
}

impl Default for NotificationManager {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Tauri Commands
// ============================================================================

#[tauri::command]
pub async fn get_notifications() -> Vec<Notification> {
    // Return from store
    // In production, this would be stored in app state
    vec![]
}

#[tauri::command]
pub async fn get_unread_notifications() -> Vec<Notification> {
    // Return unread notifications
    vec![]
}

#[tauri::command]
pub async fn mark_notification_read(id: String) -> Result<bool, String> {
    // Mark notification as read
    Ok(true)
}

#[tauri::command]
pub async fn mark_all_notifications_read() -> Result<(), String> {
    // Mark all notifications as read
    Ok(())
}

#[tauri::command]
pub async fn dismiss_notification(id: String) -> Result<bool, String> {
    // Dismiss notification
    Ok(true)
}

#[tauri::command]
pub async fn get_notification_stats() -> NotificationStats {
    // Return notification statistics
    NotificationStats {
        total: 0,
        unread: 0,
        by_category: HashMap::new(),
    }
}

#[tauri::command]
pub async fn send_notification(
    title: String,
    message: String,
    category: String,
    app: AppHandle,
) -> Result<String, String> {
    // Create and send notification
    let notification = Notification {
        id: uuid::Uuid::new_v4().to_string(),
        category: match category.as_str() {
            "agent" => NotificationCategory::Agent,
            "workflow" => NotificationCategory::Workflow,
            "system" => NotificationCategory::System,
            "message" => NotificationCategory::Message,
            "alert" => NotificationCategory::Alert,
            "update" => NotificationCategory::Update,
            _ => NotificationCategory::System,
        },
        title,
        message,
        timestamp: Utc::now(),
        read: false,
        action_url: None,
        sound: Some("default".to_string()),
        persistent: false,
    };

    let manager = NotificationManager::new();
    manager.notify(&app, notification)?;

    Ok(notification.id)
}
