# Maodou Source Sheet Generation Prompt

Use to produce `pets/rocom-maodou/spritesheet-source.png`. Two complete copy-pasteable prompts at the bottom — **Prompt A is the recommended path**.

---

## Next steps

1. **Prepare a canonical reference image** (strongly recommended). Anything that nails the appearance works: the ChatGPT-generated 大耳帽兜 you already have, the Roco World wiki canonical illustration, or an earlier good generation. Multiple references that agree on the visuals help.
2. **Open your image tool and send, in a single message:**
   - Your reference image(s) as attachments (if you have any).
   - **Prompt A** from the bottom of this doc — click the copy button on the code block and paste verbatim.
3. **Save the generated 8×8 sprite sheet** to:

   ```text
   pets/rocom-maodou/spritesheet-source.png
   ```

4. **Come back and tell me the path.** I'll run repack → inspect → validate → install with `--detect-sprites`.

If Prompt A drifts in unwanted ways (most common: ice-blue colors creeping in, or ears suddenly standing upright), see the iteration tips below, or fall back to **Prompt B** at the very bottom paired with your own character description.

---

## Character-specific iteration tips

The image-generator model has a strong "Ice type → blue palette" prior for this character because the 洛克王国 wiki text describes it as Ice / Cute type. Even with a reference image attached, this prior leaks in. The negatives baked into Prompt A fight it, but if drift persists:

- **Fight the ice-blue prior aggressively.** If ice-blue inner ears, dark-blue eyes, or a frost-blue tail tip keep appearing, prepend the negatives list at the very top of the prompt and bracket the per-row pose lines with "REMEMBER: pink not blue" markers.
- **Droopy ears, not standing.** If the model draws upright rabbit ears, regenerate only that row with: "long droopy floppy ears hanging downward past the shoulders, NOT upright like a normal rabbit. The ears are longer than the head is tall and droop forward."
- **Forehead dots, not crystal.** If a forehead gem appears, add: "NEGATIVE: forehead gem, forehead crystal, single jewel on forehead. The forehead has 2–3 small scattered pink-red dots like freckles, not a single mark."
- **Tail tip drift.** If the tail tip is missing or shrunken, emphasize: "long soft-white tail clearly visible, ending in a soft pink gradient oval tip roughly the size of the head."
- **Color drift across cells.** Generate one row at a time and assemble — this is the single highest-leverage fix for any per-cell drift.

---

## Prompt A — Character + Format (recommended)

Click the copy button on the code block below and paste it into your image tool together with any reference image you have.

