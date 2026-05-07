# Pink Star (粉星仔) Codex Pet Design

## Goal

Create a local Codex pet based on 粉星仔 (Pink Star) from Roco World / 洛克王国, optimized for local use first and kept compatible with later Petdex submission. Reference: <https://wiki.biligame.com/rocom/%E7%B2%89%E6%98%9F%E4%BB%94>.

## Package Shape

```text
pets/pink-star/
  pet.json
  spritesheet.webp
  spritesheet-source.png        (8x8 generated source sheet, dropped in by user)
  spritesheet-repacked-preview.png
```

The installed copy lives at:

```text
~/.codex/pets/pink-star/
  pet.json
  spritesheet.webp
```

## Visual Direction

- High-recognition Pink Star fan pet; "meteor spirit" (流星精灵) vibe.
- Chibi, pixel-adjacent Codex pet style — same visual register as Phrolova so they sit well in the same picker.
- Cream / off-white body fur as the dominant tone.
- Long upright rabbit-like ears with pink-blush inner-ear tips and dusty-pink ear backs.
- Pink heart-shaped tuft on the forehead (signature trait).
- Large round dark-blue eyes, simple deadpan-cute expression.
- Blue polka-dot scarf around the neck with a yellow five-point star pendant.
- Yellow five-point star earring on one side of the head.
- Long, billowing arm/sleeve "wings" in cream with brown trim, decorated with a yellow star motif near the wrist.
- Pink rear paws.
- Optional cosmetic accent: a small yellow star can appear under the feet for `idle` and `waiting` (the "standing on a star" pose), but should NOT be treated as the ground line — keep the body's feet as the reference for vertical alignment so positioning matches Phrolova.
- Codex renders the final atlas as `8 x 9` grid of `192 x 208` frames.

Avoid drifting into:

- A generic pink rabbit — the long sleeve-wings, star earring, and scarf are required for recognition.
- An overly bright magenta / hot-pink color scheme — keep the pink as accents, not the body.
- Hyperdetailed / painterly rendering — must match the simple chibi register.

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
| 0 | 6 | idle: gentle bobbing standing pose, scarf swaying |
| 1 | 6 | review: hand near chin / star pendant, "thinking" expression |
| 2 | 4 | waving: one sleeve-wing raised in a friendly wave |
| 3 | 8 | running-right: 8-frame run cycle, body angled to the right (will be mirrored to produce running-left) |
| 4 | 5 | jumping: 5-frame jump arc — crouch, push, peak, fall, land |
| 5 | 6 | running: alternate run cycle, slightly different from row 3 |
| 6 | 6 | waiting: small idle-with-fidget loop (tilting head, looking around) |
| 7 | 8 | failed: 8-frame "knocked down" loop — startled → tipped over → sad sit-up |

Frames within a row should keep the character's overall scale and ground line consistent so the repacker's bbox-centering does not jitter between frames.

## Metadata

```json
{
  "id": "pink-star",
  "displayName": "Pink Star",
  "description": "A tiny Codex-style Pink Star (粉星仔) pet from Roco World, a meteor-spirit chibi with cream fur, pink ear tips, big blue eyes, a blue polka-dot scarf, a yellow star earring, and long star-patterned arms.",
  "spritesheetPath": "spritesheet.webp"
}
```

## Build Steps

1. Generate the source sheet using `docs/pink-star-generation-prompt.md`. Save as `pets/pink-star/spritesheet-source.png`.
2. Write a per-pet repack tool (copy `tools/repack_phrolova_spritesheet.py` and adjust paths + `TARGET_ROW_SOURCE_ROWS` if the row order in the generated sheet differs).
3. `python3 tools/repack_pink_star_spritesheet.py`
4. `python3 open-pet-creator/scripts/validate_pet_atlas.py pets/pink-star/spritesheet.webp`
5. `python3 open-pet-creator/scripts/inspect_pet_atlas.py pets/pink-star/spritesheet.webp`
6. Tune `SPRITE_DISPLAY_SCALE` and `SPRITE_DISPLAY_OFFSET` until `top_min >= 35` and idle bbox lands in the `105-125 x 140-155` thumbnail sweet spot.
7. Sync to `~/.codex/pets/pink-star/`.
