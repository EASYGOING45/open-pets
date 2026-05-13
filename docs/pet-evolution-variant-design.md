# Pet Evolution & Variant System — Design Doc

> **Locked decisions (2026-05-13)**:
> - **Sprint scope**: Phase A (variants) + Phase B (stats tracking) in
>   parallel. Release & Restart escape hatch ships with Phase A.
> - **Variant weights**: 95 / 4 / 1 — locked across pets unless an
>   author has a deliberate reason to override.
> - **Cross-pet evolution chains**: chain *narrative* (which pet
>   evolves into which) is designed *later*, after more pets exist.
>   The maodou-specific branch example in §2.12 is illustrative of
>   the schema only — it is **not** the final lineup.

## Overview

Add "gotta catch 'em all" depth to OpenPets desktop companions:
**rare color variants** (异色 / 闪光) and **evolution chains** (进化),
inspired by Pokémon and Roco World.

Two fundamentally different mechanics, designed independently so either
can ship without the other:

| | Variant (异色 / 闪光) | Evolution (进化) |
|---|---|---|
| What changes | Color palette (recoloring of the same sprite) | Entire sprite — new pet identity |
| Needs new art | **No** (canvas filter; recipes in `pet.json`) | **Yes** (separate pet package) |
| When it triggers | Once, on first activation of a pet | After cumulative usage milestones |
| Rarity model | Weighted random roll | Threshold (turns / days / clicks) |
| State scope | Per-pet, persisted in `pet_state` | Per-pet, persisted in `pet_state` + replaces active pet |

§1 designs the variant system in full. §2 sketches evolution at a higher
level — that section is a Phase C concern and gets its own design pass
later.

---

## 1. Variant System — Random Color Variants

### 1.1 Goals & non-goals

**Goals**

- Each pet's first activation feels like opening a small loot box: ~95%
  you get the normal one, ~5% you get something that makes you say "ooh".
- Zero new art needed for variants — the pet author writes recipe
  values, never paints a recolored spritesheet.
- Per-pet authoring control: the author who knows their character's
  palette tunes the recipes, not a global "every pet gets +45° hue
  rotation" stamp.
- Variants persist for the lifetime of the pet identity (Pokémon
  model — your shiny is *yours*).

**Non-goals (Phase A)**

- Re-rolling. The whole point is the surprise of the first roll.
  Re-roll mechanics are deferred behind a future "Release Pet" action
  with a confirmation dialog.
- Per-region or per-frame palette edits. We're recoloring the whole
  sprite uniformly. Frame-by-frame palette work belongs in the Skill
  repacker, not the runtime.
- Cross-pet variant trading or marketplaces. Single-user local app.
- Cheating prevention. Editing `~/.openpets/config.json` to give
  yourself shiny is allowed — there's no leaderboard, the user's fun
  is theirs to define.

### 1.2 Color transformation: tech selection

Four candidate paths, scored against the criteria that matter for this
app:

| Path | WKWebView compat | Author iterability | Runtime perf | Palette-swap precision | Implementation cost |
|---|---|---|---|---|---|
| **A. Canvas2D `ctx.filter` w/ chained CSS filter functions** | ✅ Safari 16.4+ (macOS 13.3+) | ✅ tweak number, see result | ✅ GPU-composited | ⚠ limited to hue / saturate / brightness / contrast / sepia / grayscale | low |
| B. Canvas2D `ctx.filter = "url(#svg-id)"` referencing SVG `feColorMatrix` | ⚠ historically buggy on WebKit; risky | ✅ matrix is fully expressive | ✅ GPU | ✅ arbitrary 4×5 matrix | medium |
| C. Pre-bake variant spritesheets at install time (Python repacker pass) | ✅ no runtime concerns | ⚠ regenerate to iterate | ✅ best (no per-frame work) | ✅ full PIL toolchain (HSL remap, palette quantize, channel ops) | high (new repacker pass + multiple webp per pet + load logic) |
| D. Runtime LUT remap via `getImageData` / `putImageData` | ✅ universal | ⚠ author thinks in lookup tables | ❌ per-frame CPU pass | ✅ exact pixel control | medium-high |

**Choice: A.** Lowest-cost path that meets the goals. The limitation
(only ~6 named filter functions) is *fine* for the "swap palette by
~20°" effect we're aiming for. Hue-rotate happens to suit anime-style
chibi sprites well — most palette-swap effects in the source material
*are* hue rotations, and grayscale (R=G=B) pixels are unaffected by
hue-rotate, so white hair stays white.

Why not the others:

