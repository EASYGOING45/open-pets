// OpenPets — minimal sprite animator for Codex-format pet atlases.
//
// Atlas contract: 1536x1872 image; 8 cols × 9 rows of 192×208 cells.
// Row → state mapping matches the Codex protocol implemented by the
// open-pet-creator Skill.

const { invoke, convertFileSrc } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const currentWindow = window.__TAURI__.window.getCurrentWindow();

// Tauri 2's setSize accepts any object with `type: "Logical"` and
// width/height fields — we don't need to import the LogicalSize class
// (which lives at __TAURI__.dpi in some versions and would break here
// if we got the namespace wrong).
function logicalSize(width, height) {
  return { type: "Logical", width, height };
}

const CELL_W = 192;
const CELL_H = 208;

// Row index, frame count, fps, optional one-shot flag, optional fallback state.
const STATES = {
  idle: { row: 0, frames: 6, fps: 4 },
  "running-right": { row: 1, frames: 8, fps: 8 },
  "running-left": { row: 2, frames: 8, fps: 8 },
  waving: { row: 3, frames: 4, fps: 6, oneshot: true, then: "idle" },
  jumping: { row: 4, frames: 5, fps: 8, oneshot: true, then: "idle" },
  failed: { row: 5, frames: 8, fps: 6, oneshot: true, then: "idle" },
  waiting: { row: 6, frames: 6, fps: 3 },
  running: { row: 7, frames: 6, fps: 6 },
  review: { row: 8, frames: 6, fps: 4 },
};

// States where the user is being asked to do something (tool confirmation,
// permission prompt, etc). Entering these from a non-attention state plays a
// summon animation + window shake + optional sound.
const ATTENTION_STATES = new Set(["review", "waiting"]);
const RESUMMON_DELAY_MS = 30_000;

// Friendly label shown in the bubble for each state. `null` = no bubble.
// jumping is a transitional intro animation, not a state worth narrating.
const STATE_LABELS = {
  idle: null,
  running: "Running…",
  "running-right": "Running…",
  "running-left": "Running…",
  waving: "Hi!",
  jumping: null,
  failed: "Oops",
  waiting: "Waiting for you",
  review: "Review needed",
};
// Bubbles that stay visible until the state changes (vs. fading after 2s).
const PERSISTENT_BUBBLE = ATTENTION_STATES;
// Bubbles painted in the attention color + pulse animation.
const ATTENTION_BUBBLE = ATTENTION_STATES;
const BUBBLE_HOLD_MS = 2200;

const canvas = document.getElementById("pet");
const ctx = canvas.getContext("2d");
const bubbleEl = document.getElementById("bubble");
const menuEl = document.getElementById("menu");
const menuListEl = document.getElementById("menu-list");
let img = new Image();

const WINDOW_COMPACT = { w: 256, h: 256 };
// Tall enough to fit the worst-case menu (4 pets + Choose + Connect + Sound +
// Quit + section labels & separators). #menu-list also has max-height +
// overflow-y so users with many installed pets get a scrollable menu instead
// of clipped items.
const WINDOW_WITH_MENU = { w: 256, h: 620 };

let state = "idle";
let frame = 0;
let lastFrameTime = 0;

// When the jumping pre-roll finishes, the tick loop transitions to this
// target instead of jumping's default `then: "idle"`. Used for the summon.
let pendingAfterIntro = null;
let resummonTimer = null;
let bubbleHideTimer = null;
let attentionSoundEnabled = false;
let idleVarietyTimer = null;
// When the pet enters `running` via an external event, start this timer.
// If 20s pass without any new hook event (Claude is thinking / streaming
// text rather than executing tools), degrade to idle so the pet looks
// relaxed instead of sprinting for minutes.
let runningDegradeTimer = null;
const RUNNING_DEGRADE_MS = 20_000;

