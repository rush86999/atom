#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use tauri::{SystemTray, SystemTrayEvent, SystemTrayMenu, CustomMenuItem, Manager, command, AppHandle};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use tract_onnx::prelude::*;
use std::fs;
use serde_json::Value;

#[command]
async fn send_message_to_agent(app_handle: AppHandle, message: String) -> Result<String, String> {
    let settings_path = app_handle.path_resolver()
        .resolve_resource("settings.json")
        .expect("failed to resolve resource");
    let settings_file = fs::read_to_string(settings_path).map_err(|err| err.to_string())?;
    let settings: Value = serde_json::from_str(&settings_file).map_err(|err| err.to_string())?;

    let client = reqwest::Client::new();
    let res = client.post("http://localhost:3000/api/agent-handler")
        .json(&serde_json::json!({
            "message": message,
            "settings": settings
        }))
        .send()
        .await
        .map_err(|err| err.to_string())?;

    let body = res.text().await.map_err(|err| err.to_string())?;
    Ok(body)
}

fn main() {
    let show = CustomMenuItem::new("show".to_string(), "Show App");
    let quit = CustomMenuItem::new("quit".to_string(), "Quit");
    let start_transcription = CustomMenuItem::new("start_transcription".to_string(), "Start Transcription");
    let tray_menu = SystemTrayMenu::new().add_item(show).add_item(start_transcription).add_item(quit);
    let system_tray = SystemTray::new().with_menu(tray_menu);

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![send_message_to_agent])
        .setup(|app| {
            let app_handle = app.handle();
            std::thread::spawn(move || {
                let settings_path = app_handle.path_resolver()
                    .resolve_resource("settings.json")
                    .expect("failed to resolve resource");
                let settings_file = fs::read_to_string(settings_path).unwrap();
                let settings: Value = serde_json::from_str(&settings_file).unwrap();
                let integrations = &settings["integrations"];
                let llm = &settings["llm"];

                let host = cpal::default_host();
                let device = host.default_input_device().expect("no input device available");
                let config = device.default_input_config().unwrap();
                let model = tract_onnx::onnx()
                    .model_for_path("atom_wake_word.onnx")
                    .unwrap()
                    .with_input_fact(0, f32::fact([1, 16000]).into())
                    .unwrap()
                    .into_optimized()
                    .unwrap()
                    .into_runnable()
                    .unwrap();

                let stream = device.build_input_stream(
                    &config.into(),
                    move |data: &[f32], _: &cpal::InputCallbackInfo| {
                        let input = tract_ndarray::Array1::from_vec(data.to_vec());
                        let input = input.into_shape((1, 16000)).unwrap();
                        let result = model.run(tvec!(input.into())).unwrap();
                        if let Some(tensor) = result.get(0) {
                            if let Some(value) = tensor.as_slice::<f32>().unwrap().get(0) {
                                if *value > 0.5 {
                                    app_handle.emit_all("wake-word-detected", {}).unwrap();
                                }
                            }
                        }
                    },
                    |err| eprintln!("an error occurred on stream: {}", err),
                ).unwrap();
                stream.play().unwrap();
            });
            Ok(())
        })
        .system_tray(system_tray)
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::LeftClick {
                position: _,
                size: _,
                ..
            } => {
                let window = app.get_window("main").unwrap();
                if window.is_visible().unwrap() {
                    window.hide().unwrap();
                } else {
                    window.show().unwrap();
                    window.set_focus().unwrap();
                }
            }
            SystemTrayEvent::MenuItemClick { id, .. } => {
                let item_handle = app.tray_handle().get_item(&id);
                match id.as_str() {
                    "show" => {
                        let window = app.get_window("main").unwrap();
                        window.show().unwrap();
                        window.set_focus().unwrap();
                    }
                    "quit" => {
                        std::process::exit(0);
                    }
                    "start_transcription" => {
                        app.emit_all("start-transcription", {}).unwrap();
                    }
                    _ => {}
                }
            }
            _ => {}
        })
        .on_window_event(|event| match event.event() {
            tauri::WindowEvent::CloseRequested { api, .. } => {
                event.window().hide().unwrap();
                api.prevent_close();
            }
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}