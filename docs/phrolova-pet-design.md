# Phrolova Codex Pet Design

## Goal

Create a local Codex pet based on Phrolova from Wuthering Waves, optimized for local use first and kept compatible with later Petdex submission.

## Package Shape

```text
pets/phrolova/
  pet.json
  spritesheet.webp
```

The installed copy should live at:

```text
~/.codex/pets/phrolova/
  pet.json
  spritesheet.webp
```

## Visual Direction

- High-recognition Phrolova fan pet.
- Chibi, pixel-adjacent Codex pet style.
- Pale icy blue / blue-gray bob hair with heavy bangs.
- Sleepy half-lidded pink-magenta eyes and deadpan expressions.
- White, red, and black outfit with a prominent red chest bow.
- Small red flower/Havoc accents only as secondary effects.
- Multiple pet states in a 1536 x 1872 spritesheet.
- Codex renders this as an 8 x 9 grid of 192 x 208 frames.

## Codex State Rows

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

Avoid drifting into a generic dark gothic mascot: no dark purple hair, witch hat, horn-like ornaments, black mage dress, or crown-heavy design.

## Metadata

```json
{
  "id": "phrolova",
  "displayName": "Phrolova",
  "description": "A tiny Codex-style Phrolova pet from Wuthering Waves, with pale blue-gray hair, sleepy pink eyes, a red-and-white outfit, and calm deadpan chibi expressions.",
  "spritesheetPath": "spritesheet.webp"
}
```
