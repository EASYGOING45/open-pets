// Prevents additional console window on Windows in release; do nothing on macOS / Linux.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
// objc 0.2 macros emit deprecated cfg lints on modern rustc; harmless.
#![allow(unexpected_cfgs)]

use notify::{Config as NotifyConfig, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::sync::Mutex;
use std::time::Instant;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    AppHandle, Builder, Emitter, LogicalPosition, Manager, PhysicalPosition, State,
    WebviewUrl, WebviewWindowBuilder, WindowEvent,
};

// Persistent config saved to ~/.openpets/config.json. Distinct from
// state.json (which is the *event* file driven by external tools); this is
// purely OpenPets' own preferences.
#[derive(Serialize, Deserialize, Clone, Default)]
struct OpenPetsConfig {
    #[serde(default)]
    active_pet_id: Option<String>,
    #[serde(default)]
    window_position: Option<WindowPos>,
}

#[derive(Serialize, Deserialize, Clone, Default)]
struct WindowPos {
    x: f64,
    y: f64,
}

#[derive(Default)]
struct AppState {
    config: Mutex<OpenPetsConfig>,
    // Throttle window-position writes so dragging doesn't pound the disk.
    last_position_write: Mutex<Option<Instant>>,
}

#[derive(Serialize, Clone)]
struct Pet {
    id: String,
    display_name: String,
    description: String,
    spritesheet: String,
}

fn pet_dir() -> Option<PathBuf> {
    std::env::var("HOME")
        .ok()
        .map(|h| PathBuf::from(h).join(".codex").join("pets"))
}

#[tauri::command]
fn list_pets() -> Vec<Pet> {
    let Some(dir) = pet_dir() else {
        return vec![];
    };
    let Ok(entries) = fs::read_dir(&dir) else {
        return vec![];
    };

    let mut pets = vec![];
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let manifest = path.join("pet.json");
        let sheet = path.join("spritesheet.webp");
        if !manifest.exists() || !sheet.exists() {
            continue;
        }
        let Ok(text) = fs::read_to_string(&manifest) else {
            continue;
        };
        let Ok(json) = serde_json::from_str::<serde_json::Value>(&text) else {
            continue;
        };
        let id = json
            .get("id")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let display_name = json
            .get("displayName")
            .and_then(|v| v.as_str())
            .unwrap_or(&id)
            .to_string();
        let description = json
            .get("description")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        pets.push(Pet {
            id,
            display_name,
            description,
            spritesheet: sheet.to_string_lossy().into_owned(),
        });
    }
    pets.sort_by(|a, b| a.id.cmp(&b.id));
    pets
}

fn setup_tray(app: &tauri::App, pets: &[Pet]) -> tauri::Result<()> {
    let menu = Menu::new(app)?;

    // One menu entry per installed pet — clicking switches the active pet.
    for pet in pets {
        let item = MenuItem::with_id(
            app,
            format!("pet:{}", pet.id),
            &pet.display_name,
            true,
            None::<&str>,
        )?;
        menu.append(&item)?;
    }

    if !pets.is_empty() {
        menu.append(&PredefinedMenuItem::separator(app)?)?;
    }

    let picker = MenuItem::with_id(app, "picker", "Choose Pet…", true, None::<&str>)?;
    menu.append(&picker)?;

    menu.append(&PredefinedMenuItem::separator(app)?)?;

    let quit = MenuItem::with_id(app, "quit", "Quit OpenPets", true, None::<&str>)?;
    menu.append(&quit)?;

    let icon = app
        .default_window_icon()
        .cloned()
        .ok_or_else(|| tauri::Error::AssetNotFound("default window icon missing".into()))?;

    TrayIconBuilder::new()
        .menu(&menu)
        .icon(icon)
        .on_menu_event(handle_tray_event)
        .build(app)?;
    Ok(())
}

