# 大耳帽兜 (Maodou) Codex Pet Design

## Goal

Create a local Codex pet based on **大耳帽兜** (Da'er Maodou, "big-eared hood-bunny"), spirit #142 in 洛克王国 / Roco World (type: 冰 Ice + 萌 Cute, rightsholder: 腾讯 / Tencent). Optimized for local use first, kept compatible with later Petdex submission. Reference: <https://wiki.biligame.com/rocom/%E5%A4%A7%E8%80%B3%E5%B8%BD%E5%85%9C>.

## Package Shape

```text
pets/rocom-maodou/
  pet.json
  spritesheet.webp
  spritesheet-source.png        (8x8 generated source sheet, dropped in by user)
  spritesheet-repacked-preview.png
```

The installed copy lives at:

```text
~/.codex/pets/rocom-maodou/
  pet.json
  spritesheet.webp
```

## Visual Direction

- High-recognition Maodou fan pet; "tiny cinnamon-roll bunny spirit" vibe.
- Chibi, pixel-adjacent Codex pet style — same visual register as Phrolova, Pink Star, and Dimo so the four sit well together in the picker.
- **Bipedal chibi** stance for animation states (canonical art is often shown sitting/floating, but bipedal reads better at desktop-pet thumbnail size and matches the rest of the roster).
- Body palette (drawn from canonical art, NOT the wiki text — wiki text was incorrect):
  - **Soft white / cream** body, head, limbs, tail base.
  - **Pink / salmon** inner ear lining, paw pads, and a soft **pink gradient tail tip**.
  - **2-3 small pink-red dots** scattered on the forehead — signature mark.
  - **Teal / cyan** large round eyes with white catchlight, simple cute expression.
  - Tiny pink open mouth in idle / waving frames.
- Head & ears:
  - Rounded chibi head, slightly bigger than torso (cinnamon-roll proportions).
  - **Long floppy droopy ears** that hang down past the shoulders / waist — this is THE signature feature, must be unmistakable in every frame, never tucked behind the head.
  - Inner ear surface is **pink / salmon**; outer ear surface is the same soft white as the body. The pink shows clearly because the ears droop forward.
  - **2-3 small pink-red dots** on the forehead between the ears (think faint freckles, NOT a single crystal).
  - **NO forehead crystal / gem.** (Earlier wiki-derived design drafts included one. Canonical art does not.)
- Body:
  - Round chibi torso, all soft white.
  - Tiny stubby arms with small pink paw pads visible on the underside.
  - Stubby legs, may be partially hidden by the long ears.
- **Tail** (signature feature, must be visible in idle / review / waving / jumping frames):
  - Long soft tail trailing behind, ending in a clearly defined **soft pink gradient blob / oval tip**.
  - The tail tip is pink — **NOT frost-blue / ice-blue** despite the "Ice type" classification.

Avoid drifting into:

- **Ice-blue inner ears, dark-blue eyes, or frost-blue tail tip** — the wiki text description says these but the canonical art uses pink. (See `feedback_maodou_canonical_colors.md` in auto-memory.)
- A **forehead crystal / gem** — never include one.
- A generic Cinnamoroll knockoff — the pink forehead dots and pink tail tip are mandatory differentiators.
- Quadruped pose (looks awkward as a desktop pet at small thumbnail size).
- Hats, glasses, scarves, weapons, or other accessories not present in canonical art.

## Codex State Rows (target atlas)

```text
row 0: idle
row 1: running-right
row 2: running-left
row 3: waving
row 4: jumping
row 5: failed
row 6: waiting
row 7: running
row 8: review
```

## Source Sheet Contract (the file to generate)

A single `8 columns x 8 rows` PNG sheet, ideally `1536 x 1664` (cells `192 x 208`), with a flat solid black background so the existing alpha pipeline can isolate sprites. Each cell holds one centered chibi pose facing-forward unless noted.

| Source row | Frames used | Pose |
| ---: | ---: | --- |
| 0 | 6 | idle: gentle bobbing standing pose, ears swaying slightly, tail tip visible behind, forehead dots fully visible |
| 1 | 6 | review: thoughtful pose, one paw lifted near the chin, head slightly tilted, eyes half-lidded, ears drooping forward |
| 2 | 4 | waving: one paw raised high in a friendly wave, mouth slightly open in a small smile, tail tip visible |
| 3 | 8 | running-right: 8-frame run cycle, body angled to the right, ears trailing behind, tail swinging (will be mirrored to produce running-left) |
| 4 | 5 | jumping: 5-frame jump arc — crouch, push, peak airborne (limbs spread, ears lifted, tail tip visible at peak), descending, landing |
| 5 | 6 | running: alternate run cycle (slightly different rhythm or hop step from row 3) |
| 6 | 6 | waiting: small idle-with-fidget loop (tilting head, ear sway, tail swish) |
| 7 | 8 | failed: 8-frame "knocked down" loop — startled → tipped backward → sad sit-up with tiny snowflake sparks above head |

Frames within a row should keep the character's overall scale and ground line consistent so the repacker's bbox-centering does not jitter between frames. The pink forehead dots and pink tail tip must remain visible across all 64 cells.

## Metadata

```json
{
  "id": "rocom-maodou",
  "displayName": "Maodou",
  "description": "A tiny Codex-style 大耳帽兜 (Big-Eared Hood-bunny) pet from Roco World — a chibi soft-white bunny spirit with long droopy pink-lined ears, teal eyes, pink-red forehead dots, and a long tail tipped in soft pink.",
  "spritesheetPath": "spritesheet.webp"
}
```

## Build Steps

1. Generate the source sheet using `docs/rocom-maodou-generation-prompt.md`. Save as `pets/rocom-maodou/spritesheet-source.png`.
2. Repack with the Skill's CLI in **detection mode** (variable per-row sprite counts are expected from generative models):

   ```bash
   python3 open-pet-creator/scripts/repack_pet_atlas.py \
     --source pets/rocom-maodou/spritesheet-source.png \
     --output pets/rocom-maodou/spritesheet.webp \
     --preview pets/rocom-maodou/spritesheet-repacked-preview.png \
     --scale 0.98 \
     --offset-y 14 \
     --detect-sprites
   ```
3. `python3 open-pet-creator/scripts/validate_pet_atlas.py pets/rocom-maodou/spritesheet.webp`
4. `python3 open-pet-creator/scripts/inspect_pet_atlas.py pets/rocom-maodou/spritesheet.webp`
5. Tune `--scale` and `--offset-y` until the idle bbox lands in the `105-125 x 140-155` thumbnail sweet spot AND `top_min >= 35`. Start from the conservative `0.98 / 14` baseline; do NOT copy a value from another pet. Maodou's silhouette is **wide rather than tall** — the long ears droop downward / forward instead of stretching upward, so the headroom budget is generous (more like Phrolova's compact head than Pink Star's upright ears). Expect to settle around `--scale 1.00-1.05` once tuned, but start at `0.98` and confirm with `inspect`.
6. Install with `open-pet-creator/scripts/install_pet.py` to sync to `~/.codex/pets/rocom-maodou/`.
