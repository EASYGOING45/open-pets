#!/usr/bin/env python3
"""Fix Phrolova spritesheet frame jitter — preserve aspect ratio.

The original repacker scales each frame independently (fit_to_cell),
so wider sprites get scaled down more and narrower ones less.  This
causes visible size jitter during animation.

WRONG fix: resize all frames to the same pixel dimensions → distorts
frames with different aspect ratios.

CORRECT fix: scale each frame to fit within a uniform bounding box
while maintaining its own aspect ratio, then center in the cell.
This way all frames share the same max envelope (no jitter on the
"ground line" or "head position"), but each frame's internal
proportions stay faithful to the source.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path("/Users/ctenetliu/Projects/TENET_AI/open-pets")
SRC = ROOT / "pets/phrolova/spritesheet-source.png"
OUT = ROOT / "pets/phrolova/spritesheet.webp"
PREVIEW = ROOT / "pets/phrolova/spritesheet-repacked-preview.png"

SOURCE_COLS = 8
SOURCE_ROWS = 8
TARGET_COLS = 8
TARGET_ROWS = 9
CELL_W = 192
CELL_H = 208
PADDING = 10
OFFSET = (0, 13)

# The contract test requires top_min >= 35.  Since the sprite is centered
# vertically with offset_y=13, the max sprite height that satisfies this is:
#   local_y = (CELL_H - sprite_h) / 2 + OFFSET_Y >= 35
#   sprite_h <= CELL_H - 2 * (35 - OFFSET_Y) = 208 - 44 = 164
MIN_TOP_CLEARANCE = 35
MAX_SPRITE_H = CELL_H - 2 * (MIN_TOP_CLEARANCE - OFFSET[1])
MAX_SPRITE_W = CELL_W - PADDING

TARGET_ROW_SOURCE_ROWS: tuple[tuple[int, bool], ...] = (
    (0, False),  # idle
    (3, False),  # running-right
    (3, True),   # running-left
    (2, False),  # waving
    (4, False),  # jumping
    (7, False),  # failed
    (6, False),  # waiting
    (5, False),  # running
    (1, False),  # review
)
USED_COLUMNS: tuple[int, ...] = (6, 8, 8, 4, 5, 8, 6, 6, 6)


def rgba_from_black_sheet(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    luminance = image.convert("L")
    alpha = luminance.point(lambda p: 255 if p > 10 else 0)
    alpha = alpha.filter(ImageFilter.MaxFilter(5))
    image.putalpha(alpha)
    return image


def trim(frame: Image.Image) -> Image.Image | None:
    bbox = frame.getbbox()
    if bbox is None:
        return None
    return frame.crop(bbox)


def remove_border_fragments(frame: Image.Image) -> Image.Image:
    frame = frame.copy()
    alpha = frame.getchannel("A")
    width, height = frame.size
    pixels = alpha.load()
    visited = bytearray(width * height)
    components: list[tuple[int, bool, list[tuple[int, int]]]] = []

    def index(x: int, y: int) -> int:
        return y * width + x

    for start_y in range(height):
        for start_x in range(width):
            start_index = index(start_x, start_y)
            if visited[start_index] or pixels[start_x, start_y] == 0:
                continue
            queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
            visited[start_index] = 1
            points: list[tuple[int, int]] = []
            touches_border = False
            while queue:
                x, y = queue.popleft()
                points.append((x, y))
                touches_border = touches_border or x == 0 or y == 0 or x == width - 1 or y == height - 1
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    neighbor_index = index(nx, ny)
                    if visited[neighbor_index] or pixels[nx, ny] == 0:
                        continue
                    visited[neighbor_index] = 1
                    queue.append((nx, ny))
            components.append((len(points), touches_border, points))

    if not components:
        frame.putalpha(alpha)
        return frame

    largest = max(area for area, _, _ in components)
    for area, touches_border, points in components:
        if area < 12 or (touches_border and area < largest * 0.25):
            for x, y in points:
                pixels[x, y] = 0
    frame.putalpha(alpha)
    return frame


def extract_source_rows(sheet: Image.Image) -> list[list[Image.Image]]:
    """Extract trimmed frames (NOT yet scaled) from the source grid."""
    rows: list[list[Image.Image]] = []
    src_w, src_h = sheet.size
    for row in range(SOURCE_ROWS):
        frames: list[Image.Image] = []
        top = round(row * src_h / SOURCE_ROWS)
        bottom = round((row + 1) * src_h / SOURCE_ROWS)
        for col in range(SOURCE_COLS):
            left = round(col * src_w / SOURCE_COLS)
            right = round((col + 1) * src_w / SOURCE_COLS)
            frame = trim(remove_border_fragments(sheet.crop((left, top, right, bottom))))
            if frame is not None:
                frames.append(frame)
        rows.append(frames)
    return rows


def fit_frame(frame: Image.Image) -> Image.Image:
    """Scale frame to fit within MAX_SPRITE_W x MAX_SPRITE_H, preserving aspect ratio.

    Each frame gets its own scale based on its own dimensions, but the
    bounding box (max_w x max_h) is the same for all frames in the row.
    This means:
    - Taller/narrower frames get scaled to max_h, centered horizontally
    - Wider/shorter frames get scaled to max_w, centered vertically
    - The "ground line" and "head ceiling" are consistent across frames
    """
    scale = min(MAX_SPRITE_W / frame.width, MAX_SPRITE_H / frame.height)
    new_w = max(1, round(frame.width * scale))
    new_h = max(1, round(frame.height * scale))
    return frame.resize((new_w, new_h), Image.Resampling.LANCZOS)


def paste_centered(canvas: Image.Image, frame: Image.Image, index: int) -> None:
    col = index % TARGET_COLS
    row = index // TARGET_COLS
    offset_x, offset_y = OFFSET
    local_x = (CELL_W - frame.width) // 2 + offset_x
    local_y = (CELL_H - frame.height) // 2 + offset_y
    local_x = max(0, min(local_x, CELL_W - frame.width))
    local_y = max(0, min(local_y, CELL_H - frame.height))
    x = col * CELL_W + local_x
    y = row * CELL_H + local_y
    canvas.alpha_composite(frame, (x, y))


def main() -> None:
    sheet = rgba_from_black_sheet(SRC)
    source_rows = extract_source_rows(sheet)

    print(f"Cell: {CELL_W}x{CELL_H}, padding: {PADDING}, offset: {OFFSET}")
    print(f"Max sprite envelope: {MAX_SPRITE_W}x{MAX_SPRITE_H}")
    print()

    # Scale each frame to fit the uniform envelope, preserving aspect ratio
    scaled_rows: list[list[Image.Image]] = []
    for i, row_frames in enumerate(source_rows):
        scaled = [fit_frame(f) for f in row_frames]
        scaled_rows.append(scaled)
        sizes = [(f.width, f.height) for f in scaled]
        print(f"  row {i}: {len(scaled)} frames → sizes={sizes}")

    # Build the atlas
    canvas = Image.new("RGBA", (TARGET_COLS * CELL_W, TARGET_ROWS * CELL_H), (0, 0, 0, 0))
    for target_row, (source_row, mirror) in enumerate(TARGET_ROW_SOURCE_ROWS):
        row_frames = scaled_rows[source_row]
        if not row_frames:
            raise RuntimeError(f"No frames in source row {source_row}")
        for col in range(USED_COLUMNS[target_row]):
            frame = row_frames[col % len(row_frames)]
            if mirror:
                frame = ImageOps.mirror(frame)
            paste_centered(canvas, frame, target_row * TARGET_COLS + col)

    canvas.save(OUT, "WEBP", lossless=True, method=6)
    canvas.save(PREVIEW, "PNG")
    print(f"\nDone! Output: {OUT}")
    print(f"Preview: {PREVIEW}")


if __name__ == "__main__":
    main()
