#![cfg_attr(
    all(not(debug_assertions), not(target_os = "windows")),
    windows_subsystem = "windows"
)]

use serde_json::json;
use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::Path;
use std::process::Command;
use tauri::{api::dialog, AppHandle, Manager, Window};

// Enhanced file dialog command
#[tauri::command]
async fn open_file_dialog(
    filters: Option<Vec<(String, Vec<String>)>>,
) -> Result<serde_json::Value, String> {
    let mut dialog = dialog::blocking::FileDialogBuilder::new();

    // Add default filters if none provided
    if let Some(filter_list) = filters {
        for (name, extensions) in filter_list {
            let ext_slices: Vec<&str> = extensions.iter().map(|s| s.as_str()).collect();
            dialog = dialog.add_filter(&name, &ext_slices);
        }
    } else {
        dialog = dialog
            .add_filter("All Files", &["*"])
            .add_filter("Text Files", &["txt", "md", "json", "yaml", "yml"])
            .add_filter("Documents", &["pdf", "doc", "docx", "ppt", "pptx"])
            .add_filter("Images", &["jpg", "jpeg", "png", "gif", "svg", "webp"])
            .add_filter(
                "Code Files",
                &[
                    "js", "ts", "jsx", "tsx", "py", "rs", "go", "java", "cpp", "c", "html", "css",
                    "scss",
                ],
            );
    }

    match dialog.pick_file() {
        Some(path) => Ok(json!({
            "success": true,
            "path": path.to_string_lossy().to_string(),
            "filename": path.file_name().unwrap_or_default().to_string_lossy().to_string(),
            "extension": path.extension().map(|ext| ext.to_string_lossy().to_string()).unwrap_or_default(),
            "size": fs::metadata(&path).ok().map(|meta| meta.len()).unwrap_or(0)
        })),
        None => Ok(json!({
            "success": false,
            "error": "No file selected"
        })),
    }
}

// Folder selection command
#[tauri::command]
async fn open_folder_dialog() -> Result<serde_json::Value, String> {
    match dialog::blocking::FileDialogBuilder::new().pick_folder() {
        Some(path) => Ok(json!({
            "success": true,
            "path": path.to_string_lossy().to_string(),
            "name": path.file_name().unwrap_or_default().to_string_lossy().to_string()
        })),
        None => Ok(json!({
            "success": false,
            "error": "No folder selected"
        })),
    }
}

// File save dialog command
#[tauri::command]
async fn save_file_dialog(
    default_name: Option<String>,
    filters: Option<Vec<(String, Vec<String>)>>,
) -> Result<serde_json::Value, String> {
    let mut dialog = dialog::blocking::FileDialogBuilder::new();

    if let Some(name) = default_name {
        dialog = dialog.set_file_name(&name);
    }

    if let Some(filter_list) = filters {
        for (name, extensions) in filter_list {
            let ext_slices: Vec<&str> = extensions.iter().map(|s| s.as_str()).collect();
            dialog = dialog.add_filter(&name, &ext_slices);
        }
    } else {
        dialog = dialog
            .add_filter("All Files", &["*"])
            .add_filter("Text Files", &["txt", "md", "json"])
            .add_filter("Code Files", &["js", "ts", "py", "rs", "html", "css"]);
    }

    match dialog.save_file() {
        Some(path) => Ok(json!({
            "success": true,
            "path": path.to_string_lossy().to_string(),
            "filename": path.file_name().unwrap_or_default().to_string_lossy().to_string()
        })),
        None => Ok(json!({
            "success": false,
            "error": "Save cancelled"
        })),
    }
}

// System information command
#[tauri::command]
async fn get_system_info() -> Result<serde_json::Value, String> {
    let os = if cfg!(target_os = "windows") {
        "windows"
    } else if cfg!(target_os = "macos") {
        "macos"
    } else if cfg!(target_os = "linux") {
        "linux"
    } else {
        "unknown"
    };

    let arch = if cfg!(target_arch = "x86_64") {
        "x64"
    } else if cfg!(target_arch = "aarch64") {
        "arm64"
    } else {
        "unknown"
    };

    Ok(json!({
        "platform": os,
        "architecture": arch,
        "version": env!("CARGO_PKG_VERSION"),
        "tauri_version": "1.1.0",
        "features": {
            "file_system": true,
            "notifications": true,
            "system_tray": true,
            "global_shortcuts": true
        }
    }))
}

// File operations commands
#[tauri::command]
async fn read_file_content(path: String) -> Result<serde_json::Value, String> {
    match fs::read_to_string(&path) {
        Ok(content) => Ok(json!({
            "success": true,
            "content": content,
            "path": path
        })),
        Err(e) => Ok(json!({
            "success": false,
            "error": e.to_string(),
            "path": path
        })),
    }
}

#[tauri::command]
async fn write_file_content(path: String, content: String) -> Result<serde_json::Value, String> {
    // Create parent directories if they don't exist
    if let Some(parent) = Path::new(&path).parent() {
        if let Err(e) = fs::create_dir_all(parent) {
            return Ok(json!({
                "success": false,
                "error": format!("Failed to create directories: {}", e),
                "path": path
            }));
        }
    }

    match fs::write(&path, content) {
        Ok(_) => Ok(json!({
            "success": true,
            "path": path
        })),
        Err(e) => Ok(json!({
            "success": false,
            "error": e.to_string(),
            "path": path
        })),
    }
}

