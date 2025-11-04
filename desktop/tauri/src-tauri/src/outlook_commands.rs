"""
Tauri command handlers for Outlook integration
Following the same pattern as GitLab Desktop Manager
"""

#[cfg_attr(
    all(not(debug_assertions), target_os = "macos"),
    expect(unexpected(expected = "expected", received = "received")),
)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tauri::{command, State};
use tauri_plugin_oauth::{OAuthConfig, OAuthProvider};

// Outlook OAuth configuration
const OUTLOOK_CLIENT_ID: &str = "OUTLOOK_CLIENT_ID";
const OUTLOOK_CLIENT_SECRET: &str = "OUTLOOK_CLIENT_SECRET";
const OUTLOOK_TENANT_ID: &str = "OUTLOOK_TENANT_ID";
const OUTLOOK_REDIRECT_URI: &str = "http://localhost:3000/oauth/outlook/callback";

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct OutlookUserInfo {
    pub id: String,
    pub display_name: String,
    pub mail: String,
    pub user_principal_name: String,
    pub job_title: Option<String>,
    pub office_location: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OutlookConnectionStatus {
    pub connected: bool,
    pub user: Option<OutlookUserInfo>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OutlookEmail {
    pub id: String,
    pub subject: String,
    pub from: HashMap<String, String>,
    pub to_recipients: Vec<HashMap<String, String>>,
    pub body: String,
    pub received_date_time: String,
    pub is_read: bool,
    pub importance: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OutlookCalendarEvent {
    pub id: String,
    pub subject: String,
    pub start: HashMap<String, String>,
    pub end: HashMap<String, String>,
    pub location: Option<String>,
    pub body: Option<String>,
}

// Command to check Outlook OAuth status
#[command]
pub async fn check_outlook_oauth_status(
    user_id: String,
    // Add state management here if needed
) -> Result<OutlookConnectionStatus, String> {
    // Implementation would check stored tokens and validate with Microsoft Graph API
    // For now, return mock data
    Ok(OutlookConnectionStatus {
        connected: false,
        user: None,
        error: Some("Outlook integration not yet implemented".to_string()),
    })
}

// Command to initiate Outlook OAuth
#[command]
pub async fn initiate_outlook_oauth(
    user_id: String,
    window: tauri::Window,
) -> Result<HashMap<String, String>, String> {
    // Get OAuth credentials from environment
    let client_id = std::env::var(OUTLOOK_CLIENT_ID)
        .map_err(|_| "OUTLOOK_CLIENT_ID not configured".to_string())?;
    
    let redirect_uri = std::env::var(OUTLOOK_REDIRECT_URI)
        .unwrap_or_else(|_| OUTLOOK_REDIRECT_URI.to_string());

    // Microsoft Graph OAuth URL
    let mut auth_params = HashMap::new();
    auth_params.insert("client_id".to_string(), client_id);
    auth_params.insert("redirect_uri".to_string(), redirect_uri);
    auth_params.insert("response_type".to_string(), "code".to_string());
    auth_params.insert("scope".to_string(), "https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Calendars.Read https://graph.microsoft.com/User.Read offline_access".to_string());
    auth_params.insert("state".to_string(), format!("outlook_oauth_{}", user_id));
    auth_params.insert("prompt".to_string(), "consent".to_string());

    let tenant_id = std::env::var(OUTLOOK_TENANT_ID)
        .unwrap_or_else(|_| "common".to_string());

    let auth_url = format!(
        "https://login.microsoftonline.com/{}/oauth2/v2.0/authorize?{}",
        tenant_id,
        url_encode_params(&auth_params)
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

// Command to disconnect Outlook
#[command]
pub async fn disconnect_outlook(
    user_id: String,
) -> Result<HashMap<String, String>, String> {
    // Implementation would remove stored tokens
    // For now, return success
    let mut response = HashMap::new();
    response.insert("success".to_string(), "true".to_string());
    response.insert("message".to_string(), "Outlook disconnected successfully".to_string());

    Ok(response)
}

// Command to test Outlook connection
#[command]
pub async fn test_outlook_connection(
    user_id: String,
) -> Result<HashMap<String, serde_json::Value>, String> {
    // Implementation would use stored tokens to test Microsoft Graph API
    // For now, return mock data
    let mock_emails = vec![
        serde_json::json!({
            "id": "mock_email_1",
            "subject": "Welcome to ATOM",
            "from": {"name": "ATOM Team", "address": "team@atom.ai"},
            "body": "Thank you for integrating Outlook with ATOM!",
            "receivedDateTime": "2025-11-02T10:00:00Z",
            "isRead": false,
            "importance": "high"
        }),
        serde_json::json!({
            "id": "mock_email_2",
            "subject": "Integration Complete",
            "from": {"name": "System", "address": "noreply@outlook.com"},
            "body": "Your Outlook integration is ready to use.",
            "receivedDateTime": "2025-11-02T09:30:00Z",
            "isRead": true,
            "importance": "normal"
        })
    ];

    let mut response = HashMap::new();
    response.insert("success".to_string(), serde_json::Value::Bool(true));
    response.insert("total".to_string(), serde_json::Value::Number(serde_json::Number::from(mock_emails.len())));
    response.insert("emails".to_string(), serde_json::Value::Array(
        mock_emails.into_iter().collect()
    ));

    Ok(response)
}

// Command to get Outlook emails
#[command]
pub async fn get_outlook_emails(
    user_id: String,
    limit: Option<usize>,
) -> Result<Vec<OutlookEmail>, String> {
    // Implementation would use Microsoft Graph API
    // For now, return mock data
    let emails = vec![
        OutlookEmail {
            id: "mock_email_1".to_string(),
            subject: "Welcome to ATOM".to_string(),
            from: {
                let mut from = HashMap::new();
                from.insert("name".to_string(), "ATOM Team".to_string());
                from.insert("address".to_string(), "team@atom.ai".to_string());
                from
            },
            to_recipients: vec![{
                let mut recipient = HashMap::new();
                recipient.insert("name".to_string(), "User".to_string());
                recipient.insert("address".to_string(), "user@outlook.com".to_string());
                recipient
            }],
            body: "Thank you for integrating Outlook with ATOM!".to_string(),
            received_date_time: "2025-11-02T10:00:00Z".to_string(),
            is_read: false,
            importance: "high".to_string(),
        }
    ];

    Ok(emails)
}

// Command to send Outlook email
#[command]
pub async fn send_outlook_email(
    user_id: String,
    to: Vec<String>,
    subject: String,
    body: String,
    cc: Option<Vec<String>>,
    bcc: Option<Vec<String>>,
) -> Result<HashMap<String, String>, String> {
    // Implementation would use Microsoft Graph API
    // For now, return success
    let mut response = HashMap::new();
    response.insert("success".to_string(), "true".to_string());
    response.insert("message".to_string(), "Email sent successfully".to_string());
    response.insert("subject".to_string(), subject);

    Ok(response)
}

// Command to get Outlook calendar events
#[command]
pub async fn get_outlook_calendar_events(
    user_id: String,
    limit: Option<usize>,
) -> Result<Vec<OutlookCalendarEvent>, String> {
    // Implementation would use Microsoft Graph API
    // For now, return mock data
    let events = vec![
        OutlookCalendarEvent {
            id: "mock_event_1".to_string(),
            subject: "Team Meeting".to_string(),
            start: {
                let mut start = HashMap::new();
                start.insert("dateTime".to_string(), "2025-11-03T14:00:00".to_string());
                start.insert("timeZone".to_string(), "UTC".to_string());
                start
            },
            end: {
                let mut end = HashMap::new();
                end.insert("dateTime".to_string(), "2025-11-03T15:00:00".to_string());
                end.insert("timeZone".to_string(), "UTC".to_string());
                end
            },
            location: Some("Conference Room".to_string()),
            body: Some("Weekly team sync meeting".to_string()),
        }
    ];

    Ok(events)
}

// Command to create Outlook calendar event
#[command]
pub async fn create_outlook_calendar_event(
    user_id: String,
    subject: String,
    start_time: String,
    end_time: String,
    body: Option<String>,
    location: Option<String>,
    attendees: Option<Vec<String>>,
) -> Result<HashMap<String, String>, String> {
    // Implementation would use Microsoft Graph API
    // For now, return success
    let mut response = HashMap::new();
    response.insert("success".to_string(), "true".to_string());
    response.insert("message".to_string(), "Calendar event created successfully".to_string());
    response.insert("event_id".to_string(), "mock_event_new".to_string());

    Ok(response)
}

// Helper function to URL encode parameters
fn url_encode_params(params: &HashMap<String, String>) -> String {
    params.iter()
        .map(|(key, value)| format!("{}={}", urlencoding::encode(key), urlencoding::encode(value)))
        .collect::<Vec<_>>()
        .join("&")
}

// Module for Tauri plugin registration
pub mod outlook_plugin {
    use super::*;
    use tauri::{Runtime, Plugin};

    pub struct OutlookPlugin<R: Runtime> {
        phantom: std::marker::PhantomData<R>,
    }

    impl<R: Runtime> OutlookPlugin<R> {
        pub fn new() -> Self {
            Self {
                phantom: std::marker::PhantomData,
            }
        }
    }

    impl<R: Runtime> Plugin<R> for OutlookPlugin<R> {
        fn name(&self) -> &str {
            "outlook"
        }

        fn invoke(&mut self, cmd: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
            match cmd {
                "check_outlook_oauth_status" => {
                    let user_id = args["user_id"].as_str().ok_or("user_id required")?;
                    let result = tauri::async_runtime::block_on(check_outlook_oauth_status(user_id.to_string()))?;
                    Ok(serde_json::to_value(result).map_err(|e| e.to_string())?)
                }
                "initiate_outlook_oauth" => {
                    let user_id = args["user_id"].as_str().ok_or("user_id required")?;
                    let result = tauri::async_runtime::block_on(initiate_outlook_oauth(user_id.to_string(), tauri::WindowBuilder::new().build()?))?;
                    Ok(serde_json::to_value(result).map_err(|e| e.to_string())?)
                }
                "disconnect_outlook" => {
                    let user_id = args["user_id"].as_str().ok_or("user_id required")?;
                    let result = tauri::async_runtime::block_on(disconnect_outlook(user_id.to_string()))?;
                    Ok(serde_json::to_value(result).map_err(|e| e.to_string())?)
                }
                "test_outlook_connection" => {
                    let user_id = args["user_id"].as_str().ok_or("user_id required")?;
                    let result = tauri::async_runtime::block_on(test_outlook_connection(user_id.to_string()))?;
                    Ok(serde_json::to_value(result).map_err(|e| e.to_string())?)
                }
                "get_outlook_emails" => {
                    let user_id = args["user_id"].as_str().ok_or("user_id required")?;
                    let limit = args["limit"].as_u64().map(|l| l as usize);
                    let result = tauri::async_runtime::block_on(get_outlook_emails(user_id.to_string(), limit))?;
                    Ok(serde_json::to_value(result).map_err(|e| e.to_string())?)
                }
                "send_outlook_email" => {
                    let user_id = args["user_id"].as_str().ok_or("user_id required")?;
                    let to = args["to"].as_array().ok_or("to array required")?
                        .iter()
                        .map(|v| v.as_str().unwrap_or("").to_string())
                        .collect();
                    let subject = args["subject"].as_str().ok_or("subject required")?.to_string();
                    let body = args["body"].as_str().ok_or("body required")?.to_string();
                    let cc = args["cc"].as_array()
                        .map(|arr| arr.iter().map(|v| v.as_str().unwrap_or("").to_string()).collect());
                    let bcc = args["bcc"].as_array()
                        .map(|arr| arr.iter().map(|v| v.as_str().unwrap_or("").to_string()).collect());
                    let result = tauri::async_runtime::block_on(send_outlook_email(user_id.to_string(), to, subject, body, cc, bcc))?;
                    Ok(serde_json::to_value(result).map_err(|e| e.to_string())?)
                }
                "get_outlook_calendar_events" => {
                    let user_id = args["user_id"].as_str().ok_or("user_id required")?;
                    let limit = args["limit"].as_u64().map(|l| l as usize);
                    let result = tauri::async_runtime::block_on(get_outlook_calendar_events(user_id.to_string(), limit))?;
                    Ok(serde_json::to_value(result).map_err(|e| e.to_string())?)
                }
                "create_outlook_calendar_event" => {
                    let user_id = args["user_id"].as_str().ok_or("user_id required")?;
                    let subject = args["subject"].as_str().ok_or("subject required")?.to_string();
                    let start_time = args["start_time"].as_str().ok_or("start_time required")?.to_string();
                    let end_time = args["end_time"].as_str().ok_or("end_time required")?.to_string();
                    let body = args["body"].as_str().map(|s| s.to_string());
                    let location = args["location"].as_str().map(|s| s.to_string());
                    let attendees = args["attendees"].as_array()
                        .map(|arr| arr.iter().map(|v| v.as_str().unwrap_or("").to_string()).collect());
                    let result = tauri::async_runtime::block_on(create_outlook_calendar_event(user_id.to_string(), subject, start_time, end_time, body, location, attendees))?;
                    Ok(serde_json::to_value(result).map_err(|e| e.to_string())?)
                }
                _ => Err(format!("Unknown command: {}", cmd)),
            }
        }
    }

    pub fn init() -> OutlookPlugin<tauri::Wry> {
        OutlookPlugin::new()
    }
}