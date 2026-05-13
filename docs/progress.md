# Open Pets — Progress Log & Working Memory

Living document. Not in git history but always-current snapshot of where
the project is, what's open, and what we'd want to remember next time we
sit down to keep building. Pair with `CLAUDE.md` (orientation) and the
auto-memory feedback files (lessons).

> **Last updated**: 2026-05-11 — State machine hardened, idle_prompt
> regression fixed, test suite added. Idle variety, onboarding, running
> timeout degrade, and Claude Code hook matcher system all shipped.
> Remaining "Next" items re-prioritized.

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
| Phase 2.C — UX polish (round 1) | Attention-summon for review/waiting (jumping pre-roll + window shake + opt-in sound, silent re-summon at 30s); right-click pet → same menu as the tray icon; status bubbles with friendly labels (red pulse on attention states); smarter `openpets-event auto` mode parses Claude Code hook JSON so failed `PostToolUse` calls flip the pet to `failed`; auto-reinstall hooks on startup so already-connected users pick up new ones | `app/main.{js,css}`, `shake_window` / `show_context_menu` in `main.rs`, `app/scripts/openpets-event` |
| Phase 2.C — UX polish (round 2) | Idle-time variety (spontaneous `jumping` every 15–45s when idle); running timeout degrade (20s of `running` with no new event → idle, so the pet isn't sprinting while Claude streams text); first-run onboarding (bubble sequence teaching right-click + Connect, persists across restarts, cancellable by any click); Claude Code hooks redesigned from keyword-matching to native `matcher` system (11 direct-command hooks covering SessionStart/End, PreToolUse, PostToolUse, PostToolUseFailure, SubagentStop, Notification with `permission_prompt`/`idle_prompt` matchers); idle_prompt cooldown (suppress `waiting` transitions within 30s of entering idle to prevent false "Waiting for you" after Stop); state machine test suite (10 tests simulating all hook event sequences) | `app/main.{js,css}`, `app/src-tauri/src/main.rs`, `app/scripts/openpets-event`, `tests/test_state_machine.py` |

---

## ⏳ Next (priority order)

1. **Picker "Settings" sub-area** — surface Connect-toggles and the
   Attention Sound switch inside the existing magic-glass picker so the
   user doesn't have to hunt the tray menu. Tauri commands
   `list_tool_connections` / `set_tool_connection` /
   `get_attention_sound` / `set_attention_sound` already exist. Also a
   natural place to show the current pet + quick-switch.
2. **Codex CLI connector** — ~1 `ToolDef` entry plus the hook shape.
   Tauri code already iterates `TOOLS` generically.
3. **Cursor connector** — same pattern; figure out Cursor's hook surface.
4. **Click-through on transparent pixels** — sprite-bbox hit testing so
   the pet's empty corners don't intercept clicks. Lower priority since
   the pet occupies most of the 256×256 window at default scale.
5. **Linux / Windows parity** — every macOS-specific concern (NSPanel
   hack, asset protocol scope, tray icon) needs a per-platform plan.
6. **Multi-pet on screen at once** — would require multiple windows and
   a different state-machine model. Phase 3.

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

### Drag handling on transparent NSPanel

Three approaches tried, only the third works reliably on macOS 26 +
NSPanel + WKWebView:

1. **`canvas.addEventListener("mousedown", () => invoke("start_drag"))`**
   — calls `start_dragging` on every mousedown. Quick clicks race:
   `mouseup` lands before AppKit's `performWindowDrag` returns,
   throwing an NSException Rust can't unwind through. App crashes.
2. **`<canvas data-tauri-drag-region>`** — Tauri's native attribute.
   Drag itself works on opaque/regular windows, but on a transparent
   NSPanel the attribute swallows *every* mouse event on the canvas
   including right-click and middle-click. Result: drag flaky AND the
   `contextmenu` event never reaches the WebView, so the inline menu
   can't open.
3. **Movement-threshold drag in JS** *(current)* — record screen-coord
   origin on left-button mousedown; once `mousemove` shows the pointer
   has traveled past `DRAG_THRESHOLD_PX` (3px), call
   `currentWindow.startDragging()` exactly once. By then the mouse is
   verified to still be down (we're inside an active mousemove), no
   NSException race. Right-clicks and short clicks never enter the
   path, so `contextmenu` and click-to-wave both fire normally.

If you ever simplify the drag logic, **don't go back to either of the
first two** — the failure modes are silent (drag-region) or
catastrophic (bare start_drag).

### Tauri 2 capability allow-list is read-only by default

`capabilities/default.json` references `core:default`, which expands to
`core:window:default` + ~7 sibling plugin defaults. The window default
is read-only — `inner-position`, `outer-position`, `is-fullscreen`,
etc. — but does **not** include any mutating call. Anything in the
JS API that changes window state (`startDragging`, `setSize`,
`setPosition`, `setMinimizable`, …) is silently rejected at the IPC
gate unless allow-listed.

Symptoms when you forget: `currentWindow.startDragging()` no-ops
without throwing; `setSize` no-ops with a permission-denied error
that's only visible if devtools is open; the inline menu appears half
-resized because the resize call was rejected.

OpenPets currently allows: `core:window:allow-start-dragging`,
`allow-set-size`, `allow-set-position`. If you add a new JS-side window
mutation, add the matching `core:window:allow-…` entry to
`capabilities/default.json` AND verify the symptom is gone in dev. Do
**not** route around this with custom Rust commands unless there's a
real reason — the capability list is the supported path and serves as
documentation of the trust boundary.

Counter-pattern: don't replace `currentWindow.startDragging()` with
`invoke("start_drag")`. Custom commands aren't capability-gated, so
they "work" without grants, but you lose the JS API's built-in race
protection (the threshold-drag recipe in main.js depends on calling
`startDragging` *during* an active mousemove).

### Dismissing the inline menu on transparent NSPanel

`document.click` listeners only fire when the click lands on an
**opaque** WebView element. On the pet window the canvas is the only
opaque region; the rest of the body is transparent so click events on
those pixels go straight through to the OS / desktop / underlying app.

That means the obvious "click outside the menu to close it" recipe
(listen on document, check `e.target.closest("#menu")`) only catches
clicks on the pet sprite itself, not clicks on the desktop or another
app. Users *expect* clicking anywhere outside the menu to close it.

We use Tauri's `currentWindow.onFocusChanged(({ payload: focused }))`
as the cross-platform proxy for "user clicked elsewhere." When focus
leaves the pet window we close the menu. Two subtleties:

1. The setSize 256→620 that opens the menu can itself produce a
   transient blur on macOS. We set `menuOpenGrace = true` for 300ms
   inside `openInlineMenu`; the focus listener no-ops while it's set.
2. Right-click on the pet *while the menu is already open* should
   toggle it closed (covered by the `contextmenu` handler), and Esc
   should close it (covered by the `keydown` handler). The blur path
   is the *third* dismiss route, not the only one.

### Claude Code hook design: matchers, not keyword-guessing

The first version of the Notification hook scanned Claude's `message` text for
keywords like "permission" and "confirm" to decide whether to show `review`.
This produced false positives on informational messages ("Build confirmed",
"Waiting for tool output").

Claude Code's hook system has a native `matcher` field that filters
Notifications by type. The canonical discriminator is `notification_type`:
`permission_prompt` for tool-confirmation dialogs, `idle_prompt` for idle
nudges. Each matcher gets its own hook entry pointing to a direct command
(`openpets-event review/waiting claude-code`), so we never guess from text.

The full hook set is 10 entries covering 8 Claude Code events:

| Hook event | matcher | → state |
|---|---|---|
| SessionStart | — | idle |
| SessionEnd | — | idle |
| UserPromptSubmit | — | running |
| Stop | — | waving |
| PreToolUse | — | running |
| PostToolUse | — | running |
| PostToolUseFailure | — | failed |
| SubagentStop | — | running |
| Notification | permission_prompt | review |
| Notification | idle_prompt | waiting |

All hooks use direct commands (not `auto` mode) because Claude Code already
routes PostToolUse vs PostToolUseFailure to separate hooks. The `openpets-event`
`auto` mode remains useful for tools whose hook surface doesn't split
success/failure into separate events.

Hook auto-migration: on startup, `connect_tool` compares the installed hooks
against the current `CLAUDE_CODE_HOOKS` definition. If any entry is missing or
differs in command/matcher, it reinstalls the full set. This means users who
connected before a hook update automatically pick up new hooks on next app
launch.

### idle_prompt cooldown: why JS-side, not hook-side

Claude Code fires `idle_prompt` Notifications on its own schedule — seconds
after a turn completes. If we map `idle_prompt → waiting` unconditionally,
the pet shows "Waiting for you" right as the user is reading the response.

We can't control when Claude Code fires idle_prompt, so the suppression must
be JS-side. Two layers:

1. **Remove "waiting" from ATTENTION_STATES** — idle_prompt no longer
   triggers summon (shake + beep). Only `review` (permission prompts) gets
   the full attention treatment.
2. **30s cooldown in transitionToExternal** — if the pet entered idle less
   than 30 seconds ago, incoming `waiting` events are silently dropped.
   After 30s, `waiting` is allowed through (shows a gentle "Waiting for
   you" bubble that fades after 2s, no summon/shake).

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
| Test the state machine | `tests/test_state_machine.py` — simulates hook event sequences via `openpets-event` CLI and validates `~/.openpets/state.json` |

---

## 🐛 Common pitfalls & quick fixes

When a Claude Code session sits down to debug the desktop app, scan
this list before going deep on a fresh root-cause hunt. Every entry
here is a real trap we've hit, with the symptom and the patch.

### "I edited HTML/JS but the new code isn't running"

The frontend is **embedded into the Rust binary** at compile time via
`tauri::generate_context!`. `app/`'s HTML/JS/CSS files are copied
into the binary by `cargo`, not loaded live by `tauri dev`. If only
the frontend changed, cargo's incremental cache may not invalidate,
so `tauri dev` happily ships the previous embed.

The reliable trigger is to bump `BUILD_TAG` in `main.rs` — anything,
e.g. append `-v2`. Tauri dev's file watcher then sees `main.rs`
change and re-runs the macro. Rule of thumb: **every
frontend-touching session should bump BUILD_TAG before the user
re-tests.**

### "My JS-side `currentWindow.X()` call silently doesn't do anything"

You're hitting Tauri 2's capability gate. `core:default` is read-only.
Every mutating window call needs an explicit allow in
`capabilities/default.json`. See "Tauri 2 capability allow-list" in
the decisions section. Common ones:

| JS API | Capability needed |
| --- | --- |
| `startDragging()` | `core:window:allow-start-dragging` |
| `setSize(...)` | `core:window:allow-set-size` |
| `setPosition(...)` | `core:window:allow-set-position` |
| `setSize` + `setPosition` together | both, separately |
| `setFocus()` | `core:window:allow-set-focus` |
| `hide()/show()` | `core:window:allow-hide` / `…allow-show` |
| `close()` | `core:window:allow-close` |

If you don't have devtools open, the rejection looks like *nothing
happens* — no exception. The only diagnostic clue is comparing the
list of granted permissions in `capabilities/default.json` against
what you call.

### "cargo check / tauri dev hangs forever on `Compiling openpets`"

The Tauri 2 macro expansion (`generate_context!`,
`generate_handler!`) is heavy on its own, and an inconsistent
incremental cache can make rustc thrash for 15-20 minutes producing
nothing. If a single-crate compile sits at full CPU with no output
beyond "Compiling openpets" for more than ~3 min:

```bash
rm -rf app/src-tauri/target/debug/incremental
```

Re-run. Cold compile takes ~1 min on this machine; subsequent
incrementals are ~0.5s. If clearing the cache doesn't help, the bug
is real — read the diff for genuine errors.

### "I run `npm run dev` and it errors with `cargo metadata: No such file or directory`"

`npm` runs in a subshell that doesn't pick up `~/.cargo/bin` from
your zsh profile. Run with PATH explicit:

```bash
PATH="$HOME/.cargo/bin:$PATH" npm run dev
```

### "Mouse events on the canvas aren't firing"

Two failure modes that both produce "the pet is unclickable":

1. `data-tauri-drag-region` was added to the canvas. On transparent
   NSPanel + WKWebView this attribute swallows *every* mouse event
   on the element including right-click. Remove the attribute and
   use the JS movement-threshold drag (see decisions).
2. The user is testing a stale build. Verify by greping the dev log
   for the `[OpenPets] build:` line and confirming the BUILD_TAG
   matches your latest source.

### "The inline menu only shows a thin border / partial frame"

The `setSize(256, 620)` IPC was rejected by capabilities so the
window stayed at 256×256, clipping everything below. Add
`core:window:allow-set-size` to capabilities. If it's already there,
check the JS log for `setSize (expand) failed:` errors — your menu
height may be too tall for the screen.

### "Clicking outside the menu doesn't close it"

`document.click` doesn't fire on transparent body regions of an
NSPanel — those clicks go through to the OS. Use
`currentWindow.onFocusChanged(({ payload: focused }))` to catch the
blur event when the user clicks anywhere outside the WebView.
Remember the `menuOpenGrace` flag so the open-time resize doesn't
auto-close (see decisions).

### "After closing the menu, the pet jumps to a slightly different place"

The 256→620 expand near the screen bottom makes AppKit auto-shift
the window upward to keep it on screen. Without the `is_resizing`
flag, that shift fires `WindowEvent::Moved` which is persisted to
config. Make sure JS calls `set_menu_resizing(true)` *before*
setSize and `set_menu_resizing(false)` after a settle delay; on
the Rust side, `on_window_moved` should bail when `is_resizing` is
true. (Same pattern as `is_shaking` for the attention shake.)

### "I changed `~/.openpets/state.json` but the pet didn't update"

The Rust watcher watches the **directory**, not the file — atomic
`mv` writes break per-file FSEvents subscriptions on macOS. Use the
`openpets-event` helper (`~/.local/bin/openpets-event`) which does
the right tmp+rename dance, or replicate it manually. Don't use
`echo > state.json` for testing; that produces partial reads.

### "Right-click menu opens but text/items invisible"

This is what happens when one of the four `Promise.all` invokes in
`buildMenuContent` rejects (e.g. capability denial on a Tauri
command you forgot to allow). The catch silently swallows it and
all four results stay at their defaults. Open the actual webview
console (right-click in dev mode → Inspect Element) to see the
error — the project ships with `withGlobalTauri: true` so the JS
console errors are real.

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
| `feedback_drag_region_breaks_nspanel.md` | `data-tauri-drag-region` kills *all* canvas mouse events on transparent NSPanel — use JS threshold drag |
| `feedback_tauri2_capabilities_default_is_readonly.md` | `core:default` does not include window-mutating calls; allow-list each one explicitly |

---

## 🚀 New-session bootstrap

When you (or a fresh Claude Code session) sits down to keep going, the
fastest path back to context is:

1. **Read this file** end-to-end. The "Common pitfalls" section
   alone saves several debug detours.
2. `git log --oneline -10` for what just shipped.
3. `cat ~/.openpets/config.json` if you're touching the desktop app.
4. Re-read `feedback_macos_overlay_window_recipe.md` if anything in
   `pin_window_above_full_screen_apps` looks suspect.
5. Before writing JS that calls `currentWindow.X()`, check
   `app/src-tauri/capabilities/default.json` — the API silently no-ops
   if the matching `core:window:allow-…` permission isn't listed.
6. If you change frontend files and ask the user to retest, bump
   `BUILD_TAG` in `main.rs` so cargo re-embeds the assets. Without
   this bump the user keeps testing the old embed.
7. Ask the user *which* of the "⏳ Next" items they want to start on, or
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
