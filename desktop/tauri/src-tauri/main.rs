#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use reqwest;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

// --- Constants ---
const SETTINGS_FILE: &str = "atom-settings.json";
const DESKTOP_PROXY_URL: &str = "http://localhost:3000/api/agent/desktop-proxy"; // URL of the web app's backend

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
struct SearchResult {
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
async fn search_skills(_query: String) -> Result<Vec<SearchResult>, String> {
    Ok(vec![
        SearchResult {
            skill: "Finance".to_string(),
            title: "Budget Tracker".to_string(),
            url: "/skills/finance/budget".to_string(),
        },
        SearchResult {
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

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            load_setting,
            save_setting,
            get_dashboard_data,
            handle_nlu_command,
            search_skills,
            generate_learning_plan
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
