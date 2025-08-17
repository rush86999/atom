#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use tauri::{
    Manager, AppHandle, SystemTray, SystemTrayMenu, SystemTrayMenuItem, SystemTrayEvent,
    CustomMenuItem, WindowEvent
};
use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use aes_gcm::{Aes256Gcm, Key, Nonce};
use aes_gcm::aead::{Aead, NewAead};
use hex::{encode, decode};
use std::fs;
use std::path::PathBuf;
use reqwest;

// --- Constants ---
const ENCRYPTION_KEY: &[u8] = b"a_default_32_byte_encryption_key"; // 32 bytes for AES-256
const SETTINGS_FILE: &str = "atom-settings.json";
const DESKTOP_PROXY_URL: &str = "http://localhost:3000/api/agent/desktop-proxy"; // URL of the web app's backend

// --- Structs ---
#[derive(Serialize, Deserialize, Debug)]
struct Settings {
    #[serde(flatten)]
    extra: HashMap<String, String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct NluResponse {
    intent: Option<String>,
    entities: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug)]
struct SearchResult {
    skill: String,
    title: String,
    url: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct DashboardData {
    calendar: Vec<CalendarEvent>,
    tasks: Vec<Task>,
    social: Vec<SocialPost>,
}

#[derive(Serialize, Deserialize, Debug)]
struct CalendarEvent {
    id: i32,
    title: String,
    time: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct Task {
    id: i32,
    title: String,
    due_date: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct SocialPost {
    id: i32,
    platform: String,
    post: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct WorkflowNode {
    id: String,
    #[serde(rename = "type")]
    node_type: String,
    position: Position,
    data: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug)]
struct Position {
    x: f64,
    y: f64,
}

#[derive(Serialize, Deserialize, Debug)]
struct WorkflowEdge {
    id: String,
    source: String,
    target: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct WorkflowDefinition {
    nodes: Vec<WorkflowNode>,
    edges: Vec<WorkflowEdge>,
}

#[derive(Serialize, Deserialize, Debug)]
struct Workflow {
    name: String,
    definition: WorkflowDefinition,
    enabled: bool,
}

// --- Secure Storage Functions ---
fn get_settings_path(app_handle: &AppHandle) -> PathBuf {
    let mut path = app_handle.path_resolver().app_data_dir().unwrap();
    path.push(SETTINGS_FILE);
    path
}

fn encrypt(text: &str) -> String {
    let key = Key::from_slice(ENCRYPTION_KEY);
    let cipher = Aes256Gcm::new(key);
    let mut nonce_bytes = [0u8; 12];
    rand::rngs::OsRng.fill_bytes(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = cipher.encrypt(nonce, text.as_bytes()).unwrap();
    format!("{}:{}", encode(nonce), encode(ciphertext))
}

fn decrypt(encrypted_text: &str) -> Result<String, String> {
    let parts: Vec<&str> = encrypted_text.split(':').collect();
    if parts.len() != 2 {
        return Err("Invalid encrypted text format".to_string());
    }
    let nonce = Nonce::from_slice(&decode(parts[0]).unwrap());
    let ciphertext = decode(parts[1]).unwrap();
    let key = Key::from_slice(ENCRYPTION_KEY);
    let cipher = Aes256Gcm::new(key);
    let plaintext = cipher.decrypt(nonce, ciphertext.as_ref()).map_err(|e| e.to_string())?;
    Ok(String::from_utf8(plaintext).unwrap())
}

// --- Tauri Commands ---
#[tauri::command]
fn save_setting(app_handle: AppHandle, key: String, value: String) {
    let path = get_settings_path(&app_handle);
    let mut settings: Settings = match fs::read_to_string(&path) {
        Ok(content) => serde_json::from_str(&content).unwrap_or(Settings { extra: HashMap::new() }),
        Err(_) => Settings { extra: HashMap::new() },
    };
    let encrypted_value = encrypt(&value);
    settings.extra.insert(key, encrypted_value);
    fs::write(&path, serde_json::to_string_pretty(&settings).unwrap()).
