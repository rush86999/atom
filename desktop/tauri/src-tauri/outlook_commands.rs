"""
Simplified Outlook commands for Tauri integration
"""

#[tauri::command]
pub async fn get_outlook_oauth_url(
    user_id: String,
) -> Result<HashMap<String, String>, String> {
    // Microsoft OAuth configuration
    let client_id = std::env::var("OUTLOOK_CLIENT_ID")
        .unwrap_or_else(|_| "your_outlook_client_id".to_string());
    let redirect_uri = std::env::var("OUTLOOK_REDIRECT_URI")
        .unwrap_or_else(|_| "http://localhost:3000/oauth/outlook/callback".to_string());
    let tenant_id = std::env::var("OUTLOOK_TENANT_ID")
        .unwrap_or_else(|_| "common".to_string());

    // Build OAuth URL
    let auth_url = format!(
        "https://login.microsoftonline.com/{}/oauth2/v2.0/authorize?client_id={}&redirect_uri={}&response_type=code&scope=https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Calendars.Read https://graph.microsoft.com/User.Read offline_access&state={}&prompt=consent",
        tenant_id,
        client_id,
        redirect_uri,
        format!("outlook_oauth_{}", user_id)
    );

    // Open in default browser
    if let Err(e) = open::that(&auth_url) {
        return Err(format!("Failed to open browser: {}", e));
    }

    let mut response = HashMap::new();
    response.insert("success".to_string(), "true".to_string());
    response.insert("oauth_url".to_string(), auth_url);
    response.insert("service".to_string(), "outlook".to_string());

    Ok(response)
}

#[tauri::command]
pub async fn exchange_outlook_oauth_code(
    code: String,
    state: String,
) -> Result<HashMap<String, String>, String> {
    let client_id = std::env::var("OUTLOOK_CLIENT_ID")
        .unwrap_or_else(|_| "your_outlook_client_id".to_string());
    let client_secret = std::env::var("OUTLOOK_CLIENT_SECRET")
        .unwrap_or_else(|_| "your_outlook_client_secret".to_string());
    let redirect_uri = std::env::var("OUTLOOK_REDIRECT_URI")
        .unwrap_or_else(|_| "http://localhost:3000/oauth/outlook/callback".to_string());
    let tenant_id = std::env::var("OUTLOOK_TENANT_ID")
        .unwrap_or_else(|_| "common".to_string());

    let client = reqwest::Client::new();
    
    // Exchange code for tokens
    let token_response = client
        .post(&format!(
            "https://login.microsoftonline.com/{}/oauth2/v2.0/token",
            tenant_id
        ))
        .form(&[
            ("client_id", &client_id),
            ("client_secret", &client_secret),
            ("code", &code),
            ("grant_type", "authorization_code"),
            ("redirect_uri", &redirect_uri),
            ("scope", "https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Calendars.Read https://graph.microsoft.com/User.Read offline_access"),
        ])
        .send()
        .await
        .map_err(|e| format!("Failed to exchange code: {}", e))?;

    if token_response.status().is_success() {
        let token_data: serde_json::Value = token_response
            .json()
            .await
            .map_err(|e| format!("Failed to parse token response: {}", e))?;

        let mut response = HashMap::new();
        response.insert("success".to_string(), "true".to_string());
        response.insert("access_token".to_string(), token_data["access_token"].as_str().unwrap_or("").to_string());
        
        if let Some(refresh_token) = token_data["refresh_token"].as_str() {
            response.insert("refresh_token".to_string(), refresh_token.to_string());
        }
        
        if let Some(expires_in) = token_data["expires_in"].as_u64() {
            response.insert("expires_in".to_string(), expires_in.to_string());
        }

        Ok(response)
    } else {
        Err("Token exchange failed".to_string())
    }
}

#[tauri::command]
pub async fn get_outlook_connection(
    user_id: String,
) -> Result<HashMap<String, serde_json::Value>, String> {
    // Check if we have valid tokens stored
    // For now, return mock data
    Ok(HashMap::from([
        ("connected".to_string(), serde_json::Value::Bool(false)),
        ("error".to_string(), serde_json::Value::String("No valid tokens found".to_string())),
    ]))
}

