// Google API command handlers for ATOM Desktop
use crate::google_types::*;
use serde_json::{json, Value};
use std::collections::HashMap;
use chrono::{DateTime, Utc};

// ============= GMAIL API COMMANDS =============

#[tauri::command]
pub async fn google_gmail_list_emails(
    user_id: String,
    query: Option<String>,
    max_results: Option<u32>,
    include_attachments: Option<bool>,
    include_spam: Option<bool>,
    include_trash: Option<bool>,
    page_token: Option<String>,
) -> Result<GoogleEmailListResponse, String> {
    // Validate input
    if max_results.unwrap_or(0) > 100 {
        return Err("Maximum results per page is 100".to_string());
    }
    
    // Mock implementation - replace with actual Gmail API call
    let mut emails = get_mock_google_emails();
    
    // Apply filters
    if let Some(q) = query {
        emails = emails.into_iter()
            .filter(|email| {
                email.subject.to_lowercase().contains(&q.to_lowercase()) ||
                email.from.to_lowercase().contains(&q.to_lowercase()) ||
                email.snippet.to_lowercase().contains(&q.to_lowercase())
            })
            .collect::<Vec<_>>();
    }
    
    if !include_spam.unwrap_or(false) {
        emails = emails.into_iter()
            .filter(|email| !email.labels.iter().any(|l| l.contains("SPAM")))
            .collect::<Vec<_>>();
    }
    
    if !include_trash.unwrap_or(false) {
        emails = emails.into_iter()
            .filter(|email| !email.labels.iter().any(|l| l.contains("TRASH")))
            .collect::<Vec<_>>();
    }
    
    if !include_attachments.unwrap_or(true) {
        emails = emails.into_iter()
            .map(|mut email| {
                email.has_attachments = false;
                email.attachments = None;
                email
            })
            .collect::<Vec<_>>();
    }
    
    // Apply pagination
    let limit_val = max_results.unwrap_or(10);
    let start_index = page_token.as_ref()
        .and_then(|token| token.parse::<usize>().ok())
        .unwrap_or(0);
    
    let end_index = (start_index + limit_val as usize).min(emails.len());
    let paginated_emails = if start_index < emails.len() {
        emails[start_index..end_index].to_vec()
    } else {
        vec![]
    };
    
    let next_page_token = if end_index < emails.len() {
        Some(end_index.to_string())
    } else {
        None
    };
    
    Ok(GoogleEmailListResponse {
        messages: paginated_emails,
        next_page_token,
        result_size_estimate: emails.len() as u32,
    })
}

#[tauri::command]
pub async fn google_gmail_search_emails(
    user_id: String,
    query: String,
    max_results: Option<u32>,
    page_token: Option<String>,
) -> Result<GoogleSearchResult, String> {
    // Validate input
    if query.trim().is_empty() {
        return Err("Search query is required".to_string());
    }
    
    // Mock implementation - replace with actual Gmail API call
    let emails = get_mock_google_emails();
    
    // Apply search filter
    let filtered_emails = emails.into_iter()
        .filter(|email| {
            email.subject.to_lowercase().contains(&query.to_lowercase()) ||
            email.from.to_lowercase().contains(&query.to_lowercase()) ||
            email.snippet.to_lowercase().contains(&query.to_lowercase()) ||
            email.body.to_lowercase().contains(&query.to_lowercase())
        })
        .collect::<Vec<_>>();
    
    // Apply pagination
    let limit_val = max_results.unwrap_or(20);
    let start_index = page_token.as_ref()
        .and_then(|token| token.parse::<usize>().ok())
        .unwrap_or(0);
    
    let end_index = (start_index + limit_val as usize).min(filtered_emails.len());
    let paginated_emails = if start_index < filtered_emails.len() {
        filtered_emails[start_index..end_index].to_vec()
    } else {
        vec![]
    };
    
    let next_page_token = if end_index < filtered_emails.len() {
        Some(end_index.to_string())
    } else {
        None
    };
    
    Ok(GoogleSearchResult {
        emails: Some(paginated_emails),
        calendar_events: None,
        drive_files: None,
        next_page_token,
        total_results: Some(filtered_emails.len() as u32),
    })
}

