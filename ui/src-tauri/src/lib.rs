// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

struct BackendState {
    process: Mutex<Option<Child>>,
    port: u16,
}

#[tauri::command]
async fn start_backend(app_handle: tauri::AppHandle) -> Result<String, String> {
    let state = app_handle.state::<BackendState>();
    let mut process_guard = state.process.lock().unwrap();
    
    if process_guard.is_some() {
        return Err("Backend is already running".to_string());
    }
    
    // Get the path to the Python script
    let resource_dir = app_handle
        .path_resolver()
        .resolve_resource("../../src/api/chat_server.py")
        .ok_or("Could not find chat_server.py")?;
    
    // Start the Python backend
    let cmd = Command::new("python")
        .arg(&resource_dir)
        .env("AGENTICAI_API_PORT", state.port.to_string())
        .spawn()
        .map_err(|e| format!("Failed to start backend: {}", e))?;
    
    *process_guard = Some(cmd);
    
    // Wait a bit for the server to start
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
    
    Ok(format!("Backend started on port {}", state.port))
}

#[tauri::command]
async fn stop_backend(app_handle: tauri::AppHandle) -> Result<String, String> {
    let state = app_handle.state::<BackendState>();
    let mut process_guard = state.process.lock().unwrap();
    
    if let Some(mut child) = process_guard.take() {
        child.kill().map_err(|e| format!("Failed to stop backend: {}", e))?;
        child.wait().map_err(|e| format!("Failed to wait for backend: {}", e))?;
        Ok("Backend stopped".to_string())
    } else {
        Err("Backend is not running".to_string())
    }
}

#[tauri::command]
async fn send_chat_message(message: String, session_id: Option<String>) -> Result<String, String> {
    let state = tauri::State::<BackendState>::try_from_global();
    let state = state.map_err(|_| "Backend state not available")?;
    
    let url = format!("http://localhost:{}/chat", state.port);
    
    let client = reqwest::Client::new();
    let request_body = serde_json::json!({
        "message": message,
        "session_id": session_id,
        "use_tags": true,
        "use_summaries": true,
    });
    
    match client
        .post(&url)
        .json(&request_body)
        .send()
        .await
    {
        Ok(response) => {
            if response.status().is_success() {
                let json: serde_json::Value = response
                    .json()
                    .await
                    .map_err(|e| format!("Failed to parse response: {}", e))?;
                
                if let Some(response_text) = json.get("response").and_then(|v| v.as_str()) {
                    Ok(response_text.to_string())
                } else {
                    Err("Invalid response format".to_string())
                }
            } else {
                Err(format!("HTTP error: {}", response.status()))
            }
        }
        Err(e) => Err(format!("Failed to send message: {}", e)),
    }
}

#[tauri::command]
async fn get_chat_history(session_id: Option<String>, limit: i32) -> Result<Vec<serde_json::Value>, String> {
    let state = tauri::State::<BackendState>::try_from_global();
    let state = state.map_err(|_| "Backend state not available")?;
    
    let url = format!("http://localhost:{}/history", state.port);
    
    let client = reqwest::Client::new();
    let request_body = serde_json::json!({
        "session_id": session_id,
        "limit": limit,
    });
    
    match client
        .post(&url)
        .json(&request_body)
        .send()
        .await
    {
        Ok(response) => {
            if response.status().is_success() {
                let json: serde_json::Value = response
                    .json()
                    .await
                    .map_err(|e| format!("Failed to parse response: {}", e))?;
                
                if let Some(messages) = json.get("messages").and_then(|v| v.as_array()) {
                    Ok(messages.clone())
                } else {
                    Err("Invalid response format".to_string())
                }
            } else {
                Err(format!("HTTP error: {}", response.status()))
            }
        }
        Err(e) => Err(format!("Failed to get history: {}", e)),
    }
}

#[tauri::command]
async fn new_session() -> Result<String, String> {
    let state = tauri::State::<BackendState>::try_from_global();
    let state = state.map_err(|_| "Backend state not available")?;
    
    let url = format!("http://localhost:{}/new-session", state.port);
    
    let client = reqwest::Client::new();
    
    match client.post(&url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                let json: serde_json::Value = response
                    .json()
                    .await
                    .map_err(|e| format!("Failed to parse response: {}", e))?;
                
                if let Some(session_id) = json.get("session_id").and_then(|v| v.as_str()) {
                    Ok(session_id.to_string())
                } else {
                    Err("Invalid response format".to_string())
                }
            } else {
                Err(format!("HTTP error: {}", response.status()))
            }
        }
        Err(e) => Err(format!("Failed to create new session: {}", e)),
    }
}

#[tauri::command]
async fn backend_status() -> Result<bool, String> {
    let state = tauri::State::<BackendState>::try_from_global();
    let state = state.map_err(|_| "Backend state not available")?;
    
    let url = format!("http://localhost:{}/health", state.port);
    
    let client = reqwest::Client::new();
    
    match client.get(&url).send().await {
        Ok(response) => Ok(response.status().is_success()),
        Err(_) => Ok(false),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(BackendState {
            process: Mutex::new(None),
            port: 8000,
        })
        .invoke_handler(tauri::generate_handler![
            start_backend,
            stop_backend,
            send_chat_message,
            get_chat_history,
            new_session,
            backend_status,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