- **B (SVG `feColorMatrix`)**: WebKit's history of buggy `ctx.filter
  = url(...)` makes this a risky bet. We'd ship and find a Sonoma
  user has a broken pet. Not worth the matrix expressiveness for
  Phase A.
- **C (pre-bake)**: This is the *right* path if any pet ends up
  needing palette swaps that hue-rotate can't express (e.g., "swap
  the red ribbon to green but leave the white hair white"). We'll
  add it as **Phase A+1** if we hit a recipe we can't compose with
  chained filters. Not blocking.
- **D (LUT remap)**: All the runtime cost of B with none of the
  author convenience. Skip.

**WKWebView caveats locked in:**

- `ctx.filter` is supported as **string-form chained filter functions
  only**. Do not use `ctx.filter = "url(#…)"` regardless of how
  expressive the matrix would be.
- Allowed filter functions: `hue-rotate(deg)`, `saturate(n)`,
  `brightness(n)`, `contrast(n)`, `sepia(n)`, `grayscale(n)`. Avoid
  `blur` / `drop-shadow` / `invert` (none of them help recoloring).
- `clearRect` is unaffected by `ctx.filter`, so we don't need to
  toggle filter off for canvas clears.
- Setting `ctx.filter` once per pet load is enough — it persists
  across draw calls. No per-frame state thrash.
- **Sparkle particles must NOT be drawn on the pet canvas** — they'd
  inherit the recoloring filter. Use a sibling DOM layer (§1.5).

### 1.3 Recipe schema

Authors write structured recipes; we compile to filter strings in
deterministic order. This means:

- Authors can't typo `"hue-rotate(45deg)"` into something that silently
  no-ops.
- We can validate at install time / first load.
- The compile is one line: `hue-rotate → saturate → brightness →
  contrast → grayscale → sepia` (omitted ops skipped).

```jsonc
{
  "id": "rocom-maodou",
  "displayName": "Maodou",
  "spritesheetPath": "spritesheet.webp",

  "variants": [
    {
      "id": "normal",
      "weight": 95,
      "displayName": { "zh": "普通毛豆", "en": "Maodou" }
    },
    {
      "id": "rose",
      "weight": 4,
      "displayName": { "zh": "蔷薇毛豆", "en": "Rosé Maodou" },
      "recipe": { "hue_rotate": 25, "saturate": 1.25 }
    },
    {
      "id": "moonlight",
      "weight": 1,
      "displayName": { "zh": "月光毛豆", "en": "Moonlight Maodou" },
      "recipe": { "hue_rotate": 200, "saturate": 1.4, "brightness": 1.08 },
      "effects": ["sparkle"]
    }
  ]
}
```

Field rationale:

| Field | Why |
|---|---|
| `id` (string, stable) | Persisted in `pet_state` — renaming `displayName` mustn't lose the user's roll. |
| `weight` (positive int) | Integer math, no float-rounding bugs. Normalized to sum at roll time. Easier mental model than `chance: 0.04`. |
| `displayName.{zh, en}` | Bubble + Petdex display both. Defaults: if missing, fall back to `id`. |
| `recipe.{hue_rotate, saturate, brightness, contrast, grayscale, sepia}` | Each absent → omitted from filter chain. Recipe missing entirely → no filter (i.e., `ctx.filter = "none"`). |
| `effects[]` | Open array for future polish (sparkle, glow, particle bursts). Phase A only ships `"sparkle"`. |

Defaults & escape hatches:

- `variants` array missing or empty → implicit single `normal` variant
  (weight 100, no recipe, no effects). Existing pets work without
  modification.
- `filter_override: "..."` (raw CSS filter string) — escape hatch for
  pet authors who want a chained sequence we don't compile (e.g.,
  reordered ops, a `hue-rotate` in the middle of two `saturate` calls).
  Validated against the same allowed-functions list. Documented but
  discouraged — it bypasses the compile-time guarantees.

**Recipe → filter string examples (the compile output):**

| Recipe | Filter string |
|---|---|
| `{}` | `none` |
| `{ "hue_rotate": 25 }` | `hue-rotate(25deg)` |
| `{ "hue_rotate": 200, "saturate": 1.4, "brightness": 1.08 }` | `hue-rotate(200deg) saturate(1.4) brightness(1.08)` |
| `{ "saturate": 0.6, "sepia": 0.3 }` | `saturate(0.6) sepia(0.3)` |

### 1.4 Roll mechanics & persistence

**When the roll fires**: the *first* time a pet becomes the active pet
(in `set_active_pet`, if `pet_state` has no entry for this id). Not at
install — installing 5 pets up-front shouldn't pre-roll all 5 variants.
The user "discovers" each pet by activating it.

**Algorithm** (Rust):

```rust
let total: u32 = variants.iter().map(|v| v.weight).sum();
let mut r = thread_rng().gen_range(0..total);
for v in &variants {
    if r < v.weight { return v.id.clone(); }
    r -= v.weight;
}
```

**Persistence shape** (extension to `OpenPetsConfig` in
`app/src-tauri/src/main.rs`):

```rust
#[derive(Serialize, Deserialize, Clone, Default)]
struct OpenPetsConfig {
    // ... existing fields (active_pet_id, window_position,
    //                       attention_sound, onboarding_done) ...
    #[serde(default)]
    pet_state: HashMap<String, PetRollState>,
}