#[tauri::command]
pub async fn google_gmail_send_email(
    user_id: String,
    to: Vec<String>,
    cc: Option<Vec<String>>,
    bcc: Option<Vec<String>>,
    subject: String,
    body: String,
    html_body: Option<String>,
    attachments: Option<Vec<GoogleEmailAttachmentData>>,
) -> Result<GoogleEmailSendResponse, String> {
    // Validate input
    if subject.trim().is_empty() {
        return Err("Email subject is required".to_string());
    }
    
    if to.is_empty() {
        return Err("At least one recipient is required".to_string());
    }
    
    // Validate email addresses
    for email in &to {
        if !is_valid_email(email) {
            return Err(format!("Invalid email address: {}", email));
        }
    }
    
    if let Some(cc_emails) = &cc {
        for email in cc_emails {
            if !is_valid_email(email) {
                return Err(format!("Invalid CC email address: {}", email));
            }
        }
    }
    
    if let Some(bcc_emails) = &bcc {
        for email in bcc_emails {
            if !is_valid_email(email) {
                return Err(format!("Invalid BCC email address: {}", email));
            }
        }
    }
    
    // Mock implementation - replace with actual Gmail API call
    let message_id = format!("msg_{}", chrono::Utc::now().timestamp_millis());
    
    Ok(GoogleEmailSendResponse {
        success: true,
        message_id: Some(message_id),
        error: None,
    })
}

#[tauri::command]
pub async fn google_gmail_read_email(
    user_id: String,
    email_id: String,
    thread_id: Option<String>,
    mark_as_read: Option<bool>,
) -> Result<GoogleEmail, String> {
    // Validate input
    if email_id.trim().is_empty() {
        return Err("Email ID is required".to_string());
    }
    
    // Mock implementation - replace with actual Gmail API call
    let emails = get_mock_google_emails();
    
    if let Some(mut email) = emails.iter().find(|e| e.id == email_id) {
        // Mark as read if requested
        if mark_as_read.unwrap_or(true) {
            email.is_read = true;
        }
        
        Ok(email.clone())
    } else {
        Err("Email not found".to_string())
    }
}

#[tauri::command]
pub async fn google_gmail_mark_email(
    user_id: String,
    email_id: String,
    thread_id: Option<String>,
    action: String,
) -> Result<GoogleEmailActionResponse, String> {
    // Validate input
    if email_id.trim().is_empty() {
        return Err("Email ID is required".to_string());
    }
    
    let valid_actions = vec!["read", "unread", "starred", "unstarred", "important", "unimportant"];
    if !valid_actions.contains(&action.as_str()) {
        return Err(format!("Invalid action: {}. Valid actions: {}", action, valid_actions.join(", ")));
    }
    
    // Mock implementation - replace with actual Gmail API call
    // In real implementation, this would call Gmail API to modify labels
    
    Ok(GoogleEmailActionResponse {
        success: true,
        error: None,
    })
}

#[tauri::command]
pub async fn google_gmail_reply_email(
    user_id: String,
    email_id: String,
    thread_id: Option<String>,
    body: String,
    html_body: Option<String>,
    to_all: Option<bool>,
    attachments: Option<Vec<GoogleEmailAttachmentData>>,
) -> Result<GoogleEmailSendResponse, String> {
    // Validate input
    if email_id.trim().is_empty() {
        return Err("Email ID is required".to_string());
    }
    
    if body.trim().is_empty() {
        return Err("Reply body is required".to_string());
    }
    
    // Mock implementation - replace with actual Gmail API call
    let message_id = format!("reply_{}", chrono::Utc::now().timestamp_millis());
    
    Ok(GoogleEmailSendResponse {
        success: true,
        message_id: Some(message_id),
        error: None,
    })
}

#[tauri::command]
pub async fn google_gmail_delete_email(
    user_id: String,
    email_id: String,
    thread_id: Option<String>,
    permanently: Option<bool>,
) -> Result<GoogleEmailActionResponse, String> {
    // Validate input
    if email_id.trim().is_empty() {
        return Err("Email ID is required".to_string());
    }
    
    // Mock implementation - replace with actual Gmail API call
    // In real implementation, this would call Gmail API to delete or move to trash
    
    Ok(GoogleEmailActionResponse {
        success: true,
        error: None,
    })
}

// ============= GOOGLE CALENDAR API COMMANDS =============

