"""Smoke tests for preview_variants.apply_recipe.

The CSS Filter Effects 1.0 matrices are tricky enough that "obviously
correct" isn't a defence. These tests check the well-known invariants:

- Empty recipe is a true identity (image unchanged).
- hue_rotate preserves grays (R=G=B pixels are untouched — this is the
  property that lets Maodou's white fur stay white when its ears recolor).
- saturate(1) is identity; saturate(0) collapses to luma.
- brightness(n) scales each channel uniformly.
- The compile-order pipeline matches CSS chain semantics (left-to-right).

These also lock in the Python ↔ JS parity contract: if these change,
JS-side compileRecipe in app/main.js needs the same change.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "open-pet-creator/scripts"))

from PIL import Image  # noqa: E402

import preview_variants as pv  # noqa: E402


def _solid(color: tuple[int, int, int, int]) -> Image.Image:
    return Image.new("RGBA", (4, 4), color)


def _px(image: Image.Image, x: int = 0, y: int = 0) -> tuple[int, int, int, int]:
    return image.getpixel((x, y))


def test_empty_recipe_is_identity():
    src = _solid((180, 90, 200, 255))
    out = pv.apply_recipe(src, None)
    assert _px(out) == _px(src)
    out2 = pv.apply_recipe(src, {})
    assert _px(out2) == _px(src)


def test_brightness_scales_channels():
    src = _solid((100, 100, 100, 255))
    out = pv.apply_recipe(src, {"brightness": 1.5})
    r, g, b, a = _px(out)
    # 100 * 1.5 = 150; allow 1-pixel rounding slack
    assert abs(r - 150) <= 1 and abs(g - 150) <= 1 and abs(b - 150) <= 1
    assert a == 255  # alpha untouched


def test_brightness_clamps_at_255():
    src = _solid((200, 200, 200, 255))
    out = pv.apply_recipe(src, {"brightness": 2.0})
    r, _, _, a = _px(out)
    assert r == 255
    assert a == 255


def test_hue_rotate_preserves_pure_gray():
    # The key invariant for Maodou: white/gray pixels stay put under
    # any hue rotation because R=G=B is on the rotation axis.
    src = _solid((180, 180, 180, 255))
    for deg in (25, 90, 180, 270):
        out = pv.apply_recipe(src, {"hue_rotate": deg})
        r, g, b, _ = _px(out)
        # Allow ≤2-pixel drift from float rounding
        assert abs(r - 180) <= 2, f"hue_rotate({deg}) shifted gray-R by {r-180}"
        assert abs(g - 180) <= 2, f"hue_rotate({deg}) shifted gray-G by {g-180}"
        assert abs(b - 180) <= 2, f"hue_rotate({deg}) shifted gray-B by {b-180}"


def test_hue_rotate_actually_rotates_color():
    # Saturated red → some non-red after a 120° rotation. We don't pin the
    # exact RGB (that would re-implement the matrix in the test), just
    # verify the channel mixing happened.
    src = _solid((255, 0, 0, 255))
    out = pv.apply_recipe(src, {"hue_rotate": 120})
    r, g, b, _ = _px(out)
    assert g > r, "+120° rotation should pull red toward green"


def test_saturate_one_is_identity():
    src = _solid((150, 80, 200, 255))
    out = pv.apply_recipe(src, {"saturate": 1.0})
    r, g, b, _ = _px(out)
    assert abs(r - 150) <= 1
    assert abs(g - 80) <= 1
    assert abs(b - 200) <= 1


def test_saturate_zero_collapses_to_gray():
    src = _solid((200, 60, 100, 255))
    out = pv.apply_recipe(src, {"saturate": 0.0})
    r, g, b, _ = _px(out)
    # All three channels should equal the luma-weighted average; verify by
    # checking R=G=B (within rounding).
    assert abs(r - g) <= 1 and abs(g - b) <= 1
    # Luma ≈ 0.213*200 + 0.715*60 + 0.072*100 ≈ 92.5
    assert 88 <= r <= 96


def test_alpha_passes_through_filters():
    src = _solid((100, 100, 100, 128))
    for recipe in (
        {"hue_rotate": 90},
        {"saturate": 0.5},
        {"brightness": 1.5},
        {"sepia": 0.7},
        {"grayscale": 1.0},
        {"contrast": 1.4},
    ):
        out = pv.apply_recipe(src, recipe)
        assert _px(out)[3] == 128, f"alpha changed under {recipe}"


def test_chain_compile_order_matches_css():
    # CSS filter chain applies left-to-right. For brightness then
    # contrast: brightness lifts, contrast pivots around 0.5.
    # Apply manually in two steps and compare with chained recipe.
    src = _solid((100, 100, 100, 255))
    chained = pv.apply_recipe(src, {"brightness": 1.5, "contrast": 1.2})
    manual = pv.apply_recipe(
        pv.apply_recipe(src, {"brightness": 1.5}),
        {"contrast": 1.2},
    )
    # Allow 2 px drift from doing two passes vs. one composed matrix.
    for a, b in zip(_px(chained), _px(manual)):
        assert abs(a - b) <= 2, f"chained {chained.getpixel((0, 0))} != manual {manual.getpixel((0, 0))}"


def test_grayscale_one_collapses_to_luma_per_rec709():
    src = _solid((200, 60, 100, 255))
    out = pv.apply_recipe(src, {"grayscale": 1.0})
    r, g, b, _ = _px(out)
    assert abs(r - g) <= 1 and abs(g - b) <= 1
    # Luma ≈ 0.2126*200 + 0.7152*60 + 0.0722*100 ≈ 92.6
    assert 88 <= r <= 96
