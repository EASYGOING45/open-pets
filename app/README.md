# OpenPets desktop renderer (Phase 1)

A lightweight Tauri 2 desktop app that animates any Codex-format pet atlas
on your screen — independent of Codex CLI.

> ✅ **Status**: Phase 1 working. Pet renders in a transparent always-on-top
> window, **stays visible across every Space including other apps' full-screen
> Spaces**, can be dragged with the mouse, and clicks trigger the wave
> animation. macOS-first; Windows / Linux planned once the macOS path is
> battle-tested.

## What it does today

- Reads pet packages from `~/.codex/pets/*/` (same layout the Codex CLI uses)
- Renders the 192×208 sprite cells from the WebP atlas in a transparent,
  always-on-top, undecorated window
- Plays the canonical 9-state animation cycle (idle / running-right /
  running-left / waving / jumping / failed / waiting / running / review)
  defined by the [open-pet-creator Skill](../open-pet-creator/SKILL.md)
- **Floats over full-screen apps** (Safari fullscreen, Final Cut, Xcode
  fullscreen, etc.) and follows the user across Mission Control Spaces
- **Drag the pet** to move it; **click** (without drag) to play the wave
  animation
- **Pick which pet shows** via the tray menu (one menu item per installed
  pet) or a visual picker panel: tray menu → *Choose Pet…* opens a
  frosted-glass 400×240 grid of thumbnails, click one to switch. Esc
  or clicking elsewhere dismisses the picker.
- **External event source** — a file watcher on `~/.openpets/state.json`
  lets Claude Code / Codex / Cursor / any shell-driveable tool drive the
  pet's animation in real time (see "Drive the pet from your AI agent"
  below)
- Tray icon menu → `Quit`

## Roadmap (Phase 2)

- ~~External event source — let Codex / Claude Code / Cursor drive pet
  states.~~ ✅ Done — see "Drive the pet from your AI agent" below
- ~~`openpets connect <tool>` CLI — automate the manual hook install.~~
  ✅ Done as a tray-menu CheckMenuItem (no JSON pasting needed). Tauri
  commands `list_tool_connections` / `set_tool_connection` are exposed
  for future in-picker UI or external CLI.
- ~~Persist active-pet selection across launches.~~ ✅ Done via
  `~/.openpets/config.json`.
- ~~Drag-to-position memory across launches.~~ ✅ Done via the same
  config file (throttled to ~4 saves/sec while dragging).
- Codex CLI / Cursor connectors — same pattern, just need their hook
  formats and settings paths
- Per-source / per-tool reactions (e.g., Bash failures → `failed`)
- Click-through on transparent pixels (so the window doesn't intercept
  clicks on its empty edges; needs sprite-bbox hit-testing)
- Multi-pet support (multiple pets visible simultaneously), drag-to-position
  memory across launches, settings panel
- Persist active-pet selection across launches (currently always defaults
  to the first pet alphabetically on cold start)
- Cross-platform parity (Linux / Windows)

## Drive the pet from your AI agent

OpenPets watches `~/.openpets/state.json`. Anything that writes a JSON
document like

```json
{ "state": "running", "timestamp": 1715000000, "source": "claude-code" }
```

into that file will instantly drive the pet's animation. Valid `state`
values are the nine canonical Codex states: `idle`, `running-right`,
`running-left`, `waving`, `jumping`, `failed`, `waiting`, `running`,
`review`. Anything else is ignored with a log line.

### Quick test

With `npm run dev` running, in another terminal:

```bash
./scripts/openpets-event running
./scripts/openpets-event review
./scripts/openpets-event waving      # one-shot, returns to idle automatically
./scripts/openpets-event idle
```

You should see the pet's animation switch in real time. Each call also
logs an `[OpenPets] external state event:` line in the dev terminal.

### Connect Claude Code (one-click)

**Tray menu → ☐ Connect to Claude Code** — clicking it does all of this
in one step:

1. Writes the embedded `openpets-event` helper to `~/.local/bin/` and
   marks it executable.
2. Reads `~/.claude/settings.json` (creating it if absent), takes a
   backup at `settings.json.bak.openpets`, and merges the five hook
   commands into the appropriate event arrays. The merge is idempotent
   — clicking the menu item again to disconnect removes exactly the
   entries OpenPets added, leaving any other hooks you have untouched.
3. The tray menu's checkmark flips to ✓ to reflect the new state.

Restart Claude Code (or open a new session) and the pet now reacts to
your conversation:

| Claude Code event | Pet state |
| --- | --- |
| Session starts | `idle` (resting) |
| You submit a prompt | `running` (Claude is working) |
| Claude needs your attention (permission prompt, idle wait) | `review` |
| Claude finishes a turn | `waving` → returns to `idle` |
| Session ends | `idle` |

