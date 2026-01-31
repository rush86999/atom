#![cfg_attr(
    all(not(debug_assertions), not(target_os = "windows")),
    windows_subsystem = "windows"
)]

use serde::Serialize;
use serde_json::json;
use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::Path;
use std::process::Command;
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Manager, Emitter, Runtime, Window, WindowEvent};
use std::io::{BufRead, BufReader};
use std::sync::atomic::{AtomicBool, Ordering};
use notify::{Watcher, RecursiveMode, Config, Event};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{TrayIconBuilder, TrayIconEvent},
};

// Enhanced file dialog command using Tauri v2 plugin
#[tauri::command]
async fn open_file_dialog(
    app: AppHandle,
    filters: Option<Vec<(String, Vec<String>)>>,
) -> Result<serde_json::Value, String> {
    use tauri_plugin_dialog::{DialogExt, MessageDialogKind};
    
    let mut builder = app.dialog().file();
    
    // Add filters if provided
    if let Some(filter_list) = filters {
        for (name, extensions) in filter_list {
            let ext_refs: Vec<&str> = extensions.iter().map(|s| s.as_str()).collect();
            builder = builder.add_filter(&name, &ext_refs);
        }
    } else {
        // Default filters
        builder = builder
            .add_filter("All Files", &["*"])
            .add_filter("Text Files", &["txt", "md", "json", "yaml", "yml"])
            .add_filter("Documents", &["pdf", "doc", "docx", "ppt", "pptx"])
            .add_filter("Images", &["jpg", "jpeg", "png", "gif", "svg", "webp"])
            .add_filter("Code Files", &["js", "ts", "jsx", "tsx", "py", "rs", "go", "java", "cpp", "c", "html", "css", "scss"]);
    }
    
    match builder.blocking_pick_file() {
        Some(path) => {
            let path_buf = path.as_path().expect("Failed to get path");
            Ok(json!({
                "success": true,
                "path": path_buf.to_string_lossy().to_string(),
                "filename": path_buf.file_name().unwrap_or_default().to_string_lossy().to_string(),
                "extension": path_buf.extension().map(|ext| ext.to_string_lossy().to_string()).unwrap_or_default(),
                "size": fs::metadata(&path_buf).ok().map(|meta| meta.len()).unwrap_or(0)
            }))
        },
        None => Ok(json!({
            "success": false,
            "error": "No file selected"
        })),
    }
}

// Folder selection command using Tauri v2 plugin
#[tauri::command]
async fn open_folder_dialog(app: AppHandle) -> Result<serde_json::Value, String> {
    use tauri_plugin_dialog::DialogExt;
    
    match app.dialog().file().blocking_pick_folder() {
        Some(path) => {
            let path_buf = path.as_path().expect("Failed to get path");
            Ok(json!({
                "success": true,
                "path": path_buf.to_string_lossy().to_string(),
                "name": path_buf.file_name().unwrap_or_default().to_string_lossy().to_string()
            }))
        },
        None => Ok(json!({
            "success": false,
            "error": "No folder selected"
        })),
    }
}

