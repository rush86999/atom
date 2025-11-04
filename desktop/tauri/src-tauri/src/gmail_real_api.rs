// Real Gmail API Implementation
use crate::google_types::*;
use crate::google_http_client::{GoogleApiClient, GoogleApiConfig};
use anyhow::Result;

// Real Gmail API client
pub struct GmailApiClient {
    client: GoogleApiClient,
    rate_limiter: crate::google_http_client::RateLimiter,
}

impl GmailApiClient {
    pub fn new(
        access_token: String,
        user_id: String,
    ) -> Result<Self> {
        let google_client = GoogleApiClient::new(access_token, user_id, None)?;
        
        Ok(Self {
            client: google_client,
            rate_limiter: crate::google_http_client::RateLimiter::new(100), // 100 requests per second
        })
    }

    // List emails using Gmail API
    pub async fn list_emails(
        &mut self,
        query: Option<String>,
        max_results: Option<u32>,
        include_attachments: Option<bool>,
        include_spam: Option<bool>,
        include_trash: Option<bool>,
        page_token: Option<String>,
    ) -> Result<GoogleEmailListResponse> {
        self.rate_limiter.wait_if_needed().await;

        let mut params = vec![
            ("userId", "me"),
        ];

        if let Some(q) = &query {
            params.push(("q", q.as_str()));
        }

        if let Some(max) = max_results {
            params.push(("maxResults", &max.to_string()));
        }

        if let Some(token) = &page_token {
            params.push(("pageToken", token.as_str()));
        }

        // Handle label filtering
        let mut label_ids = vec!["INBOX"];
        if include_spam.unwrap_or(false) {
            label_ids.push("SPAM");
        }
        if include_trash.unwrap_or(false) {
            label_ids.push("TRASH");
        }

        params.push(("labelIds", &label_ids.join(",")));
        params.push(("includeSpamTrash", &include_spam.unwrap_or(false).to_string()));
        
        // Build URL
        let url = "https://gmail.googleapis.com/gmail/v1/users/me/messages";
        
        // Get message list
        let response: serde_json::Value = self.client.get(url, Some(params)).await?;
        
        let mut emails = Vec::new();
        if let Some(messages) = response["messages"].as_array() {
            for message in messages {
                if let Some(email) = self.get_single_email(
                    message["id"].as_str().unwrap_or("")
                ).await? {
                    emails.push(email);
                }
            }
        }

        let next_page_token = response["nextPageToken"]
            .as_str()
            .map(|s| s.to_string());

        Ok(GoogleEmailListResponse {
            messages: emails,
            next_page_token,
            result_size_estimate: response["resultSizeEstimate"].as_u64().unwrap_or(0) as u32,
        })
    }

    // Search emails
    pub async fn search_emails(
        &mut self,
        query: String,
        max_results: Option<u32>,
        page_token: Option<String>,
    ) -> Result<GoogleSearchResult> {
        self.rate_limiter.wait_if_needed().await;

        let mut params = vec![
            ("userId", "me"),
            ("q", &query),
        ];

        if let Some(max) = max_results {
            params.push(("maxResults", &max.to_string()));
        }

        if let Some(token) = &page_token {
            params.push(("pageToken", token.as_str()));
        }

        let url = "https://gmail.googleapis.com/gmail/v1/users/me/messages";
        
        // Get search results
        let response: serde_json::Value = self.client.get(url, Some(params)).await?;
        
        let mut emails = Vec::new();
        if let Some(messages) = response["messages"].as_array() {
            for message in messages.take(max_results.unwrap_or(20) as usize) {
                if let Some(email) = self.get_single_email(
                    message["id"].as_str().unwrap_or("")
                ).await? {
                    emails.push(email);
                }
            }
        }

        Ok(GoogleSearchResult {
            emails: Some(emails),
            calendar_events: None,
            drive_files: None,
            next_page_token: response["nextPageToken"].as_str().map(|s| s.to_string()),
            total_results: Some(response["resultSizeEstimate"].as_u64().unwrap_or(0) as u32),
        })
    }

    // Get single email by ID
    async fn get_single_email(&mut self, message_id: &str) -> Result<Option<GoogleEmail>> {
        self.rate_limiter.wait_if_needed().await;

        let url = format!("https://gmail.googleapis.com/gmail/v1/users/me/messages/{}", message_id);
        let params = vec![
            ("format", "full"),
            ("metadataHeaders", "From,To,Subject,Date"),
        ];

        let response: serde_json::Value = self.client.get(&url, Some(params)).await?;
        
        self.parse_gmail_message(&response)
    }

