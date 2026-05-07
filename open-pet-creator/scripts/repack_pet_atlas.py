#!/usr/bin/env python3
"""Repack an existing pet sheet into a Codex 8x9 pet atlas."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

DEFAULT_USED_COLUMNS = (6, 8, 8, 4, 5, 8, 6, 6, 6)
DEFAULT_ROW_MAP = ("0", "3", "3m", "2", "4", "7", "6", "5", "1")


def parse_int_list(value: str, expected: int, label: str) -> tuple[int, ...]:
    parts = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    if len(parts) != expected:
        raise argparse.ArgumentTypeError(f"{label} must contain {expected} comma-separated integers")
    return parts


def parse_row_map(value: str, expected: int) -> tuple[tuple[int, bool], ...]:
    rows: list[tuple[int, bool]] = []
    for raw in value.split(","):
        token = raw.strip().lower()
        mirror = token.endswith("m")
        if mirror:
            token = token[:-1]
        if not token.isdigit():
            raise argparse.ArgumentTypeError(f"invalid row-map token: {raw}")
        rows.append((int(token), mirror))
    if len(rows) != expected:
        raise argparse.ArgumentTypeError(f"row-map must contain {expected} entries")
    return tuple(rows)


def rgba_from_sheet(path: Path, black_threshold: int, outline_expand: int, use_existing_alpha: bool) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if use_existing_alpha and image.getchannel("A").getbbox() is not None:
        return image
    luminance = image.convert("L")
    alpha = luminance.point(lambda p: 255 if p > black_threshold else 0)
    if outline_expand > 1:
        alpha = alpha.filter(ImageFilter.MaxFilter(outline_expand))
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


def fit_to_cell(frame: Image.Image, cell_w: int, cell_h: int, padding: int, scale_adjust: float) -> Image.Image:
    max_w = cell_w - padding
    max_h = cell_h - padding
    fit_scale = min(max_w / frame.width, max_h / frame.height)
    scale = min(fit_scale, scale_adjust)
    width = max(1, round(frame.width * scale))
    height = max(1, round(frame.height * scale))
    return frame.resize((width, height), Image.Resampling.LANCZOS)


def extract_source_rows(sheet: Image.Image, source_cols: int, source_rows: int, cell_w: int, cell_h: int, padding: int, scale: float) -> list[list[Image.Image]]:
    rows: list[list[Image.Image]] = []
    src_w, src_h = sheet.size
    for row in range(source_rows):
        frames: list[Image.Image] = []
        top = round(row * src_h / source_rows)
        bottom = round((row + 1) * src_h / source_rows)
        for col in range(source_cols):
            left = round(col * src_w / source_cols)
            right = round((col + 1) * src_w / source_cols)
            frame = trim(remove_border_fragments(sheet.crop((left, top, right, bottom))))
            if frame is not None:
                frames.append(fit_to_cell(frame, cell_w, cell_h, padding, scale))
        rows.append(frames)
    return rows


def find_content_runs(values: list[int], threshold: float) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    in_run = False
    start = 0
    for i, v in enumerate(values):
        if v > threshold and not in_run:
            in_run = True
            start = i
        elif v <= threshold and in_run:
            in_run = False
            runs.append((start, i))
    if in_run:
        runs.append((start, len(values)))
    return runs


def extract_source_rows_detected(sheet: Image.Image, source_rows: int, cell_w: int, cell_h: int, padding: int, scale: float) -> list[list[Image.Image]]:
    """Detection-based extraction: project alpha onto axes to find sprite bboxes.

    Use when generated source sheets have variable sprite counts per row, or when
    individual sprites are wider/taller than the naive (width / source_cols) split.
    Even-grid splitting can slice such sprites across cell boundaries.
    """
    alpha = sheet.getchannel("A")
    src_w, src_h = alpha.size

    row_proj = alpha.resize((1, src_h), Image.Resampling.BOX)
    row_density = [row_proj.getpixel((0, y)) for y in range(src_h)]
    row_runs = find_content_runs(row_density, threshold=2)
    if len(row_runs) != source_rows:
        raise SystemExit(
            f"detect-sprites: expected {source_rows} rows but found {len(row_runs)}; "
            f"check --source-rows or fall back to even-grid extraction"
        )

    rows: list[list[Image.Image]] = []
    for y0, y1 in row_runs:
        band = alpha.crop((0, y0, src_w, y1))
        col_proj = band.resize((src_w, 1), Image.Resampling.BOX)
        col_density = [col_proj.getpixel((x, 0)) for x in range(src_w)]
        col_runs = find_content_runs(col_density, threshold=2)
        frames: list[Image.Image] = []
        for x0, x1 in col_runs:
            crop = sheet.crop((x0, y0, x1, y1))
            frame = trim(remove_border_fragments(crop))
            if frame is not None:
                frames.append(fit_to_cell(frame, cell_w, cell_h, padding, scale))
        rows.append(frames)
    return rows


def paste_frame(canvas: Image.Image, frame: Image.Image, index: int, columns: int, cell_w: int, cell_h: int, offset_x: int, offset_y: int) -> None:
    col = index % columns
    row = index // columns
    local_x = (cell_w - frame.width) // 2 + offset_x
    local_y = (cell_h - frame.height) // 2 + offset_y
    local_x = max(0, min(local_x, cell_w - frame.width))
    local_y = max(0, min(local_y, cell_h - frame.height))
    canvas.alpha_composite(frame, (col * cell_w + local_x, row * cell_h + local_y))


def save_image(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".webp":
        image.save(path, "WEBP", lossless=True, method=6)
    else:
        image.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--preview")
    parser.add_argument("--source-cols", type=int, default=8)
    parser.add_argument("--source-rows", type=int, default=8)
    parser.add_argument("--target-cols", type=int, default=8)
    parser.add_argument("--target-rows", type=int, default=9)
    parser.add_argument("--cell-width", type=int, default=192)
    parser.add_argument("--cell-height", type=int, default=208)
    parser.add_argument("--row-map", default=",".join(DEFAULT_ROW_MAP))
    parser.add_argument("--used-columns", default=",".join(str(item) for item in DEFAULT_USED_COLUMNS))
    parser.add_argument("--scale", type=float, default=0.98)
    parser.add_argument("--offset-x", type=int, default=0)
    parser.add_argument("--offset-y", type=int, default=16)
    parser.add_argument("--padding", type=int, default=10)
    parser.add_argument("--black-threshold", type=int, default=10)
    parser.add_argument("--outline-expand", type=int, default=5)
    parser.add_argument("--use-existing-alpha", action="store_true")
    parser.add_argument(
        "--detect-sprites",
        action="store_true",
        help="Detect sprite bounding boxes by alpha projection instead of splitting on an even (--source-cols x --source-rows) grid. Use when the source sheet has variable sprite counts per row, or when individual sprites are wider than (image_width / source_cols).",
    )
    args = parser.parse_args()

    row_map = parse_row_map(args.row_map, args.target_rows)
    used_columns = parse_int_list(args.used_columns, args.target_rows, "used-columns")

    source = Path(args.source).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    sheet = rgba_from_sheet(source, args.black_threshold, args.outline_expand, args.use_existing_alpha)
    if args.detect_sprites:
        source_rows = extract_source_rows_detected(
            sheet, args.source_rows, args.cell_width, args.cell_height, args.padding, args.scale
        )
        print(f"detect-sprites: per-row frame counts = {[len(r) for r in source_rows]}")
    else:
        source_rows = extract_source_rows(
            sheet, args.source_cols, args.source_rows, args.cell_width, args.cell_height, args.padding, args.scale
        )

    canvas = Image.new("RGBA", (args.target_cols * args.cell_width, args.target_rows * args.cell_height), (0, 0, 0, 0))
    for target_row, (source_row, mirror) in enumerate(row_map):
        if source_row >= len(source_rows):
            raise SystemExit(f"source row {source_row} is outside source row count {len(source_rows)}")
        frames = source_rows[source_row]
        if not frames:
            raise SystemExit(f"no frames extracted from source row {source_row}")
        for col in range(used_columns[target_row]):
            frame = frames[col % len(frames)]
            if mirror:
                frame = ImageOps.mirror(frame)
            paste_frame(
                canvas,
                frame,
                target_row * args.target_cols + col,
                args.target_cols,
                args.cell_width,
                args.cell_height,
                args.offset_x,
                args.offset_y,
            )

    save_image(canvas, output)
    if args.preview:
        save_image(canvas, Path(args.preview).expanduser().resolve())
    print(f"source={source}")
    print(f"output={output}")
    print(f"size={canvas.width}x{canvas.height}")


if __name__ == "__main__":
    main()