function scheduleIdleVariety() {
  cancelIdleVariety();
  if (state !== "idle") return;
  // 15–45 seconds of pure idle before the pet gets restless.
  const delay = 15000 + Math.random() * 30000;
  idleVarietyTimer = setTimeout(() => {
    idleVarietyTimer = null;
    // Don't interrupt menu or onboarding.
    if (state !== "idle" || menuIsOpen || bubbleEl.classList.contains("onboarding"))
      return;
    // Spontaneous hop — jumping is a oneshot that returns to idle.
    setState("jumping");
  }, delay);
}

function cancelIdleVariety() {
  if (idleVarietyTimer) {
    clearTimeout(idleVarietyTimer);
    idleVarietyTimer = null;
  }
}

function scheduleRunningDegrade() {
  cancelRunningDegrade();
  runningDegradeTimer = setTimeout(() => {
    runningDegradeTimer = null;
    if (state === "running") {
      // Degrade to idle — Claude is thinking / streaming, not executing.
      setState("idle");
    }
  }, RUNNING_DEGRADE_MS);
}

function cancelRunningDegrade() {
  if (runningDegradeTimer) {
    clearTimeout(runningDegradeTimer);
    runningDegradeTimer = null;
  }
}

function updateBubble(name) {
  const text = STATE_LABELS[name];
  if (bubbleHideTimer) {
    clearTimeout(bubbleHideTimer);
    bubbleHideTimer = null;
  }
  if (!text) {
    bubbleEl.classList.remove("visible", "attention");
    return;
  }
  bubbleEl.textContent = text;
  bubbleEl.classList.toggle("attention", ATTENTION_BUBBLE.has(name));
  bubbleEl.classList.add("visible");
  if (!PERSISTENT_BUBBLE.has(name)) {
    bubbleHideTimer = setTimeout(() => {
      bubbleEl.classList.remove("visible", "attention");
      bubbleHideTimer = null;
    }, BUBBLE_HOLD_MS);
  }
}

function setState(name) {
  if (!STATES[name]) return;
  state = name;
  frame = 0;
  lastFrameTime = performance.now();
  updateBubble(name);

  // Idle variety: schedule a spontaneous animation; cancel on any transition.
  if (name === "idle") {
    scheduleIdleVariety();
  } else {
    cancelIdleVariety();
  }

  // Running degrade: if an external event set us to running, start a
  // 20s timer. If no new event arrives before it fires, Claude is just
  // thinking/streaming — degrade to idle so the pet looks relaxed.
  if (name === "running") {
    scheduleRunningDegrade();
  } else {
    cancelRunningDegrade();
  }

  // Any state change cancels a pending re-summon — the user has progressed.
  if (resummonTimer) {
    clearTimeout(resummonTimer);
    resummonTimer = null;
  }

  // While the user lingers in an attention state, give one quiet nudge after
  // RESUMMON_DELAY_MS in case they didn't notice the first summon.
  if (ATTENTION_STATES.has(name)) {
    resummonTimer = setTimeout(() => {
      resummonTimer = null;
      if (state === name) summonAttention(name, { silent: true });
    }, RESUMMON_DELAY_MS);
  }
}

function summonAttention(targetState, { silent = false } = {}) {
  pendingAfterIntro = targetState;
  setState("jumping");
  // Show the target state's bubble immediately (overriding jumping's null
  // label) so the user sees both the wiggle and the explanation at once.
  updateBubble(targetState);
  invoke("shake_window").catch((e) => console.warn("shake_window failed:", e));
  if (!silent && attentionSoundEnabled) playAttentionBeep();
}

// Called for every external state transition (Claude Code hook → state.json
// → Rust → here). Plays the summon if we're entering an attention state from
// a non-attention state; otherwise just sets the state directly.
function transitionToExternal(name) {
  if (!STATES[name]) return;
  const enteringAttention = ATTENTION_STATES.has(name);
  const alreadyInAttention = ATTENTION_STATES.has(state);
  if (enteringAttention && !alreadyInAttention) {
    summonAttention(name);
  } else {
    setState(name);
  }
}