    // Parse Gmail message format
    fn parse_gmail_message(&self, message: &serde_json::Value) -> Result<Option<GoogleEmail>> {
        let payload = &message["payload"];
        let headers = &payload["headers"];
        
        // Extract basic headers
        let mut subject = "";
        let mut from = "";
        let mut to = Vec::new();
        let mut date = "";
        let mut is_read = false;
        let mut is_important = false;
        let mut is_starred = false;

        if let Some(header_array) = headers.as_array() {
            for header in header_array {
                let name = header["name"].as_str().unwrap_or("");
                let value = header["value"].as_str().unwrap_or("");
                
                match name {
                    "Subject" => subject = value,
                    "From" => from = value,
                    "To" => {
                        to = value.split(',').map(|s| s.trim().to_string()).collect();
                    }
                    "Date" => date = value,
                    _ => {}
                }
            }
        }

        // Extract labels
        let mut labels = Vec::new();
        if let Some(label_array) = message["labelIds"].as_array() {
            for label in label_array {
                if let Some(label_str) = label.as_str() {
                    labels.push(label_str.to_string());
                    
                    match label_str {
                        "UNREAD" => is_read = false,
                        "STARRED" => is_starred = true,
                        "IMPORTANT" => is_important = true,
                        _ => {}
                    }
                }
            }
        }

        // Extract body
        let (body, html_body) = self.extract_email_body(&payload);

        // Extract attachments
        let (has_attachments, attachments) = self.extract_attachments(&payload);

        Ok(Some(GoogleEmail {
            id: message["id"].as_str().unwrap_or("").to_string(),
            thread_id: message["threadId"].as_str().unwrap_or("").to_string(),
            from: from.to_string(),
            to,
            cc: None,
            bcc: None,
            subject: subject.to_string(),
            body,
            html_body,
            snippet: message["snippet"].as_str().unwrap_or("").to_string(),
            timestamp: date.to_string(),
            is_read,
            is_important,
            is_starred,
            has_attachments,
            attachments: if attachments.is_empty() { None } else { Some(attachments) },
            labels,
        }))
    }

    // Extract email body from Gmail payload
    fn extract_email_body(&self, payload: &serde_json::Value) -> (String, Option<String>) {
        let mut body = String::new();
        let mut html_body = None;

        // Look for text parts
        if let Some(parts) = payload["parts"].as_array() {
            for part in parts {
                if let Some(mime_type) = part["mimeType"].as_str() {
                    match mime_type {
                        "text/plain" => {
                            if let Some(data) = part["body"]["data"].as_str() {
                                if let Ok(decoded) = base64::decode(data) {
                                    body = String::from_utf8_lossy(&decoded).to_string();
                                }
                            }
                        }
                        "text/html" => {
                            if let Some(data) = part["body"]["data"].as_str() {
                                if let Ok(decoded) = base64::decode(data) {
                                    html_body = Some(String::from_utf8_lossy(&decoded).to_string());
                                }
                            }
                        }
                        _ => {}
                    }
                }
            }
        } else if let Some(data) = payload["body"]["data"].as_str() {
            // Single part message
            if let Ok(decoded) = base64::decode(data) {
                body = String::from_utf8_lossy(&decoded).to_string();
            }
        }

        (body, html_body)
    }

    // Extract attachments from Gmail payload
    fn extract_attachments(&self, payload: &serde_json::Value) -> (bool, Vec<GoogleEmailAttachment>) {
        let mut attachments = Vec::new();
        let mut has_attachments = false;

        if let Some(parts) = payload["parts"].as_array() {
            for part in parts {
                if let Some(mime_type) = part["mimeType"].as_str() {
                    if mime_type.starts_with("application/") || 
                       mime_type.starts_with("image/") || 
                       mime_type.starts_with("video/") ||
                       mime_type.starts_with("audio/") {
                        
                        has_attachments = true;
                        
                        if let Some(filename) = part["filename"].as_str() {
                            if let Some(attachment_id) = part["body"]["attachmentId"].as_str() {
                                attachments.push(GoogleEmailAttachment {
                                    id: attachment_id.to_string(),
                                    filename: filename.to_string(),
                                    mime_type: mime_type.to_string(),
                                    size: part["body"]["size"].as_u64().unwrap_or(0),
                                    url: Some(format!(
                                        "https://gmail.googleapis.com/gmail/v1/users/me/attachments/{}",
                                        attachment_id
                                    )),
                                });
                            }
                        }
                    }
                }
            }
        }

        (has_attachments, attachments)
    }

