// Prevents additional console window on Windows in release; do nothing on macOS / Linux.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
// objc 0.2 macros emit deprecated cfg lints on modern rustc; harmless.
#![allow(unexpected_cfgs)]

use notify::{Config as NotifyConfig, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use rand::Rng;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::sync::Mutex;
use std::time::{Instant, SystemTime, UNIX_EPOCH};
use tauri::{
    menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem},
    tray::{TrayIcon, TrayIconBuilder},
    AppHandle, Builder, Emitter, LogicalPosition, LogicalSize, Manager, PhysicalPosition, State,
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
    #[serde(default)]
    attention_sound: bool,
    #[serde(default)]
    onboarding_done: bool,
    // Per-pet variant roll state. Populated lazily on first activation
    // of each pet (see roll_pet_variant_if_needed). Keyed by pet id.
    #[serde(default)]
    pet_state: HashMap<String, PetRollState>,
    // Per-pet usage counters (Phase B). Updated on every state-machine
    // event so Phase C evolution can evaluate condition expressions
    // (turns / days / time-of-day buckets / etc.) without retroactive
    // backfill. See docs/pet-evolution-variant-design.md §3 for the
    // schema's design rationale.
    #[serde(default)]
    pet_stats: HashMap<String, PetStats>,
}

#[derive(Serialize, Deserialize, Clone, Default)]
struct WindowPos {
    x: f64,
    y: f64,
}

// Persisted variant roll for a single pet. The roll is permanent for the
// lifetime of this pet identity — until the user explicitly Releases the
// pet, which clears this entry and lets the next activation re-roll.
#[derive(Serialize, Deserialize, Clone)]
struct PetRollState {
    variant_id: String,
    // Epoch milliseconds of the roll. Stored as integer to keep deps
    // light; format on the way out (e.g., for Petdex display) when needed.
    rolled_at_ms: u64,
    // False until JS has played the first-reveal celebration. Lets the
    // moment survive an app kill between roll and reveal.
    #[serde(default)]
    revealed: bool,
    // Future Phase C fields — pre-allocated to keep schema migrations
    // minimal once evolution lands.
    #[serde(default)]
    evolved_from: Option<String>,
    #[serde(default)]
    evolved_at_ms: Option<u64>,
}

// Variant info handed to the JS layer on pet load. Mirrors the pet.json
// schema's variants[] entry plus the resolved roll bookkeeping.
#[derive(Serialize, Clone)]
struct PetVariantInfo {
    variant_id: String,
    display_name: String,
    // Pass-through of the recipe object from pet.json (or null for normal).
    // JS compiles this to a CSS filter string at draw time.
    recipe: Option<serde_json::Value>,
    weight_pct: f32,
    effects: Vec<String>,
    revealed: bool,
}

// Per-pet usage counters. Schema documented in
// docs/pet-evolution-variant-design.md §3.1. Phase B writes them; Phase C
// evolution conditions read them.
#[derive(Serialize, Deserialize, Clone, Default)]
struct PetStats {
    // Lifecycle timestamps (epoch ms). first_seen is set once on initial
    // activation; last_active_ms updates on every state change.
    #[serde(default)]
    first_seen_ms: u64,
    #[serde(default)]
    last_active_ms: u64,
    // Distinct local-time YYYY-MM-DD seen for this pet. Each entry in the
    // bucket increments at most once per day.
    #[serde(default)]
    days_active: u32,
    // Most recent local-day key (YYYYMMDD as int) — sentinel for the
    // days_active bump check. Stored separately to avoid re-comparing
    // strings on the hot path.
    #[serde(default)]
    last_local_day_key: u32,

    // Counters
    #[serde(default)]
    total_turns: u64,
    #[serde(default)]
    total_clicks: u64,
    #[serde(default)]
    total_waves: u64,
    #[serde(default)]
    failures_seen: u64,
    #[serde(default)]
    attention_seen: u64,
    #[serde(default)]
    attention_responded: u64,

    // Per-bucket turn histogram (for time_of_day / weekday conditions).
    #[serde(default)]
    turn_buckets: TurnBuckets,

    // Time accounting (sampled by the Rust tick loop every ~5s).
    #[serde(default)]
    idle_seconds: u64,
    #[serde(default)]
    active_seconds: u64,

    // Phase C (evolution) bookkeeping — pre-allocated so the schema
    // doesn't need a second migration when Phase C lands.
    #[serde(default)]
    previous_form: Option<String>,
    #[serde(default)]
    pending_evolution_branch: Option<u32>,
}

#[derive(Serialize, Deserialize, Clone, Default)]
struct TurnBuckets {
    #[serde(default)]
    morning: u64,
    #[serde(default)]
    afternoon: u64,
    #[serde(default)]
    evening: u64,
    #[serde(default)]
    night: u64,
    #[serde(default)]
    weekday: u64,
    #[serde(default)]
    weekend: u64,
}