#[tauri::command]
pub async fn get_outlook_emails(
    user_id: String,
    limit: Option<usize>,
) -> Result<Vec<HashMap<String, serde_json::Value>>, String> {
    // Mock data for now
    let emails = vec![
        HashMap::from([
            ("id".to_string(), serde_json::Value::String("mock_email_1".to_string())),
            ("subject".to_string(), serde_json::Value::String("Welcome to ATOM".to_string())),
            ("from".to_string(), serde_json::json!({"name": "ATOM Team", "address": "team@atom.ai"})),
            ("body".to_string(), serde_json::Value::String("Thank you for integrating Outlook with ATOM!".to_string())),
            ("receivedDateTime".to_string(), serde_json::Value::String("2025-11-02T10:00:00Z".to_string())),
            ("isRead".to_string(), serde_json::Value::Bool(false)),
            ("importance".to_string(), serde_json::Value::String("high".to_string())),
        ]),
        HashMap::from([
            ("id".to_string(), serde_json::Value::String("mock_email_2".to_string())),
            ("subject".to_string(), serde_json::Value::String("Integration Complete".to_string())),
            ("from".to_string(), serde_json::json!({"name": "System", "address": "noreply@outlook.com"})),
            ("body".to_string(), serde_json::Value::String("Your Outlook integration is ready to use.".to_string())),
            ("receivedDateTime".to_string(), serde_json::Value::String("2025-11-02T09:30:00Z".to_string())),
            ("isRead".to_string(), serde_json::Value::Bool(true)),
            ("importance".to_string(), serde_json::Value::String("normal".to_string())),
        ]),
    ];

    Ok(emails)
}

#[tauri::command]
pub async fn send_outlook_email(
    user_id: String,
    to: Vec<String>,
    subject: String,
    body: String,
    cc: Option<Vec<String>>,
    bcc: Option<Vec<String>>,
) -> Result<HashMap<String, String>, String> {
    // Mock implementation for now
    let mut response = HashMap::new();
    response.insert("success".to_string(), "true".to_string());
    response.insert("message".to_string(), "Email sent successfully".to_string());
    response.insert("subject".to_string(), subject);

    Ok(response)
}

#[tauri::command]
pub async fn get_outlook_calendar_events(
    user_id: String,
    limit: Option<usize>,
) -> Result<Vec<HashMap<String, serde_json::Value>>, String> {
    // Mock data for now
    let events = vec![
        HashMap::from([
            ("id".to_string(), serde_json::Value::String("mock_event_1".to_string())),
            ("subject".to_string(), serde_json::Value::String("Team Meeting".to_string())),
            ("start".to_string(), serde_json::json!({
                "dateTime": "2025-11-03T14:00:00",
                "timeZone": "UTC"
            })),
            ("end".to_string(), serde_json::json!({
                "dateTime": "2025-11-03T15:00:00",
                "timeZone": "UTC"
            })),
            ("location".to_string(), serde_json::Value::String("Conference Room".to_string())),
            ("body".to_string(), serde_json::Value::String("Weekly team sync meeting".to_string())),
        ]),
    ];

    Ok(events)
}

#[tauri::command]
pub async fn create_outlook_calendar_event(
    user_id: String,
    subject: String,
    start_time: String,
    end_time: String,
    body: Option<String>,
    location: Option<String>,
    attendees: Option<Vec<String>>,
) -> Result<HashMap<String, String>, String> {
    // Mock implementation for now
    let mut response = HashMap::new();
    response.insert("success".to_string(), "true".to_string());
    response.insert("message".to_string(), "Calendar event created successfully".to_string());
    response.insert("event_id".to_string(), "mock_event_new".to_string());

    Ok(response)
}

#[tauri::command]
pub async fn disconnect_outlook(
    user_id: String,
) -> Result<HashMap<String, String>, String> {
    // Mock implementation for now
    let mut response = HashMap::new();
    response.insert("success".to_string(), "true".to_string());
    response.insert("message".to_string(), "Outlook disconnected successfully".to_string());

    Ok(response)
}

#[tauri::command]
pub async fn check_outlook_tokens(
    user_id: String,
) -> Result<HashMap<String, serde_json::Value>, String> {
    // Mock implementation for now
    Ok(HashMap::from([
        ("valid".to_string(), serde_json::Value::Bool(false)),
        ("expired".to_string(), serde_json::Value::Bool(true)),
        ("message".to_string(), serde_json::Value::String("No tokens found".to_string())),
    ]))
}

#[tauri::command]
pub async fn refresh_outlook_tokens(
    user_id: String,
    refresh_token: String,
) -> Result<HashMap<String, String>, String> {
    // Mock implementation for now
    let mut response = HashMap::new();
    response.insert("success".to_string(), "true".to_string());
    response.insert("access_token".to_string(), "new_mock_access_token".to_string());
    response.insert("expires_in".to_string(), "3600".to_string());

    Ok(response)
}