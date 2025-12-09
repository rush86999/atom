use std::process::{Command, Child, Stdio};
use std::sync::{Arc, Mutex};
use std::path::PathBuf;
use tauri::{State, Manager};
use serde::{Deserialize, Serialize};
use tokio::process::Command as TokioCommand;
use std::fs;

pub struct LuxServerState {
    server_process: Arc<Mutex<Option<Child>>>,
    server_port: u16,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LuxCommandRequest {
    pub command: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LuxBatchRequest {
    pub commands: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LuxResponse {
    pub success: bool,
    pub message: Option<String>,
    pub data: Option<serde_json::Value>,
}

impl Default for LuxServerState {
    fn default() -> Self {
        Self {
            server_process: Arc::new(Mutex::new(None)),
            server_port: 8080,
        }
    }
}

/// Get path to LUX server Python script
fn get_lux_server_path() -> Result<PathBuf, String> {
    let mut path = std::env::current_exe()
        .map_err(|e| format!("Failed to get current executable path: {}", e))?;

    // Go up from the executable to the app bundle root
    path.pop(); // Remove executable name
    path.pop(); // Remove target/debug or target/release

    // Check if we're in a macOS app bundle
    if path.ends_with("MacOS") {
        path.pop(); // Remove MacOS
        path.pop(); // Remove app_name.app
        path.push("Resources");
        path.push("lux");
    } else {
        // Development build
        path.push("lux");
    }

    if !path.exists() {
        return Err(format!("LUX server directory not found at: {:?}", path));
    }

    Ok(path)
}

/// Find Python executable
fn find_python_executable() -> Result<String, String> {
    // Try multiple Python executable names
    let python_names = vec!["python3", "python3.11", "python"];

    for python_name in python_names {
        if let Ok(output) = Command::new(&python_name)
            .arg("--version")
            .output()
        {
            if output.status.success() {
                return Ok(python_name.to_string());
            }
        }
    }

    Err("Python executable not found".to_string())
}

/// Start the LUX Python server
pub async fn start_lux_server(state: &State<LuxServerState>) -> Result<String, String> {
    let mut process_guard = state.server_process.lock().unwrap();

    // Check if server is already running
    if process_guard.is_some() {
        return Ok("LUX server is already running".to_string());
    }

    // Get paths
    let lux_path = get_lux_server_path()?;
    let python_exe = find_python_executable()?;

    let server_script = lux_path.join("lux_server.py");

    if !server_script.exists() {
        return Err(format!("LUX server script not found at: {:?}", server_script));
    }

    // Set up environment variables for LUX
    let mut child = TokioCommand::new(&python_exe)
        .arg(&server_script)
        .arg("--port")
        .arg(state.server_port.to_string())
        .arg("--host")
        .arg("127.0.0.1")
        .current_dir(&lux_path)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start LUX server: {}", e))?;

    // Give the server a moment to start
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

    // Check if the process is still running
    match child.try_wait() {
        Ok(Some(status)) => {
            return Err(format!("LUX server exited immediately with status: {}", status));
        }
        Ok(None) => {
            // Process is still running
            *process_guard = Some(child.into_std());
            return Ok(format!("LUX server started on port {}", state.server_port));
        }
        Err(e) => {
            return Err(format!("Failed to check LUX server status: {}", e));
        }
    }
}

/// Stop the LUX Python server
pub fn stop_lux_server(state: &State<LuxServerState>) -> Result<String, String> {
    let mut process_guard = state.server_process.lock().unwrap();

    if let Some(mut child) = process_guard.take() {
        match child.kill() {
            Ok(_) => Ok("LUX server stopped".to_string()),
            Err(e) => Err(format!("Failed to stop LUX server: {}", e)),
        }
    } else {
        Ok("LUX server is not running".to_string())
    }
}

/// Check if LUX server is running
pub async fn check_lux_server(state: &State<LuxServerState>) -> Result<bool, String> {
    let client = reqwest::Client::new();
    let url = format!("http://127.0.0.1:{}/health", state.server_port);

    match client.get(&url).send().await {
        Ok(response) => Ok(response.status().is_success()),
        Err(_) => Ok(false),
    }
}

/// Make a request to the LUX server
async fn make_lux_request<T: Serialize, R: serde::de::DeserializeOwned>(
    state: &State<LuxServerState>,
    endpoint: &str,
    data: Option<T>,
) -> Result<R, String> {
    let client = reqwest::Client::new();
    let url = format!("http://127.0.0.1:{}/{}", state.server_port, endpoint);

    let mut request = match data {
        Some(d) => client.post(&url).json(&d),
        None => client.get(&url),
    };

    let response = request
        .send()
        .await
        .map_err(|e| format!("Failed to make request to LUX server: {}", e))?;

    if !response.status().is_success() {
        return Err(format!("LUX server returned error status: {}", response.status()));
    }

    response
        .json()
        .await
        .map_err(|e| format!("Failed to parse LUX server response: {}", e))
}

/// Initialize LUX module
pub fn init_lux() -> LuxServerState {
    LuxServerState::default()
}

/// Install required Python packages
pub async fn install_lux_dependencies() -> Result<String, String> {
    let python_exe = find_python_executable()?;

    let packages = vec![
        "anthropic",
        "pillow",
        "opencv-python",
        "pyautogui",
        "fastapi",
        "uvicorn",
    ];

    for package in packages {
        let output = TokioCommand::new(&python_exe)
            .arg("-m")
            .arg("pip")
            .arg("install")
            .arg(package)
            .output()
            .await
            .map_err(|e| format!("Failed to install {}: {}", package, e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("Failed to install {}: {}", package, stderr));
        }
    }

    Ok("LUX dependencies installed successfully".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_find_python() {
        match find_python_executable() {
            Ok(python) => println!("Found Python: {}", python),
            Err(e) => println!("Python not found: {}", e),
        }
    }
}