#[tauri::command]
pub async fn google_calendar_list_calendars(
    user_id: String,
) -> Result<GoogleCalendarListResponse, String> {
    // Mock implementation - replace with actual Google Calendar API call
    let calendars = get_mock_google_calendars();
    
    Ok(GoogleCalendarListResponse {
        calendars,
        next_page_token: None,
    })
}

#[tauri::command]
pub async fn google_calendar_list_events(
    user_id: String,
    calendar_id: Option<String>,
    time_min: Option<String>,
    time_max: Option<String>,
    q: Option<String>,
    max_results: Option<u32>,
    single_events: Option<bool>,
    order_by: Option<String>,
) -> Result<GoogleEventsListResponse, String> {
    // Mock implementation - replace with actual Google Calendar API call
    let mut events = get_mock_google_calendar_events();
    
    // Apply search filter
    if let Some(search_query) = q {
        events = events.into_iter()
            .filter(|event| {
                event.summary.to_lowercase().contains(&search_query.to_lowercase()) ||
                event.description.as_ref().map_or(false, |desc| desc.to_lowercase().contains(&search_query.to_lowercase())) ||
                event.location.as_ref().map_or(false, |loc| loc.to_lowercase().contains(&search_query.to_lowercase()))
            })
            .collect::<Vec<_>>();
    }
    
    // Apply time filter
    if let Some(start_time) = time_min {
        if let Ok(start_dt) = DateTime::parse_from_rfc3339(&start_time) {
            let start_timestamp = start_dt.timestamp();
            events = events.into_iter()
                .filter(|event| {
                    DateTime::parse_from_rfc3339(&event.start_time)
                        .map(|dt| dt.timestamp() >= start_timestamp)
                        .unwrap_or(false)
                })
                .collect::<Vec<_>>();
        }
    }
    
    if let Some(end_time) = time_max {
        if let Ok(end_dt) = DateTime::parse_from_rfc3339(&end_time) {
            let end_timestamp = end_dt.timestamp();
            events = events.into_iter()
                .filter(|event| {
                    DateTime::parse_from_rfc3339(&event.end_time)
                        .map(|dt| dt.timestamp() <= end_timestamp)
                        .unwrap_or(false)
                })
                .collect::<Vec<_>>();
        }
    }
    
    // Apply ordering
    let order = order_by.as_deref().unwrap_or("startTime");
    if order == "startTime" || order == "updated" {
        events.sort_by(|a, b| a.start_time.cmp(&b.start_time));
    }
    
    // Apply limit
    let limit_val = max_results.unwrap_or(10);
    events.truncate(limit_val as usize);
    
    Ok(GoogleEventsListResponse {
        events,
        next_page_token: None,
        time_zone: Some("America/New_York".to_string()),
        default_reminders: Some(vec![
            GoogleEventReminder {
                method: "email".to_string(),
                minutes: 24 * 60, // 24 hours before
            },
            GoogleEventReminder {
                method: "popup".to_string(),
                minutes: 10, // 10 minutes before
            }
        ]),
    })
}

#[tauri::command]
pub async fn google_calendar_create_event(
    user_id: String,
    calendar_id: Option<String>,
    summary: String,
    description: Option<String>,
    location: Option<String>,
    start_time: String,
    end_time: String,
    all_day: Option<bool>,
    attendees: Option<Vec<String>>,
    visibility: Option<String>,
    transparency: Option<String>,
) -> Result<GoogleCalendarEventResponse, String> {
    // Validate input
    if summary.trim().is_empty() {
        return Err("Event summary is required".to_string());
    }
    
    if start_time.trim().is_empty() || end_time.trim().is_empty() {
        return Err("Start time and end time are required".to_string());
    }
    
    // Validate time format
    if let Err(_) = DateTime::parse_from_rfc3339(&start_time) {
        return Err("Invalid start time format. Use RFC3339 format (e.g., 2025-11-03T14:00:00Z)".to_string());
    }
    
    if let Err(_) = DateTime::parse_from_rfc3339(&end_time) {
        return Err("Invalid end time format. Use RFC3339 format (e.g., 2025-11-03T15:00:00Z)".to_string());
    }
    
    // Mock implementation - replace with actual Google Calendar API call
    let event_id = format!("evt_{}", chrono::Utc::now().timestamp_millis());
    
    Ok(GoogleCalendarEventResponse {
        success: true,
        event_id: Some(event_id),
        error: None,
    })
}