fn handle_tray_event(app: &AppHandle, event: tauri::menu::MenuEvent) {
    let id = event.id.as_ref();
    if id == "quit" {
        app.exit(0);
    } else if id == "picker" {
        if let Err(e) = show_picker_window(app) {
            eprintln!("[OpenPets] failed to open picker: {e}");
        }
    } else if let Some(pet_id) = id.strip_prefix("pet:") {
        activate_pet(app, pet_id);
    }
}

fn activate_pet(app: &AppHandle, pet_id: &str) {
    let pets = list_pets();
    let Some(pet) = pets.into_iter().find(|p| p.id == pet_id) else {
        eprintln!("[OpenPets] activate_pet: '{pet_id}' not found");
        return;
    };
    if let Some(state) = app.try_state::<AppState>() {
        update_config(&state, |cfg| cfg.active_pet_id = Some(pet.id.clone()));
    }
    if let Err(e) = app.emit("pet-changed", &pet) {
        eprintln!("[OpenPets] emit pet-changed failed: {e}");
    }
}

// --- Persistent config ---------------------------------------------------

const CONFIG_FILE_NAME: &str = "config.json";

fn config_path() -> Option<PathBuf> {
    state_dir().map(|d| d.join(CONFIG_FILE_NAME))
}

fn load_config() -> OpenPetsConfig {
    let Some(path) = config_path() else {
        return OpenPetsConfig::default();
    };
    let Ok(text) = fs::read_to_string(&path) else {
        return OpenPetsConfig::default();
    };
    serde_json::from_str(&text).unwrap_or_default()
}

fn save_config(config: &OpenPetsConfig) {
    let Some(dir) = state_dir() else { return };
    if let Err(e) = fs::create_dir_all(&dir) {
        eprintln!("[OpenPets] save_config: mkdir failed: {e}");
        return;
    }
    let path = dir.join(CONFIG_FILE_NAME);
    let tmp = dir.join(".config.tmp");
    let Ok(text) = serde_json::to_string_pretty(config) else { return };
    if let Err(e) = fs::write(&tmp, text) {
        eprintln!("[OpenPets] save_config: write failed: {e}");
        return;
    }
    if let Err(e) = fs::rename(&tmp, &path) {
        eprintln!("[OpenPets] save_config: rename failed: {e}");
    }
}

/// Lock the config, mutate via the closure, snapshot, release the lock,
/// then atomically write the snapshot to disk. Returning a snapshot before
/// writing means we never hold the mutex during file IO.
fn update_config<F: FnOnce(&mut OpenPetsConfig)>(state: &AppState, f: F) {
    let snapshot = {
        let Ok(mut cfg) = state.config.lock() else { return };
        f(&mut cfg);
        cfg.clone()
    };
    save_config(&snapshot);
}

fn on_window_moved(app: &AppHandle, pos: &PhysicalPosition<i32>) {
    let Some(state) = app.try_state::<AppState>() else { return };

    // Throttle: don't write more than ~4 times per second while dragging.
    {
        let Ok(mut last) = state.last_position_write.lock() else { return };
        let now = Instant::now();
        if let Some(t) = *last {
            if now.duration_since(t).as_millis() < 250 {
                return;
            }
        }
        *last = Some(now);
    }

    let scale = app
        .get_webview_window("main")
        .and_then(|w| w.scale_factor().ok())
        .unwrap_or(1.0);
    let x = pos.x as f64 / scale;
    let y = pos.y as f64 / scale;

    update_config(&state, |cfg| {
        cfg.window_position = Some(WindowPos { x, y });
    });
}

/// Sanity-check a saved window position against the window's current monitor.
/// If the user disconnected the monitor that held the pet, fall back to the
/// default placement instead of stranding the pet off-screen.
fn position_is_on_screen(window: &tauri::WebviewWindow, p: &WindowPos) -> bool {
    let Ok(Some(monitor)) = window.current_monitor() else {
        return false;
    };
    let phys = monitor.size();
    let scale = monitor.scale_factor();
    let logical_w = phys.width as f64 / scale;
    let logical_h = phys.height as f64 / scale;
    // Require at least a corner of the window to be inside the monitor.
    p.x > -192.0 && p.y > -208.0 && p.x < logical_w - 64.0 && p.y < logical_h - 64.0
}

