# Plan B — Format / Pose Generic Prompt

This file is the **canonical source** for "Prompt B", the character-agnostic format / pose / animation prompt used to generate Open Pets / Codex source sheets. It specifies image dimensions, grid layout, per-row animation poses, and composition rules — everything **except** the character's appearance.

Every per-pet `docs/<pet-id>-generation-prompt.md` inlines this block (as "Prompt B — Format / Pose only") so users can grab both Prompt A and Prompt B from a single doc. When this canonical source changes, re-sync every per-pet doc's Prompt B section.

## When users reach for Prompt B

Most of the time users should use **Prompt A** in the per-pet doc — it is a self-contained character + format prompt that produces higher-fidelity sheets in one shot. Prompt B is for:

- Users who want to write the character description themselves with fine control over wording.
- Cases where Prompt A drifts in unwanted ways and a "minimal format-only prompt + a reference image" combo works better.
- Prototyping a new pet whose per-pet doc does not yet exist.

## How users pair Prompt B

Send to the image tool, in one message:

1. (Optional but strongly recommended) Reference image(s) of the character.
2. A short character description (palette, signature features, anatomy, what NOT to draw).
3. **Prompt B**, copy-pasted verbatim from the block below.

## Prompt B (canonical block — copy verbatim into per-pet docs)

Always render this block as a fenced `text` code block (```` ```text ```` … ```` ``` ````), NOT a markdown blockquote, so users get a one-click copy button and the pasted text doesn't carry `>` prefixes or literal `**` markers.

```text
A 1536×1664 pixel sprite sheet, 8 columns by 8 rows, 64 cells total, each cell exactly 192×208 pixels. Flat pure black background #000000 with no gradient, no halo, no signature, no watermark, no UI chrome, no grid lines, no row/column numbers, no labels. One centered bipedal chibi-style sprite per cell — all 64 cells are the SAME character (match the attached reference image and/or the character description provided alongside this prompt) — facing forward unless noted, fully inside its cell with no overlap into neighboring cells. Each sprite occupies roughly the central 150×170 of its 192×208 cell, leaving a clear black margin. Cel-shaded chibi style, clean soft outlines, flat colors with light shading, pixel-adjacent but not strict pixel art.

The 8 rows are animation strips — consistent character scale, color, and ground line across all 64 cells:

- Row 0 — idle (6 frames): bipedal standing pose facing forward, gentle bobbing across frames.
- Row 1 — review (6 frames): thoughtful pose, one paw lifted near the chin, head slightly tilted, eyes half-lidded.
- Row 2 — waving (4 frames): one paw raised high and waving, mouth open in a small smile.
- Row 3 — running-right (8 frames): full 8-frame run cycle, body angled to the right (the downstream pipeline will mirror this row to produce running-left — do NOT pre-mirror).
- Row 4 — jumping (5 frames): jump arc — crouch, push-off, peak airborne (limbs spread), descending, landing.
- Row 5 — running alternate (6 frames): a different lighter run / hop cycle, body upright, both feet visible.
- Row 6 — waiting (6 frames):  small idle fidget — tilting head, looking left/right.
- Row 7 — failed (8 frames): "knocked over" loop — surprised → tipped backward → sitting on the ground looking sad.

Unused trailing cells in shorter rows are fully black empty cells. No quadruped poses. No accessories not present in the reference image or character description.
```

## General iteration tips

(Character-specific tips live in per-pet docs.)

- **Single highest-leverage fix when appearance drifts across cells:** generate one row at a time and assemble. Most image models cannot hold a 64-cell consistency budget in a single shot.
- If trailing cells aren't fully black, ask the model explicitly: "rows 0, 1, 6 leave their last 2 cells as fully black empty cells".
- If sprites touch cell edges, reinforce "leave a clear black margin around each sprite".
- Once the sheet is acceptable, save as `pets/<pet-id>/spritesheet-source.png` and proceed to the build steps in `<pet-id>-pet-design.md`.
