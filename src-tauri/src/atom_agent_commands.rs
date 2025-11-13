// Tauri Commands for Atom Agent Message Processing
// Missing command to connect existing integrations with new chat interface

use serde_json::json;

use tauri::{api::notification, AppHandle};

/// Process message through Atom AI Agent with existing integrations
#[tauri::command]
async fn process_atom_agent_message(
    app_handle: AppHandle,
    message: String,
    user_id: Option<String>,
    active_integrations: Option<Vec<String>>,
) -> Result<serde_json::Value, String> {
    println!("🤖 Processing Atom Agent Message: {}", message);

    let user_id = user_id.unwrap_or_else(|| "desktop-user".to_string());
    let integrations = active_integrations.unwrap_or_default();

    // Analyze message intent and entities
    let analysis = analyze_message_intent(&message, &integrations).await?;

    // Generate response based on intent and available integrations
    let response = generate_agent_response(&message, &analysis, &integrations, &user_id).await?;

    // Execute integration actions if needed
    let integration_result =
        execute_integration_actions(&analysis, &integrations, app_handle.clone()).await?;

    // Show notification for important actions
    if analysis.intent == "create_task" || analysis.intent == "send_message" {
        show_agent_notification(
            app_handle.clone(),
            "Atom AI Assistant",
            &format!("Action completed: {}", analysis.intent),
        )
        .await;
    }

    let result = json!({
        "success": true,
        "agent": "atom-ai",
        "intent": analysis.intent,
        "entities": analysis.entities,
        "content": response,
        "processing_time": analysis.processing_time,
        "integration_actions": integration_result,
        "metadata": {
            "user_id": user_id,
            "active_integrations": integrations,
            "message_length": message.len(),
            "timestamp": chrono::Utc::now().to_rfc3339()
        }
    });

    println!("✅ Agent Response Generated: {}", result);
    Ok(result)
}

/// Message analysis result
#[derive(serde::Serialize, serde::Deserialize)]
struct MessageAnalysis {
    intent: String,
    entities: Vec<String>,
    confidence: f64,
    integration_needed: Option<String>,
    action_required: Option<String>,
    processing_time: u64,
}

/// Analyze message intent and entities
async fn analyze_message_intent(
    message: &str,
    integrations: &[String],
) -> Result<MessageAnalysis, String> {
    let start_time = std::time::Instant::now();

    // Simple intent recognition logic (can be enhanced with LLM)
    let (intent, entities, confidence) = if message.to_lowercase().contains("slack") {
        ("check_slack_messages", vec!["slack".to_string()], 0.9)
    } else if message.to_lowercase().contains("notion") {
        ("create_notion_document", vec!["notion".to_string()], 0.9)
    } else if message.to_lowercase().contains("asana") {
        ("get_asana_tasks", vec!["asana".to_string()], 0.9)
    } else if message.to_lowercase().contains("teams") {
        ("check_teams_conversations", vec!["teams".to_string()], 0.9)
    } else if message.to_lowercase().contains("trello") {
        ("get_trello_cards", vec!["trello".to_string()], 0.9)
    } else if message.to_lowercase().contains("figma") {
        ("check_figma_designs", vec!["figma".to_string()], 0.9)
    } else if message.to_lowercase().contains("linear") {
        ("get_linear_issues", vec!["linear".to_string()], 0.9)
    } else if message.to_lowercase().contains("create") && message.to_lowercase().contains("task") {
        ("create_task", vec!["task".to_string()], 0.8)
    } else if message.to_lowercase().contains("help") {
        ("show_help", vec!["help".to_string()], 0.7)
    } else if message.to_lowercase().contains("status") {
        ("check_status", vec!["status".to_string()], 0.8)
    } else {
        ("general_inquiry", vec![], 0.5)
    };

    // Determine integration needed based on intent
    let integration_needed = match intent {
        "check_slack_messages" => Some("slack".to_string()),
        "create_notion_document" => Some("notion".to_string()),
        "get_asana_tasks" => Some("asana".to_string()),
        "check_teams_conversations" => Some("teams".to_string()),
        "get_trello_cards" => Some("trello".to_string()),
        "check_figma_designs" => Some("figma".to_string()),
        "get_linear_issues" => Some("linear".to_string()),
        "create_task" if integrations.contains(&"asana".to_string()) => Some("asana".to_string()),
        _ => None,
    };

    // Determine action required
    let action_required = if intent.contains("create") {
        Some("create".to_string())
    } else if intent.contains("check") || intent.contains("get") {
        Some("retrieve".to_string())
    } else {
        None
    };

    // Check if integration is available
    if let Some(ref integration) = integration_needed {
        if !integrations.contains(integration) {
            return Ok(MessageAnalysis {
                intent: intent.to_string(),
                entities,
                confidence,
                integration_needed: None,
                action_required,
                processing_time: start_time.elapsed().as_millis() as u64,
            });
        }
    }

    let processing_time = start_time.elapsed().as_millis();

    Ok(MessageAnalysis {
        intent: intent.to_string(),
        entities,
        confidence,
        integration_needed,
        action_required,
        processing_time: processing_time as u64,
    })
}