fn show_picker_window(app: &AppHandle) -> tauri::Result<()> {
    if let Some(window) = app.get_webview_window("picker") {
        window.show()?;
        window.set_focus()?;
        return Ok(());
    }

    let window = WebviewWindowBuilder::new(
        app,
        "picker",
        WebviewUrl::App("picker.html".into()),
    )
    .title("Choose Pet")
    .inner_size(400.0, 240.0)
    .resizable(false)
    .decorations(false)
    .transparent(true)
    .always_on_top(true)
    .skip_taskbar(true)
    .shadow(false)
    .center()
    .build()?;

    pin_window_above_full_screen_apps(&window);

    // Auto-hide when the user clicks elsewhere (lost focus).
    let win = window.clone();
    window.on_window_event(move |event| {
        if let WindowEvent::Focused(false) = event {
            let _ = win.hide();
        }
    });

    Ok(())
}

// Pin the window to a level above full-screen apps and make it visible across
// every Space (regular desktops AND full-screen Spaces). Tauri's
// `set_visible_on_all_workspaces` only sets `canJoinAllSpaces`, which is not
// enough on macOS — we also need `fullScreenAuxiliary` and a higher window
// level than the default `NSFloatingWindowLevel` set by `alwaysOnTop`.
#[cfg(target_os = "macos")]
fn pin_window_above_full_screen_apps(window: &tauri::WebviewWindow) {
    use objc::runtime::{Class, Object, BOOL, NO};
    use objc::{class, msg_send, sel, sel_impl};

    // objc 0.2 doesn't bind the C runtime's object_setClass; declare it manually.
    extern "C" {
        fn object_setClass(obj: *mut Object, cls: *const Class) -> *const Class;
    }

    let ns_window_ptr = match window.ns_window() {
        Ok(ptr) => ptr,
        Err(e) => {
            eprintln!("[OpenPets] ns_window() failed: {e}");
            return;
        }
    };
    let ns_window = ns_window_ptr as *mut Object;

    // Promote the NSWindow to NSPanel. Plain NSWindow cannot overlay another
    // app's full-screen Space on macOS 13+, even with the right collection-
    // behavior flags and a screen-saver-level window level. NSPanel + the
    // NSWindowStyleMaskNonactivatingPanel style mask is the canonical recipe
    // (Bartender, Stickies, BetterDisplay, etc.).
    //
    // `object_setClass` swaps the live object's class. Since NSPanel is a
    // subclass of NSWindow, no fields move; the object simply gains NSPanel's
    // method dispatch.
    let panel_class: &Class = class!(NSPanel);
    unsafe { object_setClass(ns_window, panel_class as *const Class) };

    // NSWindowStyleMaskNonactivatingPanel = 1 << 7 = 128.
    // Keep whatever bits Tauri already set (transparent / borderless / etc.).
    let style_mask: u64 = unsafe { msg_send![ns_window, styleMask] };
    let new_style_mask = style_mask | 128;
    unsafe { let _: () = msg_send![ns_window, setStyleMask: new_style_mask]; }

    // canJoinAllSpaces (1) | stationary (16) | ignoresCycle (64) | fullScreenAuxiliary (256)
    const COLLECTION_BEHAVIOR: u64 = 1 | 16 | 64 | 256;
    // NSScreenSaverWindowLevel = 1000.
    const WINDOW_LEVEL: i64 = 1000;

    let prev_behavior: u64 = unsafe { msg_send![ns_window, collectionBehavior] };
    let prev_level: i64 = unsafe { msg_send![ns_window, level] };
    let prev_on_active_space: BOOL = unsafe { msg_send![ns_window, isOnActiveSpace] };
    eprintln!(
        "[OpenPets] before: behavior={prev_behavior} level={prev_level} \
         styleMask={style_mask} onActiveSpace={}",
        prev_on_active_space != NO
    );

    unsafe {
        let _: () = msg_send![ns_window, setCollectionBehavior: COLLECTION_BEHAVIOR];
        let _: () = msg_send![ns_window, setLevel: WINDOW_LEVEL];
    }

    let now_behavior: u64 = unsafe { msg_send![ns_window, collectionBehavior] };
    let now_level: i64 = unsafe { msg_send![ns_window, level] };
    let now_style_mask: u64 = unsafe { msg_send![ns_window, styleMask] };
    let now_on_active_space: BOOL = unsafe { msg_send![ns_window, isOnActiveSpace] };
    eprintln!(
        "[OpenPets] after:  behavior={now_behavior} level={now_level} \
         styleMask={now_style_mask} onActiveSpace={} (now NSPanel)",
        now_on_active_space != NO
    );
}

