// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::process::{Child, Command, Stdio};
// use std::sync::Mutex;
use std::io::{Write, BufRead, BufReader};
use tokio::sync::Mutex as AsyncMutex;
use tauri::Manager;
use serde_json::{json, Value};
use uuid::Uuid;

struct BackendState {
    process: AsyncMutex<Option<Child>>,
    stdin: AsyncMutex<Option<std::process::ChildStdin>>,
    stdout: AsyncMutex<Option<BufReader<std::process::ChildStdout>>>,
}

/// Send a JSON-RPC request to the Python backend and get response
async fn send_json_rpc(
    app_handle: &tauri::AppHandle,
    method: &str,
    params: Value,
    request_id: Option<String>,
) -> Result<Value, String> {
    let state = app_handle.state::<BackendState>();
    let request_id = request_id.unwrap_or_else(|| Uuid::new_v4().to_string());
    
    let request = json!({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    });
    
    let request_str = serde_json::to_string(&request)
        .map_err(|e| format!("Failed to serialize request: {}", e))?;
    
    // Get stdin handle
    let mut stdin_guard = state.stdin.lock().await;
    let stdin = stdin_guard.as_mut()
        .ok_or("Backend stdin not available")?;
    
    // Send request
    stdin.write_all(request_str.as_bytes())
        .map_err(|e| format!("Failed to write to backend: {}", e))?;
    stdin.write_all(b"\n")
        .map_err(|e| format!("Failed to write newline: {}", e))?;
    stdin.flush()
        .map_err(|e| format!("Failed to flush stdin: {}", e))?;
    
    // Get stdout handle and read response
    let mut stdout_guard = state.stdout.lock().await;
    let stdout = stdout_guard.as_mut()
        .ok_or("Backend stdout not available")?;
    
    let mut response_line = String::new();
    let bytes_read = stdout.read_line(&mut response_line)
        .map_err(|e| format!("Failed to read response: {}", e))?;
        
    if bytes_read == 0 {
        return Err("Backend process exited unexpectedly (EOF on stdout)".to_string());
    }
    
    let response: Value = serde_json::from_str(&response_line)
        .map_err(|e| format!("Failed to parse response: {}", e))?;
    
    // Check for JSON-RPC error
    if let Some(error) = response.get("error") {
        let error_msg = error.get("message")
            .and_then(|v| v.as_str())
            .unwrap_or("Unknown error");
        return Err(format!("JSON-RPC error: {}", error_msg));
    }
    
    // Extract result
    response.get("result")
        .cloned()
        .ok_or_else(|| "No result in response".to_string())
}

#[tauri::command]
async fn start_backend(app_handle: tauri::AppHandle) -> Result<String, String> {
    let state = app_handle.state::<BackendState>();
    {
        let guard = state.process.lock().await;
        if guard.is_some() {
            return Err("Backend is already running".to_string());
        }
    }
    
    // Get the path to the Python embedded backend
    let script_path = std::path::Path::new("../../src/api/embedded_backend.py")
        .canonicalize()
        .map_err(|e| format!("Could not find embedded_backend.py: {}", e))?;
        
    let project_root = std::path::Path::new("../../")
        .canonicalize()
        .map_err(|e| format!("Could not find project root: {}", e))?;
        
    let python_path = project_root.join(".venv/bin/python");
    
    // Start the Python embedded backend with stdin/stdout pipes
    let mut cmd = Command::new(if python_path.exists() { python_path.to_str().unwrap() } else { "python3" });
    cmd.current_dir(&project_root)
        .arg(&script_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());
    
    let mut child = cmd.spawn()
        .map_err(|e| format!("Failed to start backend: {}", e))?;
    
    // Get stdin and stdout handles
    let stdin = child.stdin.take().ok_or("Failed to get stdin handle")?;
    let stdout = child.stdout.take().ok_or("Failed to get stdout handle")?;
    let stdout_reader = BufReader::new(stdout);
    
    // Store handles in async mutexes
    *state.stdin.lock().await = Some(stdin);
    *state.stdout.lock().await = Some(stdout_reader);
    {
        let mut guard = state.process.lock().await;
        *guard = Some(child);
    }
    
    // Test connection with a health check via direct JSON-RPC call
    match send_json_rpc(&app_handle, "health", json!({}), None).await {
        Ok(result) => {
            let status = result.get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown");
            if status == "healthy" {
                Ok("Embedded backend started successfully".to_string())
            } else {
                let _ = stop_backend_internal(&app_handle).await;
                Err("Backend started but health check failed".to_string())
            }
        }
        Err(e) => {
            let _ = stop_backend_internal(&app_handle).await;
            Err(format!("Health check failed: {}", e))
        },
    }
}