// Brief Web Audio bleep — no asset to ship, just two short tones with a
// quick decay. Opt-in: only plays when the user enabled "Attention Sound"
// in the tray menu.
function playAttentionBeep() {
  try {
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return;
    const ac = new Ctor();
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.connect(gain);
    gain.connect(ac.destination);
    osc.type = "sine";
    osc.frequency.setValueAtTime(900, ac.currentTime);
    osc.frequency.exponentialRampToValueAtTime(700, ac.currentTime + 0.18);
    gain.gain.setValueAtTime(0.0001, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.18, ac.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + 0.4);
    osc.start();
    osc.stop(ac.currentTime + 0.42);
    setTimeout(() => ac.close().catch(() => {}), 600);
  } catch (e) {
    console.warn("attention beep failed:", e);
  }
}

function draw() {
  if (!img.complete || img.naturalWidth === 0) return;
  const s = STATES[state];
  ctx.clearRect(0, 0, CELL_W, CELL_H);
  ctx.drawImage(
    img,
    frame * CELL_W,
    s.row * CELL_H,
    CELL_W,
    CELL_H,
    0,
    0,
    CELL_W,
    CELL_H,
  );
}

function tick(now) {
  const s = STATES[state];
  const interval = 1000 / s.fps;
  if (now - lastFrameTime >= interval) {
    frame++;
    if (frame >= s.frames) {
      if (s.oneshot) {
        // If a summon queued an attention state behind this oneshot, jump to
        // it instead of the default fallback.
        if (pendingAfterIntro) {
          const next = pendingAfterIntro;
          pendingAfterIntro = null;
          setState(next);
        } else {
          setState(s.then);
        }
        requestAnimationFrame(tick);
        return;
      }
      frame = 0;
    }
    lastFrameTime = now;
    draw();
  }
  requestAnimationFrame(tick);
}

let animationStarted = false;

// Load the new atlas into a fresh Image first; only swap `img` once it's
// fully decoded. This avoids a flicker when the user switches pets via the
// picker and the canvas would otherwise try to draw a half-loaded image.
let onboardingStarted = false;
let onboardingActive = false;

async function startOnboarding() {
  // First run only — persist across restarts so it never replays.
  const alreadyDone = await invoke("get_onboarding_done").catch(() => false);
  if (alreadyDone) return;

  // Check whether Claude Code is already hooked up.
  let ccConnected = false;
  try {
    const tools = await invoke("list_tool_connections");
    const cc = tools.find((t) => t[0] === "claude-code");
    ccConnected = cc ? cc[2] : false;
  } catch (_) { /* fetch failed, assume not connected */ }

  const showOnboardingBubble = (text, holdMs) =>
    new Promise((resolve) => {
      bubbleEl.textContent = text;
      bubbleEl.classList.add("visible", "onboarding");
      bubbleHideTimer = setTimeout(() => {
        bubbleEl.classList.remove("visible", "onboarding");
        bubbleHideTimer = null;
        resolve();
      }, holdMs);
    });

  onboardingActive = true;

  // Step 1 — always: teach the right-click gesture.
  await showOnboardingBubble("Right-click me for menu", 4000);
  if (!onboardingActive) return; // cancelled by user interaction

  // Step 2 — only if Claude Code isn't connected yet.
  if (!ccConnected) {
    await showOnboardingBubble(
      "Connect to Claude Code — look for ☰ in your Mac menu bar",
      5000,
    );
    if (!onboardingActive) return;
  }

  onboardingActive = false;
  await invoke("set_onboarding_done", { done: true }).catch(() => {});
}

function cancelOnboarding() {
  if (!onboardingActive) return;
  onboardingActive = false;
  if (bubbleHideTimer) {
    clearTimeout(bubbleHideTimer);
    bubbleHideTimer = null;
  }
  bubbleEl.classList.remove("visible", "onboarding");
  invoke("set_onboarding_done", { done: true }).catch(() => {});
}