#[cfg(not(target_os = "macos"))]
fn pin_window_above_full_screen_apps(_window: &tauri::WebviewWindow) {}

#[tauri::command]
fn start_drag(window: tauri::WebviewWindow) -> Result<(), String> {
    eprintln!("[OpenPets] start_drag invoked");
    window.start_dragging().map_err(|e| e.to_string())
}

// External event source: any tool that wants to drive the pet's state writes
// JSON to ~/.openpets/state.json with shape:
//   {"state": "<one of the 9 Codex states>", "timestamp": 1700000000, "source": "claude-code"}
//
// We watch the directory (not the file directly), because hooks typically use
// `mv tmp state.json` for atomic writes — that breaks per-file FSEvents on
// macOS. Filtering events to the target path is fine.
const STATE_FILE_NAME: &str = "state.json";

fn state_dir() -> Option<PathBuf> {
    std::env::var("HOME")
        .ok()
        .map(|h| PathBuf::from(h).join(".openpets"))
}

fn ensure_state_dir() -> Option<PathBuf> {
    let dir = state_dir()?;
    if let Err(e) = fs::create_dir_all(&dir) {
        eprintln!("[OpenPets] mkdir {} failed: {e}", dir.display());
        return None;
    }
    let path = dir.join(STATE_FILE_NAME);
    if !path.exists() {
        let initial = r#"{"state":"idle","timestamp":0,"source":"openpets"}"#;
        if let Err(e) = fs::write(&path, initial) {
            eprintln!("[OpenPets] write initial state failed: {e}");
        }
    }
    Some(dir)
}

fn is_valid_state(name: &str) -> bool {
    matches!(
        name,
        "idle"
            | "running-right"
            | "running-left"
            | "waving"
            | "jumping"
            | "failed"
            | "waiting"
            | "running"
            | "review"
    )
}

fn handle_state_file_event(app: &AppHandle, path: &Path) {
    let Ok(text) = fs::read_to_string(path) else {
        return; // mid-write race; next event will catch up
    };
    let Ok(value) = serde_json::from_str::<serde_json::Value>(&text) else {
        return; // partial JSON during write
    };
    let Some(state_name) = value.get("state").and_then(|v| v.as_str()) else {
        return;
    };
    if !is_valid_state(state_name) {
        eprintln!(
            "[OpenPets] state.json: ignoring unknown state '{state_name}'"
        );
        return;
    }
    let source = value
        .get("source")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    eprintln!("[OpenPets] external state event: {state_name} (source={source})");
    if let Err(e) = app.emit("pet-state-changed", state_name) {
        eprintln!("[OpenPets] emit pet-state-changed failed: {e}");
    }
}

