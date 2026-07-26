use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::Manager;

#[derive(Default)]
struct BackendProcess(Mutex<Option<Child>>);

#[derive(Serialize)]
struct BackendStatus {
    port: u16,
    pid: u32,
}

#[derive(Clone, Deserialize, Serialize)]
struct RecoveryStatus {
    stage: String,
    source_version: String,
    target_version: String,
    backup_path: String,
    error_code: String,
    updated_at: String,
}

#[derive(Serialize)]
struct DesktopStatus {
    mode: &'static str,
    product: &'static str,
    version: &'static str,
    platform: &'static str,
    api_endpoint: String,
    backend_managed: bool,
    updater_enabled: bool,
    recovery: Option<RecoveryStatus>,
}

fn oihk_data_dir() -> Result<PathBuf, String> {
    #[cfg(target_os = "windows")]
    let root = std::env::var_os("APPDATA").map(PathBuf::from);
    #[cfg(target_os = "macos")]
    let root = std::env::var_os("HOME")
        .map(PathBuf::from)
        .map(|path| path.join("Library").join("Application Support"));
    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    let root = std::env::var_os("XDG_DATA_HOME")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("HOME")
                .map(PathBuf::from)
                .map(|path| path.join(".local").join("share"))
        });
    root.map(|path| path.join("OIHK-Basic")).ok_or_else(|| {
        "The operating-system application data directory is unavailable.".to_string()
    })
}

fn read_recovery_status() -> Option<RecoveryStatus> {
    let path = oihk_data_dir()
        .ok()?
        .join("updates")
        .join("last-update.json");
    let content = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&content).ok()
}

/// Find a free TCP port on 127.0.0.1
fn find_free_port() -> u16 {
    let listener =
        std::net::TcpListener::bind("127.0.0.1:0").expect("Failed to bind to find free port");
    listener.local_addr().unwrap().port()
}

/// Start the FastAPI backend
fn start_backend(port: u16) -> Result<Child, String> {
    // In debug/dev mode, try to launch Python backend directly
    #[cfg(debug_assertions)]
    {
        let python = if cfg!(target_os = "windows") {
            "python"
        } else {
            "python3"
        };

        // Search for backend/run.py starting from current dir up to root
        if let Ok(cwd) = std::env::current_dir() {
            let mut search_path = cwd.clone();
            loop {
                let run_py = search_path.join("backend").join("run.py");
                if run_py.exists() {
                    eprintln!("[OIHK Desktop] Starting Python backend from: {:?}", run_py);
                    return Command::new(python)
                        .args([&run_py.to_string_lossy(), "--port", &port.to_string()])
                        .env("OIHK_PORT", port.to_string())
                        .spawn()
                        .map_err(|e| {
                            format!(
                                "Failed to start Python backend: {}.\nMake sure Python is installed and in your PATH.",
                                e
                            )
                        });
                }
                if !search_path.pop() {
                    break;
                }
            }
        }

        return Err(
            "Could not find backend/run.py. Please run from the OIHK-Basic project root."
                .to_string(),
        );
    }

    #[cfg(not(debug_assertions))]
    // Release mode: look for the bundled PyInstaller sidecar executable
    {
        let backend_name = if cfg!(target_os = "windows") {
            "oihk-basic-backend.exe"
        } else {
            "oihk-basic-backend"
        };
        let mut candidates = Vec::new();
        if let Ok(resource_dir) = std::env::var("OIHK_RESOURCE_DIR") {
            candidates.push(std::path::PathBuf::from(resource_dir).join(backend_name));
        }
        if let Some(executable_dir) = std::env::current_exe()
            .ok()
            .and_then(|path| path.parent().map(|dir| dir.to_path_buf()))
        {
            candidates.push(executable_dir.join(backend_name));
        }
        if let Ok(current_dir) = std::env::current_dir() {
            candidates.push(current_dir.join(backend_name));
        }
        let backend_exe = candidates
            .into_iter()
            .find(|candidate| candidate.is_file())
            .ok_or_else(|| {
                "Bundled backend executable was not found in the application resources.".to_string()
            })?;

        Command::new(&backend_exe)
            .args(["--port", &port.to_string()])
            .env("OIHK_PORT", port.to_string())
            .env("OIHK_ENVIRONMENT", "desktop")
            .env("OIHK_AUTH_ENABLED", "false")
            .spawn()
            .map_err(|e| format!("Failed to start backend: {}", e))
    }
} // end #[cfg(not(debug_assertions))] block