The same checkbox toggle is also exposed as the Tauri commands
`list_tool_connections` and `set_tool_connection`, so a future
in-picker UI / external CLI can drive it without going through the tray.

<details>
<summary><b>Manual install (if you prefer to handle settings.json yourself)</b></summary>

<br>

```bash
cp app/scripts/openpets-event ~/.local/bin/
chmod +x ~/.local/bin/openpets-event
# make sure ~/.local/bin is on your PATH
```

Then add this block to `~/.claude/settings.json` (merge with any hooks
you already have):

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{ "type": "command", "command": "openpets-event idle claude-code" }]
    }],
    "UserPromptSubmit": [{
      "hooks": [{ "type": "command", "command": "openpets-event running claude-code" }]
    }],
    "Notification": [{
      "hooks": [{ "type": "command", "command": "openpets-event review claude-code" }]
    }],
    "Stop": [{
      "hooks": [{ "type": "command", "command": "openpets-event waving claude-code" }]
    }],
    "SessionEnd": [{
      "hooks": [{ "type": "command", "command": "openpets-event idle claude-code" }]
    }]
  }
}
```

</details>

### Multiple Claude Code windows

Hooks from every concurrent Claude Code session write to the same file,
so the pet shows whichever event happened most recently. This is
intentional for the MVP — it matches the "what just happened" intuition
of a desktop pet. A per-session aggregation mode (e.g., "any session
running → running") can be added later if needed.

### Connect other tools

Codex CLI, Cursor, custom scripts, CI runners — anything that can run a
shell command can drive the pet. Just call `openpets-event <state>
<source-label>` from wherever you want a state transition. The
`source-label` is a free-form string used only for diagnostics.

## Prerequisites

- **Rust** — install via `rustup`:
  ```bash
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
  ```
- **Node.js 20+** (you already have this if `npm --version` works)
- **Xcode Command Line Tools** (macOS):
  ```bash
  xcode-select --install
  ```

## Run in dev mode

From this directory (`app/`):

```bash
npm install
npm run dev
```

The first build takes a few minutes (Cargo compiles Tauri + WebKit bindings).
Subsequent runs are fast.

You should see a small transparent window in the **bottom-right** of your
screen with the first pet (alphabetically by id) under `~/.codex/pets/*/`
animating.

## Build a release `.app`

```bash
npm run build
```

Output:

```text
app/src-tauri/target/release/bundle/macos/OpenPets.app
app/src-tauri/target/release/bundle/dmg/OpenPets_0.1.0_aarch64.dmg
```

Bundle size is typically **~5 MB** thanks to using the system WebKit
(no Chromium bundled).

## Project layout

```text
app/
├── index.html            Main pet window entry (vanilla, no framework)
├── main.js               State machine + sprite animation; subscribes to
│                         `pet-changed` (which pet) and `pet-state-changed`
│                         (which animation row) events
├── style.css             Transparent body, grab cursor on the pet
├── picker.html           Pet picker dialog entry
├── picker.js             Builds the thumbnail grid; calls `set_active_pet`
├── picker.css            Frosted-glass dialog look
├── package.json          Tauri CLI as the only Node dep
├── scripts/
│   └── openpets-event    Bash helper for atomic ~/.openpets/state.json writes
└── src-tauri/
    ├── Cargo.toml        Minimal Rust deps (tauri + serde + objc on macOS)
    ├── tauri.conf.json   Main window config (transparent, always-on-top, …)
    ├── build.rs          Tauri build script
    ├── capabilities/
    │   └── default.json  Permissions for both `main` and `picker` windows
    ├── icons/
    │   └── icon.png      Placeholder generated from Phrolova
    └── src/
        └── main.rs       Pet scan + dynamic tray menu + NSPanel hack +
                          start_drag / list_pets / get_active_pet /
                          set_active_pet commands + picker window factory +
                          ~/.openpets/state.json watcher
```

## How it stays lightweight

- Vanilla HTML / CSS / JS for the frontend (no React, no bundler)
- `withGlobalTauri: true` exposes `window.__TAURI__` so the JS side imports
  zero npm packages at runtime — just calls `invoke()` and `convertFileSrc()`
- Three Rust deps total: `tauri`, `serde`, and (macOS-only) `objc 0.2`
- Release profile uses `lto = true`, `opt-level = "s"`, `strip = true`

## macOS implementation notes

The two non-trivial pieces of the macOS implementation are documented here
because they took several iterations to get right and the path forward
through the docs is misleading.

### Why we promote the NSWindow to NSPanel at runtime

Tauri (via `tao`) creates the window as a plain `NSWindow`. For a desktop
pet to be useful we need it visible **everywhere on the desktop, including
on top of other apps' full-screen Spaces**. We tried the obvious approach
first:

1. `alwaysOnTop: true` in tauri.conf.json
   → sets `NSFloatingWindowLevel` (= 3). Fine for normal apps; ignored when
   another app is full-screen.
2. `set_visible_on_all_workspaces(true)` from the Tauri API
   → sets `NSWindowCollectionBehaviorCanJoinAllSpaces`. Necessary but not
   sufficient: the window's `isOnActiveSpace` reads `true`, but it still
   doesn't render over other apps' full-screen Spaces on macOS 13+.
3. Bumping the level to `NSScreenSaverWindowLevel` (= 1000) + adding
   `fullScreenAuxiliary` and `stationary` flags
   → still doesn't show over a full-screen app.

The actual blocker is the **window's class**: a regular `NSWindow` is
simply not allowed by the macOS window server to overlay another app's
full-screen Space, regardless of flags or level. The class that *is*
allowed is `NSPanel` (with `NSWindowStyleMaskNonactivatingPanel` set).
This is what apps like Bartender, Stickies, BetterDisplay, and tauri-nspanel
all do.

We swap the class in place with the Objective-C runtime's `object_setClass`:

```rust
// objc 0.2 doesn't bind this C runtime function — declare it manually.
extern "C" {
    fn object_setClass(obj: *mut Object, cls: *const Class) -> *const Class;
}

let panel_class: &Class = class!(NSPanel);
unsafe { object_setClass(ns_window, panel_class as *const Class) };

// Then add the panel-specific style mask bit (1 << 7 = 128).
let style_mask: u64 = unsafe { msg_send![ns_window, styleMask] };
let new_style_mask = style_mask | 128;
unsafe { let _: () = msg_send![ns_window, setStyleMask: new_style_mask]; }
```

`object_setClass` is safe here because `NSPanel` is a direct subclass of
`NSWindow`: the object's memory layout doesn't change, only its method
dispatch. After the swap, the `NSWindowStyleMaskNonactivatingPanel` style
bit becomes meaningful, the window-server treats the window as a panel,
and overlaying full-screen Spaces just works.

### The collection-behavior + level still matters

Even after the class swap, set:

- `collectionBehavior = canJoinAllSpaces (1) | stationary (16) | ignoresCycle (64) | fullScreenAuxiliary (256)` = `337`
- `level = NSScreenSaverWindowLevel (1000)`

These flags are reapplied on every `Focused(true)` window event because
some macOS versions silently reset them when the window crosses into a
new Space.

### Drag uses an explicit Rust command, not `data-tauri-drag-region`

The `data-tauri-drag-region` attribute interacts oddly with
`macOSPrivateApi: true` + `transparent: true` + a canvas element, so we
expose a `start_drag` Tauri command and invoke it from `mousedown` in JS.
A clean press without movement still emits the `click` event (→ wave); a
press with movement starts an OS-native window drag.

## Troubleshooting

**No pet appears.** The window might be off-screen or behind another window.
Check the console (`tauri dev` shows logs) for `OpenPets: no pets found …`.
Install at least one pet first:

```bash
# Either via Petdex
npx petdex install phrolova

# Or manually copy from this repo
mkdir -p ~/.codex/pets/phrolova
cp ../pets/phrolova/spritesheet.webp ~/.codex/pets/phrolova/
cp ../pets/phrolova/pet.json         ~/.codex/pets/phrolova/
```

**Wrong pet shows up.** The current MVP loads the first pet alphabetically
by id. To change which one shows, rename or remove other pet directories
under `~/.codex/pets/` until your preferred one sorts first. Tray-menu
selection lands in Phase 2.

**Pet not visible over a full-screen app.** Check the dev console output
for the line `[OpenPets] after: behavior=337 level=1000 styleMask=128 …`.
If `styleMask` is missing the `128` bit, the NSPanel class swap failed —
typically because Tauri or tao moved the NSWindow under a class that's
not a direct subclass of NSWindow. Open an issue with the dev log.

**Build fails with "linker error" on macOS.** Run `xcode-select --install`
to ensure command-line tools are present.

**Tray icon missing.** Tauri's tray support requires macOS 10.15+. Verify
with `sw_vers`.

**Compiler warnings about `unexpected_cfg`.** These come from the old
`objc 0.2` macros and are harmless. We suppress them via
`#![allow(unexpected_cfgs)]` at the top of `src/main.rs`.