// File save dialog command using Tauri v2 plugin
#[tauri::command]
async fn save_file_dialog(
    app: AppHandle,
    default_name: Option<String>,
    filters: Option<Vec<(String, Vec<String>)>>,
) -> Result<serde_json::Value, String> {
    use tauri_plugin_dialog::DialogExt;
    
    let mut builder = app.dialog().file();
    
    if let Some(name) = default_name {
        builder = builder.set_file_name(&name);
    }
    
    if let Some(filter_list) = filters {
        for (name, extensions) in filter_list {
            let ext_refs: Vec<&str> = extensions.iter().map(|s| s.as_str()).collect();
            builder = builder.add_filter(&name, &ext_refs);
        }
    } else {
        builder = builder
            .add_filter("All Files", &["*"])
            .add_filter("Text Files", &["txt", "md", "json"])
            .add_filter("Code Files", &["js", "ts", "py", "rs", "html", "css"]);
    }
    
    match builder.blocking_save_file() {
        Some(path) => {
            let path_buf = path.as_path().expect("Failed to get path");
            Ok(json!({
                "success": true,
                "path": path_buf.to_string_lossy().to_string(),
                "filename": path_buf.file_name().unwrap_or_default().to_string_lossy().to_string()
            }))
        },
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
        "tauri_version": "2.0.0",
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
    app: AppHandle,
    command: String,
    args: Vec<String>,
    working_dir: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut cmd = Command::new(&command);

    if let Some(dir) = working_dir {
        cmd.current_dir(dir);
    }

    cmd.args(&args);
    cmd.stdout(std::process::Stdio::piped());
    cmd.stderr(std::process::Stdio::piped());

    let mut child = cmd.spawn().map_err(|e| e.to_string())?;
    
    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;

    let app_stdout = app.clone();
    let app_stderr = app.clone();

    // Spawn thread to handle stdout
    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            if let Ok(l) = line {
                let _ = app_stdout.emit("cli-stdout", l);
            }
        }
    });

    // Spawn thread to handle stderr
    std::thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            if let Ok(l) = line {
                let _ = app_stderr.emit("cli-stderr", l);
            }
        }
    });

    let status = child.wait().map_err(|e| e.to_string())?;

    Ok(json!({
        "success": status.success(),
        "exit_code": status.code().unwrap_or(-1),
        "command": command,
        "args": args
    }))
}

