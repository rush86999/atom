// Asana Tauri Commands - Real Implementation
// No mock data - calls backend API for all operations

use reqwest;
use serde_json::{json, Value};
use std::collections::HashMap;
use tauri::{AppHandle, Manager};

const BACKEND_BASE_URL: &str = "http://localhost:8083";

/// Initiate Asana OAuth flow by calling backend API
#[tauri::command]
pub async fn initiate_asana_oauth(user_id: String) -> Result<Value, String> {
    println!("🔐 Initiating Asana OAuth flow for user: {}", user_id);

    let client = reqwest::Client::new();
    let url = format!(
        "{}/api/auth/asana/authorize?user_id={}",
        BACKEND_BASE_URL, user_id
    );

    match client.get(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Asana OAuth initiated successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana OAuth response: {}", e);
                        Err(format!("Failed to parse OAuth response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Asana OAuth initiation failed with status: {}", status);
                Err(format!("OAuth initiation failed: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana OAuth endpoint: {}", e);
            Err(format!("Failed to call OAuth endpoint: {}", e))
        }
    }
}

/// Check Asana OAuth status by calling backend API
#[tauri::command]
pub async fn check_asana_oauth_status(user_id: String) -> Result<Value, String> {
    println!("🔍 Checking Asana OAuth status for user: {}", user_id);

    let client = reqwest::Client::new();
    let url = format!(
        "{}/api/auth/asana/status?user_id={}",
        BACKEND_BASE_URL, user_id
    );

    match client.get(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Asana status check successful");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana status response: {}", e);
                        Err(format!("Failed to parse status response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Asana status check failed with status: {}", status);
                Err(format!("Status check failed: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana status endpoint: {}", e);
            Err(format!("Failed to call status endpoint: {}", e))
        }
    }
}

/// Disconnect Asana integration by calling backend API
#[tauri::command]
pub async fn disconnect_asana(user_id: String) -> Result<Value, String> {
    println!("🚫 Disconnecting Asana integration for user: {}", user_id);

    let client = reqwest::Client::new();
    let url = format!("{}/api/auth/asana/disconnect", BACKEND_BASE_URL);

    match client
        .post(&url)
        .json(&json!({ "user_id": user_id }))
        .send()
        .await
    {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Asana disconnected successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana disconnect response: {}", e);
                        Err(format!("Failed to parse disconnect response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Asana disconnect failed with status: {}", status);
                Err(format!("Disconnect failed: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana disconnect endpoint: {}", e);
            Err(format!("Failed to call disconnect endpoint: {}", e))
        }
    }
}

/// Get Asana tasks by calling backend API
#[tauri::command]
pub async fn get_asana_tasks(
    user_id: String,
    project_id: Option<String>,
    limit: Option<usize>,
    completed: Option<bool>,
) -> Result<Value, String> {
    println!("📋 Getting Asana tasks for user: {}", user_id);

    let client = reqwest::Client::new();
    let mut url = format!("{}/api/asana/tasks?user_id={}", BACKEND_BASE_URL, user_id);

    if let Some(project_id) = project_id {
        url.push_str(&format!("&project_id={}", project_id));
    }
    if let Some(limit) = limit {
        url.push_str(&format!("&limit={}", limit));
    }
    if let Some(completed) = completed {
        url.push_str(&format!("&completed={}", completed));
    }

    match client.get(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Retrieved Asana tasks successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana tasks response: {}", e);
                        Err(format!("Failed to parse tasks response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Failed to get Asana tasks with status: {}", status);
                Err(format!("Failed to get tasks: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana tasks endpoint: {}", e);
            Err(format!("Failed to call tasks endpoint: {}", e))
        }
    }
}

/// Create Asana task by calling backend API
#[tauri::command]
pub async fn create_asana_task(
    user_id: String,
    name: String,
    notes: Option<String>,
    due_on: Option<String>,
    assignee: Option<String>,
    projects: Option<Vec<String>>,
) -> Result<Value, String> {
    println!("➕ Creating Asana task for user: {}", user_id);

    let client = reqwest::Client::new();
    let url = format!("{}/api/asana/tasks", BACKEND_BASE_URL);

    let task_data = json!({
        "user_id": user_id,
        "name": name,
        "notes": notes,
        "due_on": due_on,
        "assignee": assignee,
        "projects": projects
    });

    match client.post(&url).json(&task_data).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Asana task created successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana task creation response: {}", e);
                        Err(format!("Failed to parse task creation response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Asana task creation failed with status: {}", status);
                Err(format!("Task creation failed: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana task creation endpoint: {}", e);
            Err(format!("Failed to call task creation endpoint: {}", e))
        }
    }
}

/// Update Asana task by calling backend API
#[tauri::command]
pub async fn update_asana_task(
    user_id: String,
    task_id: String,
    name: Option<String>,
    notes: Option<String>,
    due_on: Option<String>,
    assignee: Option<String>,
    completed: Option<bool>,
) -> Result<Value, String> {
    println!("✏️ Updating Asana task {} for user: {}", task_id, user_id);

    let client = reqwest::Client::new();
    let url = format!("{}/api/asana/tasks/{}", BACKEND_BASE_URL, task_id);

    let update_data = json!({
        "user_id": user_id,
        "name": name,
        "notes": notes,
        "due_on": due_on,
        "assignee": assignee,
        "completed": completed
    });

    match client.put(&url).json(&update_data).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Asana task updated successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana task update response: {}", e);
                        Err(format!("Failed to parse task update response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Asana task update failed with status: {}", status);
                Err(format!("Task update failed: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana task update endpoint: {}", e);
            Err(format!("Failed to call task update endpoint: {}", e))
        }
    }
}

/// Get Asana projects by calling backend API
#[tauri::command]
pub async fn get_asana_projects(
    user_id: String,
    team_id: Option<String>,
    limit: Option<usize>,
) -> Result<Value, String> {
    println!("📁 Getting Asana projects for user: {}", user_id);

    let client = reqwest::Client::new();
    let mut url = format!(
        "{}/api/asana/projects?user_id={}",
        BACKEND_BASE_URL, user_id
    );

    if let Some(team_id) = team_id {
        url.push_str(&format!("&team_id={}", team_id));
    }
    if let Some(limit) = limit {
        url.push_str(&format!("&limit={}", limit));
    }

    match client.get(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Retrieved Asana projects successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana projects response: {}", e);
                        Err(format!("Failed to parse projects response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Failed to get Asana projects with status: {}", status);
                Err(format!("Failed to get projects: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana projects endpoint: {}", e);
            Err(format!("Failed to call projects endpoint: {}", e))
        }
    }
}

/// Get Asana teams by calling backend API
#[tauri::command]
pub async fn get_asana_teams(user_id: String, limit: Option<usize>) -> Result<Value, String> {
    println!("👥 Getting Asana teams for user: {}", user_id);

    let client = reqwest::Client::new();
    let mut url = format!("{}/api/asana/teams?user_id={}", BACKEND_BASE_URL, user_id);

    if let Some(limit) = limit {
        url.push_str(&format!("&limit={}", limit));
    }

    match client.get(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Retrieved Asana teams successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana teams response: {}", e);
                        Err(format!("Failed to parse teams response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Failed to get Asana teams with status: {}", status);
                Err(format!("Failed to get teams: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana teams endpoint: {}", e);
            Err(format!("Failed to call teams endpoint: {}", e))
        }
    }
}

/// Get Asana users by calling backend API
#[tauri::command]
pub async fn get_asana_users(
    user_id: String,
    team_id: Option<String>,
    limit: Option<usize>,
) -> Result<Value, String> {
    println!("👤 Getting Asana users for user: {}", user_id);

    let client = reqwest::Client::new();
    let mut url = format!("{}/api/asana/users?user_id={}", BACKEND_BASE_URL, user_id);

    if let Some(team_id) = team_id {
        url.push_str(&format!("&team_id={}", team_id));
    }
    if let Some(limit) = limit {
        url.push_str(&format!("&limit={}", limit));
    }

    match client.get(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Retrieved Asana users successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana users response: {}", e);
                        Err(format!("Failed to parse users response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Failed to get Asana users with status: {}", status);
                Err(format!("Failed to get users: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana users endpoint: {}", e);
            Err(format!("Failed to call users endpoint: {}", e))
        }
    }
}

/// Get Asana user profile by calling backend API
#[tauri::command]
pub async fn get_asana_user_profile(user_id: String) -> Result<Value, String> {
    println!("👤 Getting Asana user profile for user: {}", user_id);

    let client = reqwest::Client::new();
    let url = format!(
        "{}/api/asana/users/me?user_id={}",
        BACKEND_BASE_URL, user_id
    );

    match client.get(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Retrieved Asana user profile successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana user profile response: {}", e);
                        Err(format!("Failed to parse user profile response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!(
                    "❌ Failed to get Asana user profile with status: {}",
                    status
                );
                Err(format!("Failed to get user profile: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana user profile endpoint: {}", e);
            Err(format!("Failed to call user profile endpoint: {}", e))
        }
    }
}

/// Search Asana by calling backend API
#[tauri::command]
pub async fn search_asana(
    user_id: String,
    query: String,
    limit: Option<usize>,
) -> Result<Value, String> {
    println!(
        "🔍 Searching Asana for query: '{}' for user: {}",
        query, user_id
    );

    let client = reqwest::Client::new();
    let mut url = format!(
        "{}/api/asana/search?user_id={}&query={}",
        BACKEND_BASE_URL, user_id, query
    );

    if let Some(limit) = limit {
        url.push_str(&format!("&limit={}", limit));
    }

    match client.get(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Asana search completed successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana search response: {}", e);
                        Err(format!("Failed to parse search response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Asana search failed with status: {}", status);
                Err(format!("Search failed: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana search endpoint: {}", e);
            Err(format!("Failed to call search endpoint: {}", e))
        }
    }
}

/// Create Asana project by calling backend API
#[tauri::command]
pub async fn create_asana_project(
    user_id: String,
    name: String,
    notes: Option<String>,
    team_id: Option<String>,
    color: Option<String>,
) -> Result<Value, String> {
    println!("📁 Creating Asana project for user: {}", user_id);

    let client = reqwest::Client::new();
    let url = format!("{}/api/asana/projects", BACKEND_BASE_URL);

    let project_data = json!({
        "user_id": user_id,
        "name": name,
        "notes": notes,
        "team_id": team_id,
        "color": color
    });

    match client.post(&url).json(&project_data).send().await {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Asana project created successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana project creation response: {}", e);
                        Err(format!("Failed to parse project creation response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Asana project creation failed with status: {}", status);
                Err(format!("Project creation failed: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana project creation endpoint: {}", e);
            Err(format!("Failed to call project creation endpoint: {}", e))
        }
    }
}

/// Complete Asana task by calling backend API
#[tauri::command]
pub async fn complete_asana_task(user_id: String, task_id: String) -> Result<Value, String> {
    println!("✅ Completing Asana task {} for user: {}", task_id, user_id);

    let client = reqwest::Client::new();
    let url = format!("{}/api/asana/tasks/{}/complete", BACKEND_BASE_URL, task_id);

    match client
        .post(&url)
        .json(&json!({ "user_id": user_id }))
        .send()
        .await
    {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Asana task completed successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana task completion response: {}", e);
                        Err(format!("Failed to parse task completion response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Asana task completion failed with status: {}", status);
                Err(format!("Task completion failed: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana task completion endpoint: {}", e);
            Err(format!("Failed to call task completion endpoint: {}", e))
        }
    }
}

/// Add comment to Asana task by calling backend API
#[tauri::command]
pub async fn add_asana_comment(
    user_id: String,
    task_id: String,
    comment: String,
) -> Result<Value, String> {
    println!(
        "💬 Adding comment to Asana task {} for user: {}",
        task_id, user_id
    );

    let client = reqwest::Client::new();
    let url = format!("{}/api/asana/tasks/{}/comments", BACKEND_BASE_URL, task_id);

    match client
        .post(&url)
        .json(&json!({
            "user_id": user_id,
            "comment": comment
        }))
        .send()
        .await
    {
        Ok(response) => {
            if response.status().is_success() {
                match response.json::<Value>().await {
                    Ok(data) => {
                        println!("✅ Asana comment added successfully");
                        Ok(data)
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to parse Asana comment response: {}", e);
                        Err(format!("Failed to parse comment response: {}", e))
                    }
                }
            } else {
                let status = response.status();
                eprintln!("❌ Asana comment addition failed with status: {}", status);
                Err(format!("Comment addition failed: {}", status))
            }
        }
        Err(e) => {
            eprintln!("❌ Failed to call Asana comment endpoint: {}", e);
            Err(format!("Failed to call comment endpoint: {}", e))
        }
    }
}
