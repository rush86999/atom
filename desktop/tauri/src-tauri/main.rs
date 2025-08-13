#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use tauri::{Manager, AppHandle};
use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use aes_gcm::{Aes256Gcm, Key, Nonce};
use aes_gcm::aead::{Aead, NewAead};
use hex::{encode, decode};
use rand::rngs::OsRng;
use rand::RngCore;
use std::fs;
use std::path::PathBuf;
use reqwest;

// --- Constants ---
const ENCRYPTION_KEY: &[u8] = b"a_default_32_byte_encryption_key"; // 32 bytes for AES-256
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

// --- Secure Storage ---
fn get_settings_path(app_handle: &AppHandle) -> PathBuf {
    let mut path = app_handle.path_resolver().app_data_dir().unwrap();
    path.push(SETTINGS_FILE);
    path
}

fn encrypt(text: &str) -> String {
    let key = Key::from_slice(ENCRYPTION_KEY);
    let cipher = Aes256Gcm::new(key);
    let mut nonce_bytes = [0u8; 12];
    OsRng.fill_bytes(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = cipher.encrypt(nonce, text.as_bytes()).unwrap();
    format!("{}:{}", encode(nonce), encode(ciphertext))
}

fn decrypt(encrypted_text: &str) -> Result<String, String> {
    let parts: Vec<&str> = encrypted_text.split(':').collect();
    if parts.len() != 2 {
        return Err("Invalid encrypted text format".to_string());
    }
    let nonce = Nonce::from_slice(&decode(parts[0]).unwrap());
    let ciphertext = decode(parts[1]).unwrap();
    let key = Key::from_slice(ENCRYPTION_KEY);
    let cipher = Aes256Gcm::new(key);
    let plaintext = cipher.decrypt(nonce, ciphertext.as_ref()).map_err(|e| e.to_string())?;
    Ok(String::from_utf8(plaintext).unwrap())
}

#[tauri::command]
fn save_setting(app_handle: AppHandle, key: String, value: String) {
    let path = get_settings_path(&app_handle);
    let mut settings: Settings = match fs::read_to_string(&path) {
        Ok(content) => serde_json::from_str(&content).unwrap_or(Settings { extra: HashMap::new() }),
        Err(_) => Settings { extra: HashMap::new() },
    };
    let encrypted_value = encrypt(&value);
    settings.extra.insert(key, encrypted_value);
    fs::write(&path, serde_json::to_string_pretty(&settings).unwrap()).unwrap();
}

#[tauri::command]
fn get_setting(app_handle: AppHandle, key: String) -> Option<String> {
    let path = get_settings_path(&app_handle);
    if let Ok(content) = fs::read_to_string(&path) {
        if let Ok(settings) = serde_json::from_str::<Settings>(&content) {
            if let Some(encrypted_value) = settings.extra.get(&key) {
                return decrypt(encrypted_value).ok();
            }
        }
    }
    None
}

// --- Main Agent Command ---
#[tauri::command]
async fn send_message_to_agent(message: String, app_handle: AppHandle) -> String {
    let client = reqwest::Client::new();

    // First, get the NLU response from the web backend
    let nlu_response: NluResponse = client
        .post("http://localhost:3000/api/agent/nlu")
        .json(&serde_json::json!({ "message": message }))
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();

    if let Some(intent) = nlu_response.intent {
        if intent == "Browser" {
            if let Some(task) = nlu_response.entities.get("task").and_then(|t| t.as_str()) {
                // Handle the browser skill locally
                let _ = app_handle.shell().open(task, None).await;
                return format!("Opening {} in your browser.", task);
            }
        }
    }

    // For all other intents, gather credentials and call the desktop proxy
    let mut settings_for_proxy = HashMap::new();
    let keys_to_fetch = vec!["notion_api_key", "zapier_webhook_url", "tts_provider", "elevenlabs_api_key", "deepgram_api_key"];
    for key in keys_to_fetch {
        if let Some(value) = get_setting(app_handle.clone(), key.to_string()) {
            settings_for_proxy.insert(key.to_string(), value);
        }
    }

    let response = client
        .post(DESKTOP_PROXY_URL)
        .json(&serde_json::json!({
            "message": message,
            "settings": settings_for_proxy,
        }))
        .send()
        .await
        .unwrap()
        .text()
        .await
        .unwrap();

    response
}

#[tauri::command]
async fn get_project_health_score(app_handle: AppHandle) -> Result<u32, String> {
    let notion_api_key = get_setting(app_handle.clone(), "notion_api_key".to_string());
    let notion_database_id = get_setting(app_handle.clone(), "notion_tasks_database_id".to_string());
    let github_owner = get_setting(app_handle.clone(), "github_owner".to_string());
    let github_repo = get_setting(app_handle.clone(), "github_repo".to_string());
    let slack_channel_id = get_setting(app_handle.clone(), "slack_channel_id".to_string());

    if notion_api_key.is_none() || notion_database_id.is_none() || github_owner.is_none() || github_repo.is_none() || slack_channel_id.is_none() {
        return Err("Notion, GitHub, and Slack credentials are not configured.".to_string());
    }

    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:3000/api/projects/health")
        .json(&serde_json::json!({
            "notionApiKey": notion_api_key.unwrap(),
            "notionDatabaseId": notion_database_id.unwrap(),
            "githubOwner": github_owner.unwrap(),
            "githubRepo": github_repo.unwrap(),
            "slackChannelId": slack_channel_id.unwrap(),
        }))
        .send()
        .await;

    match response {
        Ok(res) => {
            if res.status().is_success() {
                let score_response: serde_json::Value = res.json().await.unwrap();
                Ok(score_response["score"].as_u64().unwrap() as u32)
            } else {
                Err(format!("Failed to get project health score: {}", res.status()))
            }
        }
        Err(err) => Err(format!("Failed to make request to health endpoint: {}", err)),
    }
}

#[tauri::command]
async fn run_competitor_analysis(app_handle: AppHandle, competitors: Vec<String>, notion_database_id: String) -> Result<(), String> {
    let notion_api_key = get_setting(app_handle.clone(), "notion_api_key".to_string());

    if notion_api_key.is_none() {
        return Err("Notion API key is not configured.".to_string());
    }

    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:3000/api/projects/competitor-analysis")
        .json(&serde_json::json!({
            "competitors": competitors,
            "notionDatabaseId": notion_database_id,
            "notionApiKey": notion_api_key.unwrap(),
        }))
        .send()
        .await;

    match response {
        Ok(res) => {
            if res.status().is_success() {
                Ok(())
            } else {
                Err(format!("Failed to run competitor analysis: {}", res.status()))
            }
        }
        Err(err) => Err(format!("Failed to make request to competitor analysis endpoint: {}", err)),
    }
}

#[tauri::command]
async fn generate_learning_plan(app_handle: AppHandle, notion_database_id: String) -> Result<(), String> {
    let notion_api_key = get_setting(app_handle.clone(), "notion_api_key".to_string());

    if notion_api_key.is_none() {
        return Err("Notion API key is not configured.".to_string());
    }

    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:3000/api/projects/learning-plan")
        .json(&serde_json::json!({
            "notionDatabaseId": notion_database_id,
            "notionApiKey": notion_api_key.unwrap(),
        }))
        .send()
        .await;

    match response {
        Ok(res) => {
            if res.status().is_success() {
                Ok(())
            } else {
                Err(format!("Failed to generate learning plan: {}", res.status()))
            }
        }
        Err(err) => Err(format!("Failed to make request to learning plan endpoint: {}", err)),
    }
}

#[tauri::command]
async fn smart_search(query: String) -> Result<Vec<SearchResult>, String> {
    let client = reqwest::Client::new();
    let response = client
        .get(format!("http://localhost:3000/api/smart-search?query={}", query))
        .send()
        .await;

    match response {
        Ok(res) => {
            if res.status().is_success() {
                let search_results: Vec<SearchResult> = res.json().await.unwrap();
                Ok(search_results)
            } else {
                Err(format!("Failed to get search results: {}", res.status()))
            }
        }
        Err(err) => Err(format!("Failed to make request to search endpoint: {}", err)),
    }
}

#[tauri::command]
async fn save_workflow(workflow: Workflow) -> Result<(), String> {
    let client = reqwest::Client::new();
    let response = client
        .post("http://localhost:8003/workflows/")
        .json(&workflow)
        .send()
        .await;

    match response {
        Ok(res) => {
            if res.status().is_success() {
                Ok(())
            } else {
                Err(format!("Failed to save workflow: {}", res.status()))
            }
        }
        Err(err) => Err(format!("Failed to make request to workflow endpoint: {}", err)),
    }
}

#[tauri::command]
async fn get_workflows() -> Result<Vec<Workflow>, String> {
    let client = reqwest::Client::new();
    let response = client
        .get("http://localhost:8003/workflows/")
        .send()
        .await;

    match response {
        Ok(res) => {
            if res.status().is_success() {
                res.json::<Vec<Workflow>>().await.map_err(|e| e.to_string())
            } else {
                Err(format!("Failed to get workflows: {}", res.status()))
            }
        }
        Err(err) => Err(format!("Failed to make request to workflow endpoint: {}", err)),
    }
}

#[tauri::command]
async fn trigger_workflow(workflow_id: String) -> Result<(), String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("http://localhost:8003/workflows/{}/trigger", workflow_id))
        .send()
        .await;

    match response {
        Ok(res) => {
            if res.status().is_success() {
                Ok(())
            } else {
                Err(format!("Failed to trigger workflow: {}", res.status()))
            }
        }
        Err(err) => Err(format!("Failed to make request to workflow endpoint: {}", err)),
    }
}