#[tauri::command]
pub async fn google_calendar_update_event(
    user_id: String,
    calendar_id: Option<String>,
    event_id: String,
    summary: Option<String>,
    description: Option<String>,
    location: Option<String>,
    attendees: Option<Vec<String>>,
    visibility: Option<String>,
    transparency: Option<String>,
) -> Result<GoogleCalendarEventResponse, String> {
    // Validate input
    if event_id.trim().is_empty() {
        return Err("Event ID is required".to_string());
    }
    
    // Mock implementation - replace with actual Google Calendar API call
    // In real implementation, this would call Google Calendar API to update the event
    
    Ok(GoogleCalendarEventResponse {
        success: true,
        event_id: Some(event_id),
        error: None,
    })
}

#[tauri::command]
pub async fn google_calendar_delete_event(
    user_id: String,
    calendar_id: Option<String>,
    event_id: String,
    send_updates: Option<String>,
) -> Result<GoogleCalendarActionResponse, String> {
    // Validate input
    if event_id.trim().is_empty() {
        return Err("Event ID is required".to_string());
    }
    
    // Mock implementation - replace with actual Google Calendar API call
    // In real implementation, this would call Google Calendar API to delete the event
    
    Ok(GoogleCalendarActionResponse {
        success: true,
        error: None,
    })
}

// ============= GOOGLE DRIVE API COMMANDS =============

#[tauri::command]
pub async fn google_drive_list_files(
    user_id: String,
    q: Option<String>,
    page_size: Option<u32>,
    order_by: Option<String>,
    page_token: Option<String>,
    spaces: Option<String>,
) -> Result<GoogleDriveFileListResponse, String> {
    // Validate input
    let page_size_val = page_size.unwrap_or(10);
    if page_size_val > 1000 {
        return Err("Maximum page size is 1000".to_string());
    }
    
    // Mock implementation - replace with actual Google Drive API call
    let mut files = get_mock_google_drive_files();
    
    // Apply search filter
    if let Some(search_query) = q {
        files = files.into_iter()
            .filter(|file| {
                file.name.to_lowercase().contains(&search_query.to_lowercase())
            })
            .collect::<Vec<_>>();
    }
    
    // Apply ordering
    if let Some(ordering) = order_by {
        match ordering.as_str() {
            "name" | "name_natural" => files.sort_by(|a, b| a.name.cmp(&b.name)),
            "modifiedTime" | "modifiedByMeTime" => files.sort_by(|a, b| a.modified_time.cmp(&b.modified_time)),
            "createdTime" => files.sort_by(|a, b| a.created_time.cmp(&b.created_time)),
            "size" => files.sort_by(|a, b| {
                a.size.as_ref().and_then(|s| s.parse::<u64>().ok()).cmp(&b.size.as_ref().and_then(|s| s.parse::<u64>().ok()))
            }),
            "recency" => files.sort_by(|a, b| b.modified_time.cmp(&a.modified_time)),
            _ => {}
        }
    }
    
    // Apply pagination
    let start_index = page_token.as_ref()
        .and_then(|token| token.parse::<usize>().ok())
        .unwrap_or(0);
    
    let end_index = (start_index + page_size_val as usize).min(files.len());
    let paginated_files = if start_index < files.len() {
        files[start_index..end_index].to_vec()
    } else {
        vec![]
    };
    
    let next_page_token = if end_index < files.len() {
        Some(end_index.to_string())
    } else {
        None
    };
    
    Ok(GoogleDriveFileListResponse {
        files: paginated_files,
        next_page_token,
        incomplete_search: false,
        kind: "drive#fileList".to_string(),
    })
}

