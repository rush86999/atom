// Google API Types for ATOM Desktop Backend

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// Common Google Types
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleUser {
    pub id: String,
    pub email: String,
    pub name: String,
    pub avatar: Option<String>,
    pub verified: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEmail {
    pub id: String,
    pub thread_id: String,
    pub from: String,
    pub to: Vec<String>,
    pub cc: Option<Vec<String>>,
    pub bcc: Option<Vec<String>>,
    pub subject: String,
    pub body: String,
    pub html_body: Option<String>,
    pub snippet: String,
    pub timestamp: String,
    pub is_read: bool,
    pub is_important: bool,
    pub is_starred: bool,
    pub has_attachments: bool,
    pub attachments: Option<Vec<GoogleEmailAttachment>>,
    pub labels: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEmailAttachment {
    pub id: String,
    pub filename: String,
    pub mime_type: String,
    pub size: u64,
    pub url: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleCalendar {
    pub id: String,
    pub summary: String,
    pub description: Option<String>,
    pub location: Option<String>,
    pub color: Option<String>,
    pub timezone: Option<String>,
    pub primary: bool,
    pub access_role: String,
    pub selected: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleCalendarEvent {
    pub id: String,
    pub calendar_id: String,
    pub summary: String,
    pub description: Option<String>,
    pub location: Option<String>,
    pub start_time: String,
    pub end_time: String,
    pub all_day: bool,
    pub attendees: Option<Vec<GoogleEventAttendee>>,
    pub organizer: Option<GoogleEventOrganizer>,
    pub attachments: Option<Vec<GoogleEventAttachment>>,
    pub recurrence: Option<Vec<String>>,
    pub visibility: Option<String>,
    pub transparency: Option<String>,
    pub status: String,
    pub created: String,
    pub updated: String,
    pub html_link: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEventAttendee {
    pub email: String,
    pub display_name: Option<String>,
    pub response_status: String,
    pub is_self: Option<bool>,
    pub is_organizer: Option<bool>,
    pub is_optional: Option<bool>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEventOrganizer {
    pub email: String,
    pub display_name: Option<String>,
    pub is_self: Option<bool>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEventAttachment {
    pub id: String,
    pub title: String,
    pub mime_type: String,
    pub icon_link: Option<String>,
    pub file_url: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveFile {
    pub id: String,
    pub name: String,
    pub mime_type: String,
    pub size: Option<String>,
    pub created_time: String,
    pub modified_time: String,
    pub viewed_by_me_time: Option<String>,
    pub parents: Option<Vec<String>>,
    pub web_view_link: Option<String>,
    pub web_content_link: Option<String>,
    pub icon_link: String,
    pub thumbnail_link: Option<String>,
    pub owned_by_me: bool,
    pub permissions: Option<Vec<GoogleDrivePermission>>,
    pub spaces: Vec<String>,
    pub folder_color_rgb: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDrivePermission {
    pub id: String,
    pub r#type: String,
    pub role: String,
    pub email_address: Option<String>,
    pub domain: Option<String>,
    pub display_name: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleSearchResult {
    pub emails: Option<Vec<GoogleEmail>>,
    pub calendar_events: Option<Vec<GoogleCalendarEvent>>,
    pub drive_files: Option<Vec<GoogleDriveFile>>,
    pub next_page_token: Option<String>,
    pub total_results: Option<u32>,
}

// Gmail API Response Types
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEmailListResponse {
    pub messages: Vec<GoogleEmail>,
    pub next_page_token: Option<String>,
    pub result_size_estimate: u32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEmailSendResponse {
    pub success: bool,
    pub message_id: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEmailActionResponse {
    pub success: bool,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEmailAttachmentData {
    pub filename: String,
    pub content: String,
    pub mime_type: Option<String>,
}

// Google Calendar API Response Types
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleCalendarListResponse {
    pub calendars: Vec<GoogleCalendar>,
    pub next_page_token: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEventsListResponse {
    pub events: Vec<GoogleCalendarEvent>,
    pub next_page_token: Option<String>,
    pub time_zone: Option<String>,
    pub default_reminders: Option<Vec<GoogleEventReminder>>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleEventReminder {
    pub method: String,
    pub minutes: i32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleCalendarEventResponse {
    pub success: bool,
    pub event_id: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleCalendarActionResponse {
    pub success: bool,
    pub error: Option<String>,
}

// Google Drive API Response Types
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveFileListResponse {
    pub files: Vec<GoogleDriveFile>,
    pub next_page_token: Option<String>,
    pub incomplete_search: bool,
    pub kind: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveSearchResponse {
    pub files: Vec<GoogleDriveFile>,
    pub next_page_token: Option<String>,
    pub total_results: Option<u32>,
    pub incomplete_search: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveUploadResponse {
    pub success: bool,
    pub id: String,
    pub name: String,
    pub mime_type: String,
    pub size: Option<String>,
    pub web_view_link: Option<String>,
    pub web_content_link: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveActionResponse {
    pub success: bool,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveShareResponse {
    pub success: bool,
    pub file_id: String,
    pub link: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveFileMetadataResponse {
    pub success: bool,
    pub file: Option<GoogleDriveFile>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveDownloadResponse {
    pub success: bool,
    pub content: String,
    pub mime_type: Option<String>,
    pub error: Option<String>,
}

// OAuth2 Token Types
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleOAuthToken {
    pub access_token: String,
    pub refresh_token: String,
    pub token_type: String,
    pub expires_at: String,
    pub scope: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleOAuthUrlResponse {
    pub success: bool,
    pub auth_url: String,
    pub state: String,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleOAuthCallbackResponse {
    pub success: bool,
    pub tokens: Option<GoogleOAuthToken>,
    pub user: Option<GoogleUser>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleConnectionStatus {
    pub connected: bool,
    pub user: Option<GoogleUser>,
    pub tokens: Option<GoogleOAuthToken>,
    pub last_sync: Option<String>,
    pub expires_at: Option<String>,
}

// Configuration Types
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleConfig {
    pub client_id: String,
    pub client_secret: String,
    pub redirect_uri: String,
    pub scopes: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleApiConfig {
    pub base_url: String,
    pub gmail_url: String,
    pub calendar_url: String,
    pub drive_url: String,
    pub oauth_url: String,
    pub timeout_seconds: u64,
    pub max_retries: u32,
}

// Error Types
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleApiError {
    pub code: String,
    pub message: String,
    pub details: Option<HashMap<String, serde_json::Value>>,
    pub status: i32,
}

// Request Types for Tauri Commands
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GmailListRequest {
    pub user_id: String,
    pub query: Option<String>,
    pub max_results: Option<u32>,
    pub include_attachments: Option<bool>,
    pub include_spam: Option<bool>,
    pub include_trash: Option<bool>,
    pub page_token: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GmailSendRequest {
    pub user_id: String,
    pub to: Vec<String>,
    pub cc: Option<Vec<String>>,
    pub bcc: Option<Vec<String>>,
    pub subject: String,
    pub body: String,
    pub html_body: Option<String>,
    pub attachments: Option<Vec<GoogleEmailAttachmentData>>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GmailActionRequest {
    pub user_id: String,
    pub email_id: String,
    pub thread_id: Option<String>,
    pub action: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GmailReplyRequest {
    pub user_id: String,
    pub email_id: String,
    pub thread_id: Option<String>,
    pub body: String,
    pub html_body: Option<String>,
    pub to_all: bool,
    pub attachments: Option<Vec<GoogleEmailAttachmentData>>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleCalendarEventsRequest {
    pub user_id: String,
    pub calendar_id: Option<String>,
    pub time_min: Option<String>,
    pub time_max: Option<String>,
    pub q: Option<String>,
    pub max_results: Option<u32>,
    pub single_events: Option<bool>,
    pub order_by: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleCalendarEventRequest {
    pub user_id: String,
    pub calendar_id: Option<String>,
    pub summary: String,
    pub description: Option<String>,
    pub location: Option<String>,
    pub start_time: String,
    pub end_time: String,
    pub all_day: Option<bool>,
    pub attendees: Option<Vec<String>>,
    pub visibility: Option<String>,
    pub transparency: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleCalendarEventUpdateRequest {
    pub user_id: String,
    pub calendar_id: Option<String>,
    pub event_id: String,
    pub summary: Option<String>,
    pub description: Option<String>,
    pub location: Option<String>,
    pub attendees: Option<Vec<String>>,
    pub visibility: Option<String>,
    pub transparency: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleCalendarEventDeleteRequest {
    pub user_id: String,
    pub calendar_id: Option<String>,
    pub event_id: String,
    pub send_updates: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveFilesRequest {
    pub user_id: String,
    pub q: Option<String>,
    pub page_size: Option<u32>,
    pub order_by: Option<String>,
    pub page_token: Option<String>,
    pub spaces: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveFileCreateRequest {
    pub user_id: String,
    pub name: String,
    pub content: Option<String>,
    pub mime_type: Option<String>,
    pub parents: Option<Vec<String>>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveFileDeleteRequest {
    pub user_id: String,
    pub file_id: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GoogleDriveFileShareRequest {
    pub user_id: String,
    pub file_id: String,
    pub role: String,
    pub r#type: String,
    pub email_address: Option<String>,
    pub domain: Option<String>,
    pub send_notification_email: Option<bool>,
}

// Mock Data for Testing
pub fn get_mock_google_user() -> GoogleUser {
    GoogleUser {
        id: "123456789".to_string(),
        email: "user@gmail.com".to_string(),
        name: "Test User".to_string(),
        avatar: Some("https://lh3.googleusercontent.com/avatar.jpg".to_string()),
        verified: true,
    }
}

pub fn get_mock_google_emails() -> Vec<GoogleEmail> {
    vec![
        GoogleEmail {
            id: "msg123".to_string(),
            thread_id: "thread123".to_string(),
            from: "sender@example.com".to_string(),
            to: vec!["user@gmail.com".to_string()],
            cc: None,
            bcc: None,
            subject: "Meeting Tomorrow".to_string(),
            body: "Hi, just a reminder about our meeting tomorrow at 2 PM. Please confirm your attendance.".to_string(),
            html_body: Some("<p>Hi, just a reminder about our meeting tomorrow at 2 PM. Please confirm your attendance.</p>".to_string()),
            snippet: "Hi, just a reminder about our meeting tomorrow at 2 PM...".to_string(),
            timestamp: "2025-11-02T10:30:00Z".to_string(),
            is_read: false,
            is_important: true,
            is_starred: false,
            has_attachments: true,
            attachments: Some(vec![
                GoogleEmailAttachment {
                    id: "att123".to_string(),
                    filename: "agenda.pdf".to_string(),
                    mime_type: "application/pdf".to_string(),
                    size: 1024000,
                    url: Some("https://mail.google.com/attachment".to_string()),
                }
            ]),
            labels: vec!["INBOX".to_string(), "IMPORTANT".to_string()],
        },
        GoogleEmail {
            id: "msg124".to_string(),
            thread_id: "thread124".to_string(),
            from: "newsletter@service.com".to_string(),
            to: vec!["user@gmail.com".to_string()],
            cc: None,
            bcc: None,
            subject: "Your Weekly Newsletter".to_string(),
            body: "This week's highlights and important updates...".to_string(),
            html_body: Some("<html><body><h1>This week's highlights</h1><p>Important updates...</p></body></html>".to_string()),
            snippet: "This week's highlights and important updates...".to_string(),
            timestamp: "2025-11-01T08:00:00Z".to_string(),
            is_read: true,
            is_important: false,
            is_starred: false,
            has_attachments: false,
            attachments: None,
            labels: vec!["INBOX".to_string(), "PROMOTIONS".to_string()],
        }
    ]
}

pub fn get_mock_google_calendars() -> Vec<GoogleCalendar> {
    vec![
        GoogleCalendar {
            id: "cal123".to_string(),
            summary: "Personal".to_string(),
            description: Some("Personal events and appointments".to_string()),
            location: None,
            color: Some("#4285F4".to_string()),
            timezone: Some("America/New_York".to_string()),
            primary: true,
            access_role: "owner".to_string(),
            selected: true,
        },
        GoogleCalendar {
            id: "cal124".to_string(),
            summary: "Work".to_string(),
            description: Some("Work-related events".to_string()),
            location: None,
            color: Some("#EA4335".to_string()),
            timezone: Some("America/New_York".to_string()),
            primary: false,
            access_role: "writer".to_string(),
            selected: true,
        }
    ]
}

pub fn get_mock_google_calendar_events() -> Vec<GoogleCalendarEvent> {
    vec![
        GoogleCalendarEvent {
            id: "evt123".to_string(),
            calendar_id: "cal123".to_string(),
            summary: "Team Meeting".to_string(),
            description: Some("Weekly team sync to discuss project progress".to_string()),
            location: Some("Conference Room A".to_string()),
            start_time: "2025-11-03T14:00:00Z".to_string(),
            end_time: "2025-11-03T15:00:00Z".to_string(),
            all_day: false,
            attendees: Some(vec![
                GoogleEventAttendee {
                    email: "user1@example.com".to_string(),
                    display_name: Some("Alice Johnson".to_string()),
                    response_status: "accepted".to_string(),
                    is_self: Some(false),
                    is_organizer: Some(false),
                    is_optional: Some(false),
                },
                GoogleEventAttendee {
                    email: "user2@example.com".to_string(),
                    display_name: Some("Bob Smith".to_string()),
                    response_status: "tentative".to_string(),
                    is_self: Some(false),
                    is_organizer: Some(false),
                    is_optional: Some(false),
                }
            ]),
            organizer: Some(GoogleEventOrganizer {
                email: "organizer@example.com".to_string(),
                display_name: Some("Project Manager".to_string()),
                is_self: Some(false),
            }),
            attachments: None,
            recurrence: None,
            visibility: Some("default".to_string()),
            transparency: Some("opaque".to_string()),
            status: "confirmed".to_string(),
            created: "2025-10-28T10:00:00Z".to_string(),
            updated: "2025-11-01T15:30:00Z".to_string(),
            html_link: "https://calendar.google.com/event?eid=evt123".to_string(),
        },
        GoogleCalendarEvent {
            id: "evt124".to_string(),
            calendar_id: "cal123".to_string(),
            summary: "Lunch with Client".to_string(),
            description: Some("Discuss project requirements".to_string()),
            location: Some("Downtown Restaurant".to_string()),
            start_time: "2025-11-04T12:30:00Z".to_string(),
            end_time: "2025-11-04T14:00:00Z".to_string(),
            all_day: false,
            attendees: Some(vec![
                GoogleEventAttendee {
                    email: "client@company.com".to_string(),
                    display_name: Some("Client Name".to_string()),
                    response_status: "accepted".to_string(),
                    is_self: Some(false),
                    is_organizer: Some(false),
                    is_optional: Some(false),
                }
            ]),
            organizer: Some(GoogleEventOrganizer {
                email: "user@gmail.com".to_string(),
                display_name: Some("Test User".to_string()),
                is_self: Some(true),
            }),
            attachments: Some(vec![
                GoogleEventAttachment {
                    id: "att123".to_string(),
                    title: "Project_Brief.pdf".to_string(),
                    mime_type: "application/pdf".to_string(),
                    icon_link: Some("https://drive.google.com/icon/pdf".to_string()),
                    file_url: Some("https://drive.google.com/file/d/att123".to_string()),
                }
            ]),
            recurrence: None,
            visibility: Some("private".to_string()),
            transparency: Some("opaque".to_string()),
            status: "confirmed".to_string(),
            created: "2025-11-01T09:00:00Z".to_string(),
            updated: "2025-11-02T16:00:00Z".to_string(),
            html_link: "https://calendar.google.com/event?eid=evt124".to_string(),
        }
    ]
}

pub fn get_mock_google_drive_files() -> Vec<GoogleDriveFile> {
    vec![
        GoogleDriveFile {
            id: "file123".to_string(),
            name: "Project Proposal.docx".to_string(),
            mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document".to_string(),
            size: Some("1048576".to_string()),
            created_time: "2025-10-28T10:00:00Z".to_string(),
            modified_time: "2025-11-01T15:30:00Z".to_string(),
            viewed_by_me_time: Some("2025-11-02T09:15:00Z".to_string()),
            parents: Some(vec!["folder123".to_string()]),
            web_view_link: Some("https://docs.google.com/document/d/file123".to_string()),
            web_content_link: Some("https://docs.google.com/document/d/file123/export".to_string()),
            icon_link: "https://drive.google.com/icon/docx".to_string(),
            thumbnail_link: Some("https://drive.google.com/thumbnail/file123".to_string()),
            owned_by_me: true,
            permissions: Some(vec![
                GoogleDrivePermission {
                    id: "perm123".to_string(),
                    r#type: "user".to_string(),
                    role: "owner".to_string(),
                    email_address: Some("user@gmail.com".to_string()),
                    domain: None,
                    display_name: Some("Test User".to_string()),
                }
            ]),
            spaces: vec!["drive".to_string()],
            folder_color_rgb: None,
        },
        GoogleDriveFile {
            id: "folder123".to_string(),
            name: "Work Projects".to_string(),
            mime_type: "application/vnd.google-apps.folder".to_string(),
            size: None,
            created_time: "2025-09-01T12:00:00Z".to_string(),
            modified_time: "2025-11-01T10:00:00Z".to_string(),
            viewed_by_me_time: Some("2025-11-02T08:30:00Z".to_string()),
            parents: Some(vec!["root".to_string()]),
            web_view_link: Some("https://drive.google.com/drive/folders/folder123".to_string()),
            web_content_link: None,
            icon_link: "https://drive.google.com/icon/folder".to_string(),
            thumbnail_link: None,
            owned_by_me: true,
            permissions: Some(vec![
                GoogleDrivePermission {
                    id: "perm124".to_string(),
                    r#type: "user".to_string(),
                    role: "owner".to_string(),
                    email_address: Some("user@gmail.com".to_string()),
                    domain: None,
                    display_name: Some("Test User".to_string()),
                }
            ]),
            spaces: vec!["drive".to_string()],
            folder_color_rgb: Some("#4285F4".to_string()),
        }
    ]
}