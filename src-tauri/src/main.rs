#![cfg_attr(
    all(not(debug_assertions), not(target_os = "windows")),
    windows_subsystem = "windows"
)]

use serde_json::json;
use std::collections::HashMap;
use tauri::{api::dialog, AppHandle, Manager, Window};

// Main invoke handler with all commands
#[tauri::command]
async fn atom_invoke_command(
    _app_handle: AppHandle,
    _window: Window,
    command: String,
    params: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    println!(
        "🔧 ATOM Command invoked: {} with params: {:?}",
        command, params
    );

    match command.as_str() {
        // Atom Agent status commands
        "get_atom_agent_status" => Ok(json!({
            "status": "running",
            "agent_name": "Atom AI Assistant",
            "integrations": ["asana"],
            "uptime": "2.5 hours",
            "last_sync": "2024-01-16T10:30:00Z",
            "chat_enabled": true,
            "version": "1.1.0"
        })),

        "get_integrations_health" => Ok(json!({
            "asana": { "connected": true, "last_sync": "5 minutes ago", "chat_available": true },
            "status": "healthy",
            "chat_interface": "enabled"
        })),

        // File dialog commands (for chat attachments)
        "open_file_dialog" => {
            match dialog::blocking::FileDialogBuilder::new()
                .add_filter("All Files", &["*"])
                .add_filter("Text Files", &["txt", "md"])
                .add_filter("Documents", &["pdf", "doc", "docx"])
                .add_filter("Images", &["jpg", "png", "gif", "svg"])
                .pick_file()
            {
                Some(path) => Ok(json!({
                    "success": true,
                    "path": path,
                    "filename": path.file_name().unwrap_or_default().to_string_lossy().to_string()
                })),
                None => Ok(json!({
                    "success": false,
                    "error": "No file selected"
                })),
            }
        }

        // Settings commands
        "open_chat_settings" => Ok(json!({
            "success": true,
            "message": "Chat settings opened"
        })),

        "get_chat_preferences" => Ok(json!({
            "success": true,
            "preferences": {
                "theme": "light",
                "notifications": true,
                "sound": true,
                "auto_save": true,
                "max_messages": 1000,
                "typing_indicators": true
            }
        })),

        // Simple chat command
        "process_chat_message" => {
            let message = match &params {
                Some(p) => p
                    .get("message")
                    .and_then(|m| m.as_str())
                    .unwrap_or("Hello")
                    .to_string(),
                None => "Hello".to_string(),
            };

            Ok(json!({
                "success": true,
                "response": format!("🤖 I received your message: '{}'. This is a demo response from the ATOM desktop app.", message),
                "timestamp": chrono::Utc::now().to_rfc3339()
            }))
        }

        _ => Err(format!("Unknown command: {}", command)),
    }
}

// Main entry point
fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            // Main invoke command
            atom_invoke_command,
        ])
        .setup(|app| {
            println!("🚀 ATOM Desktop Agent Starting...");
            println!("📋 Integrations Loaded:");
            println!("   ✅ Asana");
            println!("   💬 Chat Interface");

            // Initialize global state
            app.manage(std::sync::Mutex::new(
                HashMap::<String, serde_json::Value>::new(),
            ));

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
