# Open Pets — Progress Log & Working Memory

Living document. Not in git history but always-current snapshot of where
the project is, what's open, and what we'd want to remember next time we
sit down to keep building. Pair with `CLAUDE.md` (orientation) and the
auto-memory feedback files (lessons).

> **Last updated**: 2026-05-08 — Phase 2.C UX polish landed: attention
> summon (jump + window shake + opt-in sound) for review/waiting,
> right-click pet → tray menu, status bubbles with friendly labels,
> smarter `openpets-event auto` mode that promotes failed PostToolUse
> calls to the `failed` animation.

---

## ✅ Done

| Slice | What it delivered | Key files |
| --- | --- | --- |
| `open-pet-creator` Skill | repack / inspect / validate / install scripts; SKILL.md; atlas contract reference; `--detect-sprites` mode for generator sources | `open-pet-creator/` |
| 3 pets shipped | Phrolova (Wuthering Waves), Pink Star and Dimo (Roco World), all passing the 6-test contract suite | `pets/`, `tests/test_phrolova_spritesheet.py` |
| Petdex publishing | Phrolova + Pink Star are live; one-line `npx petdex install <id>` documented in both READMEs | `README.md` |
| Phase 1 desktop app | Tauri 2, macOS-first, transparent always-on-top window with NSPanel cross-fullscreen visibility, drag-to-move, click-to-wave, tray icon | `app/src-tauri/src/main.rs`, `app/main.js` |
| Pet picker (1.5) | Tray menu lists every installed pet; "Choose Pet…" opens a 400×240 frosted-glass thumbnail grid | `app/picker.{html,js,css}` |
| Phase 2.A — IDE event source | `~/.openpets/state.json` watcher on the Rust side; `openpets-event` bash helper for atomic writes; Claude Code hooks tested end-to-end | `app/scripts/openpets-event`, `watch_state_file` in `main.rs` |
| Phase 2.B — automation | One-click "Connect to Claude Code" tray toggle (no JSON pasting); active-pet and window-position persistence in `~/.openpets/config.json` | `connect_tool` / `disconnect_tool` / `OpenPetsConfig` in `main.rs` |
| Phase 2.C — UX polish | Attention-summon for review/waiting (jumping pre-roll + window shake + opt-in sound, silent re-summon at 30s); right-click pet → same menu as the tray icon; status bubbles with friendly labels (red pulse on attention states); smarter `openpets-event auto` mode parses Claude Code hook JSON so failed `PostToolUse` calls flip the pet to `failed`; auto-reinstall hooks on startup so already-connected users pick up new ones | `app/main.{js,css}`, `shake_window` / `show_context_menu` in `main.rs`, `app/scripts/openpets-event` |

---

## ⏳ Next (priority order)

1. **Idle-time variety** — long stretches of `idle` should occasionally
   trigger a small jump/blink/walk so the pet feels alive instead of a
   6-frame loop. Cheap win, JS only.
