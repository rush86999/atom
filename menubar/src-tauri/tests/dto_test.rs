/// Tests for Rust DTO serialization/deserialization
///
/// Tests verify serde JSON serialization for all data transfer objects
/// used in the menubar desktop application.

// `atom-menubar` is a binary-only Tauri crate, so an integration test cannot
// link against `commands` as a library. Compile the production modules into
// this test crate instead, supplying the crate-root items that `main.rs`
// normally provides for them, so the DTO assertions below exercise the real
// structs and serde derives rather than copies.
use std::sync::Mutex;

#[path = "../src/config.rs"]
mod config;

#[path = "../src/session.rs"]
mod session;

#[derive(Clone)]
struct UserSession {
    token: String,
    user_id: String,
    email: String,
    device_id: String,
}

struct AppState {
    auth_token: Mutex<Option<String>>,
    user_session: Mutex<Option<UserSession>>,
    session_lock: tokio::sync::Mutex<()>,
}

#[path = "../src/commands.rs"]
mod commands;

#[cfg(test)]
mod tests {
    use serde_json;
    use std::collections::HashMap;

    // Import DTOs from commands.rs
    use crate::commands::*;

    // Helper to create test agent data
    fn create_test_agent() -> AgentSummary {
        AgentSummary {
            id: "agent-123".to_string(),
            name: "Test Agent".to_string(),
            maturity_level: "AUTONOMOUS".to_string(),
            status: "active".to_string(),
            last_execution: Some("2026-03-08T12:00:00Z".to_string()),
            execution_count: 42,
        }
    }

    // Helper to create test canvas data
    fn create_test_canvas() -> CanvasSummary {
        CanvasSummary {
            id: "canvas-456".to_string(),
            canvas_type: "chart".to_string(),
            created_at: "2026-03-08T12:00:00Z".to_string(),
            agent_id: Some("agent-123".to_string()),
            agent_name: Some("Test Agent".to_string()),
        }
    }

    #[test]
    fn test_user_dto_fields() {
        // Verify User has all required fields
        let user = User {
            id: "user-1".to_string(),
            email: "test@example.com".to_string(),
            first_name: "Test".to_string(),
            last_name: "User".to_string(),
        };

        assert_eq!(user.id, "user-1");
        assert_eq!(user.email, "test@example.com");
        assert_eq!(user.first_name, "Test");
        assert_eq!(user.last_name, "User");
    }

    #[test]
    fn test_login_request_dto_fields() {
        let login_req = LoginRequest {
            email: "user@example.com".to_string(),
            password: "password123".to_string(),
            device_name: "Test Device".to_string(),
            totp_code: None,
        };

        assert_eq!(login_req.email, "user@example.com");
        assert_eq!(login_req.password, "password123");
        assert_eq!(login_req.device_name, "Test Device");
        assert_eq!(login_req.totp_code, None);

        // A first attempt must not send an empty second-factor field: the
        // server distinguishes "no code" from "wrong code".
        let json = serde_json::to_string(&login_req).expect("Failed to serialize");
        assert!(!json.contains("totp_code"));
    }

    #[test]
    fn test_login_request_serializes_totp_retry() {
        let login_req = LoginRequest {
            email: "user@example.com".to_string(),
            password: "password123".to_string(),
            device_name: "Test Device".to_string(),
            totp_code: Some("123456".to_string()),
        };

        let json = serde_json::to_string(&login_req).expect("Failed to serialize");
        assert!(json.contains("\"totp_code\":\"123456\""));
    }

    #[test]
    fn test_login_error_message_shapes() {
        // Companion handler refusal.
        assert_eq!(
            login_error_message("{\"error\":\"Invalid email or password\"}"),
            Some("Invalid email or password".to_string())
        );
        // CSRF / shared middleware refusal.
        assert_eq!(
            login_error_message(
                "{\"error\":{\"type\":\"csrf_token_invalid\",\"message\":\"Invalid or missing CSRF token\"}}"
            ),
            Some("Invalid or missing CSRF token".to_string())
        );
        // FastAPI validation/rate-limit shape.
        assert_eq!(
            login_error_message("{\"detail\":\"Too many login attempts\"}"),
            Some("Too many login attempts".to_string())
        );
        assert_eq!(login_error_message("not-json"), None);
    }

