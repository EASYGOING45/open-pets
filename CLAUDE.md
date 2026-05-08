# Open Pets — Agent Orientation

This file is loaded automatically by Claude Code when you start a session
in this repo. It is intentionally short. **Read it, then read what it
points to.**

## What this repo is

A workspace for building **Codex / Claude Code custom desktop pets**. It
contains:

- `open-pet-creator/` — a reusable Skill that any Codex / Claude Code
  agent can load to repack, validate, inspect, and install pet atlases.
- `pets/` — three ready-to-install pets (Phrolova, Pink Star, Dimo).
- `app/` — a lightweight Tauri 2 macOS desktop app that animates the
  pets independent of Codex CLI, with one-click Claude Code integration.
- `docs/` — per-pet design docs and the running progress log.
- `tools/`, `tests/` — per-pet repackers and contract tests.

## Where to look for context (in order)

1. **[`docs/progress.md`](docs/progress.md)** — current phase status,
   what's done, what's next, key architectural decisions, and a "where
   does X live" file map. Read this first whenever the user says
   "continue from where we left off".
2. **`MEMORY.md`** in this project's auto-memory directory (already in
   your context if it exists) — feedback / project memories. Especially
   important entries:
   - *macOS overlay window must be NSPanel* (the load-bearing hack in
     `app/src-tauri/src/main.rs::pin_window_above_full_screen_apps`)
   - *Per-pet `--scale` is not transferable* (re-tune from `0.98` for
     every new pet)
   - *Prefer `--detect-sprites` for generative sources*
   - *Users won't manually edit `settings.json`* (the design driver
     for the tray-menu Connect toggle)
3. **`README.md`** / **`README.en.md`** — public-facing project pitch,
   showcase, Petdex links.
4. **`app/README.md`** — desktop-app deep-dive, including the macOS
   implementation notes and the Phase 2 IDE-event integration recipe.

## Cheat sheet for common asks

```bash
# Run the desktop app
cd app && npm install && npm run dev

# Repack a new pet's source sheet (use --detect-sprites for AI-gen sources)
python3 open-pet-creator/scripts/repack_pet_atlas.py \
  --source pets/<id>/spritesheet-source.png \
  --output pets/<id>/spritesheet.webp \
  --scale 0.98 --offset-y 14 --detect-sprites

# Drive the pet from anywhere (state ∈ idle/running/waving/jumping/failed/waiting/review/running-right/running-left)
openpets-event running

# Inspect / validate a pet atlas
python3 open-pet-creator/scripts/inspect_pet_atlas.py  pets/<id>/spritesheet.webp
python3 open-pet-creator/scripts/validate_pet_atlas.py pets/<id>/spritesheet.webp
```

## When updating this file

Keep CLAUDE.md short. Long-form status, decisions, and todos belong in
`docs/progress.md`. The point of this file is to keep agent context cost
low while still steering attention to the right resources.