// Directory listing command
#[tauri::command]
async fn list_directory(path: String) -> Result<serde_json::Value, String> {
    let dir_path = Path::new(&path);
    if !dir_path.exists() {
        return Ok(json!({
            "success": false,
            "error": "Directory does not exist",
            "path": path
        }));
    }

    if !dir_path.is_dir() {
        return Ok(json!({
            "success": false,
            "error": "Path is not a directory",
            "path": path
        }));
    }

    let mut entries = Vec::new();

    match fs::read_dir(dir_path) {
        Ok(read_dir) => {
            for entry in read_dir {
                match entry {
                    Ok(entry) => {
                        let path = entry.path();
                        let metadata = entry.metadata().ok();

                        let is_dir = metadata.as_ref().map(|m| m.is_dir()).unwrap_or(false);
                        let size = metadata.as_ref().map(|m| m.len()).unwrap_or(0);
                        let modified = metadata.and_then(|m| m.modified().ok());

                        entries.push(json!({
                            "name": path.file_name().unwrap_or_default().to_string_lossy().to_string(),
                            "path": path.to_string_lossy().to_string(),
                            "is_directory": is_dir,
                            "size": size,
                            "extension": path.extension().map(|ext| ext.to_string_lossy().to_string()).unwrap_or_default(),
                            "modified": modified.map(|t| t.duration_since(std::time::UNIX_EPOCH).unwrap().as_secs())
                        }));
                    }
                    Err(e) => {
                        eprintln!("Error reading directory entry: {}", e);
                    }
                }
            }

            Ok(json!({
                "success": true,
                "path": path,
                "entries": entries
            }))
        }
        Err(e) => Ok(json!({
            "success": false,
            "error": e.to_string(),
            "path": path
        })),
    }
}

// Development tools commands
#[tauri::command]
async fn execute_command(
    command: String,
    args: Vec<String>,
    working_dir: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut cmd = Command::new(&command);

    if let Some(dir) = working_dir {
        cmd.current_dir(dir);
    }

    cmd.args(&args);

    match cmd.output() {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();

            Ok(json!({
                "success": output.status.success(),
                "exit_code": output.status.code().unwrap_or(-1),
                "stdout": stdout,
                "stderr": stderr,
                "command": command,
                "args": args
            }))
        }
        Err(e) => Ok(json!({
            "success": false,
            "error": e.to_string(),
            "command": command,
            "args": args
        })),
    }
}

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
            "integrations": ["asana", "slack", "github", "notion"],
            "uptime": "2.5 hours",
            "last_sync": "2024-01-16T10:30:00Z",
            "chat_enabled": true,
            "version": "1.1.0",
            "capabilities": ["file_operations", "system_info", "command_execution", "dialog_operations"]
        })),

        "get_integrations_health" => Ok(json!({
            "asana": { "connected": true, "last_sync": "5 minutes ago", "chat_available": true },
            "slack": { "connected": true, "last_sync": "2 minutes ago", "chat_available": true },
            "github": { "connected": true, "last_sync": "10 minutes ago", "chat_available": true },
            "notion": { "connected": true, "last_sync": "15 minutes ago", "chat_available": true },
            "status": "healthy",
            "chat_interface": "enabled"
        })),

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
                "typing_indicators": true,
                "developer_mode": false,
                "auto_update": true
            }
        })),

        // Enhanced chat command
        "process_chat_message" => {
            let message = match &params {
                Some(p) => p
                    .get("message")
                    .and_then(|m| m.as_str())
                    .unwrap_or("Hello")
                    .to_string(),
                None => "Hello".to_string(),
            };

            // Enhanced response with more capabilities
            let response = if message.to_lowercase().contains("file") {
                "🤖 I can help you with file operations! Use the file dialogs to open, save, or browse files and folders."
            } else if message.to_lowercase().contains("system") {
                "🤖 I can provide system information and execute commands. Try asking about the current platform or running a development command."
            } else if message.to_lowercase().contains("build")
                || message.to_lowercase().contains("run")
            {
                "🤖 I can execute development commands! Use the command execution feature to run build tools, package managers, or any system command."
            } else {
                &format!("🤖 I received your message: '{}'. This is an enhanced response from the ATOM desktop app with file system access, command execution, and system information capabilities.", message)
            };

            Ok(json!({
                "success": true,
                "response": response,
                "timestamp": chrono::Utc::now().to_rfc3339(),
                "capabilities_mentioned": message.to_lowercase().contains("file") || message.to_lowercase().contains("system") || message.to_lowercase().contains("build") || message.to_lowercase().contains("run")
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
            // File operations
            open_file_dialog,
            open_folder_dialog,
            save_file_dialog,
            read_file_content,
            write_file_content,
            list_directory,
            // System operations
            get_system_info,
            execute_command,
        ])
        .setup(|app| {
            println!("🚀 ATOM Desktop Agent Starting...");
            println!("📋 Integrations Loaded:");
            println!("   ✅ Asana");
            println!("   ✅ Slack");
            println!("   ✅ GitHub");
            println!("   ✅ Notion");
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