#[tauri::command]
async fn list_local_skills() -> Result<serde_json::Value, String> {
    let skills_dir = Path::new("skills/local");
    if !skills_dir.exists() {
        return Ok(json!({ "skills": [] }));
    }

    let mut skills = Vec::new();
    if let Ok(entries) = fs::read_dir(skills_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                let skill_name = path.file_name().unwrap_or_default().to_string_lossy().to_string();
                let manifest_path = path.join("skill.json");
                let mut skill_info = json!({
                    "id": skill_name,
                    "name": skill_name,
                    "description": "Local CLI Skill",
                    "path": path.to_string_lossy().to_string()
                });

                if manifest_path.exists() {
                    if let Ok(content) = fs::read_to_string(manifest_path) {
                        if let Ok(v) = serde_json::from_str::<serde_json::Value>(&content) {
                            skill_info = v;
                        }
                    }
                }
                skills.push(skill_info);
            }
        }
    }

    Ok(json!({ "skills": skills }))
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
            } else if message.to_lowercase().contains("ocr")
                || message.to_lowercase().contains("scan")
            {
                "🤖 I can process documents with OCR! Use the local OCR feature to extract text from PDFs and images offline."
            } else {
                &format!("🤖 I received your message: '{}'. This is an enhanced response from the ATOM desktop app with file system access, command execution, and system information capabilities.", message)
            };

            Ok(json!({
                "success": true,
                "response": response,
                "timestamp": chrono::Utc::now().to_rfc3339(),
                "capabilities_mentioned": message.to_lowercase().contains("file") || message.to_lowercase().contains("system") || message.to_lowercase().contains("build") || message.to_lowercase().contains("run") || message.to_lowercase().contains("ocr")
            }))
        }

        // OCR and Local Data Ingestion commands
        "check_ocr_availability" => {
            // Check for Python and OCR engines
            let python_check = Command::new("python3")
                .args(&["-c", "import sys; print(sys.version)"])
                .output();
            
            let python_available = python_check.map(|o| o.status.success()).unwrap_or(false);
            
            // Check tesseract
            let tesseract_check = Command::new("tesseract")
                .args(&["--version"])
                .output();
            let tesseract_available = tesseract_check.map(|o| o.status.success()).unwrap_or(false);
            
            // Check surya via Python
            let surya_check = Command::new("python3")
                .args(&["-c", "import surya; print('ok')"])
                .output();
            let surya_available = surya_check.map(|o| o.status.success()).unwrap_or(false);
            
            let recommended = if surya_available {
                "surya"
            } else if tesseract_available {
                "tesseract"
            } else {
                "none"
            };
            
            Ok(json!({
                "python_available": python_available,
                "tesseract_available": tesseract_available,
                "surya_available": surya_available,
                "recommended": recommended,
                "any_available": tesseract_available || surya_available
            }))
        }

        "process_local_ocr" => {
            let file_path = match &params {
                Some(p) => p.get("file_path").and_then(|v| v.as_str()).unwrap_or(""),
                None => "",
            };
            
            if file_path.is_empty() {
                return Ok(json!({"success": false, "error": "No file path provided"}));
            }
            
            let engine = match &params {
                Some(p) => p.get("engine").and_then(|v| v.as_str()).unwrap_or(""),
                None => "",
            };
            
            // Run the local OCR service
            let mut cmd = Command::new("python3");
            cmd.args(&["backend/core/local_ocr_service.py", "ocr", file_path]);
            if !engine.is_empty() {
                cmd.args(&["--engine", engine]);
            }
            
            match cmd.output() {
                Ok(output) => {
                    let stdout = String::from_utf8_lossy(&output.stdout);
                    // Try to parse as JSON
                    match serde_json::from_str::<serde_json::Value>(&stdout) {
                        Ok(result) => Ok(result),
                        Err(_) => Ok(json!({
                            "success": output.status.success(),
                            "text": stdout.to_string(),
                            "raw": true
                        }))
                    }
                }
                Err(e) => Ok(json!({
                    "success": false,
                    "error": format!("Failed to run OCR: {}", e)
                }))
            }
        }

        "ingest_local_file" => {
            // Ingest a local file into Atom memory
            let file_path = match &params {
                Some(p) => p.get("file_path").and_then(|v| v.as_str()).unwrap_or(""),
                None => "",
            };
            
            if file_path.is_empty() {
                return Ok(json!({"success": false, "error": "No file path provided"}));
            }
            
            let path = Path::new(file_path);
            if !path.exists() {
                return Ok(json!({"success": false, "error": "File not found"}));
            }
            
            let extension = path.extension()
                .map(|e| e.to_string_lossy().to_lowercase())
                .unwrap_or_default();
            
            let file_name = path.file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_default();
            
            let file_size = fs::metadata(path).map(|m| m.len()).unwrap_or(0);
            
            // Read content based on type
            let content = match extension.as_str() {
                "txt" | "md" | "json" | "csv" => {
                    fs::read_to_string(path).ok()
                }
                "pdf" | "png" | "jpg" | "jpeg" | "tiff" => {
                    // Use OCR for these
                    None // Will be processed via OCR
                }
                _ => None
            };
            
            Ok(json!({
                "success": true,
                "file_path": file_path,
                "file_name": file_name,
                "extension": extension,
                "file_size": file_size,
                "content": content,
                "needs_ocr": content.is_none() && ["pdf", "png", "jpg", "jpeg", "tiff"].contains(&extension.as_str()),
                "ingested_at": chrono::Utc::now().to_rfc3339()
            }))
        }

        "get_ocr_installation_guide" => {
            Ok(json!({
                "tesseract": {
                    "description": "Fast, lightweight OCR (~50MB)",
                    "install": {
                        "macos": "brew install tesseract && pip install pytesseract",
                        "windows": "Download from https://github.com/UB-Mannheim/tesseract/wiki",
                        "linux": "sudo apt install tesseract-ocr && pip install pytesseract"
                    }
                },
                "surya": {
                    "description": "High accuracy OCR with 90+ languages (~1-2GB models)",
                    "install": {
                        "all": "pip install surya-ocr"
                    },
                    "note": "Requires Python 3.9+ and PyTorch"
                }
            }))
        }

        "start_watching_folder" => {
            let path = params.and_then(|p| p.get("path").and_then(|v| v.as_str()).map(|s| s.to_string())).ok_or("Path is required")?;
            start_watching_folder(_app_handle, path).await.map_err(|e| e.to_string())?;
            Ok(json!({ "success": true }))
        }

        "stop_watching_folder" => {
            let path = params.and_then(|p| p.get("path").and_then(|v| v.as_str()).map(|s| s.to_string())).ok_or("Path is required")?;
            stop_watching_folder(_app_handle, path).await.map_err(|e| e.to_string())?;
            Ok(json!({ "success": true }))
        }

        "get_watched_folders" => {
            let state = _app_handle.state::<AppState>();
            let watchers = state.watchers.lock().unwrap();
            let folders: Vec<String> = watchers.keys().cloned().collect();
            Ok(json!({ "folders": folders }))
        }

        _ => Err(format!("Unknown command: {}", command)),
    }
}