2. **First-run onboarding** — small bubble/toast on first launch ("right
   click me!", "I follow Claude Code"). Avoids the user not knowing the
   tray and right-click both exist.
3. **Codex CLI connector** — ~1 `ToolDef` entry plus the hook shape.
   Tauri code already iterates `TOOLS` generically.
4. **Cursor connector** — same pattern; figure out Cursor's hook surface.
5. **Picker "Settings" sub-area** — surface Connect-toggles and the
   Attention Sound switch inside the existing magic-glass picker so the
   user doesn't have to hunt the tray menu. Tauri commands
   `list_tool_connections` / `set_tool_connection` /
   `get_attention_sound` / `set_attention_sound` already exist.
6. **Linux / Windows parity** — every macOS-specific concern (NSPanel
   hack, asset protocol scope, tray icon) needs a per-platform plan.
7. **Multi-pet on screen at once** — would require multiple windows and
   a different state-machine model. Phase 3.
8. **Click-through on transparent pixels** — sprite-bbox hit testing so
   the pet's empty corners don't intercept clicks.

---

## 🧠 Architectural decisions (the "why" we'd lose without writing it down)

### macOS overlay path: NSWindow → NSPanel hot-swap

Plain `NSWindow`, even with `canJoinAllSpaces` + screen-saver level + every
collection-behavior flag set, **cannot** float over another app's
full-screen Space on macOS 13+. The window server gates that on the
NSWindow class itself. We use `extern "C" fn object_setClass` to swap the
live NSWindow's class to `NSPanel` and then add
`NSWindowStyleMaskNonactivatingPanel` (1<<7 = 128) to its style mask. The
swap is safe because `NSPanel` is a direct subclass of `NSWindow` with
the same memory layout.

This is documented in:
- `app/src-tauri/src/main.rs::pin_window_above_full_screen_apps` (the
  load-bearing function)
- `app/README.md` → *macOS implementation notes* section
- `feedback_macos_overlay_window_recipe.md` in the auto-memory

If you ever rewrite that function, **do not drop the `object_setClass`
call**.

### Why file watching, not a socket

`~/.openpets/state.json` is the event channel. We chose a file watcher
over a Unix socket because:

- Any tool that can run `echo {...} > file` can drive the pet — no
  client SDK to ship.
- Atomic `mv` writes (which the `openpets-event` helper does) make
  partial-write races impossible.
- `cat ~/.openpets/state.json` is a one-line debugger.
- macOS FSEvents has acceptable latency (<200ms) for this purpose.

The watcher in `watch_state_file` watches the **directory**, not the file,
because atomic-mv writes break per-file FSEvents subscriptions on macOS.

### Why a Tauri command instead of a CLI binary for "connect"

The user's UX bar: end users won't paste JSON, won't `chmod +x`, won't
edit PATH. So *every* path through "wire OpenPets to Claude Code" had
to collapse to a single click. The CheckMenuItem in the tray solves this
without forcing us to ship a separate `openpets` binary. Tauri commands
`list_tool_connections` / `set_tool_connection` are exposed for the same
logic to live in a future Settings panel or external CLI.

### Attention summon: jump + shake + bubble, with a 30s re-summon

Tool-confirmation prompts (Claude Code's `Notification` hook) used to map
to the soft `review` loop. That loop alone is too easy to miss when the
pet sits behind another window or the user looked away. The current
recipe in `app/main.js`:

1. On entering `review` or `waiting` from a non-attention state,
   `summonAttention(target)` plays the `jumping` one-shot first, then
   transitions into the target loop.
2. Same call invokes `shake_window` (Rust): wiggles the window through
   `[8,-8,6,-6,4,-4,2,-2,0]` px offsets at 35ms intervals. A flag in
   `AppState.is_shaking` suppresses position-persistence during the
   wiggle so we don't save the offsets as the user's chosen spot.
3. Optional sound (`attention_sound` in `OpenPetsConfig`, default off,
   toggled in the tray menu) plays a brief Web Audio bleep.
4. The bubble is set to the *target* state's label so the user sees
   "Review needed" while the pet is still in the jumping pre-roll.
5. If the user is still in the same attention state after 30s, replay
   the summon **silently** (no sound) — one nudge is enough.

The `pendingAfterIntro` variable is what lets a generic `jumping`
one-shot (which would normally fall back to `idle`) hand off to a
custom target. Don't replace that with state-specific intro frames —
the atlas only has 9 rows and `jumping` already animates well.

### Persistence layer

Two distinct files under `~/.openpets/`:

- `state.json` — *event* file (driven by external tools, watched by us)
- `config.json` — *preference* file (written by us, read on startup)

Mixing them would mean every pet-state event also touches the user's
saved active-pet selection. Keeping them separate keeps both easy to
reason about.

`update_config(state, |cfg| ...)` is the only mutation path. It snapshots
inside the lock and writes outside (atomic `tmp + rename`), so we never
hold the mutex during file I/O.

---

## 🗺️ "Where does X live" map

| You want to… | Touch this |
| --- | --- |
| Add a new pet | `pets/<id>/`, `docs/<id>-pet-design.md`, run the Skill repacker |
| Add a new generative-image prompt template | `docs/<id>-generation-prompt.md` (copy from `rocom-dimo` as the latest exemplar) |
| Tweak the atlas contract / packaging logic | `open-pet-creator/scripts/repack_pet_atlas.py`, plus the Skill docs in `open-pet-creator/{SKILL.md,references/}` |
| Change how the desktop pet animates | `app/main.js` (`STATES` table + the tick loop) |
| Change how the desktop pet *looks* (window chrome) | `app/style.css`, `app/src-tauri/tauri.conf.json` |
| Change the picker UI | `app/picker.{html,js,css}` |
| Add a new tray menu entry | `build_tray_menu` in `app/src-tauri/src/main.rs` |
| Hook a new AI tool (Codex / Cursor) | Add a `ToolDef` to the `TOOLS` array in `main.rs`; everything else (helper install, JSON merge, tray toggle) is generic |
| Touch macOS window behavior | `pin_window_above_full_screen_apps` — and re-read the warning above before deleting any `objc::msg_send!` line |
| Change what events drive the pet | The mapping is split: hook commands in `connect_tool`'s `CLAUDE_CODE_HOOKS` decide *which Claude event → which state*; the JS state machine in `main.js` decides *what each state looks like* |
| Add a new bubble label / change wording | `STATE_LABELS` in `app/main.js`. Add the state to `PERSISTENT_BUBBLE` if it should stay until the next state change |
| Tune the attention summon (shake amplitude, re-summon delay, sound) | `shake_window` in `main.rs` for the wiggle pattern; `RESUMMON_DELAY_MS` and `playAttentionBeep` in `app/main.js` for everything else |
| Extend the smart helper (auto mode) | `app/scripts/openpets-event` — the inline Python `python3 -c "$(cat <<PY ... PY)"` block. Add a new `if ev == "X"` branch |

---

## 📚 Auto-memory cross-reference

These live in
`~/.claude/projects/-Users-ctenetliu-Projects-TENET-AI-open-pets/memory/`
and load automatically into every Claude Code session in this repo:

| File | Gist |
| --- | --- |
| `project_overview.md` | What this repo is for; what's in scope and what isn't |
| `feedback_per_pet_scale_tuning.md` | Don't copy `--scale` across pets; tall ears cap at ~1.0, compact builds tolerate 1.05+ |
| `feedback_use_detect_sprites_for_genai.md` | gpt-image / Midjourney / SDXL output is rarely a clean grid → use `--detect-sprites` |
| `feedback_roco_world_rightsholder.md` | Roco World is Tencent, not TaoMee |
| `feedback_macos_overlay_window_recipe.md` | The NSPanel hack, in one place |
| `feedback_users_wont_edit_settings_json.md` | Why every "Connect to X" path must collapse to a single click |

---

## 🚀 New-session bootstrap

When you (or a fresh Claude Code session) sits down to keep going, the
fastest path back to context is:

1. **Read this file**.
2. `git log --oneline -10` for what just shipped.
3. `cat ~/.openpets/config.json` if you're touching the desktop app.
4. Re-read `feedback_macos_overlay_window_recipe.md` if anything in
   `pin_window_above_full_screen_apps` looks suspect.
5. Ask the user *which* of the "⏳ Next" items they want to start on, or
   whether they're picking up something not on the list yet.

---

## 📝 Update protocol

Edit this file at the end of any meaningful work session. The shape that
keeps it useful:

- "Done" gets a row when a slice ships and is verified by the user.
- "Next" is reordered when priorities change; items move out of "Next"
  into "Done" when shipped.
- "Architectural decisions" only grows when we make a decision the next
  agent would need a paragraph to re-derive.
- "Where does X live" only grows when a new significant module appears.
