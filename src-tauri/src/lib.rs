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
///
/// The probe listener has to be dropped before the backend can bind the port,
/// which leaves a window in which another local process could take it. The
/// window cannot be closed from here — the port is handed to a child process
/// that does its own bind — so it is handled where it actually matters instead:
/// `wait_for_backend` watches the child while it polls, and refuses to accept a
/// `/health` answer from a server that is not the backend we started.
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
                        .args([
                            &run_py.to_string_lossy(),
                            "--port",
                            &port.to_string(),
                            "--parent-pid",
                            &std::process::id().to_string(),
                        ])
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

        Err(
            "Could not find backend/run.py. Please run from the OIHK-Basic project root."
                .to_string(),
        )
    }

    #[cfg(not(debug_assertions))]
    // Release mode: look for the bundled PyInstaller sidecar executable
    {
        let backend_name = if cfg!(target_os = "windows") {
            "oihk-basic-backend.exe"
        } else {
            "oihk-basic-backend"
        };
        // The installed executable's own directory is the authoritative
        // location and is tried first. `OIHK_RESOURCE_DIR` is normally set by
        // `run()` from Tauri's resolved resource directory, but that lookup can
        // fail, in which case a value inherited from the environment would
        // otherwise decide which binary runs as the backend. It is therefore
        // accepted only as a fallback, and only when it resolves inside the
        // installation directory.
        let executable_dir = std::env::current_exe()
            .ok()
            .and_then(|path| path.parent().map(|dir| dir.to_path_buf()));

        let mut candidates = Vec::new();
        if let Some(dir) = executable_dir.as_ref() {
            candidates.push(dir.join(backend_name));
        }
        if let (Ok(resource_dir), Some(install_dir)) =
            (std::env::var("OIHK_RESOURCE_DIR"), executable_dir.as_ref())
        {
            let candidate = std::path::PathBuf::from(resource_dir).join(backend_name);
            let contained = match (candidate.canonicalize(), install_dir.canonicalize()) {
                (Ok(resolved), Ok(root)) => resolved.starts_with(&root),
                _ => false,
            };
            if contained {
                candidates.push(candidate);
            }
        }
        let backend_exe = candidates
            .into_iter()
            .find(|candidate| candidate.is_file())
            .ok_or_else(|| {
                "Bundled backend executable was not found in the application resources.".to_string()
            })?;

        let data_dir = oihk_data_dir()?;
        std::fs::create_dir_all(&data_dir)
            .map_err(|_| "The application data directory could not be created.".to_string())?;
        Command::new(&backend_exe)
            .args([
                "--port",
                &port.to_string(),
                "--parent-pid",
                &std::process::id().to_string(),
                "--data-dir",
                &data_dir.to_string_lossy(),
            ])
            .current_dir(data_dir)
            .env("OIHK_PORT", port.to_string())
            .env("OIHK_ENVIRONMENT", "desktop")
            .env("OIHK_AUTH_ENABLED", "false")
            .env("OIHK_DESKTOP_PACKAGED", "1")
            .spawn()
            .map_err(|e| format!("Failed to start backend: {}", e))
    }
} // end #[cfg(not(debug_assertions))] block

/// Report whether the managed backend child has already exited.
///
/// Returns `false` when no child is managed at all, which is the development
/// case where an already-running backend was adopted rather than spawned.
fn managed_child_exited(state: &BackendProcess) -> bool {
    match state.0.lock() {
        Ok(mut guard) => match guard.as_mut() {
            Some(child) => matches!(child.try_wait(), Ok(Some(_))),
            None => false,
        },
        Err(_) => false,
    }
}

/// Wait for the backend health endpoint to respond
///
/// `state` is the managed child to watch while polling. A `/health` answer only
/// proves *something* is listening on the port, and the port was chosen through
/// a probe listener that had to be released before the child could bind it. If
/// another local process won that race our child exits on its failed bind, so
/// treating its death as a failure is what keeps the app from adopting a
/// stranger's server as its backend.
fn wait_for_backend(
    port: u16,
    timeout_secs: u64,
    state: Option<&BackendProcess>,
) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{}/health", port);
    let start = std::time::Instant::now();

    loop {
        if let Some(state) = state {
            if managed_child_exited(state) {
                return Err(
                    "The managed backend process exited before it became healthy. Its port may \
                     have been taken by another local process."
                        .to_string(),
                );
            }
        }
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
    if matches!(child.try_wait(), Ok(Some(_))) {
        let _ = child.wait();
        return;
    }
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
    wait_for_backend(port, 30, Some(&state))
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
                // Every other lock site reports a poisoned mutex as an error
                // rather than panicking; setup is where a panic would be worst,
                // because it leaves the child running with nothing tracking it.
                let mut guard = state
                    .0
                    .lock()
                    .map_err(|_| "The managed backend state is unavailable.".to_string())?;
                *guard = Some(child);
            }

            // Show main window immediately
            let _ = app_handle.get_webview_window("main").map(|w| {
                let _ = w.show();
                let _ = w.set_focus();
            });

            // Spawn backend health check in background
            let health_handle = app.handle().clone();
            std::thread::spawn(move || {
                let backend_port: u16 = std::env::var("OIHK_PORT")
                    .ok()
                    .and_then(|p| p.parse().ok())
                    .unwrap_or(8001);
                let state: tauri::State<BackendProcess> = health_handle.state();
                if let Err(e) = wait_for_backend(backend_port, 30, Some(&state)) {
                    eprintln!("[OIHK Desktop] Backend health check failed: {}", e);
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
