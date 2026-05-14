"""Tests for open-pet-creator/scripts/check_chain.py.

Each test builds a synthetic ~/.codex/pets/-style directory in a tmp
location, then asserts the validator catches (or doesn't catch) the
condition under test. Keeps the production pets directory untouched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "open-pet-creator/scripts"))

import check_chain as cc  # noqa: E402


def _write_pet(root: Path, pet_id: str, body: dict) -> None:
    pet_dir = root / pet_id
    pet_dir.mkdir(parents=True, exist_ok=True)
    body.setdefault("id", pet_id)
    body.setdefault("displayName", pet_id)
    body.setdefault("spritesheetPath", "spritesheet.webp")
    (pet_dir / "pet.json").write_text(json.dumps(body))
    (pet_dir / "spritesheet.webp").write_bytes(b"\x00")


def _check(roots: list[str], pets_dir: Path) -> cc.Findings:
    return cc.check(roots, pets_dir)


def test_pet_with_no_evolution_block_passes(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {})
    findings = _check(["alpha"], tmp_path)
    assert findings.errors == []
    assert findings.warnings == []


def test_branch_to_missing_pet_errors(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {
        "evolution": {
            "branches": [
                {"to": "ghost", "conditions": [{"type": "turns", "min": 10}]},
            ],
        },
    })
    findings = _check(["alpha"], tmp_path)
    assert any("ghost" in e for e in findings.errors), findings.errors


def test_unknown_condition_type_errors(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {
        "evolution": {
            "branches": [
                {"to": "alpha", "conditions": [{"type": "feet_count", "min": 4}]},
            ],
        },
    })
    findings = _check(["alpha"], tmp_path)
    assert any("feet_count" in e for e in findings.errors), findings.errors


def test_cycle_detected(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {
        "evolution": {"branches": [
            {"to": "beta", "conditions": [{"type": "turns", "min": 5}]},
        ]},
    })
    _write_pet(tmp_path, "beta", {
        "evolution": {"evolves_from": "alpha", "branches": [
            {"to": "alpha", "conditions": [{"type": "turns", "min": 10}]},
        ]},
    })
    findings = _check(["alpha"], tmp_path)
    assert any("cycle" in e for e in findings.errors), findings.errors


def test_missing_required_field_errors(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {
        "evolution": {"branches": [
            {"to": "alpha", "conditions": [{"type": "turns"}]},  # missing min
        ]},
    })
    findings = _check(["alpha"], tmp_path)
    assert any("min" in e for e in findings.errors), findings.errors


def test_at_least_one_of_field_required(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {
        "evolution": {"branches": [
            # time_of_day_ratio with no morning/afternoon/evening/night key
            {"to": "alpha", "conditions": [{"type": "time_of_day_ratio"}]},
        ]},
    })
    findings = _check(["alpha"], tmp_path)
    assert any("requires at least one" in e for e in findings.errors), findings.errors


def test_unknown_field_warns(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {
        "evolution": {"branches": [
            {"to": "alpha", "conditions": [
                {"type": "click_rate", "clicks_per_day_minimum": 2},  # typo
            ]},
        ]},
    })
    findings = _check(["alpha"], tmp_path)
    assert any("clicks_per_day_minimum" in w for w in findings.warnings), findings.warnings


def test_default_branch_must_be_last(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {
        "evolution": {"branches": [
            {"to": "alpha", "conditions": []},  # default — wrongly first
            {"to": "alpha", "conditions": [{"type": "turns", "min": 100}]},
        ]},
    })
    findings = _check(["alpha"], tmp_path)
    assert any("unreachable" in e for e in findings.errors), findings.errors


def test_default_branch_last_is_ok(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {})  # final form target
    _write_pet(tmp_path, "beta", {
        "evolution": {"branches": [
            {"to": "alpha", "conditions": [{"type": "turns", "min": 100}]},
            {"to": "alpha", "conditions": []},  # fallback — OK
        ]},
    })
    findings = _check(["beta"], tmp_path)
    assert findings.errors == []


def test_variant_id_parity_warning(tmp_path: Path) -> None:
    _write_pet(tmp_path, "stage1", {
        "variants": [
            {"id": "normal", "weight": 95},
            {"id": "rare", "weight": 4, "recipe": {"hue_rotate": 25}},
            {"id": "shiny", "weight": 1, "recipe": {"hue_rotate": 180}, "effects": ["sparkle"]},
        ],
        "evolution": {"branches": [
            {"to": "stage2", "conditions": [{"type": "turns", "min": 100}]},
        ]},
    })
    _write_pet(tmp_path, "stage2", {
        "variants": [{"id": "normal", "weight": 100}],  # missing rare + shiny
        "evolution": {"evolves_from": "stage1"},
    })
    findings = _check(["stage1"], tmp_path)
    parity_warnings = [w for w in findings.warnings if "shiny" in w or "rare" in w]
    assert parity_warnings, findings.warnings


def test_orphan_mid_chain_warning(tmp_path: Path) -> None:
    _write_pet(tmp_path, "stage2", {
        "evolution": {"evolves_from": "stage1"},  # stage1 doesn't exist as predecessor
    })
    _write_pet(tmp_path, "unrelated", {})
    findings = _check(["stage2"], tmp_path)
    # stage2 declares evolves_from but no chain root reaches it
    assert any("orphan" in w.lower() or "stage1" in w for w in findings.warnings), findings.warnings


def test_composite_or_recurses(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {
        "evolution": {"branches": [
            {"to": "alpha", "conditions": [
                {"type": "composite_or", "of": [
                    {"type": "turns", "min": 100},
                    {"type": "garbage_type", "min": 1},  # nested error
                ]},
            ]},
        ]},
    })
    findings = _check(["alpha"], tmp_path)
    assert any("garbage_type" in e for e in findings.errors), findings.errors


def test_secret_field_must_be_bool(tmp_path: Path) -> None:
    _write_pet(tmp_path, "alpha", {
        "evolution": {"branches": [
            {"to": "alpha", "conditions": [{"type": "turns", "min": 10}], "secret": "yes"},
        ]},
    })
    findings = _check(["alpha"], tmp_path)
    assert any("secret" in e for e in findings.errors), findings.errors


def test_clean_chain_is_silent(tmp_path: Path) -> None:
    _write_pet(tmp_path, "stage1", {
        "evolution": {"branches": [
            {"to": "stage2a", "conditions": [
                {"type": "turns", "min": 100},
                {"type": "time_of_day_ratio", "morning_pct_min": 0.55},
            ]},
            {"to": "stage2b", "conditions": [
                {"type": "turns", "min": 100},
                {"type": "time_of_day_ratio", "evening_pct_min": 0.55},
            ], "secret": True},
        ]},
    })
    _write_pet(tmp_path, "stage2a", {
        "evolution": {"evolves_from": "stage1"},
    })
    _write_pet(tmp_path, "stage2b", {
        "evolution": {"evolves_from": "stage1"},
    })
    findings = _check(["stage1"], tmp_path)
    assert findings.errors == [], findings.errors
    assert findings.warnings == [], findings.warnings
    assert findings.exit_code() == 0