#[derive(Default)]
struct AppState {
    config: Mutex<OpenPetsConfig>,
    // Throttle window-position writes so dragging doesn't pound the disk.
    last_position_write: Mutex<Option<Instant>>,
    // Stored so the tray menu can be rebuilt after a connect/disconnect.
    tray_icon: Mutex<Option<TrayIcon>>,
    // Set to true while shake_window is wiggling the position, so the Moved
    // handler doesn't persist the transient offsets as the user's chosen spot.
    is_shaking: Mutex<bool>,
    // Set to true while the inline menu is expanding/collapsing the window —
    // growing 256→500 near the screen bottom makes AppKit shift the window
    // up, and we don't want that transient shift recorded as the user's spot.
    is_resizing: Mutex<bool>,
    // Last external state name we saw via state.json, so Phase B counters
    // can dedupe (e.g., total_turns shouldn't double-bump if the watcher
    // fires twice for the same atomic-mv write).
    last_external_state: Mutex<Option<String>>,
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

fn build_tray_menu<R: tauri::Runtime, M: Manager<R>>(
    manager: &M,
    pets: &[Pet],
) -> tauri::Result<Menu<R>> {
    let menu = Menu::new(manager)?;

    // One menu entry per installed pet — clicking switches the active pet.
    for pet in pets {
        let item = MenuItem::with_id(
            manager,
            format!("pet:{}", pet.id),
            &pet.display_name,
            true,
            None::<&str>,
        )?;
        menu.append(&item)?;
    }

    if !pets.is_empty() {
        menu.append(&PredefinedMenuItem::separator(manager)?)?;
    }

    let picker = MenuItem::with_id(manager, "picker", "Choose Pet…", true, None::<&str>)?;
    menu.append(&picker)?;

    menu.append(&PredefinedMenuItem::separator(manager)?)?;

    // One CheckMenuItem per supported tool — checked iff our hooks are
    // currently installed in that tool's settings.
    for tool in TOOLS {
        let label = format!("Connect to {}", tool.label);
        let item = CheckMenuItem::with_id(
            manager,
            format!("connect:{}", tool.id),
            label,
            true,
            is_connected_to(tool),
            None::<&str>,
        )?;
        menu.append(&item)?;
    }

    menu.append(&PredefinedMenuItem::separator(manager)?)?;

    let sound_on = manager
        .try_state::<AppState>()
        .and_then(|s| s.config.lock().ok().map(|c| c.attention_sound))
        .unwrap_or(false);
    let sound_item = CheckMenuItem::with_id(
        manager,
        "sound:attention",
        "Attention Sound",
        true,
        sound_on,
        None::<&str>,
    )?;
    menu.append(&sound_item)?;

    menu.append(&PredefinedMenuItem::separator(manager)?)?;

    let quit = MenuItem::with_id(manager, "quit", "Quit OpenPets", true, None::<&str>)?;
    menu.append(&quit)?;

    Ok(menu)
}

fn setup_tray(app: &tauri::App, pets: &[Pet]) -> tauri::Result<()> {
    let menu = build_tray_menu(app, pets)?;

    let icon = app
        .default_window_icon()
        .cloned()
        .ok_or_else(|| tauri::Error::AssetNotFound("default window icon missing".into()))?;

    let tray = TrayIconBuilder::new()
        .menu(&menu)
        .icon(icon)
        .on_menu_event(handle_tray_event)
        .build(app)?;

    if let Some(state) = app.try_state::<AppState>() {
        if let Ok(mut g) = state.tray_icon.lock() {
            *g = Some(tray);
        }
    }

    Ok(())
}

fn rebuild_tray_menu(app: &AppHandle) {
    let pets = list_pets();
    let menu = match build_tray_menu(app, &pets) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("[OpenPets] rebuild_tray_menu failed to build: {e}");
            return;
        }
    };
    if let Some(state) = app.try_state::<AppState>() {
        if let Ok(g) = state.tray_icon.lock() {
            if let Some(tray) = g.as_ref() {
                if let Err(e) = tray.set_menu(Some(menu)) {
                    eprintln!("[OpenPets] rebuild_tray_menu set_menu failed: {e}");
                }
            }
        }
    }
}

