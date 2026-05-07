# Dimo Source Sheet Generation Prompt

Use this prompt with an image generator (gpt-image-1, GPT-4o Image, Midjourney v6+, SDXL with a chibi LoRA, etc.) to produce `pets/rocom-dimo/spritesheet-source.png`. The downstream pipeline expects the file described in `rocom-dimo-pet-design.md` ("Source Sheet Contract").

## Hard Constraints (must be in every prompt)

- Output is a **single image, 1536 x 1664 pixels**.
- Layout is an **8 columns x 8 rows grid**, exactly 64 cells of `192 x 208` each.
- Background is **flat solid pure black `#000000`** with no gradient, no halo, no signature, no watermark, no UI chrome.
- Each cell contains **one centered chibi-style sprite of the same character**, **bipedal pose**, facing forward unless noted, fully inside its cell with no overlap into neighboring cells.
- No grid lines, no row/column numbers, no labels.
- Style: clean cel-shaded chibi, soft outlines, flat colors with light shading. Pixel-adjacent but not strict pixel art. Match the visual register of a Codex desktop pet.

## Character Reference (迪莫 / Dimo)

- Small bipedal chibi cat-like creature, the "best partner" mascot of Roco World (Light type).
- Body palette:
  - **Royal blue** body / hood-like upper / limbs / tail.
  - **Soft white** face mask covering eyes/nose/cheek area, chin, and round belly.
  - **Bright yellow** accent patches on **ear tips**, the **forehead mark**, and the **tail tip star**.
- Head: rounded chibi head with two upright pointed cat ears (blue, with **yellow rectangular tip patches** on the upper portion of each ear).
- Forehead: a **bright yellow chevron / lightning-bolt mark** centered between the eyes — this mark is mandatory in every frame, never obscure or omit it.
- Eyes: large round **dark-brown / near-black** eyes with white catchlight, simple cute expression.
- Cheeks: small **pink-orange blush ovals** under each eye.
- Mouth: small, slightly visible, tiny smile or open with a hint of pink tongue.
- Limbs: short blue arms with rounded blue paw tips; stubby blue legs.
- **Tail**: long blue tail trailing behind, ending in a clearly defined **5-point star** with a blue body and yellow point caps (or solid yellow star depending on framing). Star tip should be visible in idle, waving, review and jumping frames.

Do NOT add: glasses, scarves, hats, weapons, additional characters, lightning effects covering the body, white-dominant coloring, quadruped poses, sparkle particles covering the face.

## Per-Row Pose Specification

Generate the 8 rows in this exact order. Each row is one animation strip of the SAME character with consistent proportions, ground line, and color.

| Row | Frames used | Pose direction |
| ---: | ---: | --- |
| 0 | 6 | **idle**: bipedal standing facing forward, gentle bobbing across frames, tail swaying with star tip visible, mouth in small smile |
| 1 | 6 | **review**: thoughtful pose, one paw lifted near the chin, head slightly tilted, eyes half-lidded |
| 2 | 4 | **waving**: one paw raised high and waving, mouth open with small smile, tail slightly raised |
| 3 | 8 | **running-right**: full 8-frame run cycle, bipedal, body angled to the **right**, tail trailing left, ears blown back slightly |
| 4 | 5 | **jumping**: 5-frame jump arc — crouch, push-off, peak airborne (limbs spread, tail star prominent at peak), descending, landing |
| 5 | 6 | **running** (alternate): a different lighter run / hop cycle, bipedal, body upright, both feet visible |
| 6 | 6 | **waiting**: small idle fidget — tilting head, looking left/right, tail swish, ear twitch |
| 7 | 8 | **failed**: 8-frame "knocked over" loop — surprised → tipped backward → sitting on ground looking sad with tiny lightning sparks circling head |

Cells beyond each row's used count can be left as **fully black empty cells** — the pipeline ignores them.

## Composition Rules

- Each sprite must occupy roughly the central `~150 x 170` of its `192 x 208` cell, leaving a clear black margin.
- Keep a **consistent ground line** within each row so the character does not visually jitter between frames.
- Eye height, head size, ear length, and limb proportions must be consistent across all 64 cells.
- The yellow forehead chevron must be visible in every frame; do NOT cover it with paws or angle the head so far that the mark goes off-screen.
- Mirror should be left to the pipeline — do not pre-mirror the running row; only generate `running-right` for row 3.

## Final Prompt (paste into the image tool)

> A 1536x1664 pixel sprite sheet, 8 columns by 8 rows, 64 cells total, each cell exactly 192x208 pixels, flat pure black background with no gradient or halo. One centered bipedal chibi sprite per cell, all 64 cells the same character: a small chibi cat-like creature with royal-blue hood/back/limbs/tail, soft white face-mask and round belly, two upright pointed cat ears blue with yellow rectangular tip patches, a bright yellow chevron / lightning-bolt mark centered on the forehead (mandatory in every frame), large round dark-brown eyes with white catchlight, small pink-orange blush ovals under the eyes, tiny smile, blue arms with rounded paw tips, stubby blue legs, a long blue tail ending in a 5-point yellow-and-blue star tip. Cel-shaded chibi style, clean soft outlines, flat shading. The 8 rows are animation strips: row 0 idle (6 frames, gentle bob, tail swaying), row 1 review thinking pose (6 frames, paw to chin), row 2 waving with one paw raised (4 frames), row 3 running-right cycle facing right (8 frames), row 4 jumping arc crouch-push-peak-fall-land (5 frames), row 5 alternate hop run facing forward (6 frames), row 6 waiting idle fidget head-tilt and tail swish (6 frames), row 7 failed knocked-over loop with tiny lightning-spark circles above the head (8 frames). All sprites consistent in scale, color, and ground line, the yellow forehead chevron visible in every frame, the star tail tip visible in standing/idle/jumping frames. No grid lines, no labels, no watermark, no UI chrome, no quadruped poses, no glasses or accessories. Unused trailing cells in shorter rows are fully black empty cells.

## Iteration Tips

- If color drifts (different blue saturation across cells, or the chevron disappears), generate **one row at a time** instead of the full sheet.
- If the model keeps producing quadruped poses despite the bipedal instruction, append "(human-like upright bipedal stance, two legs visible, NOT cat-like four-legged)" to that row's prompt.
- If the tail star is missing or shrunken, emphasize "long blue tail clearly visible in frame, ending in a large yellow 5-point star tip".
- Once acceptable, save as `pets/rocom-dimo/spritesheet-source.png` and proceed to the build steps in `rocom-dimo-pet-design.md`.
