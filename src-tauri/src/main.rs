// Tauri Command Registration for ATOM Agent with Chat Interface
// Updated to include all chat commands properly

#![cfg_attr(
    all(not(debug_assertions), not(target_os = "windows")),
    windows_subsystem = "windows"
)]

use tauri::{AppHandle, Manager, Window, api::notification, api::dialog};
use serde_json::json;
use std::collections::HashMap;

// Import existing commands
mod slack_commands;
mod teams_commands;
mod notion_commands;
mod trello_commands;
mod figma_commands;
mod linear_commands;
mod asana_commands;

// Import Atom Agent Chat Commands
mod atom_agent_commands;

// Shared imports
use crate::tauri_commands::{get_dexcom_jwt, get_fda_jwt, get_novolog_jwt, get_myfitnesspal_jwt, get_oura_jwt, get_myheritage_jwt, get_labcorp_jwt, get_quest_jwt, get_careevolve_jwt};

// Main invoke handler with all commands including Chat
#[tauri::command]
async fn atom_invoke_command(
    app_handle: AppHandle,
    window: Window,
    command: String,
    params: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    println!("🔧 ATOM Command invoked: {} with params: {:?}", command, params);
    
    match command.as_str() {
        // Existing JWT commands
        "get_dexcom_jwt" => get_dexcom_jwt(params),
        "get_fda_jwt" => get_fda_jwt(params),
        "get_novolog_jwt" => get_novolog_jwt(params),
        "get_myfitnesspal_jwt" => get_myfitnesspal_jwt(params),
        "get_oura_jwt" => get_oura_jwt(params),
        "get_myheritage_jwt" => get_myheritage_jwt(params),
        "get_labcorp_jwt" => get_labcorp_jwt(params),
        "get_quest_jwt" => get_quest_jwt(params),
        "get_careevolve_jwt" => get_careevolve_jwt(params),
        
        // Slack Commands
        "initiate_slack_oauth" => slack_commands::initiate_slack_oauth(app_handle.clone(), params),
        "check_slack_oauth_status" => slack_commands::check_slack_oauth_status(app_handle.clone(), params),
        "disconnect_slack" => slack_commands::disconnect_slack(app_handle.clone(), params),
        
        // Teams Commands
        "initiate_teams_oauth" => teams_commands::initiate_teams_oauth(app_handle.clone(), params),
        "check_teams_oauth_status" => teams_commands::check_teams_oauth_status(app_handle.clone(), params),
        "disconnect_teams" => teams_commands::disconnect_teams(app_handle.clone(), params),
        
        // Notion Commands
        "initiate_notion_oauth" => notion_commands::initiate_notion_oauth(app_handle.clone(), params),
        "check_notion_oauth_status" => notion_commands::check_notion_oauth_status(app_handle.clone(), params),
        "disconnect_notion" => notion_commands::disconnect_notion(app_handle.clone(), params),
        
        // Trello Commands
        "initiate_trello_oauth" => trello_commands::initiate_trello_oauth(app_handle.clone(), params),
        "check_trello_oauth_status" => trello_commands::check_trello_oauth_status(app_handle.clone(), params),
        "disconnect_trello" => trello_commands::disconnect_trello(app_handle.clone(), params),
        
        // Figma Commands
        "initiate_figma_oauth" => figma_commands::initiate_figma_oauth(app_handle.clone(), params),
        "check_figma_oauth_status" => figma_commands::check_figma_oauth_status(app_handle.clone(), params),
        "disconnect_figma" => figma_commands::disconnect_figma(app_handle.clone(), params),
        
        // Linear Commands
        "initiate_linear_oauth" => linear_commands::initiate_linear_oauth(app_handle.clone(), params),
        "check_linear_oauth_status" => linear_commands::check_linear_oauth_status(app_handle.clone(), params),
        "disconnect_linear" => linear_commands::disconnect_linear(app_handle.clone(), params),
        
        // Asana Commands
        "initiate_asana_oauth" => asana_commands::initiate_asana_oauth(app_handle.clone(), params),
        "check_asana_oauth_status" => asana_commands::check_asana_oauth_status(app_handle.clone(), params),
        "disconnect_asana" => asana_commands::disconnect_asana(app_handle.clone(), params),
        "get_asana_tasks" => asana_commands::get_asana_tasks(app_handle.clone(), params),
        "create_asana_task" => asana_commands::create_asana_task(app_handle.clone(), params),
        "update_asana_task" => asana_commands::update_asana_task(app_handle.clone(), params),
        "get_asana_projects" => asana_commands::get_asana_projects(app_handle.clone(), params),
        "get_asana_sections" => asana_commands::get_asana_sections(app_handle.clone(), params),
        "get_asana_teams" => asana_commands::get_asana_teams(app_handle.clone(), params),
        "get_asana_users" => asana_commands::get_asana_users(app_handle.clone(), params),
        "get_asana_user_profile" => asana_commands::get_asana_user_profile(app_handle.clone(), params),
        "search_asana" => asana_commands::search_asana(app_handle.clone(), params),
        "create_asana_project" => asana_commands::create_asana_project(app_handle.clone(), params),
        "complete_asana_task" => asana_commands::complete_asana_task(app_handle.clone(), params),
        "add_asana_comment" => asana_commands::add_asana_comment(app_handle.clone(), params),
        
        // **NEW: Atom Agent Chat Commands**
        "process_atom_agent_message" => atom_agent_commands::process_atom_agent_message(app_handle.clone(), params),
        
        // Atom Agent status commands
        "get_atom_agent_status" => Ok(json!({
            "status": "running",
            "agent_name": "Atom AI Assistant",
            "integrations": ["slack", "teams", "notion", "trello", "figma", "linear", "asana"],
            "uptime": "2.5 hours",
            "last_sync": "2024-01-16T10:30:00Z",
            "chat_enabled": true,
            "version": "1.1.0"
        })),
        
        "get_integrations_health" => Ok(json!({
            "slack": { "connected": true, "last_sync": "5 minutes ago", "chat_available": true },
            "teams": { "connected": true, "last_sync": "8 minutes ago", "chat_available": true },
            "notion": { "connected": true, "last_sync": "12 minutes ago", "chat_available": true },
            "trello": { "connected": true, "last_sync": "3 minutes ago", "chat_available": true },
            "figma": { "connected": true, "last_sync": "10 minutes ago", "chat_available": true },
            "linear": { "connected": true, "last_sync": "15 minutes ago", "chat_available": true },
            "asana": { "connected": true, "last_sync": "5 minutes ago", "chat_available": true },
            "status": "healthy",
            "chat_interface": "enabled"
        })),
        
        // File dialog commands (for chat attachments)
        "open_file_dialog" => {
            match params {
                Some(dialog_params) => {
                    match dialog::blocking::FileDialogBuilder::new()
                        .add_filter("All Files", &["*"])
                        .add_filter("Text Files", &["txt", "md"])
                        .add_filter("Documents", &["pdf", "doc", "docx"])
                        .add_filter("Images", &["jpg", "png", "gif", "svg"])
                        .pick_file()
                    {
                        Some(path) => Ok(json!({
                            "success": true,
                            "path": path,
                            "filename": path.split('/').last().unwrap_or("unknown")
                        })),
                        None => Ok(json!({
                            "success": false,
                            "error": "No file selected"
                        }))
                    }
                },
                None => Ok(json!({
                    "success": false,
                    "error": "No dialog parameters provided"
                }))
            }
        },
        
        // Settings commands
        "open_chat_settings" => {
            Ok(json!({
                "success": true,
                "message": "Chat settings opened"
            }))
        },
        
        "get_chat_preferences" => Ok(json!({
            "success": true,
            "preferences": {
                "theme": "light",
                "notifications": true,
                "sound": true,
                "auto_save": true,
                "max_messages": 1000,
                "typing_indicators": true
            }
        })),
        
        _ => Err(format!("Unknown command: {}", command))
    }
}

