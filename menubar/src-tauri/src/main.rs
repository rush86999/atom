// Prevents additional console window on Windows in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod menu;
mod websocket;
mod hotkeys;
mod autolaunch;
mod notifications;
mod helpers;
mod platform_specific;

use autolaunch::*;
use commands::*;
use hotkeys::*;
use menu::create_menu;
use notifications::*;
use std::sync::Mutex;
use tauri::{
    menu::Menu,
    tray::TrayIconBuilder,
    Emitter, Listener, Manager,
};

// Global state for auth token and user session
struct AppState {
    auth_token: Mutex<Option<String>>,
    user_session: Mutex<Option<UserSession>>,
}

#[derive(Clone)]
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
            get_hotkeys,
            update_hotkeys,
            trigger_hotkey,
            get_auto_launch_status,
            update_auto_launch,
            disable_auto_launch,
            get_notifications,
            get_unread_notifications,
            mark_notification_read,
            mark_all_notifications_read,
            dismiss_notification,
            get_notification_stats,
            send_notification,
        ])
        .setup(|app| {
            // Create system tray
            let tray_menu = create_menu(app).map_err(|e| format!("Failed to create menu: {}", e))?;
            let app_handle = app.handle().clone();
            let _tray = TrayIconBuilder::new()
                .menu(&tray_menu)
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Atom Menu Bar")
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "hide" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.hide();
                        }
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            // Listen for global hotkey events (Cmd+Shift+A)
            let app_handle = app.handle().clone();
            app.listen("quick-chat-hotkey", move |event| {
                println!("Quick chat hotkey triggered: {:?}", event.payload());
                // Show window and focus on chat input
                if let Some(window) = app_handle.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
