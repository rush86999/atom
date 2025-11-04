/**
 * Next.js Desktop Tauri Commands
 * Tauri backend commands for Next.js/Vercel desktop integration
 */

use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use serde::{Deserialize, Serialize};
use tauri::{command, State};
use tokio::time::{interval, Duration};

// Data structures
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NextjsProject {
    pub id: String,
    pub name: String,
    pub description: Option<String>,
    pub status: String,
    pub framework: String,
    pub runtime: String,
    pub domains: Vec<String>,
    pub created_at: String,
    pub updated_at: String,
    pub build_status: Option<String>,
    pub deployment_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NextjsHealth {
    pub connected: bool,
    pub error: Option<String>,
    pub last_check: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NextjsConfig {
    pub enable_notifications: bool,
    pub background_sync: bool,
    pub real_time_sync: bool,
    pub sync_frequency: String,
    pub max_projects: u32,
}

// Application state
pub struct AppState {
    pub projects: Arc<Mutex<Vec<NextjsProject>>>,
    pub health: Arc<Mutex<NextjsHealth>>,
    pub config: Arc<Mutex<NextjsConfig>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            projects: Arc::new(Mutex::new(Vec::new())),
            health: Arc::new(Mutex::new(NextjsHealth {
                connected: false,
                error: None,
                last_check: chrono::Utc::now().to_rfc3339().to_string(),
            })),
            config: Arc::new(Mutex::new(NextjsConfig {
                enable_notifications: true,
                background_sync: true,
                real_time_sync: true,
                sync_frequency: "realtime".to_string(),
                max_projects: 50,
            })),
        }
    }
}

// Commands
#[command]
pub async fn check_nextjs_health(state: State<'_, AppState>) -> Result<NextjsHealth, String> {
    // Check Next.js service health
    let health = match check_service_health().await {
        Ok(health) => health,
        Err(e) => NextjsHealth {
            connected: false,
            error: Some(e.to_string()),
            last_check: chrono::Utc::now().to_rfc3339().to_string(),
        }
    };

    // Update state
    {
        let mut health_state = state.health.lock().unwrap();
        *health_state = health.clone();
    }

    Ok(health)
}

#[command]
pub async fn start_nextjs_oauth(
    user_id: String,
    scopes: Vec<String>,
    state: State<'_, AppState>
) -> Result<HashMap<String, String>, String> {
    // Generate OAuth URL
    let auth_url = generate_oauth_url(&user_id, &scopes).await?;
    
    // Store OAuth state
    // In a real implementation, you'd store this securely
    
    let mut result = HashMap::new();
    result.insert("auth_url".to_string(), auth_url);
    result.insert("success".to_string(), "true".to_string());
    result.insert("user_id".to_string(), user_id);

    Ok(result)
}

#[command]
pub async fn load_nextjs_projects(
    user_id: String,
    limit: u32,
    state: State<'_, AppState>
) -> Result<HashMap<String, serde_json::Value>, String> {
    // Load projects from API
    let projects = fetch_projects(&user_id, limit).await?;
    
    // Update state
    {
        let mut projects_state = state.projects.lock().unwrap();
        *projects_state = projects.clone();
    }

    let mut result = HashMap::new();
    result.insert("success".to_string(), serde_json::Value::Bool(true));
    result.insert("projects".to_string(), serde_json::to_value(&projects).unwrap());
    
    Ok(result)
}

#[command]
pub async fn trigger_nextjs_deployment(
    user_id: String,
    project_id: String,
    branch: String,
    state: State<'_, AppState>
) -> Result<HashMap<String, String>, String> {
    // Trigger deployment
    match trigger_deployment(&user_id, &project_id, &branch).await {
        Ok(deployment_url) => {
            let mut result = HashMap::new();
            result.insert("success".to_string(), "true".to_string());
            result.insert("deployment_url".to_string(), deployment_url);
            result.insert("project_id".to_string(), project_id);
            result.insert("branch".to_string(), branch);
            
            Ok(result)
        }
        Err(e) => {
            let mut result = HashMap::new();
            result.insert("success".to_string(), "false".to_string());
            result.insert("error".to_string(), e.to_string());
            
            Ok(result)
        }
    }
}