#[tauri::command]
pub async fn google_drive_search_files(
    user_id: String,
    q: String,
    page_size: Option<u32>,
    order_by: Option<String>,
    page_token: Option<String>,
    spaces: Option<String>,
) -> Result<GoogleDriveSearchResponse, String> {
    // Validate input
    if q.trim().is_empty() {
        return Err("Search query is required".to_string());
    }
    
    // Mock implementation - replace with actual Google Drive API call
    let files = get_mock_google_drive_files();
    
    // Apply search filter
    let filtered_files = files.into_iter()
        .filter(|file| {
            file.name.to_lowercase().contains(&q.to_lowercase())
        })
        .collect::<Vec<_>>();
    
    // Apply ordering
    if let Some(ordering) = order_by {
        match ordering.as_str() {
            "relevance desc" => {}, // Keep original order for relevance
            "name" => filtered_files.sort_by(|a, b| a.name.cmp(&b.name)),
            "modifiedTime desc" => filtered_files.sort_by(|a, b| b.modified_time.cmp(&a.modified_time)),
            _ => {}
        }
    }
    
    // Apply pagination
    let page_size_val = page_size.unwrap_or(20);
    let start_index = page_token.as_ref()
        .and_then(|token| token.parse::<usize>().ok())
        .unwrap_or(0);
    
    let end_index = (start_index + page_size_val as usize).min(filtered_files.len());
    let paginated_files = if start_index < filtered_files.len() {
        filtered_files[start_index..end_index].to_vec()
    } else {
        vec![]
    };
    
    let next_page_token = if end_index < filtered_files.len() {
        Some(end_index.to_string())
    } else {
        None
    };
    
    Ok(GoogleDriveSearchResponse {
        files: paginated_files,
        next_page_token,
        total_results: Some(filtered_files.len() as u32),
        incomplete_search: false,
    })
}

#[tauri::command]
pub async fn google_drive_create_file(
    user_id: String,
    name: String,
    content: Option<String>,
    mime_type: Option<String>,
    parents: Option<Vec<String>>,
) -> Result<GoogleDriveUploadResponse, String> {
    // Validate input
    if name.trim().is_empty() {
        return Err("File name is required".to_string());
    }
    
    if !is_valid_filename(&name) {
        return Err("File name contains invalid characters".to_string());
    }
    
    // Mock implementation - replace with actual Google Drive API call
    let file_id = format!("file_{}", chrono::Utc::now().timestamp_millis());
    let content_size = content.as_ref().map(|c| c.len()).unwrap_or(0);
    
    Ok(GoogleDriveUploadResponse {
        success: true,
        id: file_id,
        name,
        mime_type: mime_type.unwrap_or("text/plain".to_string()),
        size: Some(content_size.to_string()),
        web_view_link: Some(format!("https://docs.google.com/file/d/{}", file_id)),
        web_content_link: Some(format!("https://drive.google.com/uc?export=download&id={}", file_id)),
        error: None,
    })
}

#[tauri::command]
pub async fn google_drive_create_folder(
    user_id: String,
    name: String,
    parents: Option<Vec<String>>,
) -> Result<GoogleDriveUploadResponse, String> {
    // Validate input
    if name.trim().is_empty() {
        return Err("Folder name is required".to_string());
    }
    
    if !is_valid_filename(&name) {
        return Err("Folder name contains invalid characters".to_string());
    }
    
    // Mock implementation - replace with actual Google Drive API call
    let folder_id = format!("folder_{}", chrono::Utc::now().timestamp_millis());
    
    Ok(GoogleDriveUploadResponse {
        success: true,
        id: folder_id,
        name,
        mime_type: "application/vnd.google-apps.folder".to_string(),
        size: None,
        web_view_link: Some(format!("https://drive.google.com/drive/folders/{}", folder_id)),
        web_content_link: None,
        error: None,
    })
}

#[tauri::command]
pub async fn google_drive_delete_file(
    user_id: String,
    file_id: String,
) -> Result<GoogleDriveActionResponse, String> {
    // Validate input
    if file_id.trim().is_empty() {
        return Err("File ID is required".to_string());
    }
    
    // Mock implementation - replace with actual Google Drive API call
    // In real implementation, this would call Google Drive API to delete the file
    
    Ok(GoogleDriveActionResponse {
        success: true,
        error: None,
    })
}

