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

const canvas = document.getElementById("pet");
const ctx = canvas.getContext("2d");
let img = new Image();

let state = "idle";
let frame = 0;
let lastFrameTime = 0;

function setState(name) {
  if (!STATES[name]) return;
  state = name;
  frame = 0;
  lastFrameTime = performance.now();
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
        setState(s.then);
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
      setState(event.payload);
    }
  });

  const pets = await invoke("list_pets");
  if (pets.length === 0) {
    console.warn(
      "OpenPets: no pets found in ~/.codex/pets/. Install one first " +
        "(e.g. `npx petdex install phrolova`).",
    );
    return;
  }

  // Default to the first pet; `set_active_pet` also stores it as the active
  // selection so the picker window can highlight it correctly.
  await invoke("set_active_pet", { id: pets[0].id });
}

// Window drag is invoked explicitly via a Rust command on mousedown. The OS
// then takes over the gesture: short presses without movement fall through
// to the `click` event (→ wave); presses with movement become a window drag.
canvas.addEventListener("mousedown", (e) => {
  if (e.button !== 0) return;
  invoke("start_drag").catch((err) => console.error("start_drag failed:", err));
});

canvas.addEventListener("click", () => setState("waving"));

init();