#[command]
pub async fn start_nextjs_ingestion(
    user_id: String,
    config: NextjsConfig,
    state: State<'_, AppState>
) -> Result<HashMap<String, String>, String> {
    // Update configuration
    {
        let mut config_state = state.config.lock().unwrap();
        *config_state = config.clone();
    }

    // Start ingestion process
    match start_ingestion_process(&user_id, &config).await {
        Ok(()) => {
            let mut result = HashMap::new();
            result.insert("success".to_string(), "true".to_string());
            result.insert("status".to_string(), "started".to_string());
            
            Ok(result)
        }
        Err(e) => {
            let mut result = HashMap::new();
            result.insert("success".to_string(), "false".to_string());
            result.insert("error".to_string(), e.to_string());
            
            Ok(result)
        }
    }
}

#[command]
pub async fn get_nextjs_project_details(
    project_id: String,
    state: State<'_, AppState>
) -> Result<Option<NextjsProject>, String> {
    let projects = state.projects.lock().unwrap();
    
    for project in projects.iter() {
        if project.id == project_id {
            return Ok(Some(project.clone()));
        }
    }
    
    Ok(None)
}

#[command]
pub async fn open_nextjs_project_in_browser(
    project: NextjsProject
) -> Result<(), String> {
    // Open project in default browser
    let url = project.deployment_url.unwrap_or_else(|| {
        format!("https://vercel.com/dashboard/{}", project.id)
    });
    
    match webbrowser::open(&url) {
        Ok(_) => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}

#[command]
pub async fn send_desktop_notification(
    title: String,
    body: String
) -> Result<(), String> {
    // Send desktop notification
    match notify_rust::Notification::new()
        .summary(&title)
        .body(&body)
        .show()
    {
        Ok(_) => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}

#[command]
pub async fn get_nextjs_settings(state: State<'_, AppState>) -> Result<NextjsConfig, String> {
    let config = state.config.lock().unwrap();
    Ok(config.clone())
}

#[command]
pub async fn update_nextjs_settings(
    config: NextjsConfig,
    state: State<'_, AppState>
) -> Result<(), String> {
    // Update configuration
    {
        let mut config_state = state.config.lock().unwrap();
        *config_state = config.clone();
    }

    // Save to persistent storage if needed
    // In a real implementation, you'd save this to disk/database
    
    Ok(())
}

#[command]
pub async fn open_vercel_dashboard() -> Result<(), String> {
    match webbrowser::open("https://vercel.com/dashboard") {
        Ok(_) => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}

#[command]
pub async fn get_ingestion_status(state: State<'_, AppState>) -> Result<HashMap<String, String>, String> {
    // Return current ingestion status
    let config = state.config.lock().unwrap();
    let health = state.health.lock().unwrap();
    
    let mut result = HashMap::new();
    result.insert("running".to_string(), health.connected.to_string());
    result.insert("projects_processed".to_string(), state.projects.lock().unwrap().len().to_string());
    result.insert("background_sync".to_string(), config.background_sync.to_string());
    result.insert("real_time_sync".to_string(), config.real_time_sync.to_string());
    
    Ok(result)
}

// Helper functions
async fn check_service_health() -> Result<NextjsHealth, Box<dyn std::error::Error>> {
    // Check Next.js service health by making API request
    let client = reqwest::Client::new();
    
    let response = client
        .get("http://localhost:5058/api/nextjs/health")
        .send()
        .await?;

    let health_data: serde_json::Value = response.json().await?;
    
    let connected = health_data["status"] == "healthy";
    let error = health_data["services"]["nextjs"]["error"].as_str()
        .map(|s| Some(s.to_string()))
        .unwrap_or(None);
    
    Ok(NextjsHealth {
        connected,
        error,
        last_check: chrono::Utc::now().to_rfc3339().to_string(),
    })
}

async fn generate_oauth_url(user_id: &str, scopes: &[String]) -> Result<String, Box<dyn std::error::Error>> {
    // Generate OAuth URL with state parameter
    let state = format!("{}_{}", user_id, chrono::Utc::now().timestamp());
    let scopes_str = scopes.join(" ");
    
    let client = reqwest::Client::new();
    
    let mut params = HashMap::new();
    params.insert("user_id".to_string(), user_id.to_string());
    params.insert("scopes".to_string(), scopes_str);
    params.insert("platform".to_string(), "tauri".to_string());
    
    let response = client
        .post("http://localhost:5058/api/auth/nextjs/authorize")
        .json(&params)
        .send()
        .await?;
    
    let data: serde_json::Value = response.json().await?;
    
    if let Some(auth_url) = data["authorization_url"].as_str() {
        Ok(auth_url.to_string())
    } else {
        Err("Failed to generate OAuth URL".into())
    }
}

async fn fetch_projects(user_id: &str, limit: u32) -> Result<Vec<NextjsProject>, Box<dyn std::error::Error>> {
    // Fetch projects from backend API
    let client = reqwest::Client::new();
    
    let mut params = HashMap::new();
    params.insert("user_id".to_string(), user_id.to_string());
    params.insert("limit".to_string(), limit.to_string());
    params.insert("include_deployments".to_string(), "true".to_string());
    
    let response = client
        .post("http://localhost:5058/api/integrations/nextjs/projects")
        .json(&params)
        .send()
        .await?;
    
    let data: serde_json::Value = response.json().await?;
    
    if let Some(projects_json) = data["projects"].as_array() {
        let projects: Result<Vec<NextjsProject>, _> = serde_json::from_value(serde_json::Value::Array(projects_json.clone()));
        projects.map_err(|e| e.into())
    } else {
        Err("No projects found".into())
    }
}

async fn trigger_deployment(
    user_id: &str,
    project_id: &str,
    branch: &str
) -> Result<String, Box<dyn std::error::Error>> {
    // Trigger deployment via backend API
    let client = reqwest::Client::new();
    
    let mut params = HashMap::new();
    params.insert("user_id".to_string(), user_id.to_string());
    params.insert("project_id".to_string(), project_id.to_string());
    params.insert("branch".to_string(), branch.to_string());
    
    let response = client
        .post("http://localhost:5058/api/integrations/nextjs/deploy")
        .json(&params)
        .send()
        .await?;
    
    let data: serde_json::Value = response.json().await?;
    
    if let Some(deployment_url) = data["deployment_url"].as_str() {
        Ok(deployment_url.to_string())
    } else {
        Err("Failed to trigger deployment".into())
    }
}

async fn start_ingestion_process(
    user_id: &str,
    config: &NextjsConfig
) -> Result<(), Box<dyn std::error::Error>> {
    // Start background ingestion process
    if config.background_sync {
        // Start background sync task
        tokio::spawn(async move {
            let mut interval = interval(Duration::from_secs(60)); // Every minute
            
            loop {
                interval.tick().await;
                
                // Check if ingestion should continue
                if !config.background_sync {
                    break;
                }
                
                // Perform sync
                match fetch_projects(user_id, config.max_projects).await {
                    Ok(_) => {
                        // Send notification on successful sync
                        let _ = send_desktop_notification(
                            "Next.js Sync Completed".to_string(),
                            "Projects synced successfully".to_string()
                        ).await;
                    }
                    Err(e) => {
                        eprintln!("Sync error: {}", e);
                    }
                }
            }
        });
    }
    
    Ok(())
}

// Background task runner
pub async fn run_background_tasks(state: Arc<AppState>) {
    let config = state.config.lock().unwrap().clone();
    
    if config.background_sync {
        let mut interval = interval(Duration::from_secs(300)); // Every 5 minutes
        
        loop {
            interval.tick().await;
            
            let current_config = state.config.lock().unwrap().clone();
            if !current_config.background_sync {
                break;
            }
            
            // Perform health check
            match check_service_health().await {
                Ok(health) => {
                    let mut health_state = state.health.lock().unwrap();
                    *health_state = health.clone();
                    
                    if !health.connected {
                        let _ = send_desktop_notification(
                            "Next.js Connection Lost".to_string(),
                            "Unable to connect to Next.js service".to_string()
                        ).await;
                    }
                }
                Err(e) => {
                    eprintln!("Health check error: {}", e);
                }
            }
        }
    }
}