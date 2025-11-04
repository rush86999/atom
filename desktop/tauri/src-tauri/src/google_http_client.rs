// Google HTTP Client for real API calls
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use chrono::{DateTime, Utc};
use url::Url;

// Google API Configuration
pub struct GoogleApiConfig {
    pub base_url: String,
    pub gmail_url: String,
    pub calendar_url: String,
    pub drive_url: String,
    pub oauth_url: String,
    pub timeout_seconds: u64,
    pub max_retries: u32,
}

impl Default for GoogleApiConfig {
    fn default() -> Self {
        Self {
            base_url: "https://www.googleapis.com".to_string(),
            gmail_url: "https://gmail.googleapis.com".to_string(),
            calendar_url: "https://www.googleapis.com/calendar/v3".to_string(),
            drive_url: "https://www.googleapis.com/drive/v3".to_string(),
            oauth_url: "https://oauth2.googleapis.com".to_string(),
            timeout_seconds: 30,
            max_retries: 3,
        }
    }
}

// Google API Client
pub struct GoogleApiClient {
    client: Client,
    config: GoogleApiConfig,
    access_token: String,
    user_id: String,
}

impl GoogleApiClient {
    pub fn new(
        access_token: String,
        user_id: String,
        config: Option<GoogleApiConfig>,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(
                config.as_ref().unwrap_or(&GoogleApiConfig::default()).timeout_seconds
            ))
            .build()?;

        let api_config = config.unwrap_or_default();

        Ok(Self {
            client,
            config: api_config,
            access_token,
            user_id,
        })
    }

    // Helper method to add authorization header
    fn auth_headers(&self) -> Vec<(&str, &str)> {
        vec![
            ("Authorization", &format!("Bearer {}", self.access_token)),
            ("Accept", "application/json"),
            ("Content-Type", "application/json"),
        ]
    }

    // Helper method for GET requests
    pub async fn get<T: for<'de> Deserialize<'de>>(
        &self,
        url: &str,
        params: Option<Vec<(&str, &str)>>,
    ) -> Result<T, Box<dyn std::error::Error>> {
        let mut request_url = Url::parse(url)?;
        
        if let Some(parameters) = params {
            for (key, value) in parameters {
                request_url.query_pairs_mut().append_pair(key, value);
            }
        }

        let mut headers = HashMap::new();
        for (key, value) in self.auth_headers() {
            headers.insert(key.to_string(), value.to_string());
        }

        let response = self.client
            .get(request_url)
            .headers(headers.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect())
            .send()
            .await?;

        if response.status().is_success() {
            let response_text = response.text().await?;
            let result = serde_json::from_str::<T>(&response_text)?;
            Ok(result)
        } else {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            Err(format!("Google API Error: {} - {}", status, error_text).into())
        }
    }

    // Helper method for POST requests
    pub async fn post<T: for<'de> Deserialize<'de>, B: Serialize>(
        &self,
        url: &str,
        body: &B,
        params: Option<Vec<(&str, &str)>>,
    ) -> Result<T, Box<dyn std::error::Error>> {
        let mut request_url = Url::parse(url)?;
        
        if let Some(parameters) = params {
            for (key, value) in parameters {
                request_url.query_pairs_mut().append_pair(key, value);
            }
        }

        let mut headers = HashMap::new();
        for (key, value) in self.auth_headers() {
            headers.insert(key.to_string(), value.to_string());
        }

        let json_body = serde_json::to_string(body)?;
        let response = self.client
            .post(request_url)
            .headers(headers.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect())
            .body(json_body)
            .send()
            .await?;

        if response.status().is_success() {
            let response_text = response.text().await?;
            let result = serde_json::from_str::<T>(&response_text)?;
            Ok(result)
        } else {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            Err(format!("Google API Error: {} - {}", status, error_text).into())
        }
    }

    // Helper method for PUT requests
    pub async fn put<T: for<'de> Deserialize<'de>, B: Serialize>(
        &self,
        url: &str,
        body: &B,
    ) -> Result<T, Box<dyn std::error::Error>> {
        let mut headers = HashMap::new();
        for (key, value) in self.auth_headers() {
            headers.insert(key.to_string(), value.to_string());
        }

        let json_body = serde_json::to_string(body)?;
        let response = self.client
            .put(url)
            .headers(headers.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect())
            .body(json_body)
            .send()
            .await?;

        if response.status().is_success() {
            let response_text = response.text().await?;
            let result = serde_json::from_str::<T>(&response_text)?;
            Ok(result)
        } else {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            Err(format!("Google API Error: {} - {}", status, error_text).into())
        }
    }

    // Helper method for DELETE requests
    pub async fn delete(
        &self,
        url: &str,
        params: Option<Vec<(&str, &str)>>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let mut request_url = Url::parse(url)?;
        
        if let Some(parameters) = params {
            for (key, value) in parameters {
                request_url.query_pairs_mut().append_pair(key, value);
            }
        }

        let mut headers = HashMap::new();
        for (key, value) in self.auth_headers() {
            headers.insert(key.to_string(), value.to_string());
        }

        let response = self.client
            .delete(request_url)
            .headers(headers.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect())
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            Err(format!("Google API Error: {} - {}", status, error_text).into())
        }
    }

    // Helper method for multipart uploads (for Drive file uploads)
    pub async fn upload_multipart<T: for<'de> Deserialize<'de>>(
        &self,
        url: &str,
        metadata: &serde_json::Value,
        file_content: Option<Vec<u8>>,
        content_type: Option<&str>,
        params: Option<Vec<(&str, &str)>>,
    ) -> Result<T, Box<dyn std::error::Error>> {
        use reqwest::multipart;

        let mut request_url = Url::parse(url)?;
        if let Some(parameters) = params {
            for (key, value) in parameters {
                request_url.query_pairs_mut().append_pair(key, value);
            }
        }

        let mut form = multipart::Form::new();
        form = form.part("metadata", multipart::Part::text(serde_json::to_string(metadata)?));

        if let Some(content) = file_content {
            let file_part = multipart::Part::bytes(content)
                .file_name("file")
                .mime_str(content_type.unwrap_or("application/octet-stream"))?;
            form = form.part("file", file_part);
        }

        let mut headers = HashMap::new();
        for (key, value) in self.auth_headers() {
            headers.insert(key.to_string(), value.to_string());
        }

        let response = self.client
            .post(request_url)
            .headers(headers.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect())
            .multipart(form)
            .send()
            .await?;

        if response.status().is_success() {
            let response_text = response.text().await?;
            let result = serde_json::from_str::<T>(&response_text)?;
            Ok(result)
        } else {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            Err(format!("Google API Upload Error: {} - {}", status, error_text).into())
        }
    }
}

