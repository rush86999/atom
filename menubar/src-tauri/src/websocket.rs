//! WebSocket client for real-time communication with Atom backend
//!
//! Uses tokio-tungstenite for WebSocket connections

use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use url::Url;

const WEBSOCKET_URL: &str = "ws://localhost:8000/ws/menubar"; // Configure as needed

// ============================================================================
// Event Types
// ============================================================================

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum WebSocketEvent {
    /// Agent response received
    AgentResponse {
        execution_id: String,
        agent_id: String,
        response: String,
    },
    /// Canvas presented
    CanvasPresented {
        canvas_id: String,
        canvas_type: String,
        agent_id: String,
    },
    /// Notification received
    Notification {
        title: String,
        body: String,
        data: Option<Value>,
    },
    /// Connection status changed
    ConnectionStatus {
        status: String,
    },
    /// Generic message
    Message {
        event: String,
        data: Value,
    },
}

#[derive(Debug, Serialize, Deserialize)]
pub struct WebSocketMessage {
    #[serde(flatten)]
    pub event: WebSocketEvent,
}

// ============================================================================
// WebSocket Client
// ============================================================================

pub struct WebSocketClient {
    url: String,
    token: String,
}

impl WebSocketClient {
    pub fn new(url: String, token: String) -> Self {
        Self { url, token }
    }

    /// Connect to WebSocket server and listen for events
    pub async fn connect<F>(self, mut callback: F) -> Result<(), Box<dyn std::error::Error>>
    where
        F: FnMut(WebSocketEvent) + Send + 'static,
    {
        let url = Url::parse(&self.url)?;

        let (ws_stream, _) = connect_async(&self.url).await?;
        let (mut write, mut read) = ws_stream.split();

        // Send authentication message
        let auth_msg = serde_json::json!({
            "type": "auth",
            "token": self.token
        });
        write.send(Message::Text(auth_msg.to_string().into())).await?;

        // Listen for incoming messages
        while let Some(message) = read.next().await {
            match message {
                Ok(Message::Text(text)) => {
                    if let Ok(ws_msg) = serde_json::from_str::<WebSocketMessage>(&text) {
                        callback(ws_msg.event);
                    }
                }
                Ok(Message::Close(_)) => {
                    println!("WebSocket connection closed");
                    break;
                }
                Err(e) => {
                    eprintln!("WebSocket error: {}", e);
                    break;
                }
                _ => {}
            }
        }

        Ok(())
    }
}

// ============================================================================
// Reconnection Logic
// ============================================================================

pub async fn connect_with_reconnect(
    url: String,
    token: String,
    callback: impl FnMut(WebSocketEvent) + Send + 'static,
) -> Result<(), Box<dyn std::error::Error>> {
    let client = WebSocketClient::new(url, token);
    client.connect(callback).await
}
