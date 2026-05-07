# OpenPets desktop renderer (Phase 1)

A lightweight Tauri 2 desktop app that animates any Codex-format pet atlas
on your screen — independent of Codex CLI.

> 🚧 **Status**: Phase 1 scaffold. Loads the first pet found under
> `~/.codex/pets/*/`, plays its idle loop, and lets you click for a wave.
> macOS-first; Windows / Linux to come once the macOS path stabilizes.

## What it does today

- Reads pet packages from `~/.codex/pets/*/` (same layout the Codex CLI uses)
- Renders the 192×208 sprite cells from the WebP atlas in a transparent,
  always-on-top, undecorated window
- Plays the canonical 9-state animation cycle (idle / running / waving /
  jumping / failed / waiting / review …) defined by the
  [open-pet-creator Skill](../open-pet-creator/SKILL.md)
- Click on the pet → triggers `waving`, then returns to `idle`
- Tray icon menu → `Quit`

## Roadmap (Phase 2)

- External event source — let Codex / Claude Code / Cursor drive pet states
  via a local socket or file watcher (e.g., AI is generating → `running`,
  test failed → `failed`, task done → `waving`)
- Pet picker UI in tray menu (currently just loads the first one)
- Click-through on transparent pixels (so the window doesn't intercept
  clicks on its empty edges)
- Multi-pet support, drag-to-position, settings panel
- Cross-platform parity (Linux / Windows)

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

You should see a small transparent window in the upper-left of your screen
with Phrolova (or whichever pet is first under `~/.codex/pets/`) animating.

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
├── index.html            Frontend entry (vanilla, no framework)
├── main.js               State machine + sprite animation
├── style.css             Transparent body, draggable window
├── package.json          Tauri CLI as the only Node dep
└── src-tauri/
    ├── Cargo.toml        Minimal Rust deps (tauri + serde)
    ├── tauri.conf.json   Window config (transparent, always-on-top, …)
    ├── build.rs          Tauri build script
    ├── capabilities/
    │   └── default.json  Permission set for the main window
    ├── icons/
    │   └── icon.png      Placeholder generated from Phrolova
    └── src/
        └── main.rs       Pet directory scan + tray + window startup
```

## How it stays lightweight

- Vanilla HTML / CSS / JS for the frontend (no React, no bundler)
- `withGlobalTauri: true` exposes `window.__TAURI__` so the JS side imports
  zero npm packages at runtime — just calls `invoke()` and `convertFileSrc()`
- Two Rust deps total: `tauri` and `serde`
- Release profile uses `lto = true`, `opt-level = "s"`, `strip = true`

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

**Build fails with "linker error" on macOS.** Run `xcode-select --install`
to ensure command-line tools are present.

**Tray icon missing.** Tauri's tray support requires macOS 10.15+. Verify
with `sw_vers`.
