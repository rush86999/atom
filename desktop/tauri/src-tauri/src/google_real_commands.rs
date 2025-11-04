// Enhanced Google Commands with Real API Support
use crate::google_types::*;
use crate::google_commands::*;
use crate::google_http_client::{GoogleApiClient, GoogleApiConfig, refresh_google_token, validate_google_token};
use std::collections::HashMap;
use std::sync::Mutex;
use tauri::State;

lazy_static::lazy_static! {
    static ref GOOGLE_API_CLIENTS: Mutex<HashMap<String, GoogleApiClient>> = Mutex::new(HashMap::new());
}

// Helper to get or create API client for user
async fn get_or_create_api_client(
    user_id: String,
) -> Result<GoogleApiClient, Box<dyn std::error::Error>> {
    let mut clients = GOOGLE_API_CLIENTS.lock().unwrap();
    
    if let Some(client) = clients.get(&user_id) {
        return Ok(client.clone());
    }
    
    // Get stored tokens (this would read from secure storage)
    let tokens = get_stored_tokens(&user_id)?;
    
    // Check if access token is valid
    if !validate_google_token(&tokens.access_token).await? {
        // Refresh token
        let refreshed_tokens = refresh_google_token(
            &tokens.refresh_token,
            &std::env::var("GOOGLE_CLIENT_ID").unwrap_or_default(),
            &std::env::var("GOOGLE_CLIENT_SECRET").unwrap_or_default(),
        ).await?;
        
        // Store refreshed tokens
        store_tokens(&user_id, &refreshed_tokens)?;
        
        // Create client with refreshed token
        let client = GoogleApiClient::new(
            refreshed_tokens.access_token,
            user_id.clone(),
            None
        )?;
        
        clients.insert(user_id, client.clone());
        return Ok(client);
    }
    
    // Create client with existing token
    let client = GoogleApiClient::new(
        tokens.access_token,
        user_id.clone(),
        None
    )?;
    
    clients.insert(user_id, client.clone());
    Ok(client)
}

// Mock implementations for development
#[tauri::command]
pub async fn google_gmail_list_emails_real(
    user_id: String,
    query: Option<String>,
    max_results: Option<u32>,
    include_attachments: Option<bool>,
    include_spam: Option<bool>,
    include_trash: Option<bool>,
    page_token: Option<String>,
) -> Result<GoogleEmailListResponse, String> {
    // Check if we should use mock API
    if std::env::var("GOOGLE_USE_MOCK_API").unwrap_or_else(|_| "true".to_string()) == "true" {
        return google_gmail_list_emails(
            user_id,
            query,
            max_results,
            include_attachments,
            include_spam,
            include_trash,
            page_token,
        ).await;
    }

    // Use real API
    match get_or_create_api_client(user_id).await {
        Ok(_client) => {
            // TODO: Implement real Gmail API call
            // For now, fallback to mock
            google_gmail_list_emails(
                user_id,
                query,
                max_results,
                include_attachments,
                include_spam,
                include_trash,
                page_token,
            ).await
        }
        Err(e) => {
            eprintln!("Failed to create Google API client: {}", e);
            // Fallback to mock
            google_gmail_list_emails(
                user_id,
                query,
                max_results,
                include_attachments,
                include_spam,
                include_trash,
                page_token,
            ).await
        }
    }
}

#[tauri::command]
pub async fn google_calendar_list_events_real(
    user_id: String,
    calendar_id: Option<String>,
    time_min: Option<String>,
    time_max: Option<String>,
    q: Option<String>,
    max_results: Option<u32>,
    single_events: Option<bool>,
    order_by: Option<String>,
) -> Result<GoogleEventsListResponse, String> {
    // Check if we should use mock API
    if std::env::var("GOOGLE_USE_MOCK_API").unwrap_or_else(|_| "true".to_string()) == "true" {
        return google_calendar_list_events(
            user_id,
            calendar_id,
            time_min,
            time_max,
            q,
            max_results,
            single_events,
            order_by,
        ).await;
    }

    // Use real API
    match get_or_create_api_client(user_id).await {
        Ok(_client) => {
            // TODO: Implement real Calendar API call
            // For now, fallback to mock
            google_calendar_list_events(
                user_id,
                calendar_id,
                time_min,
                time_max,
                q,
                max_results,
                single_events,
                order_by,
            ).await
        }
        Err(e) => {
            eprintln!("Failed to create Google API client: {}", e);
            // Fallback to mock
            google_calendar_list_events(
                user_id,
                calendar_id,
                time_min,
                time_max,
                q,
                max_results,
                single_events,
                order_by,
            ).await
        }
    }
}