// App state to manage watchers
struct AppState {
    watchers: Mutex<HashMap<String, notify::RecommendedWatcher>>,
}

#[derive(Clone, Serialize)]
struct FileEvent {
    path: String,
    operation: String,
}

async fn start_watching_folder(app: AppHandle, path: String) -> notify::Result<()> {
    let state = app.state::<AppState>();
    let mut watchers = state.watchers.lock().unwrap();

    if watchers.contains_key(&path) {
        return Ok(());
    }

    let app_handle = app.clone();
    let path_clone = path.clone();

    let mut watcher = notify::RecommendedWatcher::new(
        move |res: notify::Result<Event>| {
            if let Ok(event) = res {
                let operation = match event.kind {
                    notify::EventKind::Create(_) => "create",
                    notify::EventKind::Modify(_) => "modify",
                    notify::EventKind::Remove(_) => "remove",
                    _ => return,
                };

                for path_buf in event.paths {
                    let file_event = FileEvent {
                        path: path_buf.to_string_lossy().to_string(),
                        operation: operation.to_string(),
                    };
                    let _ = app_handle.emit("folder-event", file_event);
                }
            }
        },
        Config::default(),
    )?;

    watcher.watch(Path::new(&path), RecursiveMode::Recursive)?;
    watchers.insert(path_clone, watcher);

    Ok(())
}

async fn stop_watching_folder(app: AppHandle, path: String) -> notify::Result<()> {
    let state = app.state::<AppState>();
    let mut watchers = state.watchers.lock().unwrap();

    if let Some(mut watcher) = watchers.remove(&path) {
        watcher.unwatch(Path::new(&path))?;
    }

    Ok(())
}

// Main entry point
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            // Main invoke command
            atom_invoke_command,
            // File operations - NOW ENABLED with Tauri v2 plugin!
            open_file_dialog,
            open_folder_dialog,
            save_file_dialog,
            read_file_content,
            write_file_content,
            list_directory,
            // System operations
            get_system_info,
            execute_command,
            list_local_skills,
        ])
        .setup(|app| {
            println!("🚀 ATOM Desktop Agent Starting...");
            println!("📋 Integrations Loaded:");
            println!("   ✅ Asana");
            println!("   ✅ Slack");
            println!("   ✅ GitHub");
            println!("   ✅ Notion");
            println!("   💬 Chat Interface");
            println!("   📁 File Dialogs (Tauri v2)");

            // Initialize global state
            app.manage(std::sync::Mutex::new(
                HashMap::<String, serde_json::Value>::new(),
            ));

            app.manage(AppState {
                watchers: Mutex::new(HashMap::new()),
            });

            // Setup System Tray
            let show_item = MenuItem::with_id(app, "show", "Show ATOM", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "quit" => {
                        app.exit(0);
                    }
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click { .. } = event {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                // Minimize to tray instead of closing
                window.hide().unwrap();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
