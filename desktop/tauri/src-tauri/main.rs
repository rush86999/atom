#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use tauri::{SystemTray, SystemTrayEvent, SystemTrayMenu, CustomMenuItem, Manager, command, AppHandle, Window};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use tract_onnx::prelude::*;
use std::fs;
use std::sync::{Arc, Mutex};
use serde_json::Value;

#[command]
fn focus_window(window: Window) {
    window.set_focus().unwrap();
}

#[command]
async fn get_project_health_score(app_handle: AppHandle) -> Result<String, String> {
    let settings_path = app_handle.path_resolver()
        .resolve_resource("settings.json")
        .expect("failed to resolve resource");
    let settings_file = fs::read_to_string(settings_path).map_err(|err| err.to_string())?;
    let settings: Value = serde_json::from_str(&settings_file).map_err(|err| err.to_string())?;

    let client = reqwest::Client::new();
    let res = client.post("http://localhost:3000/api/project-health")
        .json(&serde_json::json!({
            "settings": settings
        }))
        .send()
        .await
        .map_err(|err| err.to_string())?;

    let body = res.text().await.map_err(|err| err.to_string())?;
    Ok(body)
}

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

use std::io::Write;

fn create_silent_audio_recording_stream(app_handle: &AppHandle, stream_mutex: &Arc<Mutex<Option<cpal::Stream>>>) {
    let settings_path = app_handle.path_resolver()
        .resolve_resource("settings.json")
        .expect("failed to resolve resource");
    let settings_file = fs::read_to_string(settings_path).unwrap();
    let settings: Value = serde_json::from_str(&settings_file).unwrap();
    let silent_audio_recording = settings["silentAudioRecording"].as_bool().unwrap_or(false);

    if !silent_audio_recording {
        return;
    }

    let host = cpal::default_host();
    let device = host.default_input_device().expect("no input device available");
    let config = device.default_input_config().unwrap();

    let app_handle_clone = app_handle.clone();
    let stream = device.build_input_stream(
        &config.into(),
        move |data: &[f32], _: &cpal::InputCallbackInfo| {
            let client = reqwest::blocking::Client::new();
            let res = client.post("http://localhost:3000/api/silent-audio-recording")
                .body(data.to_vec())
                .send();
        },
        |err| eprintln!("an error occurred on stream: {}", err),
    ).unwrap();
    stream.play().unwrap();
    *stream_mutex.lock().unwrap() = Some(stream);
}

fn create_stream(app_handle: &AppHandle, stream_mutex: &Arc<Mutex<Option<cpal::Stream>>>) {
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

    let app_handle_clone = app_handle.clone();
    let stream = device.build_input_stream(
        &config.into(),
        move |data: &[f32], _: &cpal::InputCallbackInfo| {
            let input = tract_ndarray::Array1::from_vec(data.to_vec());
            let input = input.into_shape((1, 16000)).unwrap();
            let result = model.run(tvec!(input.into())).unwrap();
            if let Some(tensor) = result.get(0) {
                if let Some(value) = tensor.as_slice::<f32>().unwrap().get(0) {
                    if *value > 0.5 {
                        app_handle_clone.emit_all("wake-word-detected", {}).unwrap();
                    }
                }
            }
        },
        |err| eprintln!("an error occurred on stream: {}", err),
    ).unwrap();
    stream.play().unwrap();
    *stream_mutex.lock().unwrap() = Some(stream);
}

fn main() {
    let show = CustomMenuItem::new("show".to_string(), "Show App");
    let quit = CustomMenuItem::new("quit".to_string(), "Quit");
    let start_transcription = CustomMenuItem::new("start_transcription".to_string(), "Start Transcription");
    let tray_menu = SystemTrayMenu::new().add_item(show).add_item(start_transcription).add_item(quit);
    let system_tray = SystemTray::new().with_menu(tray_menu);

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![send_message_to_agent, get_project_health_score, focus_window])
        .setup(|app| {
            let app_handle = app.handle();

            let audio_stream: Arc<Mutex<Option<cpal::Stream>>> = Arc::new(Mutex::new(None));

            // Initial stream creation
            let handle_clone = app_handle.clone();
            let stream_clone = audio_stream.clone();
            create_stream(&handle_clone, &stream_clone);

            // Silent audio recording thread
            let handle_clone = app_handle.clone();
            let silent_audio_stream: Arc<Mutex<Option<cpal::Stream>>> = Arc::new(Mutex::new(None));
            let stream_clone_silent = silent_audio_stream.clone();
            create_silent_audio_recording_stream(&handle_clone, &stream_clone_silent);

            // Power monitor thread
            let handle_clone = app_handle.clone();
            let stream_clone_power = audio_stream.clone();
            std::thread::spawn(move || {
                for event in power_monitor::observe().unwrap() {
                    match event {
                        power_monitor::PowerEvent::Resume => {
                            handle_clone.emit_all("resume-detected", {}).unwrap();
                            if let Some(window) = handle_clone.get_window("main") {
                                window.show().unwrap();
                                focus_window(window);
                            }
                            println!("System resumed, restarting audio stream");
                            create_stream(&handle_clone, &stream_clone_power);
                        },
                        power_monitor::PowerEvent::Suspend => {
                            println!("System suspending, stopping audio stream");
                            let mut stream = stream_clone_power.lock().unwrap();
                            if let Some(s) = stream.take() {
                                drop(s);
                            }
                        }
                        _ => {}
                    }
                }
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