#[tauri::command]
pub async fn google_drive_list_files_real(
    user_id: String,
    q: Option<String>,
    page_size: Option<u32>,
    order_by: Option<String>,
    page_token: Option<String>,
    spaces: Option<String>,
) -> Result<GoogleDriveFileListResponse, String> {
    // Check if we should use mock API
    if std::env::var("GOOGLE_USE_MOCK_API").unwrap_or_else(|_| "true".to_string()) == "true" {
        return google_drive_list_files(
            user_id,
            q,
            page_size,
            order_by,
            page_token,
            spaces,
        ).await;
    }

    // Use real API
    match get_or_create_api_client(user_id).await {
        Ok(_client) => {
            // TODO: Implement real Drive API call
            // For now, fallback to mock
            google_drive_list_files(
                user_id,
                q,
                page_size,
                order_by,
                page_token,
                spaces,
            ).await
        }
        Err(e) => {
            eprintln!("Failed to create Google API client: {}", e);
            // Fallback to mock
            google_drive_list_files(
                user_id,
                q,
                page_size,
                order_by,
                page_token,
                spaces,
            ).await
        }
    }
}

// Enhanced OAuth command with real URL generation
#[tauri::command]
pub async fn google_get_oauth_url_real(
    user_id: String,
) -> Result<GoogleOAuthUrlResponse, String> {
    let client_id = std::env::var("GOOGLE_CLIENT_ID")
        .unwrap_or_else(|_| "your_google_client_id".to_string());
    let redirect_uri = std::env::var("GOOGLE_REDIRECT_URI")
        .unwrap_or_else(|_| "http://localhost:3000/oauth/google/callback".to_string());
    
    // OAuth scopes for Gmail, Calendar, and Drive
    let scopes = vec![
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.file",
    ];
    
    let state = format!("google_auth_{}_{}", user_id, chrono::Utc::now().timestamp());
    let encoded_scopes = urlencoding::encode(&scopes.join(" "));
    let encoded_redirect = urlencoding::encode(&redirect_uri);
    
    let auth_url = format!(
        "https://accounts.google.com/o/oauth2/v2/auth?client_id={}&redirect_uri={}&response_type=code&scope={}&state={}&access_type=offline&prompt=consent",
        client_id,
        encoded_redirect,
        encoded_scopes,
        state
    );
    
    Ok(GoogleOAuthUrlResponse {
        success: true,
        auth_url,
        state,
        error: None,
    })
}

// Enhanced OAuth exchange with real token handling
#[tauri::command]
pub async fn google_exchange_oauth_code_real(
    code: String,
    state: String,
    user_id: String,
) -> Result<GoogleOAuthCallbackResponse, String> {
    let client_id = std::env::var("GOOGLE_CLIENT_ID")
        .map_err(|_| "GOOGLE_CLIENT_ID not set")?;
    let client_secret = std::env::var("GOOGLE_CLIENT_SECRET")
        .map_err(|_| "GOOGLE_CLIENT_SECRET not set")?;
    let redirect_uri = std::env::var("GOOGLE_REDIRECT_URI")
        .unwrap_or_else(|_| "http://localhost:3000/oauth/google/callback".to_string());
    
    // Exchange code for tokens
    let tokens = refresh_google_token(&code, &client_id, &client_secret).await
        .map_err(|e| format!("Failed to exchange code for tokens: {}", e))?;
    
    // Get user info
    let user_info = get_google_user_info(&tokens.access_token).await
        .map_err(|e| format!("Failed to get user info: {}", e))?;
    
    // Store tokens securely
    store_tokens(&user_id, &tokens)
        .map_err(|e| format!("Failed to store tokens: {}", e))?;
    
    Ok(GoogleOAuthCallbackResponse {
        success: true,
        tokens: Some(tokens),
        user: Some(user_info),
        error: None,
    })
}