#[tauri::command]
pub async fn google_drive_share_file(
    user_id: String,
    file_id: String,
    role: String,
    r#type: String,
    email_address: Option<String>,
    domain: Option<String>,
    send_notification_email: Option<bool>,
) -> Result<GoogleDriveShareResponse, String> {
    // Validate input
    if file_id.trim().is_empty() {
        return Err("File ID is required".to_string());
    }
    
    let valid_roles = vec!["owner", "organizer", "fileOrganizer", "writer", "commenter", "reader"];
    if !valid_roles.contains(&role.as_str()) {
        return Err(format!("Invalid role: {}. Valid roles: {}", role, valid_roles.join(", ")));
    }
    
    let valid_types = vec!["user", "group", "domain", "anyone"];
    if !valid_types.contains(&r#type.as_str()) {
        return Err(format!("Invalid type: {}. Valid types: {}", r#type, valid_types.join(", ")));
    }
    
    if r#type == "user" && email_address.is_none() {
        return Err("Email address is required when type is 'user'".to_string());
    }
    
    if r#type == "domain" && domain.is_none() {
        return Err("Domain is required when type is 'domain'".to_string());
    }
    
    // Mock implementation - replace with actual Google Drive API call
    let share_link = format!("https://drive.google.com/file/d/{}/shared", file_id);
    
    Ok(GoogleDriveShareResponse {
        success: true,
        file_id,
        link: Some(share_link),
        error: None,
    })
}

#[tauri::command]
pub async fn google_drive_get_file_metadata(
    user_id: String,
    file_id: String,
    fields: Option<String>,
) -> Result<GoogleDriveFileMetadataResponse, String> {
    // Validate input
    if file_id.trim().is_empty() {
        return Err("File ID is required".to_string());
    }
    
    // Mock implementation - replace with actual Google Drive API call
    let files = get_mock_google_drive_files();
    
    if let Some(file) = files.iter().find(|f| f.id == file_id) {
        Ok(GoogleDriveFileMetadataResponse {
            success: true,
            file: Some(file.clone()),
            error: None,
        })
    } else {
        Ok(GoogleDriveFileMetadataResponse {
            success: false,
            file: None,
            error: Some("File not found".to_string()),
        })
    }
}

#[tauri::command]
pub async fn google_drive_download_file(
    user_id: String,
    file_id: String,
) -> Result<GoogleDriveDownloadResponse, String> {
    // Validate input
    if file_id.trim().is_empty() {
        return Err("File ID is required".to_string());
    }
    
    // Mock implementation - replace with actual Google Drive API call
    let files = get_mock_google_drive_files();
    
    if let Some(file) = files.iter().find(|f| f.id == file_id) {
        Ok(GoogleDriveDownloadResponse {
            success: true,
            content: "This is mock file content for testing purposes.".to_string(),
            mime_type: Some(file.mime_type.clone()),
            error: None,
        })
    } else {
        Ok(GoogleDriveDownloadResponse {
            success: false,
            content: String::new(),
            mime_type: None,
            error: Some("File not found".to_string()),
        })
    }
}

#[tauri::command]
pub async fn google_drive_update_file(
    user_id: String,
    file_id: String,
    content: String,
) -> Result<GoogleDriveUploadResponse, String> {
    // Validate input
    if file_id.trim().is_empty() {
        return Err("File ID is required".to_string());
    }
    
    if content.trim().is_empty() {
        return Err("File content is required".to_string());
    }
    
    // Mock implementation - replace with actual Google Drive API call
    let files = get_mock_google_drive_files();
    
    if let Some(file) = files.iter().find(|f| f.id == file_id) {
        Ok(GoogleDriveUploadResponse {
            success: true,
            id: file.id.clone(),
            name: file.name.clone(),
            mime_type: file.mime_type.clone(),
            size: Some(content.len().to_string()),
            web_view_link: file.web_view_link.clone(),
            web_content_link: file.web_content_link.clone(),
            error: None,
        })
    } else {
        Ok(GoogleDriveUploadResponse {
            success: false,
            id: String::new(),
            name: String::new(),
            mime_type: String::new(),
            size: None,
            web_view_link: None,
            web_content_link: None,
            error: Some("File not found".to_string()),
        })
    }
}

// ============= GOOGLE OAUTH2 COMMANDS =============