fn handle_tray_event(app: &AppHandle, event: tauri::menu::MenuEvent) {
    let id = event.id.as_ref();
    if id == "quit" {
        app.exit(0);
    } else if id == "picker" {
        if let Err(e) = show_picker_window(app) {
            eprintln!("[OpenPets] failed to open picker: {e}");
        }
    } else if id == "sound:attention" {
        if let Some(state) = app.try_state::<AppState>() {
            let now = !state
                .config
                .lock()
                .map(|c| c.attention_sound)
                .unwrap_or(false);
            update_config(&state, |cfg| cfg.attention_sound = now);
            let _ = app.emit("attention-sound-changed", now);
            eprintln!("[OpenPets] attention sound = {now}");
        }
        rebuild_tray_menu(app);
    } else if let Some(pet_id) = id.strip_prefix("pet:") {
        activate_pet(app, pet_id);
    } else if let Some(tool_id) = id.strip_prefix("connect:") {
        toggle_tool_connection(app, tool_id);
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

    // Suppress writes while the attention shake is wiggling the window —
    // those offsets aren't a user-chosen position.
    if state.is_shaking.lock().is_ok_and(|g| *g) {
        return;
    }
    // Same for menu expand/collapse: AppKit may shift the window vertically
    // when we grow it past the bottom of the screen, but the user's chosen
    // position is what they had before they right-clicked.
    if state.is_resizing.lock().is_ok_and(|g| *g) {
        return;
    }

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

// --- Tool connections (Claude Code, Codex, Cursor) -----------------------
//
// Connecting a tool to OpenPets means two things:
//   1. Make sure ~/.local/bin/openpets-event exists and is executable.
//   2. Idempotently merge our hook commands into the tool's settings file
//      (e.g. ~/.claude/settings.json).
//
// Disconnecting reverses (2) by removing exactly the entries we added,
// leaving any other hooks the user has configured untouched. We always
// take a backup at <settings>.bak.openpets before mutating.

const OPENPETS_EVENT_SCRIPT: &str = include_str!("../../scripts/openpets-event");

#[derive(Clone, Copy)]
struct HookDef {
    event: &'static str,
    command: &'static str,
    /// Claude Code hook matcher (e.g. "permission_prompt" for Notification,
    /// "Bash" for PreToolUse). `None` means match all.
    matcher: Option<&'static str>,
}

#[derive(Clone, Copy)]
struct ToolDef {
    id: &'static str,
    label: &'static str,
    /// Returns the absolute path of the tool's settings.json (or None on
    /// platforms where we can't determine it, e.g. missing $HOME).
    settings_path_fn: fn() -> Option<PathBuf>,
    /// (Claude Code event name, command line) pairs to inject as hooks.
    hooks: &'static [HookDef],
}

const CLAUDE_CODE_HOOKS: &[HookDef] = &[
    // --- Session lifecycle ---
    HookDef {
        event: "SessionStart",
        command: "openpets-event idle    claude-code",
        matcher: None,
    },
    HookDef {
        event: "SessionEnd",
        command: "openpets-event idle    claude-code",
        matcher: None,
    },
    // --- Turn lifecycle ---
    HookDef {
        event: "UserPromptSubmit",
        command: "openpets-event running claude-code",
        matcher: None,
    },
    HookDef {
        event: "Stop",
        command: "openpets-event waving  claude-code",
        matcher: None,
    },
    // --- Tool execution ---
    // PreToolUse: Claude is about to execute a tool.
    HookDef {
        event: "PreToolUse",
        command: "openpets-event running claude-code",
        matcher: None,
    },
    // PostToolUse fires ONLY on success (per Claude Code docs). Failure has
    // its own dedicated event below — no `auto` script needed.
    HookDef {
        event: "PostToolUse",
        command: "openpets-event running claude-code",
        matcher: None,
    },
    HookDef {
        event: "PostToolUseFailure",
        command: "openpets-event failed  claude-code",
        matcher: None,
    },
    // --- Subagents ---
    // Subagent finished, but the main session continues working.
    HookDef {
        event: "SubagentStop",
        command: "openpets-event running claude-code",
        matcher: None,
    },
    // --- Notifications (matcher pinpoints the exact type) ---
    // Permission dialog → user must approve/deny.
    HookDef {
        event: "Notification",
        command: "openpets-event review  claude-code",
        matcher: Some("permission_prompt"),
    },
    // Idle prompt → Claude is waiting for the user to return.
    HookDef {
        event: "Notification",
        command: "openpets-event waiting claude-code",
        matcher: Some("idle_prompt"),
    },
];

fn claude_code_settings_path() -> Option<PathBuf> {
    std::env::var("HOME")
        .ok()
        .map(|h| PathBuf::from(h).join(".claude").join("settings.json"))
}

const TOOLS: &[ToolDef] = &[ToolDef {
    id: "claude-code",
    label: "Claude Code",
    settings_path_fn: claude_code_settings_path,
    hooks: CLAUDE_CODE_HOOKS,
}];

fn ensure_helper_installed() -> Result<PathBuf, String> {
    let home = std::env::var("HOME").map_err(|e| e.to_string())?;
    let bin_dir = PathBuf::from(&home).join(".local").join("bin");
    fs::create_dir_all(&bin_dir).map_err(|e| e.to_string())?;
    let target = bin_dir.join("openpets-event");
    fs::write(&target, OPENPETS_EVENT_SCRIPT).map_err(|e| e.to_string())?;

    use std::os::unix::fs::PermissionsExt;
    let mut perms = fs::metadata(&target)
        .map_err(|e| e.to_string())?
        .permissions();
    perms.set_mode(0o755);
    fs::set_permissions(&target, perms).map_err(|e| e.to_string())?;
    Ok(target)
}

// True iff settings.json contains *any* hook command starting with
// "openpets-event ". We use a prefix match instead of exact-string matching
// so that when we ship a new version that changes a hook command (e.g.
// Notification: review → auto), returning users still register as
// "connected" and trigger the startup auto-migration that swaps the old
// command set for the new one. Otherwise the old `openpets-event review …`
// rows would silently linger in settings.json forever.
fn is_connected_to(tool: &ToolDef) -> bool {
    let Some(path) = (tool.settings_path_fn)() else {
        return false;
    };
    let Ok(text) = fs::read_to_string(&path) else {
        return false;
    };
    let Ok(value) = serde_json::from_str::<serde_json::Value>(&text) else {
        return false;
    };
    let Some(hooks) = value.get("hooks").and_then(|h| h.as_object()) else {
        return false;
    };

    hooks.values().any(|event_arr| {
        event_arr.as_array().is_some_and(|arr| {
            arr.iter().any(|block| {
                block
                    .get("hooks")
                    .and_then(|h| h.as_array())
                    .is_some_and(|inner| {
                        inner.iter().any(|h| {
                            h.get("command")
                                .and_then(|c| c.as_str())
                                .is_some_and(|s| {
                                    s.trim_start().starts_with("openpets-event ")
                                })
                        })
                    })
            })
        })
    })
}

fn connect_tool(tool: &ToolDef) -> Result<(), String> {
    ensure_helper_installed()?;

    let Some(path) = (tool.settings_path_fn)() else {
        return Err(format!("unknown tool: {}", tool.id));
    };

    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    let mut value = if path.exists() {
        // Backup the original before mutating (overwrites any prior backup).
        let backup = path.with_extension("json.bak.openpets");
        let _ = fs::copy(&path, &backup);

        let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
        if text.trim().is_empty() {
            serde_json::json!({})
        } else {
            serde_json::from_str::<serde_json::Value>(&text).map_err(|e| e.to_string())?
        }
    } else {
        serde_json::json!({})
    };

    {
        let obj = value
            .as_object_mut()
            .ok_or_else(|| "settings.json root is not an object".to_string())?;
        let hooks_entry = obj.entry("hooks").or_insert_with(|| serde_json::json!({}));
        let hooks_obj = hooks_entry
            .as_object_mut()
            .ok_or_else(|| "settings.json `hooks` is not an object".to_string())?;

        for hook in tool.hooks {
            let event_arr = hooks_obj
                .entry(hook.event.to_string())
                .or_insert_with(|| serde_json::json!([]));
            let arr = event_arr.as_array_mut().ok_or_else(|| {
                format!("settings.json hooks.{} is not an array", hook.event)
            })?;

            // Dedup: same command AND same matcher → already installed.
            let already = arr.iter().any(|block| {
                let cmd_match = block
                    .get("hooks")
                    .and_then(|h| h.as_array())
                    .is_some_and(|inner| {
                        inner.iter().any(|h| {
                            h.get("command").and_then(|c| c.as_str()) == Some(hook.command)
                        })
                    });
                let matcher_match = match (hook.matcher, block.get("matcher").and_then(|m| m.as_str())) {
                    (None, None) => true,
                    (Some(a), Some(b)) => a == b,
                    _ => false,
                };
                cmd_match && matcher_match
            });
            if already {
                continue;
            }

            let mut block = serde_json::json!({
                "hooks": [{ "type": "command", "command": hook.command }]
            });
            if let Some(m) = hook.matcher {
                block["matcher"] = serde_json::json!(m);
            }
            arr.push(block);
        }
    }

    let pretty = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
    let tmp = path.with_extension("json.tmp.openpets");
    fs::write(&tmp, &pretty).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &path).map_err(|e| e.to_string())?;
    Ok(())
}

fn disconnect_tool(tool: &ToolDef) -> Result<(), String> {
    let Some(path) = (tool.settings_path_fn)() else {
        return Err(format!("unknown tool: {}", tool.id));
    };
    if !path.exists() {
        return Ok(());
    }

    let backup = path.with_extension("json.bak.openpets");
    let _ = fs::copy(&path, &backup);

    let text = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let mut value =
        serde_json::from_str::<serde_json::Value>(&text).map_err(|e| e.to_string())?;

    {
        let Some(hooks_obj) = value
            .as_object_mut()
            .and_then(|o| o.get_mut("hooks"))
            .and_then(|h| h.as_object_mut())
        else {
            return Ok(());
        };

        // Sweep every hook event (not just the ones in tool.hooks) and remove
        // any block whose command starts with "openpets-event ". This is a
        // prefix match instead of exact match so that when we change a hook
        // command between versions (e.g. Notification: review → auto), the
        // old row gets cleaned up too — otherwise users end up with both
        // entries and the pet receives double events.
        for (_event, value) in hooks_obj.iter_mut() {
            if let Some(arr) = value.as_array_mut() {
                arr.retain(|block| {
                    let inner = block.get("hooks").and_then(|h| h.as_array());
                    let has_our = inner.is_some_and(|inner_arr| {
                        inner_arr.iter().any(|h| {
                            h.get("command")
                                .and_then(|c| c.as_str())
                                .is_some_and(|s| {
                                    s.trim_start().starts_with("openpets-event ")
                                })
                        })
                    });
                    !has_our
                });
            }
        }
        // Drop event entries we emptied.
        hooks_obj.retain(|_, v| !v.as_array().is_some_and(|a| a.is_empty()));
    }

    // If hooks ended up empty, drop the key entirely.
    if let Some(obj) = value.as_object_mut() {
        let hooks_empty = obj
            .get("hooks")
            .and_then(|h| h.as_object())
            .is_some_and(|o| o.is_empty());
        if hooks_empty {
            obj.remove("hooks");
        }
    }

    let pretty = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
    let tmp = path.with_extension("json.tmp.openpets");
    fs::write(&tmp, &pretty).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &path).map_err(|e| e.to_string())?;
    Ok(())
}

