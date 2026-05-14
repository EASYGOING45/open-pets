#!/usr/bin/env python3
"""Render a side-by-side preview of every variant declared on a pet.

Reads a pet's ``pet.json``, extracts the idle frame from its
spritesheet, applies each declared variant's ``recipe`` using the
same CSS-filter math the runtime uses (matching W3C Filter Effects
1.0), and composes a captioned grid PNG saved alongside the pet.

Usage:
    python3 preview_variants.py pets/rocom-maodou/
    python3 preview_variants.py pets/rocom-maodou/ --sampler
    python3 preview_variants.py pets/rocom-maodou/ --open

``--sampler`` ignores any ``variants`` declared in pet.json and
renders a fixed grid of representative recipes — useful when an
author is just starting and wants to see what hue rotation /
saturation / sepia look like on their sprite before picking final
recipes.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

CELL_W = 192
CELL_H = 208
CAPTION_H = 64
TILE_PAD = 12
GRID_BG = (24, 24, 28, 255)
TILE_BG = (40, 40, 46, 255)
CAPTION_FG = (235, 235, 240, 255)
CAPTION_DIM = (160, 160, 168, 255)
TITLE_H = 56
COLS_MAX = 4

SAMPLER_VARIANTS: tuple[dict, ...] = (
    {"id": "normal", "displayName": "Normal", "weight": 100},
    {"id": "rose", "displayName": "Rose +25°", "weight": 1, "recipe": {"hue_rotate": 25, "saturate": 1.2}},
    {"id": "amber", "displayName": "Amber +50°", "weight": 1, "recipe": {"hue_rotate": 50, "saturate": 1.3}},
    {"id": "leaf", "displayName": "Leaf +120°", "weight": 1, "recipe": {"hue_rotate": 120, "saturate": 1.15}},
    {"id": "ocean", "displayName": "Ocean +200°", "weight": 1, "recipe": {"hue_rotate": 200, "saturate": 1.4, "brightness": 1.05}},
    {"id": "violet", "displayName": "Violet +260°", "weight": 1, "recipe": {"hue_rotate": 260, "saturate": 1.3}},
    {"id": "moonlit", "displayName": "Moonlit (sample)", "weight": 1, "recipe": {"hue_rotate": 200, "saturate": 1.4, "brightness": 1.08}, "effects": ["sparkle"]},
    {"id": "vintage", "displayName": "Vintage", "weight": 1, "recipe": {"sepia": 0.55, "saturate": 0.9}},
    {"id": "washed", "displayName": "Washed", "weight": 1, "recipe": {"saturate": 0.45, "brightness": 1.1}},
)


# --- CSS Filter Effects 1.0 matrices --------------------------------------
#
# Each helper returns a 4x4 affine matrix acting on column-vector
# [R, G, B, 1] where RGB is in 0..1. Composition is matrix multiply in
# CSS-filter order (left-to-right in the filter string).


def _identity() -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _hue_rotate(deg: float) -> list[list[float]]:
    rad = math.radians(deg)
    c, s = math.cos(rad), math.sin(rad)
    return [
        [0.213 + 0.787 * c - 0.213 * s, 0.715 - 0.715 * c - 0.715 * s, 0.072 - 0.072 * c + 0.928 * s, 0.0],
        [0.213 - 0.213 * c + 0.143 * s, 0.715 + 0.285 * c + 0.140 * s, 0.072 - 0.072 * c - 0.283 * s, 0.0],
        [0.213 - 0.213 * c - 0.787 * s, 0.715 - 0.715 * c + 0.715 * s, 0.072 + 0.928 * c + 0.072 * s, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _saturate(n: float) -> list[list[float]]:
    return [
        [0.213 + 0.787 * n, 0.715 - 0.715 * n, 0.072 - 0.072 * n, 0.0],
        [0.213 - 0.213 * n, 0.715 + 0.285 * n, 0.072 - 0.072 * n, 0.0],
        [0.213 - 0.213 * n, 0.715 - 0.715 * n, 0.072 + 0.928 * n, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _brightness(n: float) -> list[list[float]]:
    return [
        [n, 0.0, 0.0, 0.0],
        [0.0, n, 0.0, 0.0],
        [0.0, 0.0, n, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _contrast(n: float) -> list[list[float]]:
    offset = (1.0 - n) / 2.0
    return [
        [n, 0.0, 0.0, offset],
        [0.0, n, 0.0, offset],
        [0.0, 0.0, n, offset],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _grayscale(n: float) -> list[list[float]]:
    inv = 1.0 - n
    return [
        [0.2126 + 0.7874 * inv, 0.7152 - 0.7152 * inv, 0.0722 - 0.0722 * inv, 0.0],
        [0.2126 - 0.2126 * inv, 0.7152 + 0.2848 * inv, 0.0722 - 0.0722 * inv, 0.0],
        [0.2126 - 0.2126 * inv, 0.7152 - 0.7152 * inv, 0.0722 + 0.9278 * inv, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _sepia(n: float) -> list[list[float]]:
    inv = 1.0 - n
    return [
        [0.393 + 0.607 * inv, 0.769 - 0.769 * inv, 0.189 - 0.189 * inv, 0.0],
        [0.349 - 0.349 * inv, 0.686 + 0.314 * inv, 0.168 - 0.168 * inv, 0.0],
        [0.272 - 0.272 * inv, 0.534 - 0.534 * inv, 0.131 + 0.869 * inv, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


# Order matches the runtime compile order documented in §1.3 of the
# design doc — and what the JS side will produce.
_RECIPE_ORDER = (
    ("hue_rotate", _hue_rotate),
    ("saturate", _saturate),
    ("brightness", _brightness),
    ("contrast", _contrast),
    ("grayscale", _grayscale),
    ("sepia", _sepia),
)


def compile_recipe(recipe: dict | None) -> list[list[float]] | None:
    """Return composed 4x4 matrix for a recipe, or None for identity."""
    if not recipe:
        return None
    matrix = _identity()
    applied = False
    for key, fn in _RECIPE_ORDER:
        if key in recipe:
            matrix = _mul(fn(float(recipe[key])), matrix)
            applied = True
    return matrix if applied else None


def apply_recipe(image: Image.Image, recipe: dict | None) -> Image.Image:
    """Return ``image`` with the recipe applied. Alpha is preserved untouched."""
    matrix = compile_recipe(recipe)
    if matrix is None:
        return image.copy()
    # PIL takes a 12-tuple (3 rows × 4 cols) acting on 0..255 byte values.
    # Linear coefs pass through; offsets must scale 0..1 → 0..255.
    pil_matrix = (
        matrix[0][0], matrix[0][1], matrix[0][2], matrix[0][3] * 255.0,
        matrix[1][0], matrix[1][1], matrix[1][2], matrix[1][3] * 255.0,
        matrix[2][0], matrix[2][1], matrix[2][2], matrix[2][3] * 255.0,
    )
    if image.mode == "RGBA":
        rgb = image.convert("RGB")
        transformed = rgb.convert("RGB", pil_matrix)
        out = transformed.convert("RGBA")
        out.putalpha(image.getchannel("A"))
        return out
    return image.convert("RGB", pil_matrix)


# --- Layout ----------------------------------------------------------------


@dataclass
class Variant:
    id: str
    weight: int
    display_name: str
    recipe: dict | None
    effects: list[str]

    @classmethod
    def from_dict(cls, raw: dict) -> "Variant":
        name = raw.get("displayName")
        if isinstance(name, dict):
            display = name.get("zh") or name.get("en") or raw["id"]
        elif isinstance(name, str):
            display = name
        else:
            display = raw["id"]
        return cls(
            id=raw["id"],
            weight=int(raw.get("weight", 1)),
            display_name=display,
            recipe=raw.get("recipe"),
            effects=list(raw.get("effects", [])),
        )


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # Index hints for .ttc collections that contain multiple subfonts —
    # PingFang.ttc[2] is "PingFang SC" which has the simplified-Chinese
    # glyphs we need; index 0 is "PingFang HK" which falls back to boxes
    # for some characters when used cross-region.
    candidates: tuple[tuple[str, int], ...] = (
        ("/System/Library/Fonts/PingFang.ttc", 2),
        ("/System/Library/Fonts/PingFang.ttc", 0),
        ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
        ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
        ("/System/Library/Fonts/Helvetica.ttc", 0),
        ("/System/Library/Fonts/SFNS.ttf", 0),
    )
    for path, index in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size, index=index)
            except OSError:
                continue
    return ImageFont.load_default()


def _format_recipe(recipe: dict | None) -> str:
    if not recipe:
        return "(no filter)"
    parts: list[str] = []
    for key, _ in _RECIPE_ORDER:
        if key not in recipe:
            continue
        v = recipe[key]
        if key == "hue_rotate":
            parts.append(f"hue {int(v)}°")
        else:
            parts.append(f"{key.replace('_', ' ')} {v}")
    return " · ".join(parts)


def extract_idle_frame(spritesheet: Image.Image) -> Image.Image:
    """Crop the (0, 0) cell — first frame of the idle row — and trim alpha bbox."""
    cell = spritesheet.crop((0, 0, CELL_W, CELL_H))
    bbox = cell.getchannel("A").getbbox() if cell.mode == "RGBA" else cell.getbbox()
    if bbox is None:
        return cell
    # Center the trimmed sprite back into a full cell so all tiles share
    # the same dimensions in the grid.
    trimmed = cell.crop(bbox)
    canvas = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    x = (CELL_W - trimmed.width) // 2
    y = (CELL_H - trimmed.height) // 2
    canvas.alpha_composite(trimmed, (x, y))
    return canvas


def render_grid(
    pet_id: str,
    display_name: str,
    base_frame: Image.Image,
    variants: Sequence[Variant],
    sampler: bool,
) -> Image.Image:
    cols = min(len(variants), COLS_MAX)
    rows = (len(variants) + cols - 1) // cols
    tile_w = CELL_W + TILE_PAD * 2
    tile_h = CELL_H + CAPTION_H + TILE_PAD * 2
    grid_w = cols * tile_w + TILE_PAD
    grid_h = rows * tile_h + TITLE_H + TILE_PAD

    canvas = Image.new("RGBA", (grid_w, grid_h), GRID_BG)
    draw = ImageDraw.Draw(canvas)

    title_font = _font(20)
    sub_font = _font(13)
    name_font = _font(15)
    recipe_font = _font(11)

    title_text = f"{display_name} ({pet_id}) — {'sampler' if sampler else 'declared variants'}"
    draw.text((TILE_PAD * 2, TILE_PAD), title_text, font=title_font, fill=CAPTION_FG)
    sub_text = "Per-recipe preview matches runtime ctx.filter rendering exactly."
    draw.text((TILE_PAD * 2, TILE_PAD + 26), sub_text, font=sub_font, fill=CAPTION_DIM)

    for index, variant in enumerate(variants):
        col = index % cols
        row = index // cols
        tile_x = TILE_PAD + col * tile_w
        tile_y = TITLE_H + row * tile_h

        # Tile background
        draw.rectangle(
            (tile_x, tile_y, tile_x + tile_w - TILE_PAD, tile_y + tile_h - TILE_PAD),
            fill=TILE_BG,
        )

        sprite = apply_recipe(base_frame, variant.recipe)
        canvas.alpha_composite(sprite, (tile_x + TILE_PAD, tile_y + TILE_PAD))

        # Caption strip
        cap_y = tile_y + TILE_PAD + CELL_H + 6
        weight_label = f"  ·  weight {variant.weight}" if not sampler else ""
        # Use ★ (U+2605, BLACK STAR) instead of ✨ — PingFang/Helvetica
        # both have it, while ✨ (U+2728) needs an emoji font PIL can't
        # render in color.
        effect_label = "  ★" if "sparkle" in variant.effects else ""
        title_line = f"{variant.display_name}{effect_label}{weight_label}"
        draw.text((tile_x + TILE_PAD, cap_y), title_line, font=name_font, fill=CAPTION_FG)
        recipe_line = _format_recipe(variant.recipe)
        draw.text((tile_x + TILE_PAD, cap_y + 22), recipe_line, font=recipe_font, fill=CAPTION_DIM)
        id_line = f"id: {variant.id}"
        draw.text((tile_x + TILE_PAD, cap_y + 40), id_line, font=recipe_font, fill=CAPTION_DIM)

    return canvas


# --- Entry point -----------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pet_dir", type=Path, help="Path to a pet directory containing pet.json + spritesheet")
    parser.add_argument("--sampler", action="store_true", help="Ignore declared variants; render a fixed sampler grid instead")
    parser.add_argument("--open", action="store_true", dest="open_after", help="`open` the resulting PNG after writing it (macOS)")
    parser.add_argument("--output", type=Path, default=None, help="Override output path (default: <pet_dir>/variants-preview.png)")
    args = parser.parse_args()

    pet_dir = args.pet_dir.expanduser().resolve()
    if not pet_dir.is_dir():
        print(f"error: {pet_dir} is not a directory", file=sys.stderr)
        return 2

    pet_json_path = pet_dir / "pet.json"
    if not pet_json_path.exists():
        print(f"error: {pet_json_path} not found", file=sys.stderr)
        return 2

    pet_json = json.loads(pet_json_path.read_text())
    sheet_rel = pet_json.get("spritesheetPath", "spritesheet.webp")
    sheet_path = (pet_dir / sheet_rel).resolve()
    if not sheet_path.exists():
        print(f"error: spritesheet {sheet_path} not found", file=sys.stderr)
        return 2

    spritesheet = Image.open(sheet_path).convert("RGBA")
    base_frame = extract_idle_frame(spritesheet)

    if args.sampler:
        variants = [Variant.from_dict(v) for v in SAMPLER_VARIANTS]
        print(f"sampler mode: rendering {len(variants)} representative recipes")
    else:
        declared = pet_json.get("variants") or []
        if not declared:
            print(
                "this pet has no `variants` declared in pet.json yet.\n"
                "tip: run again with --sampler to preview common recipes\n"
                "     before picking final variants for this pet.",
                file=sys.stderr,
            )
            return 1
        variants = [Variant.from_dict(v) for v in declared]
        print(f"declared mode: rendering {len(variants)} variants from pet.json")

    grid = render_grid(
        pet_id=pet_json.get("id", pet_dir.name),
        display_name=pet_json.get("displayName", pet_dir.name),
        base_frame=base_frame,
        variants=variants,
        sampler=args.sampler,
    )

    out = args.output or (pet_dir / "variants-preview.png")
    grid.save(out, "PNG")
    print(f"wrote {out}  ({grid.width}×{grid.height})")

    if args.open_after:
        try:
            subprocess.run(["open", str(out)], check=False)
        except FileNotFoundError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
