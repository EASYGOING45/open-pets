from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import repack_phrolova_spritesheet as repack


USED_COLUMNS_BY_ROW = (6, 8, 8, 4, 5, 8, 6, 6, 6)
MIN_IDLE_THUMBNAIL_WIDTH = 105
MIN_IDLE_THUMBNAIL_HEIGHT = 140
MAX_IDLE_THUMBNAIL_CENTER_Y = 124
MIN_TOP_MENU_STRIP_CLEARANCE = 35


class PhrolovaSpritesheetContractTest(unittest.TestCase):
    def test_uses_codex_avatar_grid_contract(self) -> None:
        self.assertEqual((repack.TARGET_COLS, repack.TARGET_ROWS), (8, 9))
        self.assertEqual((repack.CELL_W, repack.CELL_H), (192, 208))
        self.assertEqual(
            (repack.TARGET_COLS * repack.CELL_W, repack.TARGET_ROWS * repack.CELL_H),
            (1536, 1872),
        )

    def test_maps_source_rows_to_codex_state_rows(self) -> None:
        self.assertEqual(
            repack.TARGET_ROW_SOURCE_ROWS,
            (
                (0, False),  # idle
                (3, False),  # running-right
                (3, True),  # running-left
                (2, False),  # waving
                (4, False),  # jumping
                (7, False),  # failed
                (6, False),  # waiting
                (5, False),  # running
                (1, False),  # review
            ),
        )

    def test_unused_codex_cells_are_transparent(self) -> None:
        sheet = repack.Image.open(repack.OUT).convert("RGBA")

        for row, used_columns in enumerate(USED_COLUMNS_BY_ROW):
            for col in range(used_columns, repack.TARGET_COLS):
                left = col * repack.CELL_W
                top = row * repack.CELL_H
                cell = sheet.crop((left, top, left + repack.CELL_W, top + repack.CELL_H))

                with self.subTest(row=row, col=col):
                    self.assertIsNone(cell.getchannel("A").getbbox())

    def test_visible_frames_are_horizontally_centered(self) -> None:
        sheet = repack.Image.open(repack.OUT).convert("RGBA")

        for row, used_columns in enumerate(USED_COLUMNS_BY_ROW):
            for col in range(used_columns):
                left = col * repack.CELL_W
                top = row * repack.CELL_H
                cell = sheet.crop((left, top, left + repack.CELL_W, top + repack.CELL_H))
                bbox = cell.getchannel("A").getbbox()
                self.assertIsNotNone(bbox)
                assert bbox is not None
                center_x = (bbox[0] + bbox[2]) / 2

                with self.subTest(row=row, col=col):
                    self.assertGreaterEqual(center_x, 92)
                    self.assertLessEqual(center_x, 100)

    def test_idle_thumbnail_uses_enough_cell_space_without_sitting_low(self) -> None:
        sheet = repack.Image.open(repack.OUT).convert("RGBA")
        first_idle = sheet.crop((0, 0, repack.CELL_W, repack.CELL_H))
        bbox = first_idle.getchannel("A").getbbox()
        self.assertIsNotNone(bbox)
        assert bbox is not None

        self.assertGreaterEqual(bbox[2] - bbox[0], MIN_IDLE_THUMBNAIL_WIDTH)
        self.assertGreaterEqual(bbox[3] - bbox[1], MIN_IDLE_THUMBNAIL_HEIGHT)
        self.assertLessEqual((bbox[1] + bbox[3]) / 2, MAX_IDLE_THUMBNAIL_CENTER_Y)

    def test_visible_frames_keep_top_menu_strip_clear(self) -> None:
        sheet = repack.Image.open(repack.OUT).convert("RGBA")

        for row, used_columns in enumerate(USED_COLUMNS_BY_ROW):
            for col in range(used_columns):
                left = col * repack.CELL_W
                top = row * repack.CELL_H
                cell = sheet.crop((left, top, left + repack.CELL_W, top + repack.CELL_H))
                bbox = cell.getchannel("A").getbbox()
                self.assertIsNotNone(bbox)
                assert bbox is not None

                with self.subTest(row=row, col=col):
                    self.assertGreaterEqual(bbox[1], MIN_TOP_MENU_STRIP_CLEARANCE)


if __name__ == "__main__":
    unittest.main()
