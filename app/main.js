// OpenPets — minimal sprite animator for Codex-format pet atlases.
//
// Atlas contract: 1536x1872 image; 8 cols × 9 rows of 192×208 cells.
// Row → state mapping matches the Codex protocol implemented by the
// open-pet-creator Skill.

const { invoke, convertFileSrc } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

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
let img = new Image();

let state = "idle";
let frame = 0;
let lastFrameTime = 0;

// When the jumping pre-roll finishes, the tick loop transitions to this
// target instead of jumping's default `then: "idle"`. Used for the summon.
let pendingAfterIntro = null;
let resummonTimer = null;
let bubbleHideTimer = null;
let attentionSoundEnabled = false;

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

// Window drag is invoked explicitly via a Rust command on mousedown. The OS
// then takes over the gesture: short presses without movement fall through
// to the `click` event (→ wave); presses with movement become a window drag.
canvas.addEventListener("mousedown", (e) => {
  if (e.button !== 0) return;
  invoke("start_drag").catch((err) => console.error("start_drag failed:", err));
});

canvas.addEventListener("click", () => setState("waving"));

// Right-click anywhere in the window pops the same menu as the tray icon.
// The macOS menu bar frequently hides the tray icon when the bar is full,
// so this is the always-available path for switching pets, connecting
// Claude Code, toggling sound, and quitting. We listen on the document so
// the transparent corners around the pet are also valid right-click zones.
document.addEventListener("contextmenu", (e) => {
  e.preventDefault();
  invoke("show_context_menu").catch((err) =>
    console.error("show_context_menu failed:", err),
  );
});

init();
