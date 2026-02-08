use crate::AppState;
use crate::UserSession;
use keyring::{Entry, Error as KeyringError};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::State;
use chrono::{DateTime, Utc};

const API_BASE_URL: &str = "http://localhost:8000"; // Configure as needed
const SERVICE_NAME: &str = "AtomMenuBar";

// ============================================================================
// Data Models
// ============================================================================

#[derive(Debug, Serialize, Deserialize)]
pub struct User {
    pub id: String,
    pub email: String,
    pub first_name: String,
    pub last_name: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LoginRequest {
    pub email: String,
    pub password: String,
    pub device_name: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LoginResponse {
    pub success: bool,
    pub access_token: Option<String>,
    pub device_id: Option<String>,
    pub user: Option<User>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AgentSummary {
    pub id: String,
    pub name: String,
    pub maturity_level: String,
    pub status: String,
    pub last_execution: Option<String>,
    pub execution_count: i32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CanvasSummary {
    pub id: String,
    pub canvas_type: String,
    pub created_at: String,
    pub agent_id: Option<String>,
    pub agent_name: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RecentItemsResponse {
    pub agents: Vec<AgentSummary>,
    pub canvases: Vec<CanvasSummary>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ConnectionStatus {
    pub status: String,
    pub device_id: Option<String>,
    pub last_seen: Option<String>,
    pub server_time: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct QuickChatRequest {
    pub message: String,
    pub agent_id: Option<String>,
    pub context: Option<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct QuickChatResponse {
    pub success: bool,
    pub response: Option<String>,
    pub execution_id: Option<String>,
    pub agent_id: Option<String>,
    pub error: Option<String>,
}

// ============================================================================
// Commands
// ============================================================================

#[tauri::command]
pub async fn login(
    email: String,
    password: String,
    device_name: String,
    state: State<'_, AppState>,
) -> Result<(String, User, String), String> {
    let client = Client::new();

    let request = LoginRequest {
        email: email.clone(),
        password,
        device_name,
    };

    let response = client
        .post(&format!("{}/api/menubar/auth/login", API_BASE_URL))
        .json(&request)
        .send()
        .await
        .map_err(|e| format!("Failed to connect to server: {}", e))?;

    let login_response: LoginResponse = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    if !login_response.success {
        return Err(login_response.error.unwrap_or_else(|| "Login failed".to_string()));
    }

    let token = login_response.access_token.ok_or("No token received")?;
    let user = login_response.user.ok_or("No user data received")?;
    let device_id = login_response.device_id.ok_or("No device ID received")?;

    // Store token securely in keychain
    let entry = Entry::new(SERVICE_NAME, &email)
        .map_err(|e| format!("Keychain error: {}", e))?;
    entry
        .set_password(&token)
        .map_err(|e| format!("Failed to store token: {}", e))?;

    // Update app state
    *state.auth_token.lock().unwrap() = Some(token.clone());
    *state.user_session.lock().unwrap() = Some(UserSession {
        token: token.clone(),
        user_id: user.id.clone(),
        email: email.clone(),
        device_id: device_id.clone(),
    });

    Ok((token, user, device_id))
}

#[tauri::command]
pub async fn logout(state: State<'_, AppState>) -> Result<(), String> {
    // Get session info before clearing
    let session_opt = state.user_session.lock().unwrap().clone();
    if let Some(session) = session_opt {
        // Remove token from keychain
        let entry = Entry::new(SERVICE_NAME, &session.email)
            .map_err(|e| format!("Keychain error: {}", e))?;
        entry
            .delete_password()
            .map_err(|e| format!("Failed to delete token: {}", e))?;
    }

    // Clear app state
    *state.auth_token.lock().unwrap() = None;
    *state.user_session.lock().unwrap() = None;

    Ok(())
}

#[tauri::command]
pub async fn get_session(state: State<'_, AppState>) -> Option<(String, User)> {
    let token = state.auth_token.lock().unwrap().clone()?;
    let session = state.user_session.lock().unwrap().clone()?;

    let user = User {
        id: session.user_id,
        email: session.email,
        first_name: "".to_string(),
        last_name: "".to_string(),
    };

    Some((token, user))
}

#[tauri::command]
pub async fn get_connection_status(
    state: State<'_, AppState>,
) -> Result<ConnectionStatus, String> {
    let token = state
        .auth_token
        .lock()
        .unwrap()
        .clone()
        .ok_or("Not authenticated")?;

    let session = state.user_session.lock().unwrap().clone();
    let device_id = session.as_ref().map(|s| s.device_id.clone());

    let client = Client::new();
    let response = client
        .get(&format!("{}/api/menubar/status", API_BASE_URL))
        .header("Authorization", format!("Bearer {}", token))
        .header("X-Device-ID", device_id.unwrap_or_else(|| "".to_string()))
        .send()
        .await
        .map_err(|e| format!("Failed to connect: {}", e))?;

    let status: ConnectionStatus = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    Ok(status)
}

#[tauri::command]
pub async fn get_recent_items(
    token: String,
    state: State<'_, AppState>,
) -> Result<RecentItemsResponse, String> {
    let client = Client::new();
    let response = client
        .get(&format!("{}/api/menubar/recent", API_BASE_URL))
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
        .map_err(|e| format!("Failed to connect: {}", e))?;

    let items: RecentItemsResponse = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    Ok(items)
}

#[tauri::command]
pub async fn quick_chat(
    token: String,
    message: String,
    agent_id: Option<String>,
    state: State<'_, AppState>,
) -> Result<QuickChatResponse, String> {
    let client = Client::new();

    let request = QuickChatRequest {
        message,
        agent_id,
        context: None,
    };

    let session = state.user_session.lock().unwrap().clone();
    let device_id = session.as_ref().map(|s| s.device_id.clone());

    let mut request_builder = client
        .post(&format!("{}/api/menubar/quick/chat", API_BASE_URL))
        .header("Authorization", format!("Bearer {}", token))
        .json(&request);

    if let Some(device_id) = device_id {
        request_builder = request_builder.header("X-Device-ID", device_id);
    }

    let response = request_builder
        .send()
        .await
        .map_err(|e| format!("Failed to connect: {}", e))?;

    let chat_response: QuickChatResponse = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    Ok(chat_response)
}

#[tauri::command]
pub async fn show_window(window: tauri::Window) -> Result<(), String> {
    window.show().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub async fn hide_window(window: tauri::Window) -> Result<(), String> {
    window.hide().map_err(|e| e.to_string())?;
    Ok(())
}
