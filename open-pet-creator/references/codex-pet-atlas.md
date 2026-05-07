# Codex Pet Atlas Reference

## Contract

Codex custom pets use a fixed atlas:

| Property | Value |
| --- | --- |
| Atlas size | `1536x1872` |
| Grid | `8` columns x `9` rows |
| Cell size | `192x208` |
| Format | PNG or WebP with alpha |

Unused cells after each row's frame count must be fully transparent.

## Rows

| Row | State | Used columns |
| --- | --- | ---: |
| 0 | idle | 6 |
| 1 | running-right | 8 |
| 2 | running-left | 8 |
| 3 | waving | 4 |
| 4 | jumping | 5 |
| 5 | failed | 8 |
| 6 | waiting | 6 |
| 7 | running | 6 |
| 8 | review | 6 |

Default row map for an 8x8 source sheet used during the Phrolova repair:

```text
0,3,3m,2,4,7,6,5,1
```

`3m` means source row 3 mirrored horizontally for the target row.

## Tuning Heuristics

- Horizontal center: visible bbox center near `96`.
- Top strip: target `40-45px` mostly clear when the app UI may show a top-right menu. "Mostly" is the operative word — chibi pets with tall hair, hats, or ears commonly let the very top of the bbox extend into this strip without obscuring menu icons. Practical floor for `top_min`: ~`35`. Anything below ~`30` starts to crowd the menu in real layouts.
- Thumbnail size: for upright chibi pets, first idle frame is usually comfortable around `105-125px` wide and `140-155px` high.
- If the pet feels too low, lower `--offset-y`; if a menu overlaps the head, raise `--offset-y`.
- If the pet feels too small, raise `--scale` first before changing cell geometry. Note that `--scale` and `--offset-y` both consume the same top headroom (see SKILL.md "Scale/offset trade-off").
- Keep unused cells transparent. Repeated frames in unused cells can cause wrong previews or state glitches.

## Validation Commands

```bash
python "$SKILL_DIR/scripts/inspect_pet_atlas.py" /path/to/spritesheet.webp
python "$SKILL_DIR/scripts/validate_pet_atlas.py" /path/to/spritesheet.webp
```

Install only after validation has no errors and visual inspection looks consistent.
