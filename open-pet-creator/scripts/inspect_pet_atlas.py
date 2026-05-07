#!/usr/bin/env python3
"""Print per-row visible bounds for a Codex/Open Pets atlas."""

from __future__ import annotations

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("atlas")
    parser.add_argument("--cell-width", type=int, default=192)
    parser.add_argument("--cell-height", type=int, default=208)
    args = parser.parse_args()

    atlas = Path(args.atlas).expanduser().resolve()
    image = Image.open(atlas).convert("RGBA")
    print(f"atlas={atlas}")
    print(f"size={image.width}x{image.height}")
    for row_index, (state, used_columns) in enumerate(ROWS):
        widths: list[int] = []
        heights: list[int] = []
        xcenters: list[float] = []
        ycenters: list[float] = []
        tops: list[int] = []
        boxes: list[tuple[int, int, int, int]] = []
        for col in range(used_columns):
            left = col * args.cell_width
            top = row_index * args.cell_height
            cell = image.crop((left, top, left + args.cell_width, top + args.cell_height))
            bbox = cell.getchannel("A").getbbox()
            if bbox is None:
                continue
            x1, y1, x2, y2 = bbox
            boxes.append(bbox)
            widths.append(x2 - x1)
            heights.append(y2 - y1)
            xcenters.append((x1 + x2) / 2)
            ycenters.append((y1 + y2) / 2)
            tops.append(y1)
        unused_clear = True
        for col in range(used_columns, 8):
            left = col * args.cell_width
            top = row_index * args.cell_height
            cell = image.crop((left, top, left + args.cell_width, top + args.cell_height))
            unused_clear = unused_clear and cell.getchannel("A").getbbox() is None
        if not boxes:
            print(f"{state:13} empty")
            continue
        print(
            f"{state:13} "
            f"avg_size={sum(widths)/len(widths):.1f}x{sum(heights)/len(heights):.1f} "
            f"xcenter={sum(xcenters)/len(xcenters):.1f} "
            f"ycenter={sum(ycenters)/len(ycenters):.1f} "
            f"top_min={min(tops)} "
            f"row_bbox=({min(b[0] for b in boxes)},{min(b[1] for b in boxes)},{max(b[2] for b in boxes)},{max(b[3] for b in boxes)}) "
            f"unused_clear={unused_clear}"
        )


if __name__ == "__main__":
    main()