/// Generate agent response based on analysis
async fn generate_agent_response(
    message: &str,
    analysis: &MessageAnalysis,
    integrations: &[String],
    _user_id: &str,
) -> Result<String, String> {
    let response = match analysis.intent.as_str() {
        "check_slack_messages" => {
            if integrations.contains(&"slack".to_string()) {
                format!("📋 I'll check your Slack messages for you. Looking for recent conversations and notifications...")
            } else {
                "❌ Slack integration is not connected. Would you like to connect Slack to your Atom account?".to_string()
            }
        }

        "create_notion_document" => {
            if integrations.contains(&"notion".to_string()) {
                format!("📝 I'll create a new Notion document for you. What would you like to title it and what content should it include?")
            } else {
                "❌ Notion integration is not connected. Would you like to connect Notion to your Atom account?".to_string()
            }
        }

        "get_asana_tasks" => {
            if integrations.contains(&"asana".to_string()) {
                format!("📋 I'll retrieve your Asana tasks for you. Let me check your current projects and tasks...")
            } else {
                "❌ Asana integration is not connected. Would you like to connect Asana to your Atom account?".to_string()
            }
        }

        "check_teams_conversations" => {
            if integrations.contains(&"teams".to_string()) {
                format!("💬 I'll check your Microsoft Teams conversations for you. Looking for recent messages and meetings...")
            } else {
                "❌ Microsoft Teams integration is not connected. Would you like to connect Teams to your Atom account?".to_string()
            }
        }

        "get_trello_cards" => {
            if integrations.contains(&"trello".to_string()) {
                format!("📋 I'll retrieve your Trello cards for you. Let me check your current boards and cards...")
            } else {
                "❌ Trello integration is not connected. Would you like to connect Trello to your Atom account?".to_string()
            }
        }

        "check_figma_designs" => {
            if integrations.contains(&"figma".to_string()) {
                format!("🎨 I'll check your Figma designs for you. Looking for recent projects and files...")
            } else {
                "❌ Figma integration is not connected. Would you like to connect Figma to your Atom account?".to_string()
            }
        }

        "get_linear_issues" => {
            if integrations.contains(&"linear".to_string()) {
                format!("🐛 I'll retrieve your Linear issues for you. Let me check your current projects and issues...")
            } else {
                "❌ Linear integration is not connected. Would you like to connect Linear to your Atom account?".to_string()
            }
        }

        "create_task" => {
            if integrations.contains(&"asana".to_string()) {
                format!("✅ I'll create a new task for you in Asana. What should the task title be and which project should it go in?")
            } else {
                "❌ Asana integration is not connected. Would you like to connect Asana to create tasks?".to_string()
            }
        }

        "show_help" => {
            format!(
                "🤖 I'm Atom AI Assistant! I can help you manage your integrated services:

Available actions:
• Check Slack messages
• Create Notion documents
• Get Asana tasks
• Check Teams conversations
• Search Trello cards
• Check Figma designs
• Get Linear issues
• Create tasks in Asana

Try saying: 'Check my Slack messages' or 'Create a Notion document'

Connected integrations: {}",
                if integrations.is_empty() {
                    "None - Connect some services to get started!"
                } else {
                    let joined = integrations.join(", ");
                    &joined
                }
            )
        }

        "check_status" => {
            let integration_status = if integrations.is_empty() {
                "No integrations connected"
            } else {
                &format!(
                    "{} integrations connected: {}",
                    integrations.len(),
                    integrations.join(", ")
                )
            };

            format!(
                "📊 Atom AI Status: Online
Agent: Ready and waiting
Integrations: {}
Response Time: {}ms

I'm here to help you manage your connected services. What would you like to do?",
                integration_status, analysis.processing_time
            )
        }

        _ => {
            if integrations.is_empty() {
                format!("👋 Welcome! I'm Atom AI Assistant. I notice you don't have any integrations connected yet.

I can help you with services like Slack, Notion, Asana, Teams, Trello, Figma, and Linear.

To get started, try connecting one of these services and then ask me to:
• Check your messages
• Create documents
• Get your tasks
• Search your projects

What would you like to do?")
            } else {
                format!(
                    "🤔 I understand you're asking about: '{}'.

With your connected services ({}, I can help you:
• Check messages from Slack/Teams
• Create documents in Notion
• Manage tasks in Asana/Trello
• Search designs in Figma
• Track issues in Linear

Could you be more specific about what you'd like to do?",
                    message,
                    integrations.join(", ")
                )
            }
        }
    };

    Ok(response)
}

/// Execute integration actions based on analysis
async fn execute_integration_actions(
    analysis: &MessageAnalysis,
    integrations: &[String],
    _app_handle: AppHandle,
) -> Result<serde_json::Value, String> {
    let mut actions = Vec::new();

    // Execute integration-specific actions
    if let Some(ref integration) = analysis.integration_needed {
        if !integrations.contains(integration) {
            return Ok(json!({
                "actions": [],
                "error": "Integration not connected"
            }));
        }

        match integration.as_str() {
            "slack" => {
                // Simulate Slack action
                actions.push(json!({
                    "integration": "slack",
                    "action": "check_messages",
                    "status": "initiated",
                    "timestamp": chrono::Utc::now().to_rfc3339()
                }));
            }

            "notion" => {
                // Simulate Notion action
                actions.push(json!({
                    "integration": "notion",
                    "action": "create_document",
                    "status": "initiated",
                    "timestamp": chrono::Utc::now().to_rfc3339()
                }));
            }

            "asana" => {
                // Simulate Asana action
                if analysis.action_required.as_ref() == Some(&"create".to_string()) {
                    actions.push(json!({
                        "integration": "asana",
                        "action": "create_task",
                        "status": "initiated",
                        "timestamp": chrono::Utc::now().to_rfc3339()
                    }));
                } else {
                    actions.push(json!({
                        "integration": "asana",
                        "action": "get_tasks",
                        "status": "initiated",
                        "timestamp": chrono::Utc::now().to_rfc3339()
                    }));
                }
            }

            "teams" => {
                // Simulate Teams action
                actions.push(json!({
                    "integration": "teams",
                    "action": "check_conversations",
                    "status": "initiated",
                    "timestamp": chrono::Utc::now().to_rfc3339()
                }));
            }

            "trello" => {
                // Simulate Trello action
                actions.push(json!({
                    "integration": "trello",
                    "action": "get_cards",
                    "status": "initiated",
                    "timestamp": chrono::Utc::now().to_rfc3339()
                }));
            }

            "figma" => {
                // Simulate Figma action
                actions.push(json!({
                    "integration": "figma",
                    "action": "check_designs",
                    "status": "initiated",
                    "timestamp": chrono::Utc::now().to_rfc3339()
                }));
            }

            "linear" => {
                // Simulate Linear action
                actions.push(json!({
                    "integration": "linear",
                    "action": "get_issues",
                    "status": "initiated",
                    "timestamp": chrono::Utc::now().to_rfc3339()
                }));
            }

            _ => {}
        }
    }

    Ok(json!({
        "actions": actions,
        "total_actions": actions.len()
    }))
}

/// Show notification for agent actions
async fn show_agent_notification(_app_handle: AppHandle, title: &str, body: &str) {
    match notification::Notification::new(title)
        .body(body)
        .icon("atom-logo")
        .show()
    {
        Ok(_) => println!("🔔 Notification shown: {} - {}", title, body),
        Err(e) => println!("❌ Failed to show notification: {}", e),
    }
}

/// Open file dialog for chat attachments
#[tauri::command]
pub async fn open_file_dialog(
    params: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    match params {
        Some(dialog_params) => {
            match tauri::api::dialog::blocking::FileDialogBuilder::new()
                .add_filter("All Files", &["*"])
                .add_filter("Text Files", &["txt", "md"])
                .add_filter("Documents", &["pdf", "doc", "docx"])
                .add_filter("Images", &["jpg", "png", "gif", "svg"])
                .pick_file()
            {
                Some(path) => Ok(json!({
                    "success": true,
                    "path": path,
                    "filename": path.file_name().unwrap_or_default().to_string_lossy().to_string()
                })),
                None => Ok(json!({
                    "success": false,
                    "error": "No file selected"
                })),
            }
        }
        None => Ok(json!({
            "success": false,
            "error": "No dialog parameters provided"
        })),
    }
}

/// Open chat settings
#[tauri::command]
pub async fn open_chat_settings(
    params: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    Ok(json!({
        "success": true,
        "message": "Chat settings opened"
    }))
}

/// Get chat preferences
#[tauri::command]
pub async fn get_chat_preferences(
    params: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    Ok(json!({
        "success": true,
        "preferences": {
            "theme": "light",
            "notifications": true,
            "sound": true,
            "auto_save": true,
            "max_messages": 1000,
            "typing_indicators": true
        }
    }))
}