    #[test]
    fn test_login_response_dto_fields() {
        let login_resp = LoginResponse {
            success: true,
            access_token: Some("token-abc123".to_string()),
            device_id: Some("device-xyz".to_string()),
            user: Some(User {
                id: "user-1".to_string(),
                email: "test@example.com".to_string(),
                first_name: "Test".to_string(),
                last_name: "User".to_string(),
            }),
            error: None,
            two_factor_required: None,
        };

        assert_eq!(login_resp.success, true);
        assert_eq!(login_resp.access_token, Some("token-abc123".to_string()));
        assert_eq!(login_resp.device_id, Some("device-xyz".to_string()));
        assert!(login_resp.user.is_some());
        assert_eq!(login_resp.error, None);
    }

    #[test]
    fn test_login_response_tolerates_missing_two_factor_field() {
        // Older/alternate backend responses omit the field entirely.
        let parsed: LoginResponse = serde_json::from_str(
            "{\"success\":false,\"error\":\"Invalid email or password\"}",
        )
        .expect("missing optional field must deserialize");
        assert!(!parsed.success);
        assert_eq!(parsed.two_factor_required, None);
    }

    #[test]
    fn test_login_session_serializes_named_fields() {
        // `login` is a Tauri success response: a Rust tuple would cross IPC as a
        // positional JSON array, which the webview cannot read by field name.
        let session = LoginSession {
            token: "token-abc123".to_string(),
            user: User {
                id: "user-1".to_string(),
                email: "test@example.com".to_string(),
                first_name: "Test".to_string(),
                last_name: "User".to_string(),
            },
            device_id: "device-xyz".to_string(),
        };

        let json = serde_json::to_value(&session).expect("Failed to serialize");

        assert!(
            json.is_object(),
            "login success must serialize as a named object, got {json}"
        );
        assert_eq!(json["token"], "token-abc123");
        assert_eq!(json["user"]["id"], "user-1");
        assert_eq!(json["user"]["email"], "test@example.com");
        assert_eq!(json["device_id"], "device-xyz");

        let object = json.as_object().expect("expected a JSON object");
        assert_eq!(object.len(), 3, "unexpected extra fields: {json}");
    }

    #[test]
    fn test_session_info_serializes_named_fields() {
        // `get_session` restores an existing session: token and user only.
        let session = SessionInfo {
            token: "token-abc123".to_string(),
            user: User {
                id: "user-1".to_string(),
                email: "test@example.com".to_string(),
                first_name: "".to_string(),
                last_name: "".to_string(),
            },
        };

        let json = serde_json::to_value(&session).expect("Failed to serialize");

        assert!(
            json.is_object(),
            "get_session success must serialize as a named object, got {json}"
        );
        assert_eq!(json["token"], "token-abc123");
        assert_eq!(json["user"]["id"], "user-1");
        assert_eq!(json["user"]["email"], "test@example.com");

        let object = json.as_object().expect("expected a JSON object");
        assert_eq!(object.len(), 2, "unexpected extra fields: {json}");
        assert!(
            !object.contains_key("device_id"),
            "device_id belongs to the login response only"
        );
    }

    #[test]
    fn test_login_error_stays_a_plain_string() {
        // The concurrent frontend worker surfaces Tauri's rejection payload
        // directly, so the error channel must stay a bare string.
        let result: Result<LoginSession, String> = Err("Invalid email or password".to_string());

        let error = result.expect_err("expected a login failure");
        let json = serde_json::to_value(&error).expect("Failed to serialize");

        assert_eq!(json, serde_json::json!("Invalid email or password"));
    }

