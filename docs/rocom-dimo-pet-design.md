# Dimo (迪莫) Codex Pet Design

## Goal

Create a local Codex pet based on 迪莫 (Dimo) from Roco World / 洛克王国 (Light type, NO.001 mascot of the Carolo continent). Optimized for local use first, kept compatible with later Petdex submission. Reference: <https://wiki.biligame.com/rocom/%E8%BF%AA%E8%8E%AB>.

## Package Shape

```text
pets/rocom-dimo/
  pet.json
  spritesheet.webp
  spritesheet-source.png        (8x8 generated source sheet, dropped in by user)
  spritesheet-repacked-preview.png
```

The installed copy lives at:

```text
~/.codex/pets/rocom-dimo/
  pet.json
  spritesheet.webp
```

## Visual Direction

- High-recognition Dimo fan pet; "Light spirit / best partner" vibe.
- Chibi, pixel-adjacent Codex pet style — same visual register as Phrolova and Pink Star so all three sit well in the same picker.
- **Bipedal chibi** posing across all states (do not ship a quadruped reference even though the official illustration shows one — bipedal reads better at desktop-pet thumbnail size and matches the rest of our roster).
- Body palette:
  - **Royal blue** body / hood / limbs / tail.
  - **Soft white** face mask, chin, belly, and inside-paw highlights.
  - **Bright yellow** for: ear tip patches, forehead lightning-bolt mark, star at the tail tip.
  - **Pink-orange** cheek blush spots (one under each eye).
- Head & ears:
  - Two pointed cat-like ears, blue with yellow tip patches.
  - Distinct **yellow lightning-bolt / chevron mark** centered on the forehead — this is the most identifiable feature, must be visible in every frame.
  - Big round dark-brown eyes with white catchlight, simple expressive look.
- Body:
  - Round chibi torso, white belly visible.
  - Short blue arms with rounded paw tips.
  - Stubby blue legs.
- **Tail** (signature feature):
  - Long blue tail trailing behind the body.
  - Tail ends in a **5-point yellow-and-blue star** (yellow point caps over a blue star body) — must be clearly visible in idle, waving, review, jumping rows.

Avoid drifting into:

- A generic blue Pikachu / Pokémon — the chevron forehead mark and star tail are mandatory.
- A quadruped pose (looks awkward as a desktop pet at small thumbnail size).
- White-dominant body (Dimo is blue-dominant; white only on face mask + belly).
- Adding glasses, scarves, or other accessories not present in canonical art.

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
| 0 | 6 | idle: gentle bobbing standing pose, tail swaying, lightning-bolt mark fully visible |
| 1 | 6 | review: thoughtful pose, one paw near the chin, head tilted, eyes half-lidded |
| 2 | 4 | waving: one paw raised high in a friendly wave, mouth open in a small smile |
| 3 | 8 | running-right: 8-frame run cycle, body angled to the right, tail trailing behind, ears blown back slightly (will be mirrored to produce running-left) |
| 4 | 5 | jumping: 5-frame jump arc — crouch, push, peak airborne (limbs spread, tail star prominent), descending, landing |
| 5 | 6 | running: alternate run cycle (slightly different rhythm or hop step from row 3) |
| 6 | 6 | waiting: small idle-with-fidget loop (tilting head, ear twitch, tail swish) |
| 7 | 8 | failed: 8-frame "knocked down" loop — startled → tipped backward → sad sit-up with tiny lightning sparks above head |

Frames within a row should keep the character's overall scale and ground line consistent so the repacker's bbox-centering does not jitter between frames. The forehead lightning mark must remain visible across all 64 cells.

## Metadata

```json
{
  "id": "rocom-dimo",
  "displayName": "Dimo",
  "description": "A tiny Codex-style Dimo (迪莫) pet from Roco World, a chibi blue-and-white cat-like Light spirit with yellow lightning-bolt forehead marks, yellow-tipped pointed ears, pink cheek blushes, big round dark eyes, and a long blue tail ending in a yellow star.",
  "spritesheetPath": "spritesheet.webp"
}
```

## Build Steps

1. Generate the source sheet using `docs/rocom-dimo-generation-prompt.md`. Save as `pets/rocom-dimo/spritesheet-source.png`.
2. Repack with the Skill's CLI in **detection mode** (variable per-row sprite counts are expected from generative models):

   ```bash
   python3 open-pet-creator/scripts/repack_pet_atlas.py \
     --source pets/rocom-dimo/spritesheet-source.png \
     --output pets/rocom-dimo/spritesheet.webp \
     --preview pets/rocom-dimo/spritesheet-repacked-preview.png \
     --scale 0.98 \
     --offset-y 14 \
     --detect-sprites
   ```
3. `python3 open-pet-creator/scripts/validate_pet_atlas.py pets/rocom-dimo/spritesheet.webp`
4. `python3 open-pet-creator/scripts/inspect_pet_atlas.py pets/rocom-dimo/spritesheet.webp`
5. Tune `--scale` and `--offset-y` until idle bbox lands in the `105-125 x 140-155` thumbnail sweet spot AND `top_min >= 35`. Start from the conservative `0.98 / 14` baseline; do NOT copy a value from another pet — Dimo's silhouette (tall ear tips + tall forehead mark) sits between Phrolova's compact build and Pink Star's tall rabbit ears, so re-tune from scratch.
6. Sync to `~/.codex/pets/rocom-dimo/`.
