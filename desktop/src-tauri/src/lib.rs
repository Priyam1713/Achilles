use std::env;
use std::fs;
use std::path::PathBuf;

/// Locates the kernel's state directory the same way `ConfigBundle.state_dir`
/// (src/sovereign_ai/kernel/config.py) resolves it: `SOVEREIGN_STATE_DIR` wins if set,
/// otherwise `<repo_root>/state`, matching what a native `python -m sovereign_ai.cli
/// serve` run on this same machine already uses (configs/system.yaml's `state_dir:
/// ./state`, unset by scripts/start.ps1 on the Windows side).
///
/// Honest limit for this first vertical slice: the repo-root fallback assumes the app is
/// still being run from within a checkout of this repository (`cargo tauri dev` from
/// `desktop/`, so `src-tauri`'s CWD is two levels under repo root) rather than installed
/// standalone elsewhere. `SOVEREIGN_STATE_DIR` is the real override for any other layout,
/// the same environment variable the Python kernel itself already honors.
fn resolve_state_dir() -> PathBuf {
    if let Ok(dir) = env::var("SOVEREIGN_STATE_DIR") {
        if !dir.is_empty() {
            return PathBuf::from(dir);
        }
    }
    env::current_dir()
        .unwrap_or_else(|_| PathBuf::from("."))
        .join("..")
        .join("..")
        .join("state")
}

/// Reads the kernel's local session token (`kernel/auth.py`'s `SessionAuth`) directly off
/// disk. This is the same mechanism the browser-served `/ui` page already relies on --
/// that docstring explicitly names "the native Windows control-plane process" as one of
/// the two intended readers of this file, which is exactly what a Tauri desktop app's Rust
/// side is. The token never crosses a network boundary to get here: both the kernel API
/// server and this desktop app run as separate processes on the same single-operator
/// machine, reading the same local, owner-permissioned file.
#[tauri::command]
fn get_session_token() -> Result<String, String> {
    let path = resolve_state_dir().join("session.token");
    fs::read_to_string(&path)
        .map(|s| s.trim().to_string())
        .map_err(|e| {
            format!(
                "could not read session token at {}: {e}. Is the kernel API server running \
                 (Run.ps1 / `python -m sovereign_ai.cli serve`)?",
                path.display()
            )
        })
}

/// The kernel API's default bind address (configs/system.yaml `api.bind`/`api.port`).
/// Hardcoded for this first slice rather than read from YAML -- the desktop app and the
/// kernel it drives are expected to share one machine's one manifest; a settings screen to
/// override this is real follow-on work once there is a second real deployment shape to
/// support, not before.
#[tauri::command]
fn get_kernel_base_url() -> String {
    env::var("SOAI_KERNEL_BASE_URL").unwrap_or_else(|_| "http://127.0.0.1:7788".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            get_session_token,
            get_kernel_base_url
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