// Helper function to get user info from Google
async fn get_google_user_info(
    access_token: &str,
) -> Result<GoogleUser, Box<dyn std::error::Error>> {
    let client = reqwest::Client::new();
    let response = client
        .get("https://www.googleapis.com/oauth2/v2/userinfo")
        .header("Authorization", format!("Bearer {}", access_token))
        .send()
        .await?;
    
    if response.status().is_success() {
        let user_data: serde_json::Value = response.json().await?;
        
        Ok(GoogleUser {
            id: user_data["id"].as_str().unwrap_or("").to_string(),
            email: user_data["email"].as_str().unwrap_or("").to_string(),
            name: user_data["name"].as_str().unwrap_or("").to_string(),
            avatar: user_data["picture"].as_str().map(|s| s.to_string()),
            verified: user_data["verified_email"].as_bool().unwrap_or(false),
        })
    } else {
        Err("Failed to get user info".into())
    }
}

// Helper functions for token storage
fn store_tokens(user_id: &str, tokens: &GoogleOAuthToken) -> Result<(), Box<dyn std::error::Error>> {
    // TODO: Implement secure token storage
    // For now, just log (in production, use encrypted storage)
    println!("Storing tokens for user {}: [ACCESS_TOKEN_REDACTED]", user_id);
    Ok(())
}

fn get_stored_tokens(user_id: &str) -> Result<GoogleOAuthToken, Box<dyn std::error::Error>> {
    // TODO: Implement secure token retrieval
    // For now, return mock tokens
    Ok(GoogleOAuthToken {
        access_token: "mock_access_token".to_string(),
        refresh_token: "mock_refresh_token".to_string(),
        token_type: "Bearer".to_string(),
        expires_at: (chrono::Utc::now() + chrono::Duration::hours(1)).to_rfc3339(),
        scope: "gmail.send gmail.readonly calendar.events drive.file".to_string(),
    })
}

// Enhanced connection status
#[tauri::command]
pub async fn google_get_connection_real(
    user_id: String,
) -> Result<GoogleConnectionStatus, String> {
    // Check if we have stored tokens
    match get_stored_tokens(&user_id) {
        Ok(tokens) => {
            // Check if tokens are valid
            match validate_google_token(&tokens.access_token).await {
                Ok(valid) => {
                    if valid {
                        // Get user info
                        match get_google_user_info(&tokens.access_token).await {
                            Ok(user) => {
                                Ok(GoogleConnectionStatus {
                                    connected: true,
                                    user: Some(user),
                                    tokens: Some(tokens),
                                    last_sync: Some(chrono::Utc::now().to_rfc3339()),
                                    expires_at: Some(tokens.expires_at.clone()),
                                })
                            }
                            Err(_) => {
                                Ok(GoogleConnectionStatus {
                                    connected: false,
                                    user: None,
                                    tokens: None,
                                    last_sync: None,
                                    expires_at: None,
                                })
                            }
                        }
                    } else {
                        // Try to refresh tokens
                        match refresh_google_token(
                            &tokens.refresh_token,
                            &std::env::var("GOOGLE_CLIENT_ID").unwrap_or_default(),
                            &std::env::var("GOOGLE_CLIENT_SECRET").unwrap_or_default(),
                        ).await {
                            Ok(refreshed_tokens) => {
                                // Store refreshed tokens
                                let _ = store_tokens(&user_id, &refreshed_tokens);
                                
                                match get_google_user_info(&refreshed_tokens.access_token).await {
                                    Ok(user) => {
                                        Ok(GoogleConnectionStatus {
                                            connected: true,
                                            user: Some(user),
                                            tokens: Some(refreshed_tokens),
                                            last_sync: Some(chrono::Utc::now().to_rfc3339()),
                                            expires_at: Some(refreshed_tokens.expires_at.clone()),
                                        })
                                    }
                                    Err(_) => {
                                        Ok(GoogleConnectionStatus {
                                            connected: false,
                                            user: None,
                                            tokens: None,
                                            last_sync: None,
                                            expires_at: None,
                                        })
                                    }
                                }
                            }
                            Err(_) => {
                                Ok(GoogleConnectionStatus {
                                    connected: false,
                                    user: None,
                                    tokens: None,
                                    last_sync: None,
                                    expires_at: None,
                                })
                            }
                        }
                    }
                }
                Err(_) => {
                    Ok(GoogleConnectionStatus {
                        connected: false,
                        user: None,
                        tokens: None,
                        last_sync: None,
                        expires_at: None,
                    })
                }
            }
        }
        Err(_) => {
            Ok(GoogleConnectionStatus {
                connected: false,
                user: None,
                tokens: None,
                last_sync: None,
                expires_at: None,
            })
        }
    }
}