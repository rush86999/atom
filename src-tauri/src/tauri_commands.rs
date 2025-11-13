use serde_json::json;
use tauri::AppHandle;
use std::collections::HashMap;

// Import atom_agent_commands functions
pub use atom_agent_commands::{
    process_atom_agent_message, 
    open_file_dialog, 
    open_chat_settings, 
    get_chat_preferences
};

/// Get Dexcom JWT
#[tauri::command]
pub async fn get_dexcom_jwt(params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    Ok(json!({
        "jwt": "mock_dexcom_jwt_token",
        "service": "dexcom",
        "expires_in": 3600
    }))
}

/// Get FDA JWT
#[tauri::command]
pub async fn get_fda_jwt(params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    Ok(json!({
        "jwt": "mock_fda_jwt_token",
        "service": "fda",
        "expires_in": 3600
    }))
}

/// Get Novolog JWT
#[tauri::command]
pub async fn get_novolog_jwt(params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    Ok(json!({
        "jwt": "mock_novolog_jwt_token",
        "service": "novolog",
        "expires_in": 3600
    }))
}

/// Get MyFitnessPal JWT
#[tauri::command]
pub async fn get_myfitnesspal_jwt(params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    Ok(json!({
        "jwt": "mock_myfitnesspal_jwt_token",
        "service": "myfitnesspal",
        "expires_in": 3600
    }))
}

/// Get Oura JWT
#[tauri::command]
pub async fn get_oura_jwt(params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    Ok(json!({
        "jwt": "mock_oura_jwt_token",
        "service": "oura",
        "expires_in": 3600
    }))
}

/// Get Withings JWT
#[tauri::command]
pub async fn get_withings_jwt(params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    Ok(json!({
        "jwt": "mock_withings_jwt_token",
        "service": "withings",
        "expires_in": 3600
    }))
}

/// Get MyHeritage JWT
#[tauri::command]
pub async fn get_myheritage_jwt(params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    Ok(json!({
        "jwt": "mock_myheritage_jwt_token",
        "service": "myheritage",
        "expires_in": 3600
    }))
}

/// Get LabCorp JWT
#[tauri::command]
pub async fn get_labcorp_jwt(params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    Ok(json!({
        "jwt": "mock_labcorp_jwt_token",
        "service": "labcorp",
        "expires_in": 3600
    }))
}

/// Get Quest JWT
#[tauri::command]
pub async fn get_quest_jwt(params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    Ok(json!({
        "jwt": "mock_quest_jwt_token",
        "service": "quest",
        "expires_in": 3600
    }))
}

/// Get CareEvolve JWT
#[tauri::command]
pub async fn get_careevolve_jwt(params: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    Ok(json!({
        "jwt": "mock_careevolve_jwt_token",
        "service": "careevolve",
        "expires_in": 3600
    }))
}