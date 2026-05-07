from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps


ROOT = Path("/Users/ctenetliu/Projects/TENET_AI/open-pets")
SRC = ROOT / "pets/pink-star/spritesheet-source.png"
OUT = ROOT / "pets/pink-star/spritesheet.webp"
PREVIEW = ROOT / "pets/pink-star/spritesheet-repacked-preview.png"

SOURCE_ROWS = 8
TARGET_COLS = 8
TARGET_ROWS = 9
CELL_W = 192
CELL_H = 208
TARGET_ROW_SOURCE_ROWS: tuple[tuple[int, bool], ...] = (
    (0, False),  # idle           <- source row 0
    (3, False),  # running-right  <- source row 3
    (3, True),   # running-left   <- source row 3 mirrored
    (2, False),  # waving         <- source row 2
    (4, False),  # jumping        <- source row 4
    (7, False),  # failed         <- source row 7
    (6, False),  # waiting        <- source row 6
    (5, False),  # running        <- source row 5
    (1, False),  # review         <- source row 1
)
USED_COLUMNS_BY_TARGET_ROW: tuple[int, ...] = (6, 8, 8, 4, 5, 8, 6, 6, 6)
SPRITE_DISPLAY_SCALE = 0.98
SPRITE_DISPLAY_OFFSET = (0, 14)
ALPHA_THRESHOLD = 30
OUTLINE_EXPAND = 3


def rgba_from_black_sheet(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    luminance = image.convert("L")
    alpha = luminance.point(lambda p: 255 if p > ALPHA_THRESHOLD else 0)
    if OUTLINE_EXPAND > 1:
        alpha = alpha.filter(ImageFilter.MaxFilter(OUTLINE_EXPAND))
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
            si = index(start_x, start_y)
            if visited[si] or pixels[start_x, start_y] == 0:
                continue
            queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
            visited[si] = 1
            points: list[tuple[int, int]] = []
            touches_border = False
            while queue:
                x, y = queue.popleft()
                points.append((x, y))
                touches_border = touches_border or x == 0 or y == 0 or x == width - 1 or y == height - 1
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    ni = index(nx, ny)
                    if visited[ni] or pixels[nx, ny] == 0:
                        continue
                    visited[ni] = 1
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


def fit_to_cell(frame: Image.Image) -> Image.Image:
    max_w = CELL_W - 10
    max_h = CELL_H - 10
    fit_scale = min(max_w / frame.width, max_h / frame.height)
    scale = min(fit_scale, SPRITE_DISPLAY_SCALE)
    width = max(1, round(frame.width * scale))
    height = max(1, round(frame.height * scale))
    return frame.resize((width, height), Image.Resampling.LANCZOS)


def find_runs(density: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    in_run = False
    start = 0
    for i, v in enumerate(density):
        if v > threshold and not in_run:
            in_run = True
            start = i
        elif v <= threshold and in_run:
            in_run = False
            runs.append((start, i))
    if in_run:
        runs.append((start, len(density)))
    return runs


def detect_source_rows_and_columns(sheet: Image.Image) -> list[list[tuple[int, int, int, int]]]:
    """Detect non-empty row bands then sprite columns within each band, by content projection.

    Returns one list of (x0, y0, x1, y1) source-image bboxes per row.
    """
    rgb = np.array(sheet.convert("RGB"))
    content = (rgb.sum(axis=2) > ALPHA_THRESHOLD).astype(np.uint8)
    H, W = content.shape

    row_bands = find_runs(content.sum(axis=1), threshold=W * 0.005)
    if len(row_bands) != SOURCE_ROWS:
        raise RuntimeError(
            f"expected {SOURCE_ROWS} source rows; detected {len(row_bands)}: {row_bands}"
        )

    rows: list[list[tuple[int, int, int, int]]] = []
    for y0, y1 in row_bands:
        band = content[y0:y1]
        col_runs = find_runs(band.sum(axis=0), threshold=2)
        rows.append([(x0, y0, x1, y1) for x0, x1 in col_runs])
    return rows


def extract_source_rows(sheet: Image.Image) -> list[list[Image.Image]]:
    bbox_rows = detect_source_rows_and_columns(sheet)
    out: list[list[Image.Image]] = []
    for bboxes in bbox_rows:
        frames: list[Image.Image] = []
        for x0, y0, x1, y1 in bboxes:
            crop = sheet.crop((x0, y0, x1, y1))
            cleaned = remove_border_fragments(crop)
            trimmed = trim(cleaned)
            if trimmed is not None:
                frames.append(fit_to_cell(trimmed))
        out.append(frames)
    return out


def paste_centered(canvas: Image.Image, frame: Image.Image, index: int) -> None:
    col = index % TARGET_COLS
    row = index // TARGET_COLS
    offset_x, offset_y = SPRITE_DISPLAY_OFFSET
    local_x = (CELL_W - frame.width) // 2 + offset_x
    local_y = (CELL_H - frame.height) // 2 + offset_y
    local_x = max(0, min(local_x, CELL_W - frame.width))
    local_y = max(0, min(local_y, CELL_H - frame.height))
    canvas.alpha_composite(frame, (col * CELL_W + local_x, row * CELL_H + local_y))


def main() -> None:
    sheet = rgba_from_black_sheet(SRC)
    source_rows = extract_source_rows(sheet)

    counts = [len(r) for r in source_rows]
    print(f"detected per-row frame counts: {counts}")

    canvas = Image.new("RGBA", (TARGET_COLS * CELL_W, TARGET_ROWS * CELL_H), (0, 0, 0, 0))

    for target_row, (source_row, mirror) in enumerate(TARGET_ROW_SOURCE_ROWS):
        row_frames = source_rows[source_row]
        if not row_frames:
            raise RuntimeError(f"no frames extracted from source row {source_row}")
        for col in range(USED_COLUMNS_BY_TARGET_ROW[target_row]):
            frame = row_frames[col % len(row_frames)]
            if mirror:
                frame = ImageOps.mirror(frame)
            paste_centered(canvas, frame, target_row * TARGET_COLS + col)

    canvas.save(OUT, "WEBP", lossless=True, method=6)
    canvas.save(PREVIEW, "PNG")
    print(OUT)
    print(PREVIEW)


if __name__ == "__main__":
    main()
