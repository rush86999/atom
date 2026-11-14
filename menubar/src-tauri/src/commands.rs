use crate::config;
use crate::AppState;
use crate::UserSession;
use keyring::Entry;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use tauri::State;

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
    /// Second-factor code supplied on the retry after the server reports that
    /// 2FA is required. Omitted entirely on the first attempt.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub totp_code: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LoginResponse {
    pub success: bool,
    pub access_token: Option<String>,
    pub device_id: Option<String>,
    pub user: Option<User>,
    pub error: Option<String>,
    /// True when the password was accepted but a TOTP retry is required.
    #[serde(default)]
    pub two_factor_required: Option<bool>,
}

/// Successful sign-in payload sent to the webview.
///
/// Tauri serializes a tuple return as a JSON array, so the fields are named
/// here to match what `App.tsx` reads (`result.token`, `result.user`,
/// `result.device_id`).
#[derive(Debug, Serialize, Deserialize)]
pub struct LoginSession {
    pub token: String,
    pub user: User,
    pub device_id: String,
}

/// Restored session payload sent to the webview.
///
/// Named for the same reason as [`LoginSession`]: the frontend reads
/// `session.token` / `session.user`, and `device_id` is only part of a fresh
/// sign-in response.
#[derive(Debug, Serialize, Deserialize)]
pub struct SessionInfo {
    pub token: String,
    pub user: User,
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

#[derive(Debug, Serialize, Deserialize)]
pub struct BackendConfig {
    pub http_base_url: String,
    pub websocket_url: String,
    /// `environment` when a loopback/isolation override was supplied,
    /// otherwise `default`.
    pub http_base_url_source: String,
}

// ============================================================================
// Commands
// ============================================================================

/// Extract a human-readable message from an error body.
///
/// The shared middleware returns ``{"error": {"type", "message"}}`` for CSRF
/// and rate-limit refusals, FastAPI returns ``{"detail": ...}``, and the
/// companion sign-in handler returns ``{"error": "..."}``. All three shapes
/// are handled so a refused sign-in never degrades into a parse error.
pub(crate) fn login_error_message(body: &str) -> Option<String> {
    let value: serde_json::Value = serde_json::from_str(body).ok()?;
    for key in ["error", "detail", "message"] {
        if let Some(candidate) = value.get(key) {
            if let Some(message) = candidate.as_str() {
                if !message.trim().is_empty() {
                    return Some(message.to_string());
                }
            }
            if let Some(message) = candidate.get("message").and_then(|m| m.as_str()) {
                if !message.trim().is_empty() {
                    return Some(message.to_string());
                }
            }
        }
    }
    None
}

#[tauri::command]
pub async fn login(
    email: String,
    password: String,
    device_name: String,
    totp_code: Option<String>,
    state: State<'_, AppState>,
) -> Result<LoginSession, String> {
    let client = Client::new();

    let request = LoginRequest {
        email: email.clone(),
        password,
        device_name,
        totp_code,
    };

    let response = client
        .post(config::api_url("/api/menubar/auth/login")?)
        .json(&request)
        .send()
        .await
        .map_err(|e| format!("Failed to connect to server: {}", e))?;

    let status = response.status();
    let body = response
        .text()
        .await
        .map_err(|e| format!("Failed to read response: {}", e))?;

    let login_response: LoginResponse = match serde_json::from_str(&body) {
        Ok(parsed) => parsed,
        Err(parse_error) => {
            return Err(login_error_message(&body).unwrap_or_else(|| {
                format!(
                    "Login failed (HTTP {}): {}",
                    status.as_u16(),
                    parse_error
                )
            }));
        }
    };

    if !login_response.success {
        let fallback = if login_response.two_factor_required.unwrap_or(false) {
            "Two-factor authentication required".to_string()
        } else {
            format!("Login failed (HTTP {})", status.as_u16())
        };
        return Err(login_response.error.unwrap_or(fallback));
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

    Ok(LoginSession {
        token,
        user,
        device_id,
    })
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
            .delete_credential()
            .map_err(|e| format!("Failed to delete token: {}", e))?;
    }

    // Clear app state
    *state.auth_token.lock().unwrap() = None;
    *state.user_session.lock().unwrap() = None;

    Ok(())
}

#[tauri::command]
pub async fn get_session(state: State<'_, AppState>) -> Result<SessionInfo, String> {
    let token = state.auth_token.lock().unwrap().clone()
        .ok_or("Not authenticated")?;
    let session = state.user_session.lock().unwrap().clone()
        .ok_or("No session found")?;

    let user = User {
        id: session.user_id,
        email: session.email,
        first_name: "".to_string(),
        last_name: "".to_string(),
    };

    Ok(SessionInfo { token, user })
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
        .get(config::api_url("/api/menubar/status")?)
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
    _state: State<'_, AppState>,
) -> Result<RecentItemsResponse, String> {
    let client = Client::new();
    let response = client
        .get(config::api_url("/api/menubar/recent")?)
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
        .post(config::api_url("/api/menubar/quick/chat")?)
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

/// Resolve the backend endpoints used by this process.
///
/// Frontend requests consume this so a native `ATOM_BACKEND_URL` override
/// (for an isolated loopback verification backend on another port) also
/// applies to direct browser-side fetches. The default remains
/// `http://localhost:8000`.
///
/// An explicit but invalid override (HTTP or WebSocket) is returned as an
/// error. The frontend must not fall back to the localhost default in that
/// case, because the operator asked for a different endpoint.
#[tauri::command]
pub fn get_backend_config() -> Result<BackendConfig, String> {
    let endpoints = config::resolve_endpoints()?;
    Ok(BackendConfig {
        http_base_url: endpoints.http_base_url,
        websocket_url: endpoints.websocket_url,
        http_base_url_source: endpoints.source.as_str().to_string(),
    })
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