function loadPet(pet) {
  console.log(`OpenPets: loading ${pet.display_name} (${pet.id})`);
  const next = new Image();
  next.onload = () => {
    img = next;
    setState("idle");
    draw();
    if (!animationStarted) {
      animationStarted = true;
      requestAnimationFrame(tick);
    }
    if (!onboardingStarted) {
      onboardingStarted = true;
      startOnboarding();
    }
  };
  next.onerror = (e) =>
    console.error(`OpenPets: failed to load atlas for ${pet.id}`, e);
  next.src = convertFileSrc(pet.spritesheet);
}

async function init() {
  // Subscribe before the first activation so we never miss the initial event.
  await listen("pet-changed", (event) => {
    if (event.payload) loadPet(event.payload);
  });

  // External event source: hooks from Claude Code / Codex / Cursor write a
  // state name to ~/.openpets/state.json; the Rust watcher relays it as a
  // `pet-state-changed` event with the state name as the payload.
  await listen("pet-state-changed", (event) => {
    if (typeof event.payload === "string") {
      console.log(`OpenPets: external → ${event.payload}`);
      transitionToExternal(event.payload);
    }
  });

  await listen("attention-sound-changed", (event) => {
    attentionSoundEnabled = !!event.payload;
  });

  attentionSoundEnabled = await invoke("get_attention_sound").catch(() => false);

  const pets = await invoke("list_pets");
  if (pets.length === 0) {
    console.warn(
      "OpenPets: no pets found in ~/.codex/pets/. Install one first " +
        "(e.g. `npx petdex install phrolova`).",
    );
    return;
  }

  // Restore the previously-active pet from the persisted config; if the
  // user uninstalled it (or this is the first launch), fall back to the
  // first pet alphabetically.
  const persisted = await invoke("get_active_pet");
  const initialId = persisted?.id ?? pets[0].id;
  await invoke("set_active_pet", { id: initialId });
}

// Window drag uses a movement-threshold approach. Two earlier attempts both
// regressed: invoking start_dragging on every mousedown raced quick clicks
// (mouseup landed before AppKit's performWindowDrag, throwing an NSException
// Rust couldn't unwind); putting `data-tauri-drag-region` on the canvas
// blocked ALL canvas mouse events on macOS NSPanel + WKWebView, so neither
// drag nor right-click reached us.
//
// Recipe: on left-button mousedown, record the screen-coords origin. On
// mousemove past DRAG_THRESHOLD_PX, call startDragging() once — by then
// AppKit's drag tracker has a real mouse-still-down to lock onto, no
// NSException. Right-clicks and short clicks never enter this path, so
// contextmenu and click-to-wave both fire normally.
const DRAG_THRESHOLD_PX = 3;
let dragOrigin = null;
let dragInitiated = false;

canvas.addEventListener("mousedown", (e) => {
  if (e.button !== 0) return;
  dragOrigin = { x: e.screenX, y: e.screenY };
  dragInitiated = false;
});

// Listen on the canvas, not window/document: on a transparent NSPanel,
// mouse events over the transparent body area don't reach the WebView
// at all (they pass through to apps underneath). The first 3px of any
// drag is still over the pet sprite though, so this fires reliably.
canvas.addEventListener("mousemove", (e) => {
  if (!dragOrigin || dragInitiated) return;
  const dx = e.screenX - dragOrigin.x;
  const dy = e.screenY - dragOrigin.y;
  if (dx * dx + dy * dy < DRAG_THRESHOLD_PX * DRAG_THRESHOLD_PX) return;
  dragInitiated = true;
  currentWindow
    .startDragging()
    .catch((err) => console.error("startDragging failed:", err));
});

window.addEventListener("mouseup", () => {
  dragOrigin = null;
  // Defer the dragInitiated reset so the click handler (which fires AFTER
  // mouseup) can still tell drag-finish from a real click and suppress the
  // wave animation when the gesture was a drag.
  setTimeout(() => {
    dragInitiated = false;
  }, 0);
});