fn watch_state_file(app: AppHandle) {
    let Some(dir) = ensure_state_dir() else {
        return;
    };
    let target = dir.join(STATE_FILE_NAME);

    std::thread::spawn(move || {
        let (tx, rx) = mpsc::channel();
        let mut watcher = match RecommendedWatcher::new(tx, NotifyConfig::default()) {
            Ok(w) => w,
            Err(e) => {
                eprintln!("[OpenPets] failed to create file watcher: {e}");
                return;
            }
        };

        if let Err(e) = watcher.watch(&dir, RecursiveMode::NonRecursive) {
            eprintln!("[OpenPets] failed to watch {}: {e}", dir.display());
            return;
        }
        eprintln!("[OpenPets] watching {}", target.display());

        for received in rx {
            match received {
                Ok(ev) => {
                    let touched = ev.paths.iter().any(|p| p == &target);
                    let interesting = matches!(
                        ev.kind,
                        EventKind::Modify(_) | EventKind::Create(_)
                    );
                    if touched && interesting {
                        handle_state_file_event(&app, &target);
                    }
                }
                Err(e) => eprintln!("[OpenPets] watcher error: {e}"),
            }
        }
    });
}

#[tauri::command]
fn get_active_pet(state: State<AppState>) -> Option<Pet> {
    let id = state.config.lock().ok()?.active_pet_id.clone()?;
    list_pets().into_iter().find(|p| p.id == id)
}

#[tauri::command]
fn set_active_pet(id: String, app: AppHandle) -> Result<Pet, String> {
    let pet = list_pets()
        .into_iter()
        .find(|p| p.id == id)
        .ok_or_else(|| format!("pet '{id}' not found"))?;
    if let Some(state) = app.try_state::<AppState>() {
        update_config(&state, |cfg| cfg.active_pet_id = Some(pet.id.clone()));
    }
    app.emit("pet-changed", &pet).map_err(|e| e.to_string())?;
    Ok(pet)
}

fn main() {
    Builder::default()
        .manage(AppState::default())
        .setup(|app| {
            // Hydrate the in-memory config from disk (active pet, window
            // position). First-run users get a default, returning users
            // pick up where they left off.
            let loaded = load_config();
            if let Some(state) = app.try_state::<AppState>() {
                if let Ok(mut cfg) = state.config.lock() {
                    *cfg = loaded.clone();
                }
            }

            let pets = list_pets();
            setup_tray(app, &pets)?;

            if let Some(window) = app.get_webview_window("main") {
                pin_window_above_full_screen_apps(&window);

                // Reapply the pin on focus events. If macOS reverts the
                // collection behavior when the window crosses Spaces (some
                // versions do), this catches it.
                let pin_target = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::Focused(true) = event {
                        eprintln!("[OpenPets] focus event → reapplying pin");
                        pin_window_above_full_screen_apps(&pin_target);
                    }
                });

                // Persist window position when the user drags the pet around
                // (throttled to once per ~250ms so a continuous drag doesn't
                // pound the disk).
                let app_handle = app.handle().clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::Moved(pos) = event {
                        on_window_moved(&app_handle, pos);
                    }
                });

                // Position: previous session > bottom-right default.
                let restored = loaded
                    .window_position
                    .as_ref()
                    .filter(|p| position_is_on_screen(&window, p));
                if let Some(p) = restored {
                    let _ = window.set_position(LogicalPosition::new(p.x, p.y));
                } else if let Ok(Some(monitor)) = window.current_monitor() {
                    let phys = monitor.size();
                    let scale = monitor.scale_factor();
                    let logical_w = phys.width as f64 / scale;
                    let logical_h = phys.height as f64 / scale;
                    let x = (logical_w - 256.0 - 40.0).max(0.0);
                    let y = (logical_h - 256.0 - 100.0).max(0.0);
                    let _ = window.set_position(LogicalPosition::new(x, y));
                }
            }

            // Start the external-event watcher so Claude Code / Codex / Cursor
            // hooks can drive the pet's animation state via ~/.openpets/state.json.
            watch_state_file(app.handle().clone());

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            list_pets,
            get_active_pet,
            set_active_pet,
            start_drag,
        ])
        .run(tauri::generate_context!())
        .expect("failed to run OpenPets");
}
