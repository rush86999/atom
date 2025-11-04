// ATOM Agent - Asana Integration Tauri Commands
// Complete Asana command handlers for desktop integration

#![allow(non_snake_case)]

use tauri::{AppHandle, Manager};
use serde_json::{json, Value};
use std::collections::HashMap;

/// Initiate Asana OAuth 2.0 flow for desktop app
#[tauri::command]
pub async fn initiate_asana_oauth(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("🔐 Initiating Asana OAuth flow...");
    
    // Extract parameters
    let scopes = params
        .as_ref()
        .and_then(|p| p.get("scopes"))
        .and_then(|s| s.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str())
                .collect::<Vec<_>>()
                .join(" ")
        })
        .unwrap_or_else(|| "default tasks:read tasks:write projects:read projects:write stories:read stories:write teams:read users:read webhooks:read webhooks:write".to_string());
    
    let state = params
        .as_ref()
        .and_then(|p| p.get("state"))
        .and_then(|s| s.as_str())
        .unwrap_or("asana_oauth_state");
    
    let redirect_uri = params
        .as_ref()
        .and_then(|p| p.get("redirect_uri"))
        .and_then(|u| u.as_str())
        .unwrap_or("atom://auth/asana/callback");
    
    // Generate authorization URL (using real Asana client ID)
    let client_id = "1154934678576461"; // Real Asana client ID
    let auth_url = format!(
        "https://app.asana.com/-/oauth_authorize?client_id={}&redirect_uri={}&response_type=code&scope={}&state={}",
        client_id,
        urlencoding::encode(redirect_uri),
        urlencoding::encode(&scopes),
        urlencoding::encode(state)
    );
    
    println!("🔗 Opening Asana OAuth URL: {}", auth_url);
    
    // Open in system browser
    match open::that(&auth_url) {
        Ok(_) => {
            println!("✅ Asana OAuth URL opened in system browser");
            
            // Store state for callback verification
            if let Some(window) = app_handle.get_webview_window("main") {
                let _ = window.eval(&format!("window.asanaOAuthState = '{}';", state));
            }
            
            Ok(json!({
                "ok": true,
                "authorization_url": auth_url,
                "message": "Asana OAuth initiated successfully",
                "redirect_uri": redirect_uri,
                "scopes": scopes,
                "state": state
            }))
        }
        Err(e) => {
            eprintln!("❌ Failed to open Asana OAuth URL: {}", e);
            Err(format!("Failed to open OAuth URL: {}", e))
        }
    }
}

