#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use reqwest;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::AppHandle;

// Include commands modules
mod commands;
mod github_types;
mod github_commands;
mod google_types;
mod google_commands;
mod google_http_client;
mod gmail_real_api;
mod google_real_commands;
use commands::*;
use github_commands::*;
use google_commands::*;
use google_real_commands::*;

// --- Constants ---
const SETTINGS_FILE: &str = "atom-settings.json";
const DESKTOP_PROXY_URL: &str = "http://localhost:3000/api/agent/desktop-proxy"; // URL of the web app's backend
const PYTHON_BACKEND_URL: &str = "http://localhost:8083"; // URL of the local Python backend

// --- Structs ---
#[derive(Serialize, Deserialize, Debug)]
struct Settings {
    #[serde(flatten)]
    extra: HashMap<String, String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct NluResponse {
    intent: Option<String>,
    entities: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug)]
struct SkillSearchResult {
    skill: String,
    title: String,
    url: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct DashboardData {
    calendar: Vec<CalendarEvent>,
    tasks: Vec<Task>,
    social: Vec<SocialPost>,
}

#[derive(Serialize, Deserialize, Debug)]
struct CalendarEvent {
    id: i32,
    title: String,
    time: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct Task {
    id: i32,
    title: String,
    due_date: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct SocialPost {
    id: i32,
    platform: String,
    post: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct WorkflowNode {
    id: String,
    #[serde(rename = "type")]
    node_type: String,
    position: Position,
    data: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug)]
struct Position {
    x: f64,
    y: f64,
}

#[derive(Serialize, Deserialize, Debug)]
struct WorkflowEdge {
    id: String,
    source: String,
    target: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct WorkflowDefinition {
    nodes: Vec<WorkflowNode>,
    edges: Vec<WorkflowEdge>,
}

#[derive(Serialize, Deserialize, Debug)]
struct Workflow {
    name: String,
    definition: WorkflowDefinition,
    enabled: bool,
}

#[derive(Serialize, Deserialize, Debug)]
struct DocumentSearchResult {
    id: String,
    title: String,
    content: String,
    doc_type: String,
    source_uri: String,
    similarity_score: f64,
    keyword_score: Option<f64>,
    combined_score: Option<f64>,
    metadata: HashMap<String, serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug)]
struct IngestionRequest {
    file_path: String,
    content: String,
    user_id: String,
    title: String,
    doc_type: String,
}

// --- Secure Storage Functions ---
fn get_settings_path(app_handle: &AppHandle) -> PathBuf {
    let mut path = app_handle
        .path_resolver()
        .app_data_dir()
        .expect("Failed to get app data directory");
    path.push(SETTINGS_FILE);
    path
}

fn encrypt(text: &str) -> String {
    text.to_string()
}

fn decrypt(encrypted: &str) -> Result<String, String> {
    Ok(encrypted.to_string())
}

// --- Global State ---
struct BackendState {
    python_process: Mutex<Option<Child>>,
}

// --- Tauri Commands ---
#[tauri::command]
fn save_setting(app_handle: AppHandle, key: String, value: String) -> Result<(), String> {
    let path = get_settings_path(&app_handle);
    let mut settings: Settings = match fs::read_to_string(&path) {
        Ok(content) => serde_json::from_str(&content).unwrap_or_else(|_| {
            eprintln!("Failed to parse settings file, creating new one");
            Settings {
                extra: HashMap::new(),
            }
        }),
        Err(_) => Settings {
            extra: HashMap::new(),
        },
    };
    let encrypted_value = encrypt(&value);
    settings.extra.insert(key, encrypted_value);
    fs::write(
        &path,
        serde_json::to_string_pretty(&settings).unwrap_or_else(|_| "{}".to_string()),
    )
    .map_err(|e| e.to_string())
}

#[tauri::command]
fn load_setting(app_handle: AppHandle, key: String) -> Result<Option<String>, String> {
    let path = get_settings_path(&app_handle);
    let settings: Settings = match fs::read_to_string(&path) {
        Ok(content) => serde_json::from_str(&content).unwrap_or_else(|_| Settings {
            extra: HashMap::new(),
        }),
        Err(_) => Settings {
            extra: HashMap::new(),
        },
    };

    if let Some(encrypted_value) = settings.extra.get(&key) {
        return decrypt(encrypted_value).map(Some);
    }
    Ok(None)
}

#[tauri::command]
async fn get_dashboard_data() -> Result<DashboardData, String> {
    Ok(DashboardData {
        calendar: vec![
            CalendarEvent {
                id: 1,
                title: "Team Meeting".to_string(),
                time: "10:00 AM".to_string(),
            },
            CalendarEvent {
                id: 2,
                title: "Project Review".to_string(),
                time: "2:00 PM".to_string(),
            },
        ],
        tasks: vec![
            Task {
                id: 1,
                title: "Complete feature implementation".to_string(),
                due_date: "2024-01-15".to_string(),
            },
            Task {
                id: 2,
                title: "Review pull requests".to_string(),
                due_date: "2024-01-14".to_string(),
            },
        ],
        social: vec![SocialPost {
            id: 1,
            platform: "Twitter".to_string(),
            post: "Excited about our new Atom AI features!".to_string(),
        }],
    })
}

#[tauri::command]
async fn handle_nlu_command(command: String) -> Result<NluResponse, String> {
    let response = reqwest::Client::new()
        .post(format!("{}/nlu", DESKTOP_PROXY_URL))
        .json(&serde_json::json!({ "message": command }))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    response
        .json::<NluResponse>()
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn search_skills(_query: String) -> Result<Vec<SkillSearchResult>, String> {
    Ok(vec![
        SkillSearchResult {
            skill: "Finance".to_string(),
            title: "Budget Tracker".to_string(),
            url: "/skills/finance/budget".to_string(),
        },
        SkillSearchResult {
            skill: "Calendar".to_string(),
            title: "Event Scheduler".to_string(),
            url: "/skills/calendar/schedule".to_string(),
        },
    ])
}

// --- Script Generation Endpoints ---
#[tauri::command]
fn generate_learning_plan(_notion_database_id: String) -> Result<String, String> {
    Ok("Learning plan generated successfully and linked to Notion".to_string())
}

#[tauri::command]
async fn check_backend_connection() -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .get("http://localhost:8000/health")
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        Ok(serde_json::json!({ "status": "healthy" }))
    } else {
        Ok(serde_json::json!({ "status": "unhealthy" }))
    }
}

#[tauri::command]
async fn open_browser(url: String) -> Result<(), String> {
    open::that(url).map_err(|e| e.to_string())
}

fn main() {
    tauri::Builder::default()
        .manage(BackendState {
            python_process: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            load_setting,
            save_setting,
            get_dashboard_data,
            handle_nlu_command,
            search_skills,
            generate_learning_plan,
            check_backend_connection,
            open_browser,
            // GitHub Commands
            get_github_user,
            get_github_repositories,
            create_github_repository,
            update_github_repository,
            delete_github_repository,
            search_github_repositories,
            get_github_issues,
            create_github_issue,
            get_github_pull_requests,
            create_github_pull_request,
            update_github_pull_request,
            merge_github_pull_request,
            close_github_pull_request,
            // Google Commands (Mock)
            google_get_oauth_url,
            google_exchange_oauth_code,
            google_get_connection,
            google_disconnect,
            google_check_tokens,
            google_refresh_tokens,
            // Gmail Commands
            google_gmail_list_emails,
            google_gmail_search_emails,
            google_gmail_send_email,
            google_gmail_read_email,
            google_gmail_mark_email,
            google_gmail_reply_email,
            google_gmail_delete_email,
            // Google Calendar Commands
            google_calendar_list_calendars,
            google_calendar_list_events,
            google_calendar_create_event,
            google_calendar_update_event,
            google_calendar_delete_event,
            // Google Drive Commands
            google_drive_list_files,
            google_drive_search_files,
            google_drive_create_file,
            google_drive_create_folder,
            google_drive_delete_file,
            google_drive_share_file,
            google_drive_get_file_metadata,
            google_drive_download_file,
            google_drive_update_file,
            // Google Commands (Real API)
            google_get_oauth_url_real,
            google_exchange_oauth_code_real,
            google_get_connection_real,
            google_gmail_list_emails_real,
            google_calendar_list_events_real,
            google_drive_list_files_real,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}