canvas.addEventListener("click", () => {
  // The mouseup that ended a drag also fires a click — ignore it.
  if (dragInitiated) return;
  // Any click during onboarding dismisses it — the user saw the hint.
  if (onboardingActive) {
    cancelOnboarding();
    return;
  }
  // While the inline menu is open, clicking the pet dismisses it
  // instead of triggering a wave.
  if (menuIsOpen) {
    closeInlineMenu();
    return;
  }
  setState("waving");
});

// ---------------------------------------------------------------------
// Inline right-click menu
// ---------------------------------------------------------------------
//
// We render the menu *inside the pet window itself* rather than opening
// a separate Tauri window. Two reasons:
//
//   1. Cross-Space visibility: the pet window is already pinned (NSPanel
//      + fullScreenAuxiliary at app startup). A child div inherits that
//      visibility for free, so the menu shows on full-screen Spaces.
//   2. Stability: opening a new transparent NSPanel mid-event-loop on
//      macOS 26 reliably aborts the app via NSException during the
//      class swap. Staying inside the existing panel sidesteps it.
//
// The window grows from 256x256 to 256x500 while the menu is visible so
// the menu has room below the pet sprite, then shrinks back on close.
// The pet's vertical position stays fixed because the body uses
// `align-items: flex-start` with a 24px top padding.

let menuIsOpen = false;
let pendingMenuHide = null;
// Set to true for ~300ms while the menu is opening — so the resize-induced
// transient blur (setSize 256→620) doesn't auto-close us right away.
let menuOpenGrace = false;
// If the pet sits near the screen bottom, growing to 256x500 can push
// the window off-screen and AppKit shifts it up. We snapshot the
// pre-open position and restore it after the menu collapses, so the
// pet ends up exactly where it started.
let savedWindowPosition = null;

function makeMenuItem(label, onClick, opts = {}) {
  const li = document.createElement("li");
  li.className =
    "menu-item" +
    (opts.checked ? " checked" : "") +
    (opts.danger ? " danger" : "");
  li.textContent = label;
  li.addEventListener("click", async (e) => {
    e.stopPropagation();
    closeInlineMenu();
    try {
      await onClick();
    } catch (err) {
      console.error(`menu action "${label}" failed:`, err);
    }
  });
  return li;
}

function makeSeparator() {
  const li = document.createElement("li");
  li.className = "menu-separator";
  return li;
}

function makeSectionLabel(text) {
  const li = document.createElement("li");
  li.className = "menu-section-label";
  li.textContent = text;
  return li;
}

async function buildMenuContent() {
  menuListEl.innerHTML = "";

  let pets = [];
  let persisted = null;
  let tools = [];
  let soundOn = false;
  try {
    [pets, persisted, tools, soundOn] = await Promise.all([
      invoke("list_pets"),
      invoke("get_active_pet"),
      invoke("list_tool_connections"),
      invoke("get_attention_sound"),
    ]);
  } catch (e) {
    console.error("buildMenuContent fetch failed:", e);
  }
  const activeId = persisted?.id;

  if (pets.length) {
    menuListEl.appendChild(makeSectionLabel("Pet"));
    for (const pet of pets) {
      menuListEl.appendChild(
        makeMenuItem(
          pet.display_name,
          () => invoke("set_active_pet", { id: pet.id }),
          { checked: pet.id === activeId },
        ),
      );
    }
    menuListEl.appendChild(
      makeMenuItem("Choose Pet…", () => invoke("show_picker_window_cmd")),
    );
    menuListEl.appendChild(makeSeparator());
  }

  if (tools.length) {
    menuListEl.appendChild(makeSectionLabel("Integrations"));
    for (const [id, label, connected] of tools) {
      menuListEl.appendChild(
        makeMenuItem(
          `Connect to ${label}`,
          () => invoke("set_tool_connection", { id, connected: !connected }),
          { checked: connected },
        ),
      );
    }
    menuListEl.appendChild(makeSeparator());
  }

  menuListEl.appendChild(makeSectionLabel("Settings"));
  menuListEl.appendChild(
    makeMenuItem(
      "Attention Sound",
      () => invoke("set_attention_sound", { enabled: !soundOn }),
      { checked: soundOn },
    ),
  );
  menuListEl.appendChild(makeSeparator());

  menuListEl.appendChild(
    makeMenuItem("Quit OpenPets", () => invoke("quit_app"), { danger: true }),
  );
}

