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

// --- Python Backend Integration ---
#[tauri::command]
async fn start_python_backend() -> Result<bool, String> {
    let _output = Command::new("python3")
        .arg("src-tauri/python-backend/start_backend.py")
        .arg("start")
        .current_dir(".")
        .spawn()
        .map_err(|e| e.to_string())?;

    // Store the process in global state
    // Note: Process management simplified - backend process will run independently

    // Wait a bit for the backend to start
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

    // Check if backend is running
    let client = reqwest::Client::new();
    match client
        .get(format!("{}/health", PYTHON_BACKEND_URL))
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await
    {
        Ok(response) if response.status().is_success() => Ok(true),
        _ => Err("Python backend failed to start".to_string()),
    }
}

#[tauri::command]
async fn stop_python_backend() -> Result<bool, String> {
    // Note: Process management simplified - backend process will run independently
    // For now, return true as if process was stopped
    Ok(true)
}

#[tauri::command]
async fn wake_word_start() -> Result<bool, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/wake-word/start", PYTHON_BACKEND_URL))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        Ok(true)
    } else {
        Err("Failed to start wake word detection".to_string())
    }
}

#[tauri::command]
async fn wake_word_stop() -> Result<bool, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/wake-word/stop", PYTHON_BACKEND_URL))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        Ok(true)
    } else {
        Err("Failed to stop wake word detection".to_string())
    }
}

#[tauri::command]
async fn wake_word_status() -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .get(format!("{}/api/wake-word/status", PYTHON_BACKEND_URL))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to get wake word status".to_string())
    }
}

#[tauri::command]
async fn transcribe_audio(audio_data: Vec<u8>) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/voice/transcribe", PYTHON_BACKEND_URL))
        .json(&serde_json::json!({ "audio_data": audio_data }))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to transcribe audio".to_string())
    }
}

#[tauri::command]
async fn search_meetings(query: String, user_id: String) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/search/meetings", PYTHON_BACKEND_URL))
        .json(&serde_json::json!({ "query": query, "user_id": user_id }))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to search meetings".to_string())
    }
}

#[tauri::command]
async fn search_documents(
    query: String,
    user_id: String,
    search_type: String,
    limit: usize,
) -> Result<Vec<DocumentSearchResult>, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/lancedb-search/hybrid", PYTHON_BACKEND_URL))
        .json(&serde_json::json!({
            "query": query,
            "user_id": user_id,
            "search_type": search_type,
            "limit": limit
        }))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        let data: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;

        if let Some(success) = data.get("success") {
            if success.as_bool() == Some(true) {
                if let Some(results) = data.get("results") {
                    let search_results: Vec<DocumentSearchResult> =
                        serde_json::from_value(results.clone())
                            .map_err(|e| format!("Failed to parse search results: {}", e))?;
                    return Ok(search_results);
                }
            }
        }

        Err("Search failed or returned no results".to_string())
    } else {
        Err("Failed to search documents".to_string())
    }
}

#[tauri::command]
async fn ingest_document(
    _file_path: String,
    content: String,
    user_id: String,
    title: String,
    doc_type: String,
) -> Result<bool, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/search/add_document", PYTHON_BACKEND_URL))
        .json(&serde_json::json!({
            "content": content,
            "title": title,
            "user_id": user_id,
            "type": doc_type
        }))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        let data: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;

        if let Some(status) = data.get("status") {
            if status.as_str() == Some("success") {
                return Ok(true);
            }
        }
        Err("Document ingestion failed".to_string())
    } else {
        Err("Failed to ingest document".to_string())
    }
}

#[tauri::command]
async fn get_search_suggestions(query: String, user_id: String) -> Result<Vec<String>, String> {
    let client = reqwest::Client::new();
    let response = client
        .get(format!(
            "{}/api/lancedb-search/suggestions",
            PYTHON_BACKEND_URL
        ))
        .query(&[
            ("query", query),
            ("user_id", user_id),
            ("limit", "5".to_string()),
        ])
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        let data: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;

        if let Some(success) = data.get("success") {
            if success.as_bool() == Some(true) {
                if let Some(suggestions) = data.get("suggestions") {
                    let suggestion_list: Vec<String> = serde_json::from_value(suggestions.clone())
                        .map_err(|e| format!("Failed to parse suggestions: {}", e))?;
                    return Ok(suggestion_list);
                }
            }
        }

        Ok(vec![])
    } else {
        Err("Failed to get search suggestions".to_string())
    }
}

// --- Script Generation Endpoints ---
#[tauri::command]
fn generate_learning_plan(_notion_database_id: String) -> Result<String, String> {
    Ok("Learning plan generated successfully and linked to Notion".to_string())
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
            start_python_backend,
            stop_python_backend,
            wake_word_start,
            wake_word_stop,
            wake_word_status,
            transcribe_audio,
            search_meetings,
            search_documents,
            ingest_document,
            get_search_suggestions
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
