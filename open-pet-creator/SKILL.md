---
name: open-pet-creator
description: Create, repair, validate, and install Codex/Open Pets custom pet spritesheets. Use when Codex needs to turn a generated pet sheet into the official 1536x1872, 8x9, 192x208-cell atlas; tune sprite scale or centering; keep unused cells transparent; inspect frame bounds; package pet.json and spritesheet.webp into ~/.codex/pets; or fix display issues such as small, low, off-center, opaque, or dirty-cell pet sprites.
---

# Open Pet Creator

## Overview

Use this skill for deterministic Open Pets/Codex pet packaging and repair. It does not generate new character art; use image generation or `hatch-pet` for visuals, then use this skill to repack, inspect, validate, tune, and install the final pet atlas.

## Workflow

1. Locate the source art and target pet folder.
   - Source art is an 8×8 sprite sheet on a flat black (or transparent) background.
   - If it has not been generated yet, see `Generation Prompts` below for the prompt-authoring workflow.
   - Keep the canonical output shape `1536x1872`, `8x9` cells, `192x208` per cell.
2. Read `references/codex-pet-atlas.md` when you need the official row counts, row meanings, or tuning heuristics.
3. Repack the source into a Codex atlas with `scripts/repack_pet_atlas.py`.
4. Inspect the atlas with `scripts/inspect_pet_atlas.py`; tune `--scale`, `--offset-x`, and `--offset-y` until the pet is visually balanced.
5. Validate with `scripts/validate_pet_atlas.py`. Treat errors as blockers.
6. Install with `scripts/install_pet.py` when the user wants the pet usable in Codex.
7. **(Optional, Phase A+) Add variants** — declare a `variants` array in pet.json (id + weight + displayName + recipe + effects). Iterate the recipes with `scripts/preview_variants.py --sampler` to pick directions, then re-run without `--sampler` to validate the final picks against your sprite. See `pets/rocom-maodou/pet.json` for the canonical example.
8. **(Optional, Phase C+) Add evolution** — wire `evolution.branches` blocks in pet.json per `docs/pet-evolution-variant-design.md` §2.4-§2.5. Validate with `scripts/check_chain.py <pet-id>` before publishing — a typo in `branches[].to` becomes a runtime "my pet vanished" error if uncaught.

Do not locally draw, invent, or synthesize missing pet frames with these scripts. These tools may crop, alpha-clean, resize, mirror, center, validate, package, **recolor, or chain-validate** already-existing pet art.

## Generation Prompts

When the user is creating a **brand new pet** and asks for a prompt to feed to an image generator (gpt-image, GPT-4o Image, Midjourney, SDXL, etc.), produce a per-pet `docs/<pet-id>-generation-prompt.md`.

**Before writing the doc:**

1. Understand the character from the user's requirements — palette, anatomy, signature features, and what NOT to draw.
2. Read `references/generation-prompt-format.md` to get the current canonical Prompt B block. (Prompt B is the global format / pose / animation contract shared across all pets — the canonical source may have been updated since the last per-pet doc was written.)

Then produce the doc with this structure:

1. **Top of doc — Next steps:** a short numbered checklist telling the user exactly what to do — prepare a reference image if available, copy one of the two prompts at the bottom into their image tool, save the output to `pets/<pet-id>/spritesheet-source.png`, return for repack / inspect / validate / install.
2. **Character-specific iteration tips:** per-pet drift traps and signature features to defend (e.g., for Maodou: fight the ice-blue prior; ears must always droop, never stand upright).
3. **Two prompts at the tail of the doc, copy-pasteable:**
   - **Prompt A — Character + Format (recommended):** a **self-contained, character-rich** prompt that combines a full character description (palette, anatomy, signature features, negatives) with the format / pose / animation requirements. The user pastes Prompt A together with any reference image they have. Works standalone if no reference image exists.
   - **Prompt B — Format / Pose only (Plan B):** copied verbatim from `references/generation-prompt-format.md`. The user pairs Prompt B with their own short character description when they want fine control over wording or when Prompt A drifts.

**Default recommendation to the user is Prompt A.** Prompt B is the fallback — use it when the user already has a reference image and prefers to pair it with the bare format/pose prompt, when they want fine control over the character description wording, or when Prompt A drifts in unwanted ways.

**Always render both prompts as fenced `text` code blocks** (```` ```text ```` … ```` ``` ````), NOT as markdown blockquotes — most viewers offer a one-click copy button on code blocks, and `**bold**` / `>` markers would otherwise end up in the pasted text and confuse the image generator. Within the code block, use ALL CAPS or sentence position for emphasis instead of markdown bold.