    #[test]
    fn test_agent_dto_serialize_to_json() {
        let agent = create_test_agent();

        let json = serde_json::to_string(&agent).expect("Failed to serialize");

        assert!(json.contains("\"id\":\"agent-123\""));
        assert!(json.contains("\"name\":\"Test Agent\""));
        assert!(json.contains("\"maturity_level\":\"AUTONOMOUS\""));
        assert!(json.contains("\"status\":\"active\""));
    }

    #[test]
    fn test_agent_dto_deserialize_from_json() {
        let json = r#"{
            "id": "agent-123",
            "name": "Test Agent",
            "maturity_level": "AUTONOMOUS",
            "status": "active",
            "last_execution": "2026-03-08T12:00:00Z",
            "execution_count": 42
        }"#;

        let agent: AgentSummary = serde_json::from_str(json).expect("Failed to deserialize");

        assert_eq!(agent.id, "agent-123");
        assert_eq!(agent.name, "Test Agent");
        assert_eq!(agent.maturity_level, "AUTONOMOUS");
        assert_eq!(agent.status, "active");
        assert_eq!(agent.execution_count, 42);
    }

    #[test]
    fn test_canvas_dto_serialize_to_json() {
        let canvas = create_test_canvas();

        let json = serde_json::to_string(&canvas).expect("Failed to serialize");

        assert!(json.contains("\"id\":\"canvas-456\""));
        assert!(json.contains("\"canvas_type\":\"chart\""));
    }

    #[test]
    fn test_canvas_dto_deserialize_from_json() {
        let json = r#"{
            "id": "canvas-456",
            "canvas_type": "chart",
            "created_at": "2026-03-08T12:00:00Z",
            "agent_id": "agent-123",
            "agent_name": "Test Agent"
        }"#;

        let canvas: CanvasSummary = serde_json::from_str(json).expect("Failed to deserialize");

        assert_eq!(canvas.id, "canvas-456");
        assert_eq!(canvas.canvas_type, "chart");
        assert_eq!(canvas.agent_id, Some("agent-123".to_string()));
        assert_eq!(canvas.agent_name, Some("Test Agent".to_string()));
    }

    #[test]
    fn test_agent_dto_round_trip() {
        let original = create_test_agent();

        let json = serde_json::to_string(&original).expect("Failed to serialize");
        let deserialized: AgentSummary = serde_json::from_str(&json).expect("Failed to deserialize");

        assert_eq!(original.id, deserialized.id);
        assert_eq!(original.name, deserialized.name);
        assert_eq!(original.maturity_level, deserialized.maturity_level);
        assert_eq!(original.status, deserialized.status);
        assert_eq!(original.execution_count, deserialized.execution_count);
    }

    #[test]
    fn test_canvas_dto_round_trip() {
        let original = create_test_canvas();

        let json = serde_json::to_string(&original).expect("Failed to serialize");
        let deserialized: CanvasSummary = serde_json::from_str(&json).expect("Failed to deserialize");

        assert_eq!(original.id, deserialized.id);
        assert_eq!(original.canvas_type, deserialized.canvas_type);
        assert_eq!(original.created_at, deserialized.created_at);
        assert_eq!(original.agent_id, deserialized.agent_id);
        assert_eq!(original.agent_name, deserialized.agent_name);
    }

    #[test]
    fn test_recent_items_response_structure() {
        let agents = vec![create_test_agent()];
        let canvases = vec![create_test_canvas()];

        let response = RecentItemsResponse {
            agents,
            canvases,
        };

        assert_eq!(response.agents.len(), 1);
        assert_eq!(response.canvases.len(), 1);
        assert_eq!(response.agents[0].id, "agent-123");
        assert_eq!(response.canvases[0].id, "canvas-456");
    }

    #[test]
    fn test_connection_status_dto_fields() {
        let status = ConnectionStatus {
            status: "connected".to_string(),
            device_id: Some("device-123".to_string()),
            last_seen: Some("2026-03-08T12:00:00Z".to_string()),
            server_time: "2026-03-08T12:00:00Z".to_string(),
        };

        assert_eq!(status.status, "connected");
        assert_eq!(status.device_id, Some("device-123".to_string()));
        assert_eq!(status.server_time, "2026-03-08T12:00:00Z");
    }

    #[test]
    fn test_quick_chat_request_dto_fields() {
        let mut context = HashMap::new();
        context.insert("key".to_string(), serde_json::json!("value"));

        let request = QuickChatRequest {
            message: "Hello, agent!".to_string(),
            agent_id: Some("agent-123".to_string()),
            context: Some(serde_json::to_value(context).unwrap()),
        };

        assert_eq!(request.message, "Hello, agent!");
        assert_eq!(request.agent_id, Some("agent-123".to_string()));
        assert!(request.context.is_some());
    }

    #[test]
    fn test_quick_chat_response_dto_fields() {
        let response = QuickChatResponse {
            success: true,
            response: Some("Hello, user!".to_string()),
            execution_id: Some("exec-123".to_string()),
            agent_id: Some("agent-123".to_string()),
            error: None,
        };

        assert_eq!(response.success, true);
        assert_eq!(response.response, Some("Hello, user!".to_string()));
        assert_eq!(response.execution_id, Some("exec-123".to_string()));
        assert_eq!(response.error, None);
    }

    #[test]
    fn test_optional_fields_handle_none_correctly() {
        // Test with None values
        let canvas = CanvasSummary {
            id: "canvas-789".to_string(),
            canvas_type: "markdown".to_string(),
            created_at: "2026-03-08T12:00:00Z".to_string(),
            agent_id: None,
            agent_name: None,
        };

        assert!(canvas.agent_id.is_none());
        assert!(canvas.agent_name.is_none());

        // Verify serialization includes null
        let json = serde_json::to_string(&canvas).expect("Failed to serialize");
        assert!(json.contains("\"agent_id\":null"));
    }

    #[test]
    fn test_empty_arrays_handle_correctly() {
        let response = RecentItemsResponse {
            agents: vec![],
            canvases: vec![],
        };

        assert_eq!(response.agents.len(), 0);
        assert_eq!(response.canvases.len(), 0);

        // Verify serialization includes empty arrays
        let json = serde_json::to_string(&response).expect("Failed to serialize");
        assert!(json.contains("\"agents\":[]"));
        assert!(json.contains("\"canvases\":[]"));
    }

    #[test]
    fn test_special_characters_in_strings() {
        let agent = AgentSummary {
            id: "agent-\"quotes\"".to_string(),
            name: "Test \n Agent \t User".to_string(),
            maturity_level: "AUTONOMOUS".to_string(),
            status: "active".to_string(),
            last_execution: None,
            execution_count: 0,
        };

        let json = serde_json::to_string(&agent).expect("Failed to serialize");
        let deserialized: AgentSummary = serde_json::from_str(&json).expect("Failed to deserialize");

        assert_eq!(deserialized.id, "agent-\"quotes\"");
        assert_eq!(deserialized.name, "Test \n Agent \t User");
    }

    #[test]
    fn test_enum_serialization_maturity_levels() {
        // Test different maturity levels
        let maturities = vec!["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"];

        for maturity in maturities {
            let agent = AgentSummary {
                id: format!("agent-{}", maturity),
                name: "Test Agent".to_string(),
                maturity_level: maturity.to_string(),
                status: "active".to_string(),
                last_execution: None,
                execution_count: 0,
            };

            let json = serde_json::to_string(&agent).expect("Failed to serialize");
            assert!(json.contains(&format!("\"maturity_level\":\"{}\"", maturity)));
        }
    }

    #[test]
    fn test_invalid_json_deserialization() {
        // Test missing required fields
        let invalid_json = r#"{"id": "agent-123"}"#;  // Missing required fields

        let result: Result<AgentSummary, _> = serde_json::from_str(invalid_json);
        assert!(result.is_err(), "Should fail with missing required fields");
    }

    #[test]
    fn test_malformed_json_deserialization() {
        // Test malformed JSON
        let malformed_json = r#"{invalid json}"#;

        let result: Result<AgentSummary, _> = serde_json::from_str(malformed_json);
        assert!(result.is_err(), "Should fail with malformed JSON");
    }
}
