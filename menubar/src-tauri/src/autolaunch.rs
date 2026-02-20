use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tauri::AppHandle;

// ============================================================================
// Data Models
// ============================================================================

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AutoLaunchConfig {
    pub enabled: bool,
    pub start_minimized: bool,
    pub launch_delay_seconds: u64,
}

impl Default for AutoLaunchConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            start_minimized: true,
            launch_delay_seconds: 0,
        }
    }
}

// ============================================================================
// AutoLaunch Manager
// ============================================================================

pub struct AutoLaunchManager {
    app_path: PathBuf,
    app_name: String,
}

impl AutoLaunchManager {
    pub fn new(app_handle: &AppHandle) -> Self {
        let app_path = app_handle.path().app_dir().unwrap_or_else(|_| {
            std::env::current_exe()
                .unwrap()
                .parent()
                .unwrap()
                .to_path_buf()
        });

        Self {
            app_path,
            app_name: "Atom Menu Bar".to_string(),
        }
    }

    pub fn is_enabled(&self) -> Result<bool, String> {
        #[cfg(target_os = "macos")]
        {
            self.check_macos_launch_agent()
        }

        #[cfg(target_os = "windows")]
        {
            self.check_windows_registry()
        }

        #[cfg(target_os = "linux")]
        {
            self.check_linux_autostart()
        }

        #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
        {
            Err("Auto-launch not supported on this platform".to_string())
        }
    }

    pub fn enable(&self, config: &AutoLaunchConfig) -> Result<(), String> {
        if config.enabled {
            #[cfg(target_os = "macos")]
            {
                self.setup_macos_launch_agent(config)?;
            }

            #[cfg(target_os = "windows")]
            {
                self.setup_windows_registry(config)?;
            }

            #[cfg(target_os = "linux")]
            {
                self.setup_linux_autostart(config)?;
            }
        } else {
            self.disable()?;
        }

        Ok(())
    }

    pub fn disable(&self) -> Result<(), String> {
        #[cfg(target_os = "macos")]
        {
            self.remove_macos_launch_agent()?;
        }

        #[cfg(target_os = "windows")]
        {
            self.remove_windows_registry()?;
        }

        #[cfg(target_os = "linux")]
        {
            self.remove_linux_autostart()?;
        }

        #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
        {
            return Err("Auto-launch not supported on this platform".to_string());
        }

        Ok(())
    }

    // macOS implementation using LaunchAgents
    #[cfg(target_os = "macos")]
    fn check_macos_launch_agent(&self) -> Result<bool, String> {
        let plist_path = self.get_macos_plist_path()?;
        Ok(plist_path.exists())
    }

    #[cfg(target_os = "macos")]
    fn setup_macos_launch_agent(&self, config: &AutoLaunchConfig) -> Result<(), String> {
        let plist_path = self.get_macos_plist_path()?;
        let plist_dir = plist_path
            .parent()
            .ok_or("Invalid plist path")?;

        // Create LaunchAgents directory if it doesn't exist
        std::fs::create_dir_all(plist_dir)
            .map_err(|e| format!("Failed to create LaunchAgents directory: {}", e))?;

        // Create plist content
        let plist_content = self.generate_macos_plist(config)?;

        // Write plist file
        std::fs::write(&plist_path, plist_content)
            .map_err(|e| format!("Failed to write plist file: {}", e))?;

        // Load the launch agent
        std::process::Command::new("launchctl")
            .args(&["load", plist_path.to_str().unwrap()])
            .output()
            .map_err(|e| format!("Failed to load launch agent: {}", e))?;

        Ok(())
    }

    #[cfg(target_os = "macos")]
    fn remove_macos_launch_agent(&self) -> Result<(), String> {
        let plist_path = self.get_macos_plist_path()?;

        if plist_path.exists() {
            // Unload the launch agent
            let _ = std::process::Command::new("launchctl")
                .args(&["unload", plist_path.to_str().unwrap()])
                .output();

            // Remove plist file
            std::fs::remove_file(&plist_path)
                .map_err(|e| format!("Failed to remove plist file: {}", e))?;
        }

        Ok(())
    }

    #[cfg(target_os = "macos")]
    fn get_macos_plist_path(&self) -> Result<PathBuf, String> {
        let home_dir = std::env::var("HOME")
            .map_err(|_| "Failed to get HOME directory".to_string())?;
        let bundle_id = "com.atom.menubar";

        Ok(PathBuf::from(home_dir)
            .join("Library")
            .join("LaunchAgents")
            .join(format!("{}.plist", bundle_id)))
    }

