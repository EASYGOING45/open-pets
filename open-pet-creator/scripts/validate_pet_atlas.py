#!/usr/bin/env python3
"""Validate a Codex/Open Pets atlas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

ROWS = (
    ("idle", 6),
    ("running-right", 8),
    ("running-left", 8),
    ("waving", 4),
    ("jumping", 5),
    ("failed", 8),
    ("waiting", 6),
    ("running", 6),
    ("review", 6),
)


def alpha_count(image: Image.Image) -> int:
    return sum(image.getchannel("A").histogram()[1:])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("atlas")
    parser.add_argument("--json-out")
    parser.add_argument("--cell-width", type=int, default=192)
    parser.add_argument("--cell-height", type=int, default=208)
    parser.add_argument("--min-used-pixels", type=int, default=50)
    args = parser.parse_args()

    atlas = Path(args.atlas).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    cells: list[dict[str, object]] = []

    try:
        with Image.open(atlas) as opened:
            source_format = opened.format
            source_mode = opened.mode
            image = opened.convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "errors": [f"could not open atlas: {exc}"], "warnings": []}
        print(json.dumps(result, indent=2))
        raise SystemExit(1)

    expected_size = (8 * args.cell_width, 9 * args.cell_height)
    if image.size != expected_size:
        errors.append(f"expected {expected_size[0]}x{expected_size[1]}, got {image.width}x{image.height}")
    if source_format not in {"PNG", "WEBP"}:
        errors.append(f"expected PNG or WebP, got {source_format}")
    if "A" not in source_mode:
        errors.append("atlas source mode does not expose alpha")

    for row_index, (state, used_columns) in enumerate(ROWS):
        for col in range(8):
            left = col * args.cell_width
            top = row_index * args.cell_height
            cell = image.crop((left, top, left + args.cell_width, top + args.cell_height))
            nontransparent = alpha_count(cell)
            used = col < used_columns
            cells.append({"state": state, "row": row_index, "column": col, "used": used, "pixels": nontransparent})
            if used and nontransparent < args.min_used_pixels:
                errors.append(f"{state} row {row_index} column {col} is empty or too sparse ({nontransparent})")
            if not used and nontransparent:
                errors.append(f"{state} row {row_index} unused column {col} is not transparent ({nontransparent})")

    result = {
        "ok": not errors,
        "file": str(atlas),
        "format": source_format,
        "mode": source_mode,
        "width": image.width,
        "height": image.height,
        "errors": errors,
        "warnings": warnings,
        "cells": cells,
    }
    if args.json_out:
        Path(args.json_out).expanduser().resolve().write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "cells"}, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