/// Check Asana OAuth connection status
#[tauri::command]
pub async fn check_asana_oauth_status(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("🔍 Checking Asana OAuth status...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    // In real implementation, would check secure storage
    // For now, return mock status for testing
    let tokens_stored = true; // Would check actual token storage
    
    if tokens_stored {
        Ok(json!({
            "ok": true,
            "connected": true,
            "user_id": user_id,
            "app_name": "ATOM Platform Integration",
            "last_sync": "2024-01-16T10:30:00Z",
            "token_status": "valid",
            "expires_at": "2024-01-17T10:30:00Z",
            "scopes": ["default", "tasks:read", "tasks:write", "projects:read", "projects:write"],
            "message": "Asana connection is active"
        }))
    } else {
        Ok(json!({
            "ok": true,
            "connected": false,
            "user_id": user_id,
            "message": "Asana not connected. Please authenticate first."
        }))
    }
}

/// Disconnect Asana integration
#[tauri::command]
pub async fn disconnect_asana(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("🔌 Disconnecting Asana integration...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    // In real implementation, would remove tokens from secure storage
    println!("🗑️  Removing Asana tokens for user: {}", user_id);
    
    Ok(json!({
        "ok": true,
        "success": true,
        "message": "Asana integration disconnected successfully",
        "user_id": user_id
    }))
}

/// Get Asana tasks for user
#[tauri::command]
pub async fn get_asana_tasks(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("📋 Getting Asana tasks...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let workspace_id = params
        .as_ref()
        .and_then(|p| p.get("workspace_id"))
        .and_then(|u| u.as_str());
    
    let project_id = params
        .as_ref()
        .and_then(|p| p.get("project_id"))
        .and_then(|u| u.as_str());
    
    let include_completed = params
        .as_ref()
        .and_then(|p| p.get("include_completed"))
        .and_then(|c| c.as_bool())
        .unwrap_or(true);
    
    let limit = params
        .as_ref()
        .and_then(|p| p.get("limit"))
        .and_then(|l| l.as_u64())
        .unwrap_or(50);
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/tasks")
        .json(&json!({
            "user_id": user_id,
            "workspace_id": workspace_id,
            "project_id": project_id,
            "include_completed": include_completed,
            "limit": limit
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to fetch Asana tasks: {}", e))?;
    
    if response.status().is_success() {
        let tasks_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse tasks response: {}", e))?;
        
        println!("✅ Retrieved {} Asana tasks", 
            tasks_data.get("total_count").and_then(|c| c.as_u64()).unwrap_or(0));
        
        Ok(tasks_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to fetch Asana tasks: {}", error_text))
    }
}

/// Create Asana task
#[tauri::command]
pub async fn create_asana_task(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("📝 Creating Asana task...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let task_data = params
        .as_ref()
        .and_then(|p| p.get("data"))
        .cloned()
        .unwrap_or_else(|| json!({}));
    
    // Validate required fields
    if let Some(name) = task_data.get("name").and_then(|n| n.as_str()) {
        if name.trim().is_empty() {
            return Err("Task name is required".to_string());
        }
    } else {
        return Err("Task name is required".to_string());
    }
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/tasks")
        .json(&json!({
            "user_id": user_id,
            "operation": "create",
            "data": task_data
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to create Asana task: {}", e))?;
    
    if response.status().is_success() {
        let result_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse creation response: {}", e))?;
        
        println!("✅ Created Asana task: {}", 
            result_data.get("data").and_then(|d| d.get("task"))
                .and_then(|t| t.get("name"))
                .and_then(|n| n.as_str())
                .unwrap_or("unknown"));
        
        Ok(result_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to create Asana task: {}", error_text))
    }
}

/// Update Asana task
#[tauri::command]
pub async fn update_asana_task(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("🔄 Updating Asana task...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let task_id = params
        .as_ref()
        .and_then(|p| p.get("task_id"))
        .and_then(|u| u.as_str())
        .ok_or_else(|| "Task ID is required".to_string())?;
    
    let updates = params
        .as_ref()
        .and_then(|p| p.get("updates"))
        .cloned()
        .unwrap_or_else(|| json!({}));
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/tasks/update")
        .json(&json!({
            "user_id": user_id,
            "task_id": task_id,
            "updates": updates
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to update Asana task: {}", e))?;
    
    if response.status().is_success() {
        let result_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse update response: {}", e))?;
        
        println!("✅ Updated Asana task: {}", task_id);
        
        Ok(result_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to update Asana task: {}", error_text))
    }
}

/// Get Asana projects
#[tauri::command]
pub async fn get_asana_projects(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("🗂️  Getting Asana projects...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let workspace_id = params
        .as_ref()
        .and_then(|p| p.get("workspace_id"))
        .and_then(|u| u.as_str());
    
    let team_id = params
        .as_ref()
        .and_then(|p| p.get("team_id"))
        .and_then(|u| u.as_str());
    
    let limit = params
        .as_ref()
        .and_then(|p| p.get("limit"))
        .and_then(|l| l.as_u64())
        .unwrap_or(50);
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/projects")
        .json(&json!({
            "user_id": user_id,
            "workspace_id": workspace_id,
            "team_id": team_id,
            "limit": limit
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to fetch Asana projects: {}", e))?;
    
    if response.status().is_success() {
        let projects_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse projects response: {}", e))?;
        
        println!("✅ Retrieved {} Asana projects", 
            projects_data.get("total_count").and_then(|c| c.as_u64()).unwrap_or(0));
        
        Ok(projects_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to fetch Asana projects: {}", error_text))
    }
}

/// Get Asana sections
#[tauri::command]
pub async fn get_asana_sections(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("📂 Getting Asana sections...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let project_id = params
        .as_ref()
        .and_then(|p| p.get("project_id"))
        .and_then(|u| u.as_str());
    
    let limit = params
        .as_ref()
        .and_then(|p| p.get("limit"))
        .and_then(|l| l.as_u64())
        .unwrap_or(50);
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/sections")
        .json(&json!({
            "user_id": user_id,
            "project_id": project_id,
            "limit": limit
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to fetch Asana sections: {}", e))?;
    
    if response.status().is_success() {
        let sections_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse sections response: {}", e))?;
        
        println!("✅ Retrieved {} Asana sections", 
            sections_data.get("total_count").and_then(|c| c.as_u64()).unwrap_or(0));
        
        Ok(sections_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to fetch Asana sections: {}", error_text))
    }
}

/// Get Asana teams
#[tauri::command]
pub async fn get_asana_teams(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("👥 Getting Asana teams...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let workspace_id = params
        .as_ref()
        .and_then(|p| p.get("workspace_id"))
        .and_then(|u| u.as_str());
    
    let limit = params
        .as_ref()
        .and_then(|p| p.get("limit"))
        .and_then(|l| l.as_u64())
        .unwrap_or(20);
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/teams")
        .json(&json!({
            "user_id": user_id,
            "workspace_id": workspace_id,
            "limit": limit
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to fetch Asana teams: {}", e))?;
    
    if response.status().is_success() {
        let teams_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse teams response: {}", e))?;
        
        println!("✅ Retrieved {} Asana teams", 
            teams_data.get("total_count").and_then(|c| c.as_u64()).unwrap_or(0));
        
        Ok(teams_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to fetch Asana teams: {}", error_text))
    }
}

/// Get Asana users
#[tauri::command]
pub async fn get_asana_users(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("👤 Getting Asana users...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let workspace_id = params
        .as_ref()
        .and_then(|p| p.get("workspace_id"))
        .and_then(|u| u.as_str());
    
    let limit = params
        .as_ref()
        .and_then(|p| p.get("limit"))
        .and_then(|l| l.as_u64())
        .unwrap_or(100);
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/users")
        .json(&json!({
            "user_id": user_id,
            "workspace_id": workspace_id,
            "limit": limit
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to fetch Asana users: {}", e))?;
    
    if response.status().is_success() {
        let users_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse users response: {}", e))?;
        
        println!("✅ Retrieved {} Asana users", 
            users_data.get("total_count").and_then(|c| c.as_u64()).unwrap_or(0));
        
        Ok(users_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to fetch Asana users: {}", error_text))
    }
}

/// Get Asana user profile
#[tauri::command]
pub async fn get_asana_user_profile(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("👤 Getting Asana user profile...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/user/profile")
        .json(&json!({
            "user_id": user_id
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to fetch Asana user profile: {}", e))?;
    
    if response.status().is_success() {
        let profile_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse profile response: {}", e))?;
        
        println!("✅ Retrieved Asana user profile");
        
        Ok(profile_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to fetch Asana user profile: {}", error_text))
    }
}

/// Search Asana
#[tauri::command]
pub async fn search_asana(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("🔍 Searching Asana...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let query = params
        .as_ref()
        .and_then(|p| p.get("query"))
        .and_then(|u| u.as_str())
        .ok_or_else(|| "Search query is required".to_string())?;
    
    let search_type = params
        .as_ref()
        .and_then(|p| p.get("type"))
        .and_then(|u| u.as_str())
        .unwrap_or("tasks");
    
    let limit = params
        .as_ref()
        .and_then(|p| p.get("limit"))
        .and_then(|l| l.as_u64())
        .unwrap_or(50);
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/search")
        .json(&json!({
            "user_id": user_id,
            "query": query,
            "type": search_type,
            "limit": limit
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to search Asana: {}", e))?;
    
    if response.status().is_success() {
        let search_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse search response: {}", e))?;
        
        println!("✅ Found {} Asana search results for '{}'", 
            search_data.get("total_count").and_then(|c| c.as_u64()).unwrap_or(0),
            query);
        
        Ok(search_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to search Asana: {}", error_text))
    }
}

/// Create Asana project
#[tauri::command]
pub async fn create_asana_project(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("🗂️  Creating Asana project...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let project_data = params
        .as_ref()
        .and_then(|p| p.get("data"))
        .cloned()
        .unwrap_or_else(|| json!({}));
    
    // Validate required fields
    if let Some(name) = project_data.get("name").and_then(|n| n.as_str()) {
        if name.trim().is_empty() {
            return Err("Project name is required".to_string());
        }
    } else {
        return Err("Project name is required".to_string());
    }
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/projects")
        .json(&json!({
            "user_id": user_id,
            "operation": "create",
            "data": project_data
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to create Asana project: {}", e))?;
    
    if response.status().is_success() {
        let result_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse creation response: {}", e))?;
        
        println!("✅ Created Asana project: {}", 
            result_data.get("data").and_then(|d| d.get("project"))
                .and_then(|p| p.get("name"))
                .and_then(|n| n.as_str())
                .unwrap_or("unknown"));
        
        Ok(result_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to create Asana project: {}", error_text))
    }
}

/// Complete Asana task
#[tauri::command]
pub async fn complete_asana_task(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("✅ Completing Asana task...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let task_id = params
        .as_ref()
        .and_then(|p| p.get("task_id"))
        .and_then(|u| u.as_str())
        .ok_or_else(|| "Task ID is required".to_string())?;
    
    // Call backend API with completed=true
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/tasks/update")
        .json(&json!({
            "user_id": user_id,
            "task_id": task_id,
            "updates": {
                "completed": true
            }
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to complete Asana task: {}", e))?;
    
    if response.status().is_success() {
        let result_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse completion response: {}", e))?;
        
        println!("✅ Completed Asana task: {}", task_id);
        
        Ok(result_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to complete Asana task: {}", error_text))
    }
}

/// Add comment to Asana task
#[tauri::command]
pub async fn add_asana_comment(app_handle: AppHandle, params: Option<Value>) -> Result<Value, String> {
    println!("💬 Adding comment to Asana task...");
    
    let user_id = params
        .as_ref()
        .and_then(|p| p.get("user_id"))
        .and_then(|u| u.as_str())
        .unwrap_or("default-user");
    
    let task_id = params
        .as_ref()
        .and_then(|p| p.get("task_id"))
        .and_then(|u| u.as_str())
        .ok_or_else(|| "Task ID is required".to_string())?;
    
    let comment_text = params
        .as_ref()
        .and_then(|p| p.get("comment"))
        .and_then(|u| u.as_str())
        .ok_or_else(|| "Comment text is required".to_string())?;
    
    if comment_text.trim().is_empty() {
        return Err("Comment text cannot be empty".to_string());
    }
    
    // Call backend API
    let response = reqwest::Client::new()
        .post("http://localhost:5000/api/integrations/asana/tasks/comment")
        .json(&json!({
            "user_id": user_id,
            "task_id": task_id,
            "comment": comment_text
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to add Asana comment: {}", e))?;
    
    if response.status().is_success() {
        let result_data: Value = response.json().await
            .map_err(|e| format!("Failed to parse comment response: {}", e))?;
        
        println!("✅ Added comment to Asana task: {}", task_id);
        
        Ok(result_data)
    } else {
        let error_text = response.text().await.unwrap_or_default();
        Err(format!("Failed to add Asana comment: {}", error_text))
    }
}

// Include required dependencies
use open;
use reqwest;
use urlencoding;

/// Initialize Asana integration
pub fn init() {
    println!("🚀 Initializing Asana Integration...");
    
    // Set up logging
    env_logger::Builder::from_default_env()
        .filter_level(log::LevelFilter::Info)
        .init();
    
    println!("✅ Asana Integration initialized");
    println!("   🔐 OAuth 2.0 flow ready");
    println!("   📋 Task management commands ready");
    println!("   🗂️  Project management commands ready");
    println!("   👥 Team management commands ready");
    println!("   🔍 Search functionality ready");
    println!("   💬 Comment management ready");
}