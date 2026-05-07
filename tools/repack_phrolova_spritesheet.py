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
TARGET_ROW_SOURCE_ROWS: tuple[tuple[int, bool], ...] = (
    (0, False),  # idle
    (3, False),  # running-right
    (3, True),  # running-left
    (2, False),  # waving
    (4, False),  # jumping
    (7, False),  # failed
    (6, False),  # waiting
    (5, False),  # running
    (1, False),  # review
)
USED_COLUMNS_BY_TARGET_ROW: tuple[int, ...] = (6, 8, 8, 4, 5, 8, 6, 6, 6)
SPRITE_DISPLAY_SCALE = 1.07
SPRITE_DISPLAY_OFFSET = (0, 13)


def rgba_from_black_sheet(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    luminance = image.convert("L")
    alpha = luminance.point(lambda p: 255 if p > 10 else 0)
    # Preserve dark sprite outlines by expanding the visible subject mask.
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


def fit_to_cell(frame: Image.Image) -> Image.Image:
    max_w = CELL_W - 10
    max_h = CELL_H - 10
    fit_scale = min(max_w / frame.width, max_h / frame.height)
    scale = min(fit_scale, SPRITE_DISPLAY_SCALE)
    width = max(1, round(frame.width * scale))
    height = max(1, round(frame.height * scale))
    return frame.resize((width, height), Image.Resampling.LANCZOS)


def extract_source_rows(sheet: Image.Image) -> list[list[Image.Image]]:
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
                frames.append(fit_to_cell(frame))
        rows.append(frames)

    return rows


def extract_frames(sheet: Image.Image) -> list[Image.Image]:
    return [frame for row in extract_source_rows(sheet) for frame in row]


def paste_centered(canvas: Image.Image, frame: Image.Image, index: int) -> None:
    col = index % TARGET_COLS
    row = index // TARGET_COLS
    offset_x, offset_y = SPRITE_DISPLAY_OFFSET
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
    extracted_count = sum(len(row) for row in source_rows)
    if extracted_count == 0:
        raise RuntimeError("No frames extracted from source sheet")

    canvas = Image.new("RGBA", (TARGET_COLS * CELL_W, TARGET_ROWS * CELL_H), (0, 0, 0, 0))

    # Codex indexes a fixed 8 x 9 sheet; unused cells must stay transparent.
    for target_row, (source_row, mirror) in enumerate(TARGET_ROW_SOURCE_ROWS):
        row_frames = source_rows[source_row]
        if not row_frames:
            raise RuntimeError(f"No frames extracted from source row {source_row}")
        for col in range(USED_COLUMNS_BY_TARGET_ROW[target_row]):
            frame = row_frames[col % len(row_frames)]
            if mirror:
                frame = ImageOps.mirror(frame)
            paste_centered(canvas, frame, target_row * TARGET_COLS + col)

    canvas.save(OUT, "WEBP", lossless=True, method=6)
    canvas.save(PREVIEW, "PNG")
    print(f"extracted={extracted_count}")
    print(OUT)
    print(PREVIEW)


if __name__ == "__main__":
    main()
