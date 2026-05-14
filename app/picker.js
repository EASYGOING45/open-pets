// Pet picker — populates a grid of thumbnail cards from list_pets, lets the
// user click one to switch the main pet, then hides itself. Closes on Esc
// and on focus loss as well (focus-loss handled by the Rust side).

const { invoke, convertFileSrc } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const pickerWindow = window.__TAURI__.window.getCurrentWindow();

// Atlas contract: 1536x1872 image, 8 columns × 9 rows, cells 192x208.
// Idle frame for the thumbnail = top-left cell (0, 0). Each thumbnail is
// rendered at 64x70, so we scale the atlas by 64/192 ≈ 0.333.
const ATLAS_BG_W = 512; // 1536 * (64 / 192)
const ATLAS_BG_H = 624; // 1872 * (64 / 192)

const grid = document.getElementById("pet-grid");

function buildCard(pet, isActive, variantInfo) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "pet-card" + (isActive ? " is-active" : "");
  card.dataset.petId = pet.id;
  const variantSuffix =
    variantInfo && variantInfo.variant_id !== "normal" && variantInfo.recipe
      ? ` — ${variantInfo.display_name}`
      : "";
  card.title = (pet.description || pet.display_name) + variantSuffix;

  const thumb = document.createElement("div");
  thumb.className = "pet-thumb";
  const url = convertFileSrc(pet.spritesheet);
  thumb.style.backgroundImage = `url('${url}')`;
  thumb.style.backgroundPosition = "0 0";
  thumb.style.backgroundSize = `${ATLAS_BG_W}px ${ATLAS_BG_H}px`;

  // Sparkle ★ badge for pets whose user-rolled variant has the sparkle
  // effect. Indicates "you got something rare here".
  if (variantInfo && variantInfo.effects?.includes("sparkle")) {
    const badge = document.createElement("div");
    badge.className = "pet-badge-sparkle";
    badge.textContent = "★";
    thumb.appendChild(badge);
  }

  const name = document.createElement("div");
  name.className = "pet-name";
  name.textContent = pet.display_name;

  card.appendChild(thumb);
  card.appendChild(name);

  card.addEventListener("click", async () => {
    try {
      await invoke("set_active_pet", { id: pet.id });
      await pickerWindow.hide();
    } catch (err) {
      console.error("set_active_pet failed:", err);
    }
  });

  return card;
}

async function init() {
  let pets = [];
  let activeId = null;
  try {
    [pets, activeId] = await Promise.all([
      invoke("list_pets"),
      invoke("get_active_pet").then((p) => (p ? p.id : null)),
    ]);
  } catch (err) {
    console.error("picker init failed:", err);
  }

  grid.innerHTML = "";

  if (pets.length === 0) {
    const empty = document.createElement("div");
    empty.className = "pet-empty";
    empty.textContent = "No pets installed in ~/.codex/pets/";
    grid.appendChild(empty);
    return;
  }

  // Fetch variant info for every pet (parallel) so we can render badges.
  const variants = await Promise.all(
    pets.map((pet) =>
      invoke("get_pet_variant", { petId: pet.id }).catch(() => null),
    ),
  );

  pets.forEach((pet, i) => {
    grid.appendChild(buildCard(pet, pet.id === activeId, variants[i]));
  });
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    pickerWindow.hide();
  }
});

// If the user switches pet via the tray menu while the picker happens to be
// open, mirror the highlight without rebuilding the grid.
listen("pet-changed", (event) => {
  const newId = event.payload?.id;
  if (!newId) return;
  for (const card of grid.querySelectorAll(".pet-card")) {
    card.classList.toggle("is-active", card.dataset.petId === newId);
  }
});

init();
