// Prevents additional console window on Windows in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod menu;
mod websocket;

use commands::*;
use menu::create_menu;
use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{TrayIconBuilder, TrayIconEvent},
    Manager, App, Emitter, Listener, RunEvent
};
use tokio::sync::Mutex as TokioMutex;

// Global state for auth token and user session
struct AppState {
    auth_token: Mutex<Option<String>>,
    user_session: Mutex<Option<UserSession>>,
}

struct UserSession {
    token: String,
    user_id: String,
    email: String,
    device_id: String,
}

#[tokio::main]
async fn main() {
    // Initialize app state
    let app_state = AppState {
        auth_token: Mutex::new(None),
        user_session: Mutex::new(None),
    };

    tauri::Builder::default()
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            login,
            logout,
            get_session,
            get_connection_status,
            get_recent_items,
            quick_chat,
            show_window,
            hide_window,
        ])
        .setup(|app| {
            // Create system tray
            let tray_menu = create_menu(app);
            let _tray = TrayIconBuilder::new()
                .menu(&tray_menu)
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Atom Menu Bar")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            window.show().unwrap();
                            window.set_focus().unwrap();
                        }
                    }
                    "hide" => {
                        if let Some(window) = app.get_webview_window("main") {
                            window.hide().unwrap();
                        }
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            // Set up window behavior (hide when focus is lost)
            let window = app.get_webview_window("main").unwrap();
            window.on_window_event(|event| match event {
                tauri::WindowEvent::Focused(focused) => {
                    if !focused {
                        // Auto-hide when window loses focus
                        if let Some(window) = window.app_handle().get_webview_window("main") {
                            let _ = window.hide();
                        }
                    }
                }
                _ => {}
            });

            // Listen for global hotkey events (Cmd+Shift+A)
            app.listen("quick-chat-hotkey", |event| {
                println!("Quick chat hotkey triggered: {:?}", event.payload);
                // Show window and focus on chat input
                if let Some(window) = event.window().unwrap().app_handle().get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
