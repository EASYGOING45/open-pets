# Pink Star Source Sheet Generation Prompt

Use this prompt with an image generator (gpt-image-1, GPT-4o Image, Midjourney v6+, SDXL with a chibi LoRA, etc.) to produce `pets/pink-star/spritesheet-source.png`. The downstream pipeline expects the file described in `pink-star-pet-design.md` ("Source Sheet Contract").

## Hard Constraints (must be in every prompt)

- Output is a **single image, 1536 x 1664 pixels**.
- Layout is an **8 columns x 8 rows grid**, exactly 64 cells of `192 x 208` each.
- Background is **flat solid pure black `#000000`** with no gradient, no halo, no signature, no watermark, no UI chrome.
- Each cell contains **one centered chibi-style sprite of the same character**, facing forward unless noted, fully inside its cell with no overlap into neighboring cells.
- No grid lines, no row/column numbers, no labels.
- Style: clean cel-shaded chibi, soft outlines, flat colors with light shading. Pixel-adjacent but not strict pixel art. Match the visual register of a Codex desktop pet.

## Character Reference (粉星仔 / Pink Star)

- Small chibi creature, "meteor spirit" from Roco World.
- Body fur: **cream / off-white**, with **dusty-pink ear backs and pink ear tips**, tiny pink heart-shaped forehead tuft.
- Long upright rabbit-like ears.
- Large round **dark-blue eyes**, simple soft deadpan-cute expression, tiny smile.
- **Blue polka-dot scarf** around the neck.
- **Yellow five-point star pendant** hanging from the scarf.
- **Yellow five-point star earring** on one side of the head.
- Long flowing **sleeve-wings** in cream with brown trim, decorated with a **yellow star motif near the wrist**.
- Pink rear paws.
- Optional: a small soft yellow star may sit under the feet for grounded/idle poses, but should not block view of the feet.

Do NOT add: hot-pink body, magenta, sparkles covering the face, painterly rendering, gem crowns, witch hats, additional characters, weapons.

## Per-Row Pose Specification

Generate the 8 rows in this exact order. Each row is one animation strip of the SAME character with consistent proportions and ground line.

| Row | Frames used | Pose direction |
| ---: | ---: | --- |
| 0 | 6 | **idle**: standing facing forward, gentle bobbing across frames, scarf and ears slightly drifting; a small yellow star may sit under the feet |
| 1 | 6 | **review**: thoughtful pose, one paw lifted near the chin / star pendant, head slightly tilted, eyes half-lidded |
| 2 | 4 | **waving**: one sleeve-wing raised high and waving, friendly smile |
| 3 | 8 | **running-right**: full 8-frame run cycle, body angled to the **right**, sleeve-wings trailing, ears bouncing |
| 4 | 5 | **jumping**: 5-frame jump arc — crouch, push-off, peak airborne (sleeve-wings spread), descending, landing |
| 5 | 6 | **running** (alternate): a different lighter run / hop cycle, body upright, both feet visible |
| 6 | 6 | **waiting**: small idle fidget — tilting head, looking left/right, swaying scarf |
| 7 | 8 | **failed**: 8-frame "knocked over" loop — surprised → tipped backward → sitting on ground looking sad with stars circling head |

Cells 7-of-row-0, 7-of-row-1, 5-of-row-2, etc. (the unused frames per row) can be left as **fully black empty cells** — the pipeline ignores them.

## Composition Rules

- Each sprite must occupy roughly the central `~150 x 170` of its `192 x 208` cell, leaving a clear black margin.
- Keep a **consistent ground line** within each row so the character does not visually jitter between frames.
- Eye height, head size, and limb proportions must be consistent across all 64 cells.
- Mirror should be left to the pipeline — do not pre-mirror the running row; only generate `running-right` for row 3.

## Final Prompt (paste into the image tool)

> A 1536x1664 pixel sprite sheet, 8 columns by 8 rows, 64 cells total, each cell exactly 192x208 pixels, flat pure black background with no gradient or halo. One centered chibi sprite per cell, all 64 cells the same character: a small cream / off-white chibi creature with long upright rabbit ears (pink ear tips, dusty-pink ear backs), tiny pink heart-shaped forehead tuft, large round dark-blue eyes, soft tiny smile, blue polka-dot scarf with a yellow five-point star pendant, yellow five-point star earring on one ear, long flowing cream sleeve-wings with brown trim and a yellow star motif near the wrists, pink rear paws. Cel-shaded chibi style, clean soft outlines, flat shading. The 8 rows are animation strips: row 0 idle (6 frames, small yellow star under feet), row 1 review thinking pose (6 frames), row 2 waving with one sleeve-wing raised (4 frames), row 3 running-right cycle facing right (8 frames), row 4 jumping arc crouch-push-peak-fall-land (5 frames), row 5 alternate run/hop facing forward (6 frames), row 6 waiting idle fidget (6 frames), row 7 failed knocked-over loop with sad stars (8 frames). All sprites consistent in scale and ground line, no grid lines, no labels, no watermark, no UI chrome. Unused trailing cells in shorter rows are fully black empty cells.

## Iteration Tips

- If the character drifts (different colors/proportions across cells), generate **one row at a time** instead of the full sheet, then assemble.
- If shadows/ground accents bleed past the cell, regenerate that row or manually black-fill the bleed in the final composite.
- Once the sheet is acceptable, save it as `pets/pink-star/spritesheet-source.png` and proceed to the build steps in `pink-star-pet-design.md`.