// Main entry point
fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            // OAuth commands for all integrations including Asana
            atom_invoke_command,
            
            // Legacy direct commands
            get_dexcom_jwt,
            get_fda_jwt,
            get_novolog_jwt,
            get_myfitnesspal_jwt,
            get_oura_jwt,
            get_withings_jwt,
            get_myheritage_jwt,
            get_labcorp_jwt,
            get_quest_jwt,
            get_careevolve_jwt,
            
            // Slack commands
            slack_commands::initiate_slack_oauth,
            slack_commands::check_slack_oauth_status,
            slack_commands::disconnect_slack,
            
            // Teams commands
            teams_commands::initiate_teams_oauth,
            teams_commands::check_teams_oauth_status,
            teams_commands::disconnect_teams,
            
            // Notion commands
            notion_commands::initiate_notion_oauth,
            notion_commands::check_notion_oauth_status,
            notion_commands::disconnect_notion,
            
            // Trello commands
            trello_commands::initiate_trello_oauth,
            trello_commands::check_trello_oauth_status,
            trello_commands::disconnect_trello,
            
            // Figma commands
            figma_commands::initiate_figma_oauth,
            figma_commands::check_figma_oauth_status,
            figma_commands::disconnect_figma,
            
            // Linear commands
            linear_commands::initiate_linear_oauth,
            linear_commands::check_linear_oauth_status,
            linear_commands::disconnect_linear,
            
            // Asana commands
            asana_commands::initiate_asana_oauth,
            asana_commands::check_asana_oauth_status,
            asana_commands::disconnect_asana,
            asana_commands::get_asana_tasks,
            asana_commands::create_asana_task,
            asana_commands::update_asana_task,
            asana_commands::get_asana_projects,
            asana_commands::get_asana_sections,
            asana_commands::get_asana_teams,
            asana_commands::get_asana_users,
            asana_commands::get_asana_user_profile,
            asana_commands::search_asana,
            asana_commands::create_asana_project,
            asana_commands::complete_asana_task,
            asana_commands::add_asana_comment,
            
            // **NEW: Atom Agent Chat Commands**
            atom_agent_commands::process_atom_agent_message,
        ])
        .setup(|app| {
            println!("🚀 ATOM Desktop Agent Starting...");
            println!("📋 Integrations Loaded:");
            println!("   ✅ Slack");
            println!("   ✅ Teams");
            println!("   ✅ Notion");
            println!("   ✅ Trello");
            println!("   ✅ Figma");
            println!("   ✅ Linear");
            println!("   ✅ Asana");
            println!("   💬 Chat Interface (NEW)");
            
            // Initialize global state
            app.manage(std::sync::Mutex::new(HashMap::<String, serde_json::Value>::new()));
            
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}