Prompt B is identical across every pet (the format / pose contract is fixed). The per-pet doc inlines it for user convenience — users grab both prompts from a single file — but the canonical source lives in `references/generation-prompt-format.md`. When that block changes (e.g., atlas dimensions, row count), update the canonical source and re-sync every per-pet doc's Prompt B section.

## Repack

Use the default row map for Phrolova-style 8x8 source sheets:

```bash
python "$SKILL_DIR/scripts/repack_pet_atlas.py" \
  --source /absolute/path/spritesheet-source.png \
  --output /absolute/path/spritesheet.webp \
  --preview /absolute/path/spritesheet-preview.png \
  --scale 0.98 \
  --offset-y 16
```

Useful options:

- `--row-map 0,3,3m,2,4,7,6,5,1` maps source rows to Codex rows. Add `m` to mirror that source row.
- `--used-columns 6,8,8,4,5,8,6,6,6` keeps unused cells transparent.
- `--scale` changes visible sprite size inside each `192x208` cell.
- `--offset-x` and `--offset-y` tune placement after centering.
- `--black-threshold` and `--outline-expand` control black-background alpha cleanup.
- `--detect-sprites` switches from even-grid splitting to alpha-projection detection of each sprite's bounding box. Use when the generated sheet has **variable sprite counts per row** or when individual sprites are wider than `image_width / source_cols` (in which case even-grid splitting will slice tall/wide sprites across cell boundaries and produce visible fragments). Detection still requires `--source-rows` to match the actual row count; per-row sprite counts are auto-discovered.

### When to choose even-grid vs detection

- **Even-grid (default)**: pick when the source comes from a controlled pipeline that lays sprites out on a strict NxM grid with consistent cell sizes (e.g., a custom renderer, or a previous `open-pet-creator` output).
- **Detection (`--detect-sprites`)**: pick when the source comes from a generative model (gpt-image, Midjourney, SDXL) where the model decides per-row how many frames to produce and sprite widths vary. Symptoms in the inspect/preview output that hint at needing detection: visible sprite fragments at the edges of cells, or rows where `row_bbox` left/right boundaries don't roughly match `(col * cell_w, col * cell_w + frame_width)`.

## Inspect And Tune

Run:

```bash
python "$SKILL_DIR/scripts/inspect_pet_atlas.py" /absolute/path/spritesheet.webp
```

Interpretation:

- `xcenter` should usually sit near `96`.
- `top_min` is the safety check for the top menu strip. Aim for `>= 35`; treat `< 30` as a regression.
- If thumbnail/scene views feel small, increase `--scale`.
- If the pet feels low, reduce `--offset-y`; if a top-right menu overlaps the head, increase `--offset-y` slightly.
- If rows after the expected frame count are non-empty, fix `--used-columns` or the repack script call.

For thumbnail-friendly chibi pets, a good first idle frame often has a visible bbox around `105-125px` wide and `140-155px` high while staying inside the cell.

### Scale/offset trade-off

`--scale` and `--offset-y` both consume the same top-of-cell headroom:

- Raising `--scale` makes the bbox taller, which pushes its top edge **up** by half the height delta.
- Lowering `--offset-y` shifts the entire bbox **up**.

If you want both a bigger pet and a higher-sitting one, you will run out of top clearance fast. Practical recipe:

1. Run inspect; note `top_min` and the row that owns it (often the tallest pose: `review` or `waving`).
2. Estimate the available headroom: `top_min - 35`. That is the total upward budget across both levers.
3. Allocate it: e.g., `top_min = 46` gives a budget of `11px`. A scale bump of `+0.07` on a `~150px` pose costs ~5px of headroom, leaving ~6px for `--offset-y` reduction.
4. Re-inspect after each pass; the actual `top_min` is what matters, not the estimate.

## Validate

Run:

```bash
python "$SKILL_DIR/scripts/validate_pet_atlas.py" /absolute/path/spritesheet.webp
```

The validator checks dimensions, alpha support, used cell occupancy, and transparent unused cells. Keep `errors` empty before installing or reporting completion.

## Install

Run:

```bash
python "$SKILL_DIR/scripts/install_pet.py" \
  --pet-id phrolova \
  --display-name Phrolova \
  --description "A tiny Codex-style pet." \
  --spritesheet /absolute/path/spritesheet.webp
```

This writes:

```text
~/.codex/pets/<pet-id>/
  pet.json
  spritesheet.webp
```

When installing outside the current workspace, request filesystem approval if the runtime requires it.

## Repair Loop

For display complaints such as "too small", "not centered", "too low", or "menu overlaps":

1. Inspect current bbox stats.
2. Add or update tests in the user's repo when one exists.
3. Tune only `--scale`, `--offset-x`, and `--offset-y` first.
4. Repack, preview, validate, and install.
5. Report the exact installed path and the before/after bbox numbers.