// Google API Response wrapper
#[derive(Debug, Serialize, Deserialize)]
pub struct GoogleApiResponse<T> {
    pub data: Option<T>,
    pub error: Option<serde_json::Value>,
    pub next_page_token: Option<String>,
}

// Rate limiting helper
pub struct RateLimiter {
    requests_per_second: u32,
    last_request_time: std::time::Instant,
    request_count: u32,
}

impl RateLimiter {
    pub fn new(requests_per_second: u32) -> Self {
        Self {
            requests_per_second,
            last_request_time: std::time::Instant::now(),
            request_count: 0,
        }
    }

    pub async fn wait_if_needed(&mut self) {
        let now = std::time::Instant::now();
        let duration_since_last = now.duration_since(self.last_request_time);
        
        // Reset counter if a second has passed
        if duration_since_last >= std::time::Duration::from_secs(1) {
            self.request_count = 0;
            self.last_request_time = now;
            return;
        }
        
        // If we've hit the limit, wait
        if self.request_count >= self.requests_per_second {
            let wait_time = std::time::Duration::from_secs(1) - duration_since_last;
            tokio::time::sleep(wait_time).await;
            self.request_count = 0;
            self.last_request_time = std::time::Instant::now();
        }
        
        self.request_count += 1;
    }
}

// Retry logic helper
pub async fn retry_with_backoff<F, T, E>(
    max_retries: u32,
    mut operation: F,
) -> Result<T, E>
where
    F: FnMut() -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<T, E>> + Send>>,
{
    let mut last_error = None;
    
    for attempt in 0..=max_retries {
        match operation().await {
            Ok(result) => return Ok(result),
            Err(error) => {
                last_error = Some(error);
                
                if attempt < max_retries {
                    let delay_ms = 1000 * 2_u64.pow(attempt); // Exponential backoff
                    tokio::time::sleep(std::time::Duration::from_millis(delay_ms)).await;
                }
            }
        }
    }
    
    Err(last_error.unwrap())
}

// OAuth2 token refresh helper
pub async fn refresh_google_token(
    refresh_token: &str,
    client_id: &str,
    client_secret: &str,
) -> Result<crate::google_types::GoogleOAuthToken, Box<dyn std::error::Error>> {
    let client = Client::new();
    
    let mut params = HashMap::new();
    params.insert("grant_type", "refresh_token");
    params.insert("refresh_token", refresh_token);
    params.insert("client_id", client_id);
    params.insert("client_secret", client_secret);

    let response = client
        .post("https://oauth2.googleapis.com/token")
        .form(&params)
        .send()
        .await?;

    if response.status().is_success() {
        let response_text = response.text().await?;
        let token_response: serde_json::Value = serde_json::from_str(&response_text)?;
        
        Ok(crate::google_types::GoogleOAuthToken {
            access_token: token_response["access_token"]
                .as_str()
                .unwrap_or("")
                .to_string(),
            refresh_token: refresh_token.to_string(),
            token_type: token_response["token_type"]
                .as_str()
                .unwrap_or("Bearer")
                .to_string(),
            expires_at: (Utc::now() + chrono::Duration::seconds(
                token_response["expires_in"]
                    .as_u64()
                    .unwrap_or(3600)
            )).to_rfc3339(),
            scope: token_response["scope"]
                .as_str()
                .unwrap_or("")
                .to_string(),
        })
    } else {
        Err("Failed to refresh Google token".into())
    }
}

// Validate Google access token
pub async fn validate_google_token(
    access_token: &str,
) -> Result<bool, Box<dyn std::error::Error>> {
    let client = Client::new();
    
    let response = client
        .get("https://www.googleapis.com/oauth2/v2/userinfo")
        .header("Authorization", format!("Bearer {}", access_token))
        .send()
        .await?;

    Ok(response.status().is_success())
}