fn toggle_tool_connection(app: &AppHandle, tool_id: &str) {
    let Some(tool) = TOOLS.iter().find(|t| t.id == tool_id) else {
        eprintln!("[OpenPets] unknown tool: {tool_id}");
        return;
    };
    let was_connected = is_connected_to(tool);
    let result = if was_connected {
        disconnect_tool(tool)
    } else {
        connect_tool(tool)
    };

    match result {
        Ok(()) => {
            let action = if was_connected {
                "disconnected from"
            } else {
                "connected to"
            };
            eprintln!("[OpenPets] {action} {}", tool.label);
            rebuild_tray_menu(app);
        }
        Err(e) => {
            eprintln!(
                "[OpenPets] toggle_tool_connection({}): {e}",
                tool.id
            );
        }
    }
}

#[tauri::command]
fn list_tool_connections() -> Vec<(String, String, bool)> {
    TOOLS
        .iter()
        .map(|t| (t.id.to_string(), t.label.to_string(), is_connected_to(t)))
        .collect()
}

#[tauri::command]
fn set_tool_connection(app: AppHandle, id: String, connected: bool) -> Result<(), String> {
    let tool = TOOLS
        .iter()
        .find(|t| t.id == id)
        .ok_or_else(|| format!("unknown tool: {id}"))?;
    let currently = is_connected_to(tool);
    if connected == currently {
        return Ok(());
    }
    if connected {
        connect_tool(tool)?;
    } else {
        disconnect_tool(tool)?;
    }
    rebuild_tray_menu(&app);
    Ok(())
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

// Briefly wiggle the pet window horizontally to grab the user's attention
// when Claude Code is waiting for them (review / waiting state). The Moved
// handler is told to ignore these offsets via the is_shaking flag so the
// transient wiggle isn't persisted as the user's chosen position.
#[tauri::command]
fn shake_window(window: tauri::WebviewWindow, state: State<AppState>) -> Result<(), String> {
    let origin = window.outer_position().map_err(|e| e.to_string())?;

    if let Ok(mut g) = state.is_shaking.lock() {
        if *g {
            // A shake is already in progress — don't stack them.
            return Ok(());
        }
        *g = true;
    }

    let win = window.clone();
    let app = window.app_handle().clone();
    std::thread::spawn(move || {
        // Symmetric, decaying horizontal offsets — feels like a head shake.
        let offsets: [i32; 9] = [8, -8, 6, -6, 4, -4, 2, -2, 0];
        for off in offsets {
            let _ = win.set_position(PhysicalPosition::new(origin.x + off, origin.y));
            std::thread::sleep(std::time::Duration::from_millis(35));
        }
        // Ensure we land exactly at the original position even if the OS
        // coalesced the last move.
        let _ = win.set_position(PhysicalPosition::new(origin.x, origin.y));

        if let Some(s) = app.try_state::<AppState>() {
            if let Ok(mut g) = s.is_shaking.lock() {
                *g = false;
            }
        }
    });

    Ok(())
}

// Right-click on the pet pops a custom HTML menu rendered in its own
// Tauri WebviewWindow. We don't use AppKit's NSMenu (via popup_menu)
// because NSMenu's internal popup window doesn't inherit the
// fullScreenAuxiliary collection-behavior + screen-saver level that we
// apply to the pet panel — so on a full-screen Space the menu would
// pop into the regular desktop and be invisible. The HTML menu uses the
// same pin_window_above_full_screen_apps recipe as the pet, so it shows
// over any full-screen app exactly like the pet does.
#[tauri::command]
fn show_context_menu(app: AppHandle, x: f64, y: f64) -> Result<(), String> {
    eprintln!("[OpenPets] show_context_menu at screen ({x}, {y})");
    open_ctxmenu_window(&app, x, y).map_err(|e| e.to_string())
}

#[tauri::command]
fn quit_app(app: AppHandle) {
    app.exit(0);
}

// JS calls this around setSize when opening/closing the inline menu so the
// transient position shifts AppKit may apply (when the resized window
// overlaps the dock or the bottom of the screen) don't get persisted as
// the user's chosen pet position.
#[tauri::command]
fn set_menu_resizing(state: State<AppState>, resizing: bool) {
    if let Ok(mut g) = state.is_resizing.lock() {
        *g = resizing;
    }
}

#[tauri::command]
fn show_picker_window_cmd(app: AppHandle) -> Result<(), String> {
    show_picker_window(&app).map_err(|e| e.to_string())
}

// Called by ctxmenu.js after the menu items render so we can shrink the
// window to fit. We start with a generous default size; this trims the
// transparent padding so the menu shadow doesn't bleed onto adjacent
// content.
#[tauri::command]
fn resize_ctxmenu(app: AppHandle, width: f64, height: f64) -> Result<(), String> {
    let Some(w) = app.get_webview_window("ctxmenu") else {
        return Ok(());
    };
    w.set_size(LogicalSize::new(width, height))
        .map_err(|e| e.to_string())
}

fn open_ctxmenu_window(app: &AppHandle, x: f64, y: f64) -> tauri::Result<()> {
    // Always close any existing menu window so a fresh right-click
    // re-fetches state (active pet, sound toggle, connection state) and
    // pops at the new cursor position.
    if let Some(existing) = app.get_webview_window("ctxmenu") {
        let _ = existing.close();
    }

    let window = WebviewWindowBuilder::new(
        app,
        "ctxmenu",
        WebviewUrl::App("ctxmenu.html".into()),
    )
    .title("OpenPets Menu")
    // Generous initial size — ctxmenu.js calls resize_ctxmenu after it
    // renders to shrink to fit the actual content.
    .inner_size(240.0, 360.0)
    .resizable(false)
    .decorations(false)
    .transparent(true)
    .always_on_top(true)
    .skip_taskbar(true)
    .shadow(false)
    .build()?;

    // Position at the cursor in *logical* (CSS) pixels, matching the
    // event.screenX/Y coords JS hands us.
    let _ = window.set_position(LogicalPosition::new(x, y));

    // KNOWN LIMITATION: we deliberately do NOT call
    // pin_window_above_full_screen_apps on ctxmenu. On macOS 26+,
    // running the NSPanel class-swap on a freshly-built transparent
    // WKWebView panel that was created mid-event-loop reliably aborts
    // the app via NSException ("Rust cannot catch foreign exceptions").
    // Deferring the pin (tested up to 120ms) does not help. Pet and
    // picker survive the same recipe only because they're built during
    // app setup, before the run loop processes user events.
    //
    // Trade-off: in a full-screen Space owned by another app, the pet
    // is still visible (its panel is pinned at startup) but the right-
    // click menu opens on the regular desktop instead of the active
    // full-screen Space, so it appears not to show. Workaround for
    // those users: use the menu-bar tray icon (always available) or
    // exit the full-screen app. Tracked as a follow-up — see
    // docs/progress.md.
    let close_target = window.clone();
    window.on_window_event(move |event| {
        if let WindowEvent::Focused(false) = event {
            let _ = close_target.close();
        }
    });

    Ok(())
}

#[tauri::command]
fn get_attention_sound(state: State<AppState>) -> bool {
    state.config.lock().map(|c| c.attention_sound).unwrap_or(false)
}

#[tauri::command]
fn get_onboarding_done(state: State<AppState>) -> bool {
    state
        .config
        .lock()
        .map(|c| c.onboarding_done)
        .unwrap_or(false)
}

#[tauri::command]
fn set_onboarding_done(state: State<AppState>, done: bool) {
    update_config(&state, |cfg| cfg.onboarding_done = done);
}

#[tauri::command]
fn set_attention_sound(app: AppHandle, enabled: bool) -> Result<(), String> {
    if let Some(state) = app.try_state::<AppState>() {
        update_config(&state, |cfg| cfg.attention_sound = enabled);
    }
    rebuild_tray_menu(&app);
    let _ = app.emit("attention-sound-changed", enabled);
    Ok(())
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

    // Phase B counter bump for the active pet — done before the JS emit so a
    // crash in the JS path doesn't lose the counter increment.
    if let Some(state) = app.try_state::<AppState>() {
        let active_pet_id = state.config.lock().ok().and_then(|c| c.active_pet_id.clone());
        let prev = state
            .last_external_state
            .lock()
            .ok()
            .and_then(|m| m.clone());
        if let Some(pet_id) = active_pet_id {
            record_state_event(&state, &pet_id, state_name, prev.as_deref());
        }
        if let Ok(mut last) = state.last_external_state.lock() {
            *last = Some(state_name.to_string());
        }
    }

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
        // Roll the variant *before* persisting active_pet_id so the JS
        // pet-changed listener can immediately fetch the variant on load.
        // Roll is idempotent — only fires the first time this pet is seen.
        roll_pet_variant_if_needed(&state, &pet.id);
        // Phase B: ensure pet_stats entry exists with first_seen_ms set.
        // The closure is empty — bump_pet_stats already lazily initializes
        // first_seen and days_active in its wrapper.
        bump_pet_stats(&state, &pet.id, |_| {});
        update_config(&state, |cfg| cfg.active_pet_id = Some(pet.id.clone()));
    }
    app.emit("pet-changed", &pet).map_err(|e| e.to_string())?;
    Ok(pet)
}