async fn stop_backend_internal(app_handle: &tauri::AppHandle) -> Result<String, String> {
    let state = app_handle.state::<BackendState>();
    
    // Clear stdin/stdout handles first
    *state.stdin.lock().await = None;
    *state.stdout.lock().await = None;
    
    // Get the child process
    let child_opt = {
    let mut process_guard = state.process.lock().await;
        process_guard.take()
    };
    
    if let Some(mut child) = child_opt {
        let _ = child.kill();
        let _ = child.wait();
        Ok("Backend stopped".to_string())
    } else {
        Err("Backend is not running".to_string())
    }
}

#[tauri::command]
async fn stop_backend(app_handle: tauri::AppHandle) -> Result<String, String> {
    stop_backend_internal(&app_handle).await
}

#[tauri::command]
async fn send_chat_message(
    app_handle: tauri::AppHandle,
    message: String, 
    session_id: Option<String>
) -> Result<serde_json::Value, String> {
    let params = json!({
        "message": message,
        "session_id": session_id,
        "use_tags": true,
        "use_summaries": true,
        "request_id": Uuid::new_v4().to_string()
    });
    
    let result = send_json_rpc(&app_handle, "chat", params, None).await?;
    
    if result.get("response").is_some() {
        Ok(result)
    } else {
        Err("No response in result".to_string())
    }
}

#[tauri::command]
async fn get_chat_history(
    app_handle: tauri::AppHandle,
    session_id: Option<String>, 
    limit: i32
) -> Result<Vec<serde_json::Value>, String> {
    let params = json!({
        "session_id": session_id,
        "limit": limit,
        "request_id": Uuid::new_v4().to_string()
    });
    
    let result = send_json_rpc(&app_handle, "history", params, None).await?;
    
    result.get("messages")
        .and_then(|v| v.as_array())
        .map(|arr| arr.clone())
        .ok_or_else(|| "No messages in result".to_string())
}

#[tauri::command]
async fn new_session(app_handle: tauri::AppHandle) -> Result<String, String> {
    let result = send_json_rpc(&app_handle, "new_session", json!({}), None).await?;
    
    result.get("session_id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .ok_or_else(|| "No session_id in result".to_string())
}

#[tauri::command]
async fn backend_status(app_handle: tauri::AppHandle) -> Result<bool, String> {
    let _state = app_handle.state::<BackendState>();
    
    match send_json_rpc(&app_handle, "health", json!({}), None).await {
        Ok(result) => {
            // Check if we got a valid health response
            let status = result.get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown");
            Ok(status == "healthy")
        }
        Err(_) => Ok(false),
    }
}

#[tauri::command]
async fn get_all_sessions(app_handle: tauri::AppHandle) -> Result<Vec<serde_json::Value>, String> {
    let result = send_json_rpc(&app_handle, "get_sessions", json!({}), None).await?;
    
    result.get("sessions")
        .and_then(|v| v.as_array())
        .map(|arr| arr.clone())
        .ok_or_else(|| "No sessions in result".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(BackendState {
            process: AsyncMutex::new(None),
            stdin: AsyncMutex::new(None),
            stdout: AsyncMutex::new(None),
        })
        .setup(|app| {
            let quit_i = tauri::menu::MenuItem::with_id(app, "quit", "Quit AgenticAI", true, None::<&str>)?;
            let show_i = tauri::menu::MenuItem::with_id(app, "show", "Show Chat", true, None::<&str>)?;
            
            let menu = tauri::menu::Menu::with_items(app, &[&show_i, &quit_i])?;

            let _tray = tauri::tray::TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "quit" => {
                        std::process::exit(0);
                    }
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let tauri::tray::TrayIconEvent::Click {
                        button: tauri::tray::MouseButton::Left,
                        button_state: tauri::tray::MouseButtonState::Up,
                        ..
                    } = event {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            send_chat_message,
            get_chat_history,
            new_session,
            backend_status,
            get_all_sessions,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