    // Send email
    pub async fn send_email(
        &mut self,
        to: Vec<String>,
        cc: Option<Vec<String>>,
        bcc: Option<Vec<String>>,
        subject: String,
        body: String,
        html_body: Option<String>,
        attachments: Option<Vec<GoogleEmailAttachmentData>>,
    ) -> Result<GoogleEmailSendResponse> {
        self.rate_limiter.wait_if_needed().await;

        // Create RFC 822 message
        let mime_message = self.create_mime_message(
            to.clone(),
            cc.clone(),
            bcc.clone(),
            subject.clone(),
            body.clone(),
            html_body.clone(),
            attachments.clone(),
        )?;

        // URL encode the message
        let encoded_message = base64::encode(mime_message.as_bytes());

        // Prepare request
        let request_body = serde_json::json!({
            "raw": encoded_message
        });

        let url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send";
        
        // Send the email
        let response: serde_json::Value = self.client.post(url, &request_body, None).await?;
        
        if let Some(id) = response["id"].as_str() {
            Ok(GoogleEmailSendResponse {
                success: true,
                message_id: Some(id.to_string()),
                error: None,
            })
        } else {
            Ok(GoogleEmailSendResponse {
                success: false,
                message_id: None,
                error: Some("Failed to send email".to_string()),
            })
        }
    }

    // Create MIME message for sending
    fn create_mime_message(
        &self,
        to: Vec<String>,
        cc: Option<Vec<String>>,
        bcc: Option<Vec<String>>,
        subject: String,
        body: String,
        html_body: Option<String>,
        _attachments: Option<Vec<GoogleEmailAttachmentData>>,
    ) -> Result<String> {
        let mut message = String::new();
        
        // Headers
        message.push_str(&format!("To: {}\r\n", to.join(", ")));
        
        if let Some(cc_list) = cc {
            if !cc_list.is_empty() {
                message.push_str(&format!("Cc: {}\r\n", cc_list.join(", ")));
            }
        }
        
        if let Some(bcc_list) = bcc {
            if !bcc_list.is_empty() {
                message.push_str(&format!("Bcc: {}\r\n", bcc_list.join(", ")));
            }
        }
        
        message.push_str(&format!("Subject: {}\r\n", subject));
        message.push_str(&format!("Date: {}\r\n", chrono::Utc::now().to_rfc2822()));
        message.push_str("MIME-Version: 1.0\r\n");
        
        if let Some(html) = html_body {
            // Multipart alternative
            message.push_str("Content-Type: multipart/alternative; boundary=\"boundary123\"\r\n\r\n");
            message.push_str("--boundary123\r\n");
            message.push_str("Content-Type: text/plain; charset=UTF-8\r\n\r\n");
            message.push_str(&body);
            message.push_str("\r\n--boundary123\r\n");
            message.push_str("Content-Type: text/html; charset=UTF-8\r\n\r\n");
            message.push_str(&html);
            message.push_str("\r\n--boundary123--");
        } else {
            // Plain text
            message.push_str("Content-Type: text/plain; charset=UTF-8\r\n\r\n");
            message.push_str(&body);
        }
        
        Ok(message)
    }

    // Mark email
    pub async fn mark_email(
        &mut self,
        email_id: String,
        action: &str,
    ) -> Result<GoogleEmailActionResponse> {
        self.rate_limiter.wait_if_needed().await;

        let url = format!("https://gmail.googleapis.com/gmail/v1/users/me/messages/{}", email_id);
        
        // Determine the label change based on action
        let (add_labels, remove_labels) = match action {
            "read" => (vec!["INBOX"], vec!["UNREAD"]),
            "unread" => (vec!["UNREAD"], vec!["INBOX"]),
            "starred" => (vec!["STARRED"], vec![]),
            "unstarred" => (vec![], vec!["STARRED"]),
            "important" => (vec!["IMPORTANT"], vec![]),
            "unimportant" => (vec![], vec!["IMPORTANT"]),
            _ => (vec![], vec![]),
        };

        let request_body = serde_json::json!({
            "addLabelIds": add_labels,
            "removeLabelIds": remove_labels,
        });

        let response: serde_json::Value = self.client.post(&url, &request_body, None).await?;
        
        Ok(GoogleEmailActionResponse {
            success: response["labelIds"].as_array().is_some(),
            error: None,
        })
    }

    // Delete email
    pub async fn delete_email(
        &mut self,
        email_id: String,
        permanently: bool,
    ) -> Result<GoogleEmailActionResponse> {
        self.rate_limiter.wait_if_needed().await;

        let url = if permanently {
            format!("https://gmail.googleapis.com/gmail/v1/users/me/messages/{}", email_id)
        } else {
            format!("https://gmail.googleapis.com/gmail/v1/users/me/messages/{}?trash=true", email_id)
        };

        if let Err(e) = self.client.delete(&url, None).await {
            Ok(GoogleEmailActionResponse {
                success: false,
                error: Some(e.to_string()),
            })
        } else {
            Ok(GoogleEmailActionResponse {
                success: true,
                error: None,
            })
        }
    }
}