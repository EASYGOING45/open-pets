// Prevents additional console window on Windows in release; do nothing on macOS / Linux.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::fs;
use std::path::PathBuf;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Builder, LogicalPosition, Manager,
};

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

fn setup_tray(app: &tauri::App) -> tauri::Result<()> {
    let quit = MenuItem::with_id(app, "quit", "Quit OpenPets", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&quit])?;

    let icon = app
        .default_window_icon()
        .cloned()
        .ok_or_else(|| tauri::Error::AssetNotFound("default window icon missing".into()))?;

    TrayIconBuilder::new()
        .menu(&menu)
        .icon(icon)
        .on_menu_event(|app, event| {
            if event.id == "quit" {
                app.exit(0);
            }
        })
        .build(app)?;
    Ok(())
}

// Pin the window to a level above full-screen apps and make it visible across
// every Space (regular desktops AND full-screen Spaces). Tauri's
// `set_visible_on_all_workspaces` only sets `canJoinAllSpaces`, which is not
// enough on macOS — we also need `fullScreenAuxiliary` and a higher window
// level than the default `NSFloatingWindowLevel` set by `alwaysOnTop`.
#[cfg(target_os = "macos")]
fn pin_window_above_full_screen_apps(window: &tauri::WebviewWindow) {
    use objc::runtime::Object;
    use objc::{msg_send, sel, sel_impl};

    let Ok(ns_window_ptr) = window.ns_window() else {
        return;
    };
    let ns_window = ns_window_ptr as *mut Object;

    // NSWindowCollectionBehavior bitmask:
    //   NSWindowCollectionBehaviorCanJoinAllSpaces    = 1 << 0 = 1
    //   NSWindowCollectionBehaviorIgnoresCycle        = 1 << 6 = 64
    //   NSWindowCollectionBehaviorFullScreenAuxiliary = 1 << 8 = 256
    const COLLECTION_BEHAVIOR: u64 = 1 | 64 | 256;

    // NSStatusWindowLevel = 25. Higher than NSFloatingWindowLevel (3), low
    // enough to stay below screen-saver / system alerts.
    const WINDOW_LEVEL: i64 = 25;

    unsafe {
        let _: () = msg_send![ns_window, setCollectionBehavior: COLLECTION_BEHAVIOR];
        let _: () = msg_send![ns_window, setLevel: WINDOW_LEVEL];
    }
}

#[cfg(not(target_os = "macos"))]
fn pin_window_above_full_screen_apps(_window: &tauri::WebviewWindow) {}

fn main() {
    Builder::default()
        .setup(|app| {
            setup_tray(app)?;

            if let Some(window) = app.get_webview_window("main") {
                pin_window_above_full_screen_apps(&window);

                // Park the pet in the bottom-right of the primary screen so it
                // does not cover the user's working area on first launch.
                if let Ok(Some(monitor)) = window.current_monitor() {
                    let phys = monitor.size();
                    let scale = monitor.scale_factor();
                    let logical_w = phys.width as f64 / scale;
                    let logical_h = phys.height as f64 / scale;
                    let x = (logical_w - 256.0 - 40.0).max(0.0);
                    let y = (logical_h - 256.0 - 100.0).max(0.0);
                    let _ = window.set_position(LogicalPosition::new(x, y));
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![list_pets])
        .run(tauri::generate_context!())
        .expect("failed to run OpenPets");
}
