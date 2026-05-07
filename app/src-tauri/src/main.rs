// Prevents additional console window on Windows in release; do nothing on macOS / Linux.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
// objc 0.2 macros emit deprecated cfg lints on modern rustc; harmless.
#![allow(unexpected_cfgs)]

use serde::Serialize;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
    AppHandle, Builder, Emitter, LogicalPosition, Manager, State, WebviewUrl,
    WebviewWindowBuilder, WindowEvent,
};

#[derive(Default)]
struct AppState {
    active_pet_id: Mutex<Option<String>>,
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
        if let Ok(mut g) = state.active_pet_id.lock() {
            *g = Some(pet.id.clone());
        }
    }
    if let Err(e) = app.emit("pet-changed", &pet) {
        eprintln!("[OpenPets] emit pet-changed failed: {e}");
    }
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

#[tauri::command]
fn get_active_pet(state: State<AppState>) -> Option<Pet> {
    let id = state.active_pet_id.lock().ok()?.clone()?;
    list_pets().into_iter().find(|p| p.id == id)
}

#[tauri::command]
fn set_active_pet(id: String, app: AppHandle) -> Result<Pet, String> {
    let pet = list_pets()
        .into_iter()
        .find(|p| p.id == id)
        .ok_or_else(|| format!("pet '{id}' not found"))?;
    if let Some(state) = app.try_state::<AppState>() {
        *state
            .active_pet_id
            .lock()
            .map_err(|e| e.to_string())? = Some(pet.id.clone());
    }
    app.emit("pet-changed", &pet).map_err(|e| e.to_string())?;
    Ok(pet)
}

fn main() {
    Builder::default()
        .manage(AppState::default())
        .setup(|app| {
            let pets = list_pets();
            setup_tray(app, &pets)?;

            if let Some(window) = app.get_webview_window("main") {
                pin_window_above_full_screen_apps(&window);

                // Reapply the pin on focus events. If macOS reverts the
                // collection behavior when the window crosses Spaces (some
                // versions do), this catches it.
                let win = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::Focused(true) = event {
                        eprintln!("[OpenPets] focus event → reapplying pin");
                        pin_window_above_full_screen_apps(&win);
                    }
                });

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
        .invoke_handler(tauri::generate_handler![
            list_pets,
            get_active_pet,
            set_active_pet,
            start_drag,
        ])
        .run(tauri::generate_context!())
        .expect("failed to run OpenPets");
}