#[tauri::command]
async fn delete_workflow(workflow_id: String) -> Result<(), String> {
    let client = reqwest::Client::new();
    let response = client
        .delete(format!("http://localhost:8003/workflows/{}", workflow_id))
        .send()
        .await;

    match response {
        Ok(res) => {
            if res.status().is_success() {
                Ok(())
            } else {
                Err(format!("Failed to delete workflow: {}", res.status()))
            }
        }
        Err(err) => Err(format!("Failed to make request to workflow endpoint: {}", err)),
    }
}

#[tauri::command]
async fn update_workflow(workflow_id: String, workflow: Workflow) -> Result<(), String> {
    let client = reqwest::Client::new();
    let response = client
        .put(format!("http://localhost:8003/workflows/{}", workflow_id))
        .json(&workflow)
        .send()
        .await;

    match response {
        Ok(res) => {
            if res.status().is_success() {
                Ok(())
            } else {
                Err(format!("Failed to update workflow: {}", res.status()))
            }
        }
        Err(err) => Err(format!("Failed to make request to workflow endpoint: {}", err)),
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            send_message_to_agent,
            save_setting,
            get_setting,
            get_project_health_score,
            run_competitor_analysis,
            generate_learning_plan,
            smart_search,
            dashboard,
            save_workflow,
            get_workflows,
            trigger_workflow,
            delete_workflow,
            update_workflow
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[tauri::command]
async fn dashboard() -> Result<DashboardData, String> {
    let client = reqwest::Client::new();
    let response = client
        .get("http://localhost:3000/api/dashboard")
        .send()
        .await;

    match response {
        Ok(res) => {
            if res.status().is_success() {
                let dashboard_data: DashboardData = res.json().await.unwrap();
                Ok(dashboard_data)
            } else {
                Err(format!("Failed to get dashboard data: {}", res.status()))
            }
        }
        Err(err) => Err(format!("Failed to make request to dashboard endpoint: {}", err)),
    }
}