/// Wait for the backend health endpoint to respond
fn wait_for_backend(port: u16, timeout_secs: u64) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{}/health", port);
    let start = std::time::Instant::now();

    loop {
        if start.elapsed().as_secs() > timeout_secs {
            return Err(format!(
                "Backend did not start within {} seconds",
                timeout_secs
            ));
        }
        match ureq::get(&url).call() {
            Ok(resp) if resp.status() == 200 => return Ok(()),
            _ => std::thread::sleep(std::time::Duration::from_millis(200)),
        }
    }
}

fn terminate_backend(child: &mut Child) {
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        let _ = Command::new("taskkill.exe")
            .args(["/PID", &child.id().to_string(), "/T", "/F"])
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }
    let _ = child.kill();
    let _ = child.wait();
}

#[tauri::command]
fn get_backend_url(state: tauri::State<BackendProcess>) -> Result<BackendStatus, String> {
    let guard = state.0.lock().map_err(|e| format!("Lock error: {}", e))?;

    let port: u16 = std::env::var("OIHK_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8001);

    Ok(BackendStatus {
        port,
        pid: guard.as_ref().map(Child::id).unwrap_or(0),
    })
}

#[tauri::command]
fn desktop_status(state: tauri::State<BackendProcess>) -> Result<DesktopStatus, String> {
    let guard = state.0.lock().map_err(|e| format!("Lock error: {}", e))?;
    let port = std::env::var("OIHK_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(8001);
    Ok(DesktopStatus {
        mode: "desktop",
        product: "OIHK Basic",
        version: env!("CARGO_PKG_VERSION"),
        platform: std::env::consts::OS,
        api_endpoint: format!("http://127.0.0.1:{}", port),
        backend_managed: guard.is_some(),
        updater_enabled: cfg!(feature = "updater-release"),
        recovery: read_recovery_status(),
    })
}

#[tauri::command]
fn stop_backend_for_update(
    state: tauri::State<BackendProcess>,
    update_token: String,
) -> Result<(), String> {
    if update_token.len() < 32 || update_token.len() > 256 {
        return Err("The update preparation token is invalid.".to_string());
    }
    let port = std::env::var("OIHK_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(8001);
    let mut child = {
        let mut guard = state
            .0
            .lock()
            .map_err(|_| "The managed backend state is unavailable.".to_string())?;
        guard
            .take()
            .ok_or_else(|| "The updater can only stop its managed packaged backend.".to_string())?
    };

    let shutdown_url = format!("http://127.0.0.1:{}/updates/shutdown", port);
    let request = ureq::post(&shutdown_url)
        .set("X-OIHK-Update-Token", &update_token)
        .set("Content-Type", "application/json")
        .timeout(Duration::from_secs(5))
        .send_string("{}");
    if request
        .as_ref()
        .map(|response| response.status())
        .unwrap_or(0)
        != 202
    {
        if let Ok(mut guard) = state.0.lock() {
            *guard = Some(child);
        }
        return Err("The backend refused the authenticated update shutdown request.".to_string());
    }

    let deadline = Instant::now() + Duration::from_secs(15);
    loop {
        match child.try_wait() {
            Ok(Some(_)) => return Ok(()),
            Ok(None) if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(100)),
            Ok(None) => {
                terminate_backend(&mut child);
                return Err(
                    "The local service did not stop within the safety timeout. Installation was cancelled."
                        .to_string(),
                );
            }
            Err(_) => {
                terminate_backend(&mut child);
                return Err(
                    "The local service exit could not be verified. Installation was cancelled."
                        .to_string(),
                );
            }
        }
    }
}

#[tauri::command]
fn restart_backend_after_update_failure(state: tauri::State<BackendProcess>) -> Result<(), String> {
    let port = std::env::var("OIHK_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(8001);
    {
        let guard = state
            .0
            .lock()
            .map_err(|_| "The managed backend state is unavailable.".to_string())?;
        if guard.is_some() {
            return Ok(());
        }
    }
    let child = start_backend(port)?;
    {
        let mut guard = state
            .0
            .lock()
            .map_err(|_| "The managed backend state is unavailable.".to_string())?;
        *guard = Some(child);
    }
    wait_for_backend(port, 30)
}

#[tauri::command]
fn open_backup_directory() -> Result<(), String> {
    let directory = oihk_data_dir()?.join("backups").join("pre-update");
    std::fs::create_dir_all(&directory)
        .map_err(|_| "The backup directory could not be created.".to_string())?;
    #[cfg(target_os = "windows")]
    let status = Command::new("explorer.exe").arg(&directory).status();
    #[cfg(target_os = "macos")]
    let status = Command::new("open").arg(&directory).status();
    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    let status = Command::new("xdg-open").arg(&directory).status();
    match status {
        Ok(result) if result.success() => Ok(()),
        _ => Err("The backup directory could not be opened.".to_string()),
    }
}

/// Check if a backend is already running on a known port
fn find_existing_backend() -> Option<u16> {
    #[cfg(debug_assertions)]
    {
        for &port in &[8001, 8000] {
            let url = format!("http://127.0.0.1:{}/health", port);
            match ureq::get(&url)
                .timeout(std::time::Duration::from_secs(1))
                .call()
            {
                Ok(resp) if resp.status() == 200 => {
                    eprintln!("[OIHK Desktop] Backend already running on port {}", port);
                    return Some(port);
                }
                _ => continue,
            }
        }
    }
    None
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let existing_port = find_existing_backend();
    let port = existing_port.unwrap_or_else(find_free_port);
    std::env::set_var("OIHK_PORT", port.to_string());

    let builder = tauri::Builder::default();
    #[cfg(feature = "updater-release")]
    let builder = builder.plugin(tauri_plugin_updater::Builder::new().build());

    builder
        .manage(BackendProcess::default())
        .setup(move |app| {
            let app_handle = app.handle().clone();
            if let Ok(resource_dir) = app.path().resource_dir() {
                std::env::set_var("OIHK_RESOURCE_DIR", resource_dir);
            }

            // Only start backend if not already running
            if existing_port.is_none() {
                let child = start_backend(port).map_err(|e| {
                    eprintln!("Failed to start backend: {}", e);
                    e
                })?;

                let state: tauri::State<BackendProcess> = app.state();
                *state.0.lock().unwrap() = Some(child);
            }

            // Show main window immediately
            let _ = app_handle.get_webview_window("main").map(|w| {
                let _ = w.show();
                let _ = w.set_focus();
            });

            // Spawn backend health check in background
            let handle = app_handle.clone();
            std::thread::spawn(move || {
                let backend_port: u16 = std::env::var("OIHK_PORT")
                    .ok()
                    .and_then(|p| p.parse().ok())
                    .unwrap_or(8001);
                if let Err(e) = wait_for_backend(backend_port, 30) {
                    let _ = handle.get_webview_window("main").map(|w| {
                        let safe_error = serde_json::to_string(&e)
                            .unwrap_or_else(|_| "\"Backend startup failed\"".to_string());
                        let _ = w.eval(&format!(
                            r#"setTimeout(() => {{
                                const d = document.createElement('div');
                                d.style.cssText = 'position:fixed;bottom:1rem;right:1rem;z-index:9999;padding:1rem 1.5rem;background:#1a1a2e;border:1px solid #ef4444;border-radius:8px;color:#fca5a5;font-size:0.875rem;max-width:400px;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
                                d.textContent = 'Backend error: ' + {};
                                document.body.appendChild(d);
                            }}, 3000);"#,
                            safe_error
                        ));
                    });
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(state) = window.try_state::<BackendProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            terminate_backend(&mut child);
                        }
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_backend_url,
            desktop_status,
            stop_backend_for_update,
            restart_backend_after_update_failure,
            open_backup_directory
        ])
        .run(tauri::generate_context!())
        .expect("Error while running OIHK Basic");
}