```text
A 1536×1664 pixel sprite sheet, 8 columns by 8 rows, 64 cells total, each cell exactly 192×208 pixels. Flat pure black background #000000 with no gradient, no halo, no watermark, no UI chrome, no grid lines, no labels. One centered bipedal chibi-style sprite per cell — all 64 cells are the SAME character — facing forward unless noted, fully inside its cell, leaving a clear black margin (sprite occupies roughly the central 150×170 of its cell). Cel-shaded chibi style, clean soft outlines, flat colors with light shading.

If a reference image is attached, MATCH IT for appearance. Otherwise, draw the following character from scratch.

Character: 大耳帽兜 / Maodou from 洛克王国 / Roco World (rightsholder: 腾讯 / Tencent). A soft-white chibi bunny-like spirit with very long droopy floppy ears that hang down past the shoulders — outer side soft-white, inner side pink / salmon, clearly visible because the ears hang forward. 2-3 small pink-red dots scattered on the forehead between the ears like faint freckles (NOT a single forehead crystal or gem). Large round teal / cyan eyes with a single white catchlight, simple cute expression. Tiny pink mouth. Soft-white round chibi torso, tiny short white arms with small pink paw pads on the underside, stubby short legs. Long soft-white tail ending in a soft pink gradient oval tip roughly the size of the head.

The 8 rows are animation strips — consistent character scale, color, and ground line across all 64 cells:

- Row 0 — idle (6 frames): bipedal standing facing forward, gentle bob, ears swaying, pink tail tip visible behind.
- Row 1 — review (6 frames): one paw lifted near the chin, head slightly tilted, eyes half-lidded, ears drooping forward over the shoulders.
- Row 2 — waving (4 frames): one paw raised high and waving, mouth open in a small smile, pink tail tip visible.
- Row 3 — running-right (8 frames): bipedal run cycle, body angled to the RIGHT, ears trailing LEFT behind the head. Do NOT pre-mirror — the downstream pipeline produces the left-facing variant.
- Row 4 — jumping (5 frames): crouch → push-off → peak airborne (limbs spread, pink tail tip prominent) → descending → landing.
- Row 5 — running alternate (6 frames): lighter run / hop cycle, body upright, both feet visible.
- Row 6 — waiting (6 frames): small idle fidget — tilting head, looking left/right, ear sway, tail swish.
- Row 7 — failed (8 frames): "knocked over" loop — surprised → tipped backward → sitting sad on the ground, with tiny snowflake-spark circles above the head (Ice / Cute type signature — soft and small, not aggressive).

Hard constraints across all 64 cells:

- The ears are ALWAYS droopy / hanging forward / sideways — NEVER standing upright like a normal rabbit, even during running or jumping (ears trail in the direction of motion but still droop, never stiffen).
- The 2-3 pink-red forehead dots are visible in every frame.
- The pink tail tip is visible in idle, review, waving, and jumping frames.
- Unused trailing cells in shorter rows are fully black empty cells.

NEGATIVE — the model is biased toward these for "Ice type" characters; do NOT include any: ice-blue inner ears, pale-cyan inner ears, dark-blue eyes, indigo eyes, frost-blue tail tip, blue tail tip of any kind, forehead crystal, forehead gem, single jewel between the eyes, upright rabbit ears, hats, hoods, scarves, glasses, weapons, additional characters, sparkle particles covering the face, quadruped poses, magenta-saturated body, painterly rendering.
```

---

## Prompt B — Format / Pose only (Plan B)

Pair this with your own short character description (or with a reference image) when you want finer control over wording, or as a fallback if Prompt A drifts. Canonical source: `open-pet-creator/references/generation-prompt-format.md` — if this block ever looks out of date, re-sync from there.

```text
A 1536×1664 pixel sprite sheet, 8 columns by 8 rows, 64 cells total, each cell exactly 192×208 pixels. Flat pure black background #000000 with no gradient, no halo, no signature, no watermark, no UI chrome, no grid lines, no row/column numbers, no labels. One centered bipedal chibi-style sprite per cell — all 64 cells are the SAME character (match the attached reference image and/or the character description provided alongside this prompt) — facing forward unless noted, fully inside its cell with no overlap into neighboring cells. Each sprite occupies roughly the central 150×170 of its 192×208 cell, leaving a clear black margin. Cel-shaded chibi style, clean soft outlines, flat colors with light shading, pixel-adjacent but not strict pixel art.

The 8 rows are animation strips — consistent character scale, color, and ground line across all 64 cells:

- Row 0 — idle (6 frames): bipedal standing pose facing forward, gentle bobbing across frames.
- Row 1 — review (6 frames): thoughtful pose, one paw lifted near the chin, head slightly tilted, eyes half-lidded.
- Row 2 — waving (4 frames): one paw raised high and waving, mouth open in a small smile.
- Row 3 — running-right (8 frames): full 8-frame run cycle, body angled to the right (the downstream pipeline will mirror this row to produce running-left — do NOT pre-mirror).
- Row 4 — jumping (5 frames): jump arc — crouch, push-off, peak airborne (limbs spread), descending, landing.
- Row 5 — running alternate (6 frames): a different lighter run / hop cycle, body upright, both feet visible.
- Row 6 — waiting (6 frames): small idle fidget — tilting head, looking left/right.
- Row 7 — failed (8 frames): "knocked over" loop — surprised → tipped backward → sitting on the ground looking sad.

Unused trailing cells in shorter rows are fully black empty cells. No quadruped poses. No accessories not present in the reference image or character description.
```