#[tauri::command]
pub async fn google_get_oauth_url(
    user_id: String,
) -> Result<GoogleOAuthUrlResponse, String> {
    // Google OAuth configuration
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

#[tauri::command]
pub async fn google_exchange_oauth_code(
    code: String,
    state: String,
    user_id: String,
) -> Result<GoogleOAuthCallbackResponse, String> {
    // Mock implementation - replace with actual Google OAuth2 token exchange
    let mock_tokens = GoogleOAuthToken {
        access_token: "mock_google_access_token_12345".to_string(),
        refresh_token: "mock_google_refresh_token_67890".to_string(),
        token_type: "Bearer".to_string(),
        expires_at: chrono::Utc::now() + chrono::Duration::hours(1),
        scope: "gmail.send gmail.readonly calendar.events drive.file".to_string(),
    };
    
    let mock_user = get_mock_google_user();
    
    // Store tokens securely (implement secure storage in production)
    // For now, just return the tokens
    
    Ok(GoogleOAuthCallbackResponse {
        success: true,
        tokens: Some(mock_tokens),
        user: Some(mock_user),
        error: None,
    })
}

#[tauri::command]
pub async fn google_get_connection(
    user_id: String,
) -> Result<GoogleConnectionStatus, String> {
    // Mock implementation - replace with actual token validation
    let mock_user = get_mock_google_user();
    let mock_tokens = GoogleOAuthToken {
        access_token: "mock_google_access_token_12345".to_string(),
        refresh_token: "mock_google_refresh_token_67890".to_string(),
        token_type: "Bearer".to_string(),
        expires_at: chrono::Utc::now() + chrono::Duration::hours(1),
        scope: "gmail.send gmail.readonly calendar.events drive.file".to_string(),
    };
    
    Ok(GoogleConnectionStatus {
        connected: true,
        user: Some(mock_user),
        tokens: Some(mock_tokens),
        last_sync: Some(chrono::Utc::now().to_rfc3339()),
        expires_at: Some((chrono::Utc::now() + chrono::Duration::hours(1)).to_rfc3339()),
    })
}

#[tauri::command]
pub async fn google_disconnect(
    user_id: String,
) -> Result<bool, String> {
    // Mock implementation - replace with actual token deletion
    // In real implementation, this would delete stored tokens
    
    Ok(true)
}

#[tauri::command]
pub async fn google_check_tokens(
    user_id: String,
) -> Result<HashMap<String, serde_json::Value>, String> {
    // Mock implementation - replace with actual token validation
    let valid = chrono::Utc::now().timestamp() < 1735632000; // expires in 2025
    
    Ok(HashMap::from([
        ("valid".to_string(), serde_json::Value::Bool(valid)),
        ("expires_at".to_string(), serde_json::Value::String("2025-01-01T00:00:00Z".to_string())),
        ("message".to_string(), serde_json::Value::String(if valid { "Tokens are valid".to_string() } else { "Tokens have expired".to_string() }))
    ]))
}

#[tauri::command]
pub async fn google_refresh_tokens(
    user_id: String,
    refresh_token: String,
) -> Result<HashMap<String, serde_json::Value>, String> {
    // Mock implementation - replace with actual token refresh
    Ok(HashMap::from([
        ("success".to_string(), serde_json::Value::Bool(true)),
        ("access_token".to_string(), serde_json::Value::String("new_mock_google_access_token_12345".to_string())),
        ("refresh_token".to_string(), serde_json::Value::String("new_mock_google_refresh_token_67890".to_string())),
        ("expires_at".to_string(), serde_json::Value::String((chrono::Utc::now() + chrono::Duration::hours(1)).to_rfc3339()))
    ]))
}

// ============= HELPER FUNCTIONS =============

fn is_valid_email(email: &str) -> bool {
    // Basic email validation
    if email.is_empty() || email.len() > 254 {
        return false;
    }
    
    // Check for @ symbol
    let parts: Vec<&str> = email.split('@').collect();
    if parts.len() != 2 {
        return false;
    }
    
    let (local_part, domain) = (parts[0], parts[1]);
    
    // Validate local part
    if local_part.is_empty() || local_part.len() > 64 {
        return false;
    }
    
    // Validate domain
    if domain.is_empty() || domain.len() > 253 {
        return false;
    }
    
    // Check for at least one dot in domain
    if !domain.contains('.') {
        return false;
    }
    
    true
}

fn is_valid_filename(name: &str) -> bool {
    // Basic filename validation
    if name.is_empty() || name.len() > 255 {
        return false;
    }
    
    // Check for invalid characters
    let invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00'];
    if name.chars().any(|c| invalid_chars.contains(&c)) {
        return false;
    }
    
    true
}