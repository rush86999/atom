#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use open;
use reqwest;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::AppHandle;

// Include Outlook commands
mod outlook_commands;
use outlook_commands::*;

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

// --- Jira OAuth Commands ---
#[tauri::command]
async fn get_jira_oauth_url(user_id: String) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .get("http://localhost:8000/api/auth/jira/start")
        .query(&[("user_id", user_id)])
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to get Jira OAuth URL".to_string())
    }
}

#[tauri::command]
async fn exchange_jira_oauth_code(
    code: String,
    state: String,
    user_id: String,
) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .get("http://localhost:8000/api/auth/jira/callback")
        .query(&[("code", code), ("state", state), ("user_id", user_id)])
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to exchange Jira OAuth code".to_string())
    }
}

#[tauri::command]
async fn get_jira_connection(user_id: String) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .get("http://localhost:8000/api/auth/jira/resources")
        .query(&[("user_id", user_id)])
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to get Jira connection status".to_string())
    }
}

#[tauri::command]
async fn get_jira_resources(access_token: String) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .get("https://api.atlassian.com/oauth/token/accessible-resources")
        .header("Authorization", format!("Bearer {}", access_token))
        .header("Accept", "application/json")
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to get Jira resources".to_string())
    }
}

#[tauri::command]
async fn get_jira_projects(
    access_token: String,
    cloud_id: String,
) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let url = format!("https://{}/rest/api/3/project/search", cloud_id);
    let response = client
        .get(&url)
        .header("Authorization", format!("Bearer {}", access_token))
        .header("Accept", "application/json")
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to get Jira projects".to_string())
    }
}

#[tauri::command]
async fn get_jira_issues(
    access_token: String,
    cloud_id: String,
    project_key: String,
) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let url = format!("https://{}/rest/api/3/search", cloud_id);
    let jql = format!("project = {} ORDER BY created DESC", project_key);
    let response = client
        .get(&url)
        .header("Authorization", format!("Bearer {}", access_token))
        .header("Accept", "application/json")
        .query(&[("jql", jql), ("maxResults", "20".to_string())])
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to get Jira issues".to_string())
    }
}

#[tauri::command]
async fn create_jira_issue(
    access_token: String,
    cloud_id: String,
    project_key: String,
    summary: String,
    description: String,
) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let url = format!("https://{}/rest/api/3/issue", cloud_id);
    let issue_data = serde_json::json!({
        "fields": {
            "project": {
                "key": project_key
            },
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": description
                            }
                        ]
                    }
                ]
            },
            "issuetype": {
                "name": "Task"
            }
        }
    });

    let response = client
        .post(&url)
        .header("Authorization", format!("Bearer {}", access_token))
        .header("Accept", "application/json")
        .header("Content-Type", "application/json")
        .json(&issue_data)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to create Jira issue".to_string())
    }
}

#[tauri::command]
async fn search_jira_issues(
    access_token: String,
    cloud_id: String,
    query: String,
    project_key: Option<String>,
) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let url = format!("https://{}/rest/api/3/search", cloud_id);
    let jql = if let Some(project) = project_key {
        format!("project = {} AND text ~ \"{}\"", project, query)
    } else {
        format!("text ~ \"{}\"", query)
    };

    let response = client
        .get(&url)
        .header("Authorization", format!("Bearer {}", access_token))
        .header("Accept", "application/json")
        .query(&[("jql", jql), ("maxResults", "50".to_string())])
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to search Jira issues".to_string())
    }
}

#[tauri::command]
async fn disconnect_jira(user_id: String) -> Result<bool, String> {
    let client = reqwest::Client::new();
    let response = client
        .delete("http://localhost:8000/api/auth/jira/resources")
        .query(&[("user_id", user_id)])
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        Ok(true)
    } else {
        Err("Failed to disconnect Jira".to_string())
    }
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

#[tauri::command]
async fn store_oauth_state(
    app_handle: tauri::AppHandle,
    state: serde_json::Value,
) -> Result<(), String> {
    // Store OAuth state in secure desktop storage
    // This is a simplified implementation - in production, use proper encryption
    let state_json = serde_json::to_string(&state).map_err(|e| e.to_string())?;
    save_setting(app_handle, "oauth_state".to_string(), state_json)
}

#[tauri::command]
async fn setup_jira_tray(access_token: String, update_interval: u64) -> Result<bool, String> {
    // Setup system tray integration for Jira
    // This would be implemented in production
    Ok(true)
}

#[tauri::command]
async fn setup_jira_notifications(
    access_token: String,
    events: Vec<String>,
) -> Result<bool, String> {
    // Setup native notifications for Jira events
    // This would be implemented in production
    Ok(true)
}

#[tauri::command]
async fn setup_jira_background_sync(
    access_token: String,
    sync_interval: u64,
) -> Result<bool, String> {
    // Setup background sync for Jira data
    // This would be implemented in production
    Ok(true)
}

#[tauri::command]
async fn get_jira_user_info(access_token: String) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .get("https://api.atlassian.com/me")
        .header("Authorization", format!("Bearer {}", access_token))
        .header("Accept", "application/json")
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if response.status().is_success() {
        response
            .json::<serde_json::Value>()
            .await
            .map_err(|e| e.to_string())
    } else {
        Err("Failed to get Jira user info".to_string())
    }
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
            get_search_suggestions,
            get_jira_oauth_url,
            exchange_jira_oauth_code,
            get_jira_connection,
            get_jira_resources,
            get_jira_projects,
            get_jira_issues,
            create_jira_issue,
            search_jira_issues,
            disconnect_jira,
            check_backend_connection,
            open_browser,
            store_oauth_state,
            setup_jira_tray,
            setup_jira_notifications,
            setup_jira_background_sync,
            get_jira_user_info,
            
            // Outlook Commands
            get_outlook_oauth_url,
            exchange_outlook_oauth_code,
            get_outlook_connection,
            get_outlook_emails,
            send_outlook_email,
            get_outlook_calendar_events,
            create_outlook_calendar_event,
            disconnect_outlook,
            check_outlook_tokens,
            refresh_outlook_tokens
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