#[derive(Serialize, Deserialize, Clone)]
struct PetRollState {
    variant_id: String,
    rolled_at: String,    // ISO 8601 UTC
    revealed: bool,       // false until JS plays the celebration animation
}
```

**Why `revealed` exists**: the roll happens in Rust before JS knows
about it. The first time JS reads pet state with `revealed=false`, it
plays the celebration (§1.6), then calls `mark_variant_revealed`. If
the app is killed between roll and reveal, the celebration plays on
next launch. **The user always gets their moment.**

**Re-roll for Phase A: none.** A pet's variant is permanent. We
document the design intent ("the surprise loses meaning if it's
rerollable"). A future "Release Pet" action would clear the
`pet_state` entry behind a confirmation dialog.

### 1.5 Effects layer (sparkles)

Sparkles render in a **separate DOM layer**, not on the pet canvas.
This avoids inheriting the variant's `ctx.filter` and keeps the
particle scheduler decoupled from the pet animation tick.

```html
<!-- index.html -->
<canvas id="pet"></canvas>
<div id="sparkle-layer"></div>
```

```css
#sparkle-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}
.sparkle {
  position: absolute;
  width: 8px;
  height: 8px;
  background: radial-gradient(circle, #fff 0%, #fff8 50%, transparent 100%);
  border-radius: 50%;
  animation: sparkle 1.2s ease-out forwards;
}
@keyframes sparkle {
  0%   { transform: scale(0);   opacity: 0; }
  30%  { transform: scale(1);   opacity: 1; }
  100% { transform: scale(0.4) translateY(-8px); opacity: 0; }
}
```

JS helper:

```js
function spawnSparkle(x, y) {
  const el = document.createElement("div");
  el.className = "sparkle";
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  document.getElementById("sparkle-layer").appendChild(el);
  el.addEventListener("animationend", () => el.remove(), { once: true });
}
```

Triggers (only fire if active variant's `effects` includes `"sparkle"`):

| Trigger | Behavior |
|---|---|
| **First reveal** (`revealed=false`) | 12-particle ring around the pet's bbox center, 200ms after pet first appears |
| **Idle ambient** | 3 particles at random positions over the pet's bbox, every 8–20s during idle. Throttled — never two bursts inside 5s |
| **Click-to-wave celebration** | Single-particle pop on entering `waving` after a click — clicking a shiny pet should feel rewarding |

### 1.6 Discoverability & celebration UX

The user must *know* they got something rare. Three layers:

**1. First-reveal moment** (one-time, gated by `pet_state[id].revealed`):

| Variant tier | First-reveal behavior |
|---|---|
| Normal (no recipe) | Silent. Pet just appears. |
| Rare (recipe present, no `sparkle` effect) | Bubble: `"{displayName}"` for 3s. No burst, no sound. A small but genuine "oh, you got the rare color" moment. |
| Shiny (recipe + `effects: ["sparkle"]`) | 200ms idle, then sparkle burst (12 particles), then bubble: `"✨ {displayName} ({weight*100/total}%)"` for 4s. Optional sound (gated by existing `attention_sound` config). |

After the bubble fades, JS calls `mark_variant_revealed` and Rust
persists `revealed=true`. The reveal is one-shot per pet identity.

**2. Re-discoverability** (anytime, post-reveal):

- **Right-click menu**: under the pet's name line, append
  `"({variant displayName})"` if variant != normal.
- **Picker grid tile**: small ⭐ badge in top-right of each tile whose
  pet has a sparkle-effect variant rolled. For rare-tier (no sparkle),
  no badge — the recolor itself is the badge.
- **Future Petdex card**: "Caught: {rolled_at}", variant displayName,
  weight % printed.

**3. Escape hatch — what if a variant looks bad on a pet?**

The pet author owns recipe quality. But the user might disagree
(e.g., "the moonlight palette looks ugly on my desktop"). Phase A
behavior: no per-user override. If a user truly hates their roll,
they can edit `~/.openpets/config.json` and change `variant_id` —
it's a single-user app, no harm. We document this in the user-facing
README.

A "Hide variant filter (just for me)" toggle in the right-click menu
is a possible Phase B addition — but not before we have evidence
anyone wants it.

### 1.7 Pet-author workflow & the preview tool

Without a preview tool, recipe authoring is "edit pet.json → restart
app → roll the dice repeatedly until you get the variant → squint".
That's awful. **The preview script is the load-bearing tool of Phase
A** — it must ship before any pet gets variants.

`open-pet-creator/scripts/preview_variants.py`:

```bash
$ python3 open-pet-creator/scripts/preview_variants.py pets/rocom-maodou/

# Reads pet.json, extracts the idle frame from spritesheet.webp,
# applies each variant's recipe in PIL, composites a side-by-side
# grid with captions.
# Saves to pets/rocom-maodou/variants-preview.png and `open`s it.
```

Author workflow:

1. Eyeball the source sprite. Decide on 2–3 variant directions
   (warm shift, cool shift, monochrome, etc.).
2. Add `variants` to pet.json with placeholder recipes.
3. Run the preview script.
4. Get a preview PNG: idle frame on the left, each variant rendered
   to its right, with the recipe formula and weight as caption.
5. Iterate on recipe values until each variant looks like a deliberate
   alternate skin, not a render bug.
6. Ship.

PIL implementation of `apply_recipe(image, recipe) -> image`:

| Filter function | PIL implementation |
|---|---|
| `hue_rotate(deg)` | Convert RGBA → HSV, add `deg/360` to H mod 1, convert back, restore A. |
| `saturate(n)` | Blend with grayscale image: `n<1` → blend toward gray; `n>1` → extrapolate away. |
| `brightness(n)` | Per-pixel `RGB *= n`, clamp 0..255. Alpha untouched. |
| `contrast(n)` | `(p-128)*n + 128`, clamp. Alpha untouched. |
| `sepia(n)` | Blend toward sepia matrix `[0.393 0.769 0.189; 0.349 0.686 0.168; 0.272 0.534 0.131]` at weight n. |
| `grayscale(n)` | Blend toward L-channel duplicated to RGB at weight n. |

These are all single-pass PIL ops. The output matches what the canvas
filter renders at runtime — CSS filter functions are defined to match
these well-known image ops, so author-time preview equals runtime
look.

### 1.8 Cross-system interactions

| Interaction | Rule |
|---|---|
| Variant × Evolution | `variant_id` carries through evolution chains. Stage-2 looks up the same id in its own `variants`; if absent, falls back to stage-1's recipe stored in pet_state. Shiny + evolution combines celebrations (see §2.7 + §2.9). |
| Variant × Picker | Picker tile shows a ⭐ badge for variants whose `effects` includes `"sparkle"`. Hover tooltip shows variant displayName + caught date. |
| Variant × Right-click menu | Pet name line shows `"({displayName})"` suffix for non-normal variants. |
| Variant × State machine | Variants are pure visual recoloring — they don't gate any states. A `waiting`/`review`/`failed` pet looks the same modulo the recoloring. |
| Variant × Bubble UI | Bubble color and pulse animation unchanged. Bubble *content* gets a `"✨"` prefix on shiny first-reveal only. |
| Variant × Onboarding | First-launch onboarding bubbles play *before* the variant celebration. Variant celebration is queued and plays after onboarding completes. |
| Backfill (existing pet, new variants array) | On next `set_active_pet`, the pet rolls — same code path as a brand-new pet. Existing users get the variant moment when they reactivate the pet. |
| Hot-reload (pet.json edited while running) | Out of scope. App restart picks up the new variants array; existing rolls persist. |

### 1.9 Phase A implementation checklist (ordered)

1. **Preview script first.** `open-pet-creator/scripts/preview_variants.py`
   plus `apply_recipe(pil_image, recipe)` helper. Without this,
   step 2 is blind.
2. **Pet.json: declare variants on `rocom-maodou`** (the cutest pet,
   easiest to validate the visual). Use the schema in §1.3. Iterate
   with the preview script until each variant looks deliberate.
3. **Rust: extend `OpenPetsConfig`** with
   `pet_state: HashMap<String, PetRollState>`. `#[serde(default)]` for
   backwards compat with existing config.json files.
4. **Rust: roll on first activation.** In `set_active_pet`, after
   loading the pet, check if `pet_state` has this id. If not, parse
   the pet's `variants` array, run the algorithm in §1.4, persist.
5. **Rust: new Tauri commands**
   - `get_pet_variant(pet_id) -> Option<{ variant_id, recipe,
     display_name, weight_pct, effects, revealed }>` for JS to consume
     on pet load.
   - `mark_variant_revealed(pet_id) -> ()` for JS to call after the
     celebration animation.
   - Add both to `capabilities/default.json` if needed (custom
     commands aren't gated, but list them for hygiene).
6. **JS: read variant on pet load.** In the pet-load path
   (`app/main.js`, after `convertFileSrc`), fetch variant info,
   compile recipe → filter string, set `ctx.filter` once.
7. **JS: sparkle layer.** Add `<div id="sparkle-layer">` to
   `index.html`. Add `spawnSparkle(x, y)` helper. Wire to (a) reveal
   moment, (b) idle ambient timer (8–20s, only if effects contain
   `"sparkle"`), (c) `waving` transition for sparkle variants.
8. **JS: first-reveal celebration.** If `revealed=false`, queue the
   tier-appropriate animation (table in §1.6), then call
   `mark_variant_revealed`. Honor onboarding-first ordering.
9. **JS: right-click menu suffix.** Append
   `"({variant displayName})"` to the pet name line in
   `buildMenuContent` for non-normal variants.
10. **JS: picker tile badge.** ⭐ overlay top-right of each tile whose
    pet has a sparkle-effect variant rolled.
11. **Test: state machine doesn't regress.** `pytest tests/`. Variant
    changes should be invisible to the state-machine tests.
12. **Test: backfill manual.** `rm ~/.openpets/config.json`, launch
    app, switch to maodou — verify roll fires, celebration plays,
    persists, and survives restart with `revealed=true`.
13. **Release & Restart action.** Tray menu item "Release {pet}…"
    behind a confirmation dialog ("This permanently resets {pet}'s
    variant + stats. Cannot be undone."). On confirm: clear this
    pet's `pet_state` + `pet_stats` entries; next activation re-rolls
    the variant. Document in the tray-menu section of `app/README.md`.
14. **Bump `BUILD_TAG`** in `main.rs` so the user retests against the
    new embed.

### 1.10 Open questions

- **Default variant pool for pets without explicit `variants`?**
  Phase A: no. Pets opt in. A "tasteful default pool" needs careful
  per-pet tuning — too risky to apply blindly across all pets.
- **Should the rolled_at timestamp be visible to the user?** Phase A:
  hidden in config. Phase B: shown in Petdex once Petdex exists.
- **Variant id namespace — global or per-pet?** Per-pet.
  `rocom-maodou.shiny` and `phrolova.shiny` are independent; nothing
  references variants across pets.
- **Variant migration for already-rolled users when pet.json
  variants change?** The existing roll sticks. Document that new
  variants only reach users who haven't rolled yet (or who manually
  clear pet_state).
- **Reduced-motion accessibility?** Sparkle ambient is the most
  motion-heavy element. Phase B: gate on
  `prefers-reduced-motion` media query (skip ambient sparkles, keep
  reveal burst at half particle count).

---

## 2. Evolution System — Pet-to-Pet Progression

Evolution is the *narrative arc* of long-term pet ownership: your
companion changes shape based on how you've used the AI tool with
them. Where variants (§1) are a one-time roll, evolution is the
shape your daily coding leaves on the pet.

### 2.1 Goals & non-goals

**Goals**

- Evolution should feel *earned* — based on real usage signals, not
  a single arbitrary counter.
- Branches should be **expressive of how you used the pet** — a
  morning coder gets a sunward form; a night owl gets a moonlit one;
  someone who lets the pet sit serenely on the desktop for weeks
  earns a "sage" form.
- Some branches are **discoverable** (visible in progress UI), some
  are **secret** (pure surprises). Both have a place.
- Pet authors describe chains in **data only** (no code). The runtime
  ships a library of condition primitives; authors compose them.
- The animation should make evolution feel like a *moment* — you'll
  remember when your pet evolved.

**Non-goals**

- Combat / battle / party mechanics. We're a coding companion, not a
  game. (~70% of Pokémon's surface mechanics get rejected here.)
- "Stones" or item drops. There's no inventory in OpenPets and no
  natural place for items to come from.
- Trading / multiplayer. Single-user local app.
- Reversal of completed evolution. Permanent decisions are
  meaningful; a "Release & restart" escape hatch exists for users
  who want a clean slate (clears all stats, starts the chain over).
- Punishment-based mechanics ("your pet will die if you don't open
  the app"). Following Yu-kai Chou's framework, neglect can *unlock*
  a different branch but never destroys progress.

### 2.2 What we borrow vs. reject from each model

| Model | Borrowed | Rejected |
|---|---|---|
| **Pokémon** | Multi-trigger system; Eevee-style branching (one species → 8 forms based on conditions); time-of-day branching; visible vs. hidden conditions | Combat, party composition, trading, stones, EVs/IVs |
| **Tamagotchi** | Care-quality affecting branch outcome (mapped to "attention responsiveness"); life-stage discrete progression | Care-mistakes-kill-the-pet; need bars; sleep cycles |
| **Digimon** | Multi-axis stats branching; "the path you took shapes the form"; permanent commitment to the chosen branch | Combat stats; weight/feeding minigames |
| **洛克王国 (Roco World)** | "Selective release" idea (user agency in shaping the form); time-of-day / weather conditions; sprite-self-determination ideas | Battle stats per se; gender-locked branches |
| **Nanomon (2025)** | "What you give the pet shapes its form" — we substitute "how you code" for "what you feed"; multiple final-form variety as a Petdex incentive | Death-on-final-evolution mechanic |
| **Yu-kai Chou framework** | Delight + unpredictability over guilt; CD7 (unpredictability) via secret branches; CD2 (development) via visible progress | Pure punishment loops; loss-aversion as primary driver |

### 2.3 The usage signature — what we track

Every signal is derived from events we *already* receive (state-machine
transitions + clicks + time). No new instrumentation needed — `pet_stats`
just maintains rolling counters.

| Axis | What it counts | Source |
|---|---|---|
| `total_turns` | UserPromptSubmit count | Claude Code hook → `running` state entry |
| `days_active` | Distinct local-time calendar days the pet has been active | Calendar diff at every state change |
| `total_clicks` | Canvas left-clicks (excluding drags below threshold) | JS canvas event |
| `total_waves` | `waving` state entries (post-click celebrations) | State machine |
| `failures_seen` | `failed` state entries | Claude Code PostToolUseFailure hook |
| `attention_seen` | `review` + `waiting` state entries | Hook |
| `attention_responded` | Of those, how many the user dismissed within 30s | JS-side correlation, persisted to Rust |
| `turn_buckets` | Histogram of turns by time-of-day (morning/afternoon/evening/night) and weekday/weekend | Local time at event |
| `idle_seconds` / `active_seconds` | Time spent in each major state class | Tick-loop accumulator (sampled every 5s) |
| `recent_active_at` | Timestamp of last state change | Always-updated |

Time-of-day buckets (local time, default boundaries):

- `morning`: 06:00–11:59
- `afternoon`: 12:00–17:59
- `evening`: 18:00–22:59
- `night`: 23:00–05:59

Boundaries can be overridden per condition (an author who wants "deep
night coder" can specify custom hours).

### 2.4 Condition DSL — the building blocks

Authors compose evolution conditions from a fixed library. Small
enough to be exhaustive — no string-templated escape hatches — so we
can validate every chain at install time.

| Condition type | Fields | True when |
|---|---|---|
| `turns` | `min`, optional `max` | `min ≤ total_turns ≤ max` |
| `days_active` | `min` / `max` | `min ≤ days_active ≤ max` |
| `clicks` | `min` / `max` | self-evident |
| `waves` | `min` / `max` | self-evident |
| `failures` | `min` / `max` | self-evident |
| `time_of_day_ratio` | one of `{morning,afternoon,evening,night}_pct_min` (or `_max`) | bucket / total_turns ≥ pct_min |
| `weekday_ratio` | `weekday_pct_min` / `weekday_pct_max` | weekday-bucket ratio |
| `attention_responsiveness` | `min`, `max`, optional `min_attention_seen` (sample-size floor) | `attention_responded / attention_seen ≥ min`, requires sample size to avoid early-game flukes |
| `click_rate` | `clicks_per_day_min` / `clicks_per_day_max` | `total_clicks / days_active` |
| `recent_activity` | `days_since_last_max` (presence) or `days_since_last_min` (anti-presence) | seconds-to-days diff |
| `composite_or` | `of: [<condition>, ...]` | any sub-condition holds |

Each branch's `conditions` field is an implicit AND of the listed
items. `composite_or` is the only way to express OR — it nests inside
a branch's `conditions` array.

**Sample-size guards (`min_attention_seen`)**: ratio-based conditions
need a sample-size floor or they fire on day 1 from a single event.
This is the Pokémon-Go lesson: your "preferred buddy distance" can't
be inferred from one walk.

### 2.5 Branching schema

Each pet declares 0+ branches in priority order. **First match wins.**
Pets with zero branches are final forms.

```jsonc
{
  "id": "rocom-maodou",
  "displayName": "Maodou",
  "spritesheetPath": "spritesheet.webp",

  "evolution": {
    "stage": 1,
    "branches": [
      {
        "to": "rocom-maodou-sunward",
        "label": { "zh": "晨曦毛豆", "en": "Sunward Maodou" },
        "conditions": [
          { "type": "turns", "min": 100 },
          { "type": "time_of_day_ratio", "morning_pct_min": 0.55 }
        ]
      },
      {
        "to": "rocom-maodou-moonlit",
        "label": { "zh": "月夜毛豆", "en": "Moonlit Maodou" },
        "conditions": [
          { "type": "turns", "min": 100 },
          { "type": "time_of_day_ratio", "evening_pct_min": 0.55 }
        ]
      },
      {
        "to": "rocom-maodou-sage",
        "label": { "zh": "帽兜贤者", "en": "Hooded Sage" },
        "conditions": [
          { "type": "days_active", "min": 14 },
          { "type": "click_rate", "clicks_per_day_max": 1.5 }
        ],
        "secret": true,
        "unlocks": "你给了我空间。"
      },
      {
        "to": "rocom-maodou-wild",
        "label": { "zh": "野毛豆", "en": "Wild Maodou" },
        "conditions": [
          { "type": "failures", "min": 10 },
          { "type": "turns", "min": 50 }
        ],
        "secret": true,
        "unlocks": "我们一起穿过了风暴。"
      }
    ]
  }
}
```

**Why first-match-wins (vs. priority-by-best-fit)**:

- Predictable. The chain author orders branches; the order *is* the
  precedence.
- Conditions can specify `min` AND `max` so authors write
  mutually-exclusive bands without runtime tie-breaking.
- Easy to test deterministically.

**Branch-level fields**:

| Field | Purpose |
|---|---|
| `to` (pet id) | Target form. Must be installed; chain validator catches missing. |
| `label.{zh, en}` | Used in evolution celebration bubble + Petdex. |
| `conditions[]` | Implicit AND. Empty array = always fires (sentinel "default" branch — order it last). |
| `secret` (default false) | Hidden from progress UI / Petdex hints until first triggered (anywhere — once any pet's secret branch fires, future pets show a "?" placeholder slot). |
| `unlocks` (string, optional) | Free-text "earned" message shown in Petdex when first triggered. Defaults to label. |

### 2.6 Evaluation timing & the idle queue

Evaluating "did anyone evolve?" on every event is wasteful (most events
are mid-task). The runtime checks at three deliberate moments:

1. **State transitions to `idle`** — natural pause; the user just
   finished a turn or dismissed an attention prompt.
2. **SessionEnd hook** — Claude Code closed; user is between tasks.
3. **App startup** — for pets that crossed the threshold while the
   app was off.

```rust
fn check_evolution(stats: &PetStats, branches: &[Branch]) -> Option<&Branch> {
    branches.iter()
        .find(|b| b.conditions.iter().all(|c| evaluate(c, stats)))
}
```

If a branch is eligible, **do not interrupt the current pet state**.
Instead, set `pending_evolution = Some(branch_index)` in the persisted
config and let the JS-side animation play on the next idle moment.

This means:

- A user mid-task isn't yanked out of `running` to watch a 6-second
  cinematic.
- The pending evolution survives app restart (it's persisted).
- The user always gets their moment, on their terms.

### 2.7 Animation & celebration

The evolution sequence is the most dramatic visual moment in the app.
Six phases over ~6 seconds:

| Phase | Duration | Visual | Bubble |
|---|---|---|---|
| **0. Anticipation** | 0 ms | Pet enters `jumping` from idle | "{Pet} feels different…" |
| **1. Charge-up** | 2000 ms | Pet stays in `jumping` row at 0.4× speed; `ctx.filter = "brightness(N)"` pulses N ∈ [1.0, 1.4] every 400ms; window shake at low amplitude (3px) | "Evolving…" |
| **2. Peak flash** | 600 ms | `ctx.filter = "brightness(2.0)"`; CSS `transform: scale(1.05)`; shake stops; sparkle burst (16 particles ring) | (none) |
| **3. Reveal** | 0 ms (instant swap) | `img.src` swaps to new pet's spritesheet; `ctx.filter` resets to new variant's recipe | (none) |
| **4. Reveal jump** | 800 ms | New pet plays `jumping` oneshot; bubble visible | "→ {new label}!" |
| **5. Settle** | 4000 ms | Pet enters idle; bubble holds, then fades | (fades after 4s) |

The shake is gated by the existing `is_shaking` flag so it doesn't
persist as the user's window position.

**Secret-branch discovery toast**: 1 second after Phase 5 starts, if
the branch was `secret`, an extra toast appears for 5 seconds:
`"✨ Discovered: {label} — {unlocks}"`. This is the surprise payoff.

**Shiny + evolution combined celebration**: if the user is on a
sparkle-effect variant, Phase 2's burst doubles to 32 particles, and
the optional sound plays (gated by `attention_sound`).

### 2.8 Progress visibility — the right-click menu line

When the pet is mid-chain, the right-click menu shows a "Progress to
evolution" line. The line shows the **most-advanced non-secret branch**
(so the user has a clear target without spoilers):

```
Maodou (晨曦 path)
Progress: 73 / 100 turns · morning streak 58 %
```

Algorithm: for each non-secret branch, compute "% of conditions
satisfied" as the min across its conditions (so a branch is "100%
ready" only when every condition holds). Pick the branch with highest
%. Display its label and the most-relevant unsatisfied condition.

For final forms (no `branches` or all branches' conditions exclusive):

```
Maodou (final form)
```

Secret branches don't appear in this UI — they contribute only to the
actual fire check.

### 2.9 Variant × Evolution: the rules in detail

Updating §1.8's row with concrete rules:

1. **`variant_id` carries through.** When `rocom-maodou` evolves into
   `rocom-maodou-sunward`, the variant id ("normal" / "rare" /
   "shiny" / etc.) carries over.
2. **Recipe lookup falls back through the chain.** Stage-2's `variants`
   array is consulted for the same id; if absent, fall back to the
   recipe stored in pet_state from stage-1. Stage-2 authors choose:
   re-tune per variant, or inherit silently.
3. **`revealed=true` carries through.** No replay of the variant
   celebration — the evolution celebration is its own moment.
4. **Shiny + evolution = combined celebration.** See §2.7.
5. **Two timestamps: `rolled_at` vs. `evolved_at`.** The pet's
   "caught" date stays as rolled_at (when you first met them);
   evolved_at is when the chain advanced. Petdex can show both.
6. **Stats reset at evolution**, except `previous_form` which records
   the prior id. Counters start fresh for the new form.

### 2.10 Authoring workflow

A pet author shipping a chain produces N pet packages (one per stage).
The Skill repacker doesn't change — each stage is independently packed.

1. **Design on paper.** Decide stages, branches, conditions. Write
   what each branch *means narratively* (this is the storytelling
   work; conditions are just the in-game vocabulary for the story).
2. **Generate art per stage.** Stage-1 → stage-2 art should share
   visual language (so it feels like the same character) but differ
   enough that evolution is *visible*.
3. **Pack each stage** as a normal pet (1536×1872 atlas, Skill
   repacker).
4. **Wire `evolution.branches`** into stage-1's pet.json. For
   mid-chain stages, optionally add their own evolution block. Final
   forms have no evolution block.
5. **Run the chain validator**:
   ```
   $ python3 open-pet-creator/scripts/check_chain.py rocom-maodou
   ✓ Chain root: rocom-maodou
   ✓ Branches: sunward, moonlit, sage [secret], wild [secret]
   ✓ All targets installed
   ✓ No cycles
   ✓ All conditions parse
   ```
6. **Optional preview**:
   ```
   $ python3 open-pet-creator/scripts/preview_chain.py rocom-maodou
   ```
   Outputs a PNG: stage-1 thumbnail + arrow + branch thumbnails
   side-by-side, captioned with label + (non-secret) conditions.

The validator is **mandatory**. Without it, a typo in `branches[].to`
becomes a runtime "evolution to nonexistent pet" error visible to the
user as "my pet vanished".

### 2.11 Chain validator rules (`check_chain.py`)

Reject chains that fail any of:

1. **Target installed**: every `branches[].to` resolves to an
   installed pet (presence in `~/.codex/pets/<id>/pet.json`).
2. **No cycles**: walk the chain graph; reject if any path revisits
   a pet.
3. **No orphaned mid-chain pets** (warning, not error): every pet
   with `evolves_from` set should be reachable from at least one
   chain root. Warning because authors may be working piecemeal.
4. **Conditions parse**: every condition's `type` is in the library;
   every required field is present and well-typed.
5. **At most one default-branch**: only the last branch may have
   empty `conditions`; earlier empty-condition branches would
   short-circuit unreachable later branches.
6. **Variant id parity (warning)**: if both stages declare variants,
   warn on variant ids that exist in one stage but not the other.

### 2.12 Schema example: the Maodou chain (illustrative only)

> **Not a product commitment.** Per the locked decision in the doc
> header, the actual evolution lineup will be designed *across pets*
> later, once we have a fuller cast. This section exists only to show
> what a populated `evolution.branches` block looks like.

```
                      rocom-maodou (Stage 1)
                              │
        ┌─────────────────┬───┴─────┬───────────────────┐
        ▼                 ▼         ▼                   ▼
 sunward (晨曦)      moonlit (月夜)  sage [secret]   wild [secret]
 turns ≥ 100         turns ≥ 100    days ≥ 14       failures ≥ 10
 morning ≥ 55%       evening ≥ 55%  ≤ 1.5 click/d   turns ≥ 50
```

Narrative intent for each branch (the author's job — these inform art
direction):

- **晨曦毛豆 / Sunward Maodou** — bright, sun-themed palette. Earned
  by morning coders. Implies: "you start your day with me."
- **月夜毛豆 / Moonlit Maodou** — cool, lunar palette, sleepy
  expression. Earned by night coders. Implies: "we burn the
  midnight oil together."
- **帽兜贤者 / Hooded Sage** — secret. Larger, calmer pose. Earned by
  users who let the pet sit on the desktop for two weeks but rarely
  click it. Implies: "you didn't pet me — you trusted me to be
  there."
- **野毛豆 / Wild Maodou** — secret. Wilder fur, mischievous
  expression. Earned by users with frequent failures. Implies:
  "we've been through chaos together."

Stage 2 → Stage 3 chains can be added later; for Phase C, all four
stage-2 forms are final.

### 2.13 Phase C implementation checklist (ordered)

1. **Schema validator first.** `open-pet-creator/scripts/check_chain.py`.
   Without it, every chain change is a coin flip.
2. **Stats schema (Phase B prerequisite)** — extend
   `OpenPetsConfig` with `pet_stats: HashMap<String, PetStats>` and
   all the fields from §2.3. `#[serde(default)]` everywhere.
3. **Rust: condition evaluator.** Pure function `evaluate(condition,
   &PetStats) -> bool`. Heavy unit-test target — most likely surface
   for bugs.
4. **Rust: chain loader.** Parse a pet's `evolution.branches` at load
   time, validate every condition (defensive — validator should
   already have caught it).
5. **Rust: evaluation timing.** Hook `check_evolution` into:
   - state transition to idle
   - SessionEnd handler
   - app startup
   Set `pending_evolution = Some(branch_index)` if a branch fires.
   Persist immediately so app-kill doesn't lose the moment.
6. **Rust: new Tauri commands.**
   - `get_pending_evolution(pet_id) → Option<{ to, label, was_secret, unlocks }>`
   - `commit_evolution(pet_id) → Result<()>` — JS calls after
     animation completes; Rust swaps active pet, copies variant_id
     forward, resets pet_stats with `previous_form` set,
     updates pet_state with `evolved_from` + `evolved_at`.
   - `get_evolution_progress(pet_id) → Option<{ branch_label,
     signals: [{ name, current, target }] }>` for the right-click
     menu line.
7. **JS: animation sequencer.** The 6-phase sequence in §2.7. Use
   existing `is_shaking` flag for shake guard.
8. **JS: idle queue check.** On entering idle, if
   `get_pending_evolution()` returns Some, fire the sequence (after
   any onboarding / variant celebration that's already queued).
9. **JS: progress menu line.** Add to `buildMenuContent` with the
   §2.8 algorithm.
10. **JS: secret-discovery toast.** §2.7 phase 5+1s.
11. **Tests: condition evaluator.** All branches + edge cases (zero
    sample size, ties at boundary, missing axes).
12. **Tests: end-to-end maodou chain.** Mock pet_stats to satisfy
    each branch in turn; verify the right one fires.
13. **Author the maodou stage-2 art** (out of code-engineering scope;
    Skill workflow). Produces `pets/rocom-maodou-{sunward,moonlit,
    sage,wild}/`.
14. **Bump BUILD_TAG**.

### 2.14 Open questions

- **Should secret branches *ever* be hinted?** Currently no. Once any
  user discovers any secret branch on any pet, we could add a "?"
  placeholder slot in the Petdex chain UI signaling "there's more to
  find" without spoiling specific conditions. Phase D decision.
- **Anniversary branches?** The condition library doesn't currently
  express "fixed calendar date" (e.g., "1 year since first_seen").
  Add `since_first_seen_min: { days: 365 }` if requested. Defer.
- **What if two non-secret branches' conditions both hold?**
  First-match wins, period. Document this in the author guide —
  order branches by exclusivity, with the most specific first.
- **Mega/temporary forms** (Pokémon X-Y mega evolution: pet enters
  alternate form during attention states, reverts after)? Interesting
  but expanding scope. Phase E?
- **Cross-pet evolution** (one pet's progress unlocks a *different*
  pet)? Not even Pokémon does this generally. Out of scope.
- **Release-and-restart UX** — a tray menu item that clears the pet's
  pet_state + pet_stats with a confirmation dialog. Needs careful
  copy ("This permanently resets {pet}'s evolution progress. Cannot
  be undone."). Phase D after Petdex shows progress more clearly.

---

## 3. Stats Tracking

Variants are persisted in `pet_state` (§1.4). Evolution counters live
in a parallel structure `pet_stats` for clarity — different write
frequencies, different lifecycles.

### 3.1 Persistence shape

```jsonc
// ~/.openpets/config.json
{
  "pet_state": {
    "rocom-maodou": {
      "variant_id": "moonlight",
      "rolled_at": "2026-05-13T10:00:00Z",
      "revealed": true,
      "evolved_from": null,
      "evolved_at": null
    }
  },
  "pet_stats": {
    "rocom-maodou": {
      "first_seen": "2026-05-13T09:00:00Z",
      "last_active_at": "2026-05-13T14:30:00Z",
      "days_active": 1,

      "total_turns": 42,
      "total_clicks": 15,
      "total_waves": 8,
      "failures_seen": 1,
      "attention_seen": 3,
      "attention_responded": 3,

      "turn_buckets": {
        "morning": 25, "afternoon": 12, "evening": 4, "night": 1,
        "weekday": 38, "weekend": 4
      },

      "idle_seconds": 9_240,
      "active_seconds": 1_840,

      "previous_form": null,
      "pending_evolution_branch": null
    }
  }
}
```

Why split:

- `pet_state` is written rarely (roll, reveal, evolution). Mostly
  read-only at runtime.
- `pet_stats` is written frequently (every state change updates
  counters). Hot path — needs efficient serialization.
- Variant and evolution can ship independently. Don't couple their
  schemas.

### 3.2 When each counter increments

| Counter | Source event | Written by |
|---|---|---|
| `total_turns` | Claude Code `UserPromptSubmit` hook → `running` state | Rust state-watcher |
| `total_clicks` | JS canvas `click` event (drag-threshold filtered) | JS → batched IPC every 30s |
| `total_waves` | State transition to `waving` | Rust state-watcher |
| `failures_seen` | State transition to `failed` | Rust state-watcher |
| `attention_seen` | State transition to `review` or `waiting` | Rust state-watcher |
| `attention_responded` | Attention state transitions back to a non-attention state within 30s | JS-side detector → IPC |
| `turn_buckets.{bucket}` | At each `total_turns` increment, also increment the matching time-of-day + weekday bucket | Rust |
| `idle_seconds` / `active_seconds` | Sampled every 5s by the Rust tick loop | Rust |
| `last_active_at` | Any state change | Rust |
| `days_active` | At every state change, if `last_active_at`'s YYYY-MM-DD differs from now's, increment | Rust |
| `first_seen` | Set once on initial `set_active_pet` | Rust |

### 3.3 Click batching — why JS ↔ Rust IPC isn't per-click

Clicks fire at human rate but the Rust mutex+disk write isn't free.
We batch:

- JS holds an in-memory `pending_clicks` counter
- Every 30s (or on app blur / SIGTERM), JS calls
  `record_clicks(pet_id, n)` and resets local count
- On clean shutdown, last batch flushes synchronously

Loss bound: max 30 seconds of click count on hard kill. Acceptable.

### 3.4 Idle/active time accounting

States classified as "active" for the purposes of `active_seconds`:
`running`, `running-right`, `running-left`, `waving`, `jumping`,
`failed`, `review`. Anything else (`idle`, `waiting`) counts as
`idle_seconds`.

Sampled every 5s by the existing tick loop. Drift is tolerable.

---

## 4. Petdex Integration (future)

The Petdex (pet index / collection viewer) is the home for
collection state — every pet you've activated, with its variant, its
chain progress, and its stats. Designed assuming variant + evolution
both ship.

### 4.1 What each Petdex card shows

For an evolved chain:

```
┌────────────────────────────────────────────────────────────┐
│ Maodou Chain                                               │
│                                                            │
│   ┌──┐    ┌──┐                                             │
│   │🐰│ →  │☀│   Sunward Maodou  ← caught                   │
│   └──┘    └──┘   Caught: 2026-05-13   Variant: ★ Moonlight │
│       ↘  ┌──┐                                              │
│        ↘ │🌙│   Moonlit Maodou (silhouette)                │
│          └──┘   "morning < 55%"                            │
│       ↘  ┌──┐                                              │
│        ↘ │ ?│   secret branch (silhouette + ?)             │
│          └──┘   "you've discovered another secret elsewhere" │
└────────────────────────────────────────────────────────────┘
```

Caption rules:

- **Earned branch**: full art, label, caught date, current variant
  badge if non-normal.
- **Visible un-earned branch**: silhouette + label + the most-distant
  unsatisfied condition (so the user knows what would unlock it).
- **Secret un-discovered branch**: shown only as `?` *if* the user
  has discovered at least one secret branch anywhere in their
  collection. Otherwise hidden entirely.

### 4.2 Collection stats summary

Top of the Petdex:

```
🏆 Pets caught: 3 / 5      ⭐ Variants found: 2 / 12
🌱 Chains progressed: 2 / 5 (1 fully completed)
✨ Secret branches: 1 / ? (keep exploring)
```

The `?` for secret-branch totals is intentional — we don't reveal
the count of secret branches across the whole catalog. Discovering
them all should feel like an open frontier.

### 4.3 Per-pet drill-down

Click a Petdex card → drill-down panel:

- Full chain visualization (§4.1)
- Variant grid: rolled variants for this chain side-by-side, with
  caught dates
- Usage stats relevant to this pet: total_turns, days_active,
  morning/evening preference, click rate, etc.
- "Release & restart" button (Phase D), behind a confirmation dialog

### 4.4 Implementation note — Petdex is its own window

Probably a second WebView window (`open_petdex` Tauri command), not
overlaid on the pet. The current pet window is small and transparent;
Petdex is dense and benefits from its own surface (frosted glass,
~600×800).

---

## 5. Implementation Phasing

### Phase A + B: Variant foundation **and** stats tracking (parallel)

Per the locked decision in the doc header, A and B run together as
one sprint. Phase A delivers a visible product win (the variants);
Phase B lays the instrumentation that Phase C will need without
adding any visible UI yet.

See **§1.9** for the Phase A ordered checklist (now including
Release & Restart at step 13). Phase B work fits in alongside it.

### Phase B: Stats tracking (the work that ships alongside A)

Prerequisite for Phase C. All the counters from §3 land here, but no
evolution evaluation yet — just instrumentation.

- Rust: extend `OpenPetsConfig` with `pet_stats: HashMap<String, PetStats>`.
- Rust: increment counters on the events listed in §3.2.
- Rust: time-of-day / weekday bucketing on `total_turns` increment.
- Rust: idle/active time accounting via tick-loop sampler.
- JS: click batcher (every 30s + on blur / SIGTERM).
- JS: attention-responsiveness detector (track time from attention →
  next non-attention transition, IPC if ≤30s).
- Tests: each counter increments correctly under simulated event
  sequences (extend `tests/test_state_machine.py`).

### Phase C: Evolution

See **§2.13** for the ordered checklist. Roughly: chain validator →
condition evaluator → idle-queued evolution → animation sequencer →
progress UI → secret-discovery toast → maodou chain art.

### Phase D: Petdex + release-and-restart

- Build the Petdex window (§4).
- Variant grid, chain visualization, stats summary, secret-discovery
  hints.
- "Release & restart" with confirmation.
- Possibly: cross-collection achievements ("3 chains completed").

### Phase E (speculative): mega forms, anniversary branches

Only if Phase C+D land cleanly and there's user appetite for more
depth. Don't build until requested.

---

## 6. Cross-cutting design decisions

### 6.1 Why deterministic on-first-activation, not per-session (variants)

The surprise of discovering you got a "shiny" is a one-time moment.
Per-session rolls dilute it. Persistence means the user can show off
their rare variant. Matches Pokémon Go's model: you check, you get
what you get.

### 6.2 Why evolution = separate pet packages, not internal "stages"

- Evolution changes the character significantly (body shape,
  accessories, size), not just color. A filter can't add wings or
  change proportions.
- Separate packages mean the evolved form has its own design doc, AI
  generation, and repacking. The Skill workflow stays unchanged.
- The evolution chain is just data linking pet IDs — no special-case
  in the spritesheet pipeline.
- A pet author can ship stage-1 alone first; stage-2+ ship later.

### 6.3 Why variant uses canvas filter, not pre-baked spritesheets

Three reasons in priority order:

1. **Zero art cost.** AI generation can't reliably produce
   color-consistent variants across all 72+ atlas cells.
   Hand-painting them is hours per pet.
2. **Author iteration speed.** Tweaking a number in pet.json + 5s of
   preview script vs. regenerating an entire spritesheet.
3. **Disk + load time.** N variants × ~1.5MB webp adds up; canvas
   filter is free.

The downside: filter expressiveness is limited. When a pet's variants
exceed what chained CSS filters can do, we add the pre-bake path as
Phase A+1 (§1.2 path C). Until then, pick recipes that work in the
filter vocabulary.

### 6.4 Why first-match-wins for branches, not best-fit scoring

- **Predictable.** The chain author orders branches; that order *is*
  the precedence.
- **Authorable.** A best-fit scoring function would force authors to
  reason about utility weights between conditions. Nobody wants to
  tune that.
- **Testable.** Deterministic outcomes given identical stats.
- **`min`/`max` in conditions** lets authors write mutually-exclusive
  bands (morning ≥ 55% on one branch, evening ≥ 55% on another) so
  ordering rarely matters in practice.

### 6.5 Why neglect *unlocks* a branch instead of damaging the pet

Yu-kai Chou's framework warns against guilt-cycling as the dominant
loop — works short-term, burns out long-term. We use the
*ambiguous-care* mechanic instead:

- High click rate → "you cared for me" branch
- Low click rate (but consistent presence) → "you trusted me to be
  there" branch (the Hooded Sage)
- Both are valid. Neither destroys the pet.

The pet author shapes the meaning by naming the branches. "Hooded
Sage" reframes "you didn't pet me much" into "you respected my space"
— the same usage signature, but with a positive narrative.

### 6.6 Why secret branches at all

- Pure surprise (CD7 in Yu-kai's framework). The first time a user
  discovers a secret branch — especially one that emerged from their
  *actual* coding habits — is the highest-emotional-value moment in
  the whole system.
- Replayability for users who try second pets or release+restart.
- Discovery becomes shareable: "wait, you can get a Hooded Sage?"
  → this is the only social vector OpenPets has, and secrets
  give it material.

### 6.7 Why idle-queued evolution instead of immediate

Evolution is a 6-second cinematic. Firing it mid-task interrupts
flow. Queueing to the next idle moment means:

- The user finishes their current thought, sees their pet has paused,
  and *then* the evolution begins.
- The animation feels like a reward for the work just completed,
  not an interruption of work in progress.
- If the user stays busy for hours, the evolution waits patiently —
  the moment isn't lost, just deferred.