    #[cfg(target_os = "macos")]
    fn generate_macos_plist(&self, config: &AutoLaunchConfig) -> Result<String, String> {
        let exe_path = std::env::current_exe()
            .map_err(|e| format!("Failed to get executable path: {}", e))?;

        let exe_str = exe_path
            .to_str()
            .ok_or("Invalid executable path")?;

        let mut args = vec![];
        if config.start_minimized {
            args.push("--hidden".to_string());
        }

        let args_str = if args.is_empty() {
            String::new()
        } else {
            format!("<array>{}</array>",
                args.iter()
                    .map(|arg| format!("<string>{}</string>", arg))
                    .collect::<Vec<_>>()
                    .join(""))
        };

        Ok(format!(r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atom.menubar</string>
    <key>ProgramArguments</key>
    <array>
        <string>{}</string>
        {}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"#, exe_str, args_str))
    }

    // Windows implementation using Registry
    #[cfg(target_os = "windows")]
    fn check_windows_registry(&self) -> Result<bool, String> {
        // Check if registry key exists
        // Note: This requires winreg crate or similar
        // For now, return false as placeholder
        Ok(false)
    }

    #[cfg(target_os = "windows")]
    fn setup_windows_registry(&self, config: &AutoLaunchConfig) -> Result<(), String> {
        // Add registry entry in HKCU\Software\Microsoft\Windows\CurrentVersion\Run
        // Note: This requires winreg crate
        Err("Windows auto-launch not yet implemented".to_string())
    }

    #[cfg(target_os = "windows")]
    fn remove_windows_registry(&self) -> Result<(), String> {
        // Remove registry entry
        Err("Windows auto-launch not yet implemented".to_string())
    }

    // Linux implementation using .desktop files
    #[cfg(target_os = "linux")]
    fn check_linux_autostart(&self) -> Result<bool, String> {
        let home_dir = std::env::var("HOME")
            .map_err(|_| "Failed to get HOME directory".to_string())?;
        let autostart_path = PathBuf::from(home_dir)
            .join(".config")
            .join("autostart")
            .join("atom-menubar.desktop");

        Ok(autostart_path.exists())
    }

    #[cfg(target_os = "linux")]
    fn setup_linux_autostart(&self, config: &AutoLaunchConfig) -> Result<(), String> {
        let home_dir = std::env::var("HOME")
            .map_err(|_| "Failed to get HOME directory".to_string())?;
        let autostart_dir = PathBuf::from(home_dir)
            .join(".config")
            .join("autostart");

        std::fs::create_dir_all(&autostart_dir)
            .map_err(|e| format!("Failed to create autostart directory: {}", e))?;

        let desktop_path = autostart_dir.join("atom-menubar.desktop");
        let desktop_content = self.generate_linux_desktop(config)?;

        std::fs::write(&desktop_path, desktop_content)
            .map_err(|e| format!("Failed to write desktop file: {}", e))?;

        Ok(())
    }

    #[cfg(target_os = "linux")]
    fn remove_linux_autostart(&self) -> Result<(), String> {
        let home_dir = std::env::var("HOME")
            .map_err(|_| "Failed to get HOME directory".to_string())?;
        let desktop_path = PathBuf::from(home_dir)
            .join(".config")
            .join("autostart")
            .join("atom-menubar.desktop");

        if desktop_path.exists() {
            std::fs::remove_file(&desktop_path)
                .map_err(|e| format!("Failed to remove desktop file: {}", e))?;
        }

        Ok(())
    }

    #[cfg(target_os = "linux")]
    fn generate_linux_desktop(&self, config: &AutoLaunchConfig) -> Result<String, String> {
        let exe_path = std::env::current_exe()
            .map_err(|e| format!("Failed to get executable path: {}", e))?;

        let exe_str = exe_path
            .to_str()
            .ok_or("Invalid executable path")?;

        let mut args = vec![];
        if config.start_minimized {
            args.push("--hidden");
        }

        let exec_cmd = if args.is_empty() {
            exe_str.to_string()
        } else {
            format!("{} {}", exe_str, args.join(" "))
        };

        Ok(format!(r#"[Desktop Entry]
Type=Application
Name=Atom Menu Bar
Exec={}
Icon=atom-menubar
X-GNOME-Autostart-enabled=true
Hidden=false
NoDisplay=false
Comment=AI-powered automation at your fingertips
X-GNOME-Autostart-Delay=0
"#, exec_cmd))
    }
}

// ============================================================================
// Tauri Commands
// ============================================================================

#[tauri::command]
pub async fn get_auto_launch_status(app_handle: AppHandle) -> Result<bool, String> {
    let manager = AutoLaunchManager::new(&app_handle);
    manager.is_enabled()
}

#[tauri::command]
pub async fn update_auto_launch(
    config: AutoLaunchConfig,
    app_handle: AppHandle,
) -> Result<(), String> {
    let manager = AutoLaunchManager::new(&app_handle);
    manager.enable(&config)
}

#[tauri::command]
pub async fn disable_auto_launch(app_handle: AppHandle) -> Result<(), String> {
    let manager = AutoLaunchManager::new(&app_handle);
    manager.disable()
}