// --- Variant system (Phase A) ---------------------------------------------

// Read the variants[] array from a pet's pet.json. Empty vec = pet has no
// variants declared, in which case the pet behaves as if it has a single
// implicit "normal" variant (no recipe, no celebration).
fn load_pet_variants(pet_id: &str) -> Vec<serde_json::Value> {
    let Some(dir) = pet_dir() else {
        return vec![];
    };
    let manifest = dir.join(pet_id).join("pet.json");
    let Ok(text) = fs::read_to_string(&manifest) else {
        return vec![];
    };
    let Ok(json) = serde_json::from_str::<serde_json::Value>(&text) else {
        return vec![];
    };
    json.get("variants")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
}

fn variant_total_weight(variants: &[serde_json::Value]) -> u32 {
    variants
        .iter()
        .filter_map(|v| v.get("weight").and_then(|w| w.as_u64()))
        .map(|w| w as u32)
        .sum()
}

// Weighted random pick. Returns the chosen variant's id string. None only if
// the variants list is empty or every weight is 0/missing — both invalid
// configs that the caller treats as "no roll needed".
fn roll_variant_id(variants: &[serde_json::Value]) -> Option<String> {
    let total = variant_total_weight(variants);
    if total == 0 {
        return None;
    }
    let mut r: u32 = rand::thread_rng().gen_range(0..total);
    for v in variants {
        let weight = v.get("weight").and_then(|w| w.as_u64()).unwrap_or(0) as u32;
        if r < weight {
            return v.get("id").and_then(|id| id.as_str()).map(String::from);
        }
        r -= weight;
    }
    None
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

// Roll the variant for `pet_id` if and only if config has no entry for it
// yet. Idempotent: subsequent activations of the same pet are no-ops.
fn roll_pet_variant_if_needed(state: &AppState, pet_id: &str) {
    let already_rolled = state
        .config
        .lock()
        .ok()
        .map(|c| c.pet_state.contains_key(pet_id))
        .unwrap_or(false);
    if already_rolled {
        return;
    }
    let variants = load_pet_variants(pet_id);
    let Some(variant_id) = roll_variant_id(&variants) else {
        return;
    };
    update_config(state, |cfg| {
        cfg.pet_state.insert(
            pet_id.to_string(),
            PetRollState {
                variant_id,
                rolled_at_ms: now_ms(),
                revealed: false,
                evolved_from: None,
                evolved_at_ms: None,
            },
        );
    });
}

// Resolve a variant id back to its full info (recipe, displayName, effects)
// from the pet's pet.json. Returns None if the pet's variants array no
// longer contains this id (e.g., author renamed it after the user rolled).
// In that fallback case the JS side treats the pet as un-styled (normal).
fn resolve_variant_info(pet_id: &str, variant_id: &str, revealed: bool) -> Option<PetVariantInfo> {
    let variants = load_pet_variants(pet_id);
    let total = variant_total_weight(&variants);
    let total_f = if total == 0 { 1 } else { total } as f32;
    let v = variants
        .iter()
        .find(|v| v.get("id").and_then(|x| x.as_str()) == Some(variant_id))?;
    let weight = v.get("weight").and_then(|w| w.as_u64()).unwrap_or(0) as f32;
    let display_name = v
        .get("displayName")
        .and_then(|n| {
            // Prefer zh; fall back to en; then to id.
            if let Some(s) = n.as_str() {
                Some(s.to_string())
            } else {
                let zh = n.get("zh").and_then(|s| s.as_str()).map(String::from);
                let en = n.get("en").and_then(|s| s.as_str()).map(String::from);
                zh.or(en)
            }
        })
        .unwrap_or_else(|| variant_id.to_string());
    let recipe = v.get("recipe").cloned();
    let recipe = match recipe {
        Some(serde_json::Value::Object(map)) if !map.is_empty() => {
            Some(serde_json::Value::Object(map))
        }
        _ => None,
    };
    let effects = v
        .get("effects")
        .and_then(|e| e.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|x| x.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();
    Some(PetVariantInfo {
        variant_id: variant_id.to_string(),
        display_name,
        recipe,
        weight_pct: weight / total_f,
        effects,
        revealed,
    })
}

#[tauri::command]
fn get_pet_variant(pet_id: String, state: State<AppState>) -> Option<PetVariantInfo> {
    let (variant_id, revealed) = {
        let cfg = state.config.lock().ok()?;
        let s = cfg.pet_state.get(&pet_id)?;
        (s.variant_id.clone(), s.revealed)
    };
    resolve_variant_info(&pet_id, &variant_id, revealed)
}

#[tauri::command]
fn mark_variant_revealed(pet_id: String, app: AppHandle) -> Result<(), String> {
    if let Some(state) = app.try_state::<AppState>() {
        update_config(&state, |cfg| {
            if let Some(s) = cfg.pet_state.get_mut(&pet_id) {
                s.revealed = true;
            }
        });
    }
    Ok(())
}

#[tauri::command]
fn release_pet(pet_id: String, app: AppHandle) -> Result<(), String> {
    if let Some(state) = app.try_state::<AppState>() {
        update_config(&state, |cfg| {
            cfg.pet_state.remove(&pet_id);
            cfg.pet_stats.remove(&pet_id);
        });
    }
    // If the released pet is the active one, re-roll on next activation by
    // re-emitting pet-changed so the frontend re-fetches everything.
    let is_active = app
        .try_state::<AppState>()
        .and_then(|s| s.config.lock().ok().and_then(|c| c.active_pet_id.clone()))
        .map(|id| id == pet_id)
        .unwrap_or(false);
    if is_active {
        // Roll again immediately — the user expects the new state on
        // confirm-click, not "next time you switch pets".
        if let Some(state) = app.try_state::<AppState>() {
            roll_pet_variant_if_needed(&state, &pet_id);
        }
        if let Some(pet) = list_pets().into_iter().find(|p| p.id == pet_id) {
            app.emit("pet-changed", &pet).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

// --- Stats tracking (Phase B) ---------------------------------------------
//
// Local-time helpers. We deliberately avoid a chrono/time crate dep — they
// significantly slowed Tauri macro re-expansion on this project. Instead
// we shell out to `/bin/date`, which is universally present on macOS and
// Linux and handles TZ + DST correctly via the OS. Cost: ~1ms per call,
// fired only on state events (a few per second tops).

fn date_field(epoch_ms: u64, fmt: &str) -> Option<String> {
    use std::process::Command;
    let secs = (epoch_ms / 1000) as i64;
    // BSD date (macOS) uses `-r <epoch>`; GNU date uses `-d @<epoch>`.
    // Try BSD first, fall back to GNU.
    let out = Command::new("date")
        .args(["-r", &secs.to_string(), fmt])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .or_else(|| {
            Command::new("date")
                .args(["-d", &format!("@{secs}"), fmt])
                .output()
                .ok()
        })?;
    let s = String::from_utf8(out.stdout).ok()?;
    Some(s.trim().to_string())
}

fn local_hour(epoch_ms: u64) -> u8 {
    date_field(epoch_ms, "+%H")
        .and_then(|s| s.parse::<u8>().ok())
        .unwrap_or(12)
}

fn local_day_key(epoch_ms: u64) -> u32 {
    date_field(epoch_ms, "+%Y%m%d")
        .and_then(|s| s.parse::<u32>().ok())
        .unwrap_or(0)
}

fn is_weekday(epoch_ms: u64) -> bool {
    // %u prints day of week 1–7 with Monday = 1.
    date_field(epoch_ms, "+%u")
        .and_then(|s| s.parse::<u8>().ok())
        .map(|n| n <= 5)
        .unwrap_or(true)
}

// Time-of-day bucket for an epoch_ms in the user's local time. Boundaries
// match docs/pet-evolution-variant-design.md §2.3 — morning 06–11,
// afternoon 12–17, evening 18–22, night 23–05.
fn classify_time_of_day(epoch_ms: u64) -> &'static str {
    let hour = local_hour(epoch_ms);
    match hour {
        6..=11 => "morning",
        12..=17 => "afternoon",
        18..=22 => "evening",
        _ => "night",
    }
}

// Mutate the pet_stats[pet_id] entry, lazily creating it if missing.
// Mirrors the update_config(state, |cfg| ...) pattern.
fn bump_pet_stats<F: FnOnce(&mut PetStats)>(state: &AppState, pet_id: &str, f: F) {
    update_config(state, |cfg| {
        let stats = cfg
            .pet_stats
            .entry(pet_id.to_string())
            .or_insert_with(PetStats::default);
        let now = now_ms();
        if stats.first_seen_ms == 0 {
            stats.first_seen_ms = now;
        }
        let day = local_day_key(now);
        if day != 0 && day != stats.last_local_day_key {
            stats.last_local_day_key = day;
            stats.days_active += 1;
        }
        stats.last_active_ms = now;
        f(stats);
    });
}

// Called from handle_state_file_event whenever the external state changes.
// Increments the right counter for each meaningful state entry.
fn record_state_event(state: &AppState, pet_id: &str, new_state: &str, prev_state: Option<&str>) {
    bump_pet_stats(state, pet_id, |stats| {
        match new_state {
            "running" if prev_state != Some("running") => {
                stats.total_turns += 1;
                let now = stats.last_active_ms;
                let bucket = classify_time_of_day(now);
                match bucket {
                    "morning" => stats.turn_buckets.morning += 1,
                    "afternoon" => stats.turn_buckets.afternoon += 1,
                    "evening" => stats.turn_buckets.evening += 1,
                    _ => stats.turn_buckets.night += 1,
                }
                if is_weekday(now) {
                    stats.turn_buckets.weekday += 1;
                } else {
                    stats.turn_buckets.weekend += 1;
                }
            }
            "waving" if prev_state != Some("waving") => {
                stats.total_waves += 1;
            }
            "failed" if prev_state != Some("failed") => {
                stats.failures_seen += 1;
            }
            "review" | "waiting" if prev_state != Some(new_state) => {
                stats.attention_seen += 1;
            }
            _ => {}
        }
    });
}

// JS-side calls: clicks are batched in JS (every 30s + on blur) so we
// don't IPC per-click; attention_responded fires when the user dismisses
// an attention prompt within the responsive window (also JS-detected).
#[tauri::command]
fn record_clicks(pet_id: String, count: u32, app: AppHandle) {
    if count == 0 {
        return;
    }
    if let Some(state) = app.try_state::<AppState>() {
        bump_pet_stats(&state, &pet_id, |stats| {
            stats.total_clicks += count as u64;
        });
    }
}

#[tauri::command]
fn record_attention_responded(pet_id: String, app: AppHandle) {
    if let Some(state) = app.try_state::<AppState>() {
        bump_pet_stats(&state, &pet_id, |stats| {
            stats.attention_responded += 1;
        });
    }
}

// Dev helper for the Phase C work — JS / tests can read the current
// counters without going through file I/O.
#[tauri::command]
fn get_pet_stats(pet_id: String, state: State<AppState>) -> Option<PetStats> {
    state.config.lock().ok()?.pet_stats.get(&pet_id).cloned()
}

// Build tag — touch this string to force cargo to recompile main.rs and
// re-embed the latest frontend assets (the tauri::generate_context! macro
// re-evaluates per compile). Frontend-only edits don't trigger a rebuild
// otherwise, so a stale binary serves stale HTML/JS.
const BUILD_TAG: &str = "openpets-2026-05-14-variants-phaseAB";

fn main() {
    eprintln!("[OpenPets] build: {BUILD_TAG}");
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

            // Auto-migrate connected users: disconnect (prefix-matches all
            // openpets-event rows, including legacy hook commands like
            // `openpets-event review claude-code`) and then re-connect with
            // the current canonical hook set. Idempotent for users already
            // on the latest version, and the path that swaps a renamed hook
            // command for users coming from an older version.
            for tool in TOOLS {
                if is_connected_to(tool) {
                    if let Err(e) = disconnect_tool(tool).and_then(|_| connect_tool(tool)) {
                        eprintln!("[OpenPets] hook migration for {}: {e}", tool.label);
                    }
                }
            }

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
            shake_window,
            show_context_menu,
            quit_app,
            show_picker_window_cmd,
            resize_ctxmenu,
            set_menu_resizing,
            get_attention_sound,
            set_attention_sound,
            get_onboarding_done,
            set_onboarding_done,
            list_tool_connections,
            set_tool_connection,
            get_pet_variant,
            mark_variant_revealed,
            release_pet,
            record_clicks,
            record_attention_responded,
            get_pet_stats,
        ])
        .run(tauri::generate_context!())
        .expect("failed to run OpenPets");
}