async function openInlineMenu() {
  if (menuIsOpen) return;
  menuIsOpen = true;
  menuOpenGrace = true;
  setTimeout(() => {
    menuOpenGrace = false;
  }, 300);
  if (pendingMenuHide) {
    clearTimeout(pendingMenuHide);
    pendingMenuHide = null;
  }
  try {
    savedWindowPosition = await currentWindow.outerPosition();
  } catch (e) {
    savedWindowPosition = null;
  }
  // Tell Rust to ignore Moved events for the duration of the resize — when
  // the pet sits near the screen bottom AppKit shifts the window upward to
  // keep the new 500px height on screen, and we don't want that transient
  // shift saved as the user's chosen pet position.
  await invoke("set_menu_resizing", { resizing: true }).catch(() => {});
  try {
    await currentWindow.setSize(
      logicalSize(WINDOW_WITH_MENU.w, WINDOW_WITH_MENU.h),
    );
  } catch (e) {
    console.error("setSize (expand) failed:", e);
  }
  // Give AppKit one frame to settle any auto-shift before we re-enable
  // position persistence.
  setTimeout(() => {
    invoke("set_menu_resizing", { resizing: false }).catch(() => {});
  }, 50);
  await buildMenuContent();
  menuEl.hidden = false;
  // Trigger CSS transition on next frame so initial styles apply first.
  requestAnimationFrame(() => menuEl.classList.add("open"));
}

function closeInlineMenu() {
  if (!menuIsOpen) return;
  menuIsOpen = false;
  menuEl.classList.remove("open");
  // Wait for the fade-out before hiding the element and shrinking the
  // window — keeps the animation visible and avoids a content-shift jolt.
  pendingMenuHide = setTimeout(async () => {
    pendingMenuHide = null;
    if (menuIsOpen) return; // re-opened during the timeout
    menuEl.hidden = true;
    await invoke("set_menu_resizing", { resizing: true }).catch(() => {});
    try {
      await currentWindow.setSize(
        logicalSize(WINDOW_COMPACT.w, WINDOW_COMPACT.h),
      );
      if (savedWindowPosition) {
        await currentWindow.setPosition(savedWindowPosition);
      }
    } catch (e) {
      console.error("setSize/restore (shrink) failed:", e);
    }
    setTimeout(() => {
      invoke("set_menu_resizing", { resizing: false }).catch(() => {});
    }, 50);
    savedWindowPosition = null;
  }, 160);
}

document.addEventListener("contextmenu", (e) => {
  e.preventDefault();
  // Right-click during onboarding: dismiss the hint and show menu.
  if (onboardingActive) cancelOnboarding();
  if (menuIsOpen) {
    closeInlineMenu();
  } else {
    openInlineMenu();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && menuIsOpen) closeInlineMenu();
});

// In-WebView click outside #menu (e.g. on the pet itself, the bubble
// region) dismisses the menu. Clicks on transparent body areas don't
// reach the WebView at all on macOS NSPanel, which is why this alone
// isn't enough — see the focus listener below.
document.addEventListener("click", (e) => {
  if (!menuIsOpen) return;
  if (e.target.closest("#menu")) return;
  closeInlineMenu();
});

// Window-blur dismiss: clicking anywhere outside our window (other apps,
// the desktop, transparent regions of our own window) makes AppKit move
// keyboard focus away from us. Because the pet window is a non-activating
// NSPanel, click-through is the dominant mode of "user clicked elsewhere"
// — a plain `document.click` listener never sees those clicks. The Tauri
// onFocusChanged signal is the reliable proxy.
currentWindow.onFocusChanged(({ payload: focused }) => {
  if (!focused && menuIsOpen && !menuOpenGrace) closeInlineMenu();
});

init();
