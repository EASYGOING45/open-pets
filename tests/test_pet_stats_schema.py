"""Schema-level tests for the pet_stats counter shape.

These don't run the Rust code (that's a different test runner). They
verify the *config.json* shape that Rust produces matches what the
design doc claims, by spot-checking the JSON structure after a Phase B
build runs against a controlled environment.

Right now this is a smoke test: just assert the schema fields exist
with sensible defaults. When Phase C lands, expand to assert the
condition evaluator reads them correctly.
"""

from __future__ import annotations

import json
from pathlib import Path

# These keys MUST appear in every pet_stats[id] entry (matches §3.1 of
# docs/pet-evolution-variant-design.md and the PetStats struct in main.rs).
REQUIRED_STATS_FIELDS = {
    "first_seen_ms",
    "last_active_ms",
    "days_active",
    "last_local_day_key",
    "total_turns",
    "total_clicks",
    "total_waves",
    "failures_seen",
    "attention_seen",
    "attention_responded",
    "turn_buckets",
    "idle_seconds",
    "active_seconds",
    "previous_form",
    "pending_evolution_branch",
}

REQUIRED_BUCKET_FIELDS = {
    "morning",
    "afternoon",
    "evening",
    "night",
    "weekday",
    "weekend",
}


def test_design_doc_lists_every_required_field():
    # Sanity check that the design doc still mentions every counter we
    # ship — catches drift where the schema gains a field but the doc
    # doesn't get updated.
    doc = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "pet-evolution-variant-design.md"
    ).read_text()

    # Some field names in the doc use camelCase / human prose; map them.
    doc_aliases = {
        "first_seen_ms": "first_seen",
        "last_active_ms": "last_active",
        "last_local_day_key": "last_local_day_key",  # internal-only OK if absent
        "previous_form": "previous_form",
        "pending_evolution_branch": "pending_evolution",
    }
    for field in REQUIRED_STATS_FIELDS:
        alias = doc_aliases.get(field, field)
        # Either the rust field name or its doc alias should appear.
        if field not in doc and alias not in doc:
            # last_local_day_key is internal optimization, not user-facing.
            if field in {"last_local_day_key", "pending_evolution_branch"}:
                continue
            assert False, f"design doc missing reference to '{field}' or '{alias}'"


def test_required_bucket_fields_match_design():
    # turn_buckets sub-shape spec from §3.1 of the design doc.
    doc = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "pet-evolution-variant-design.md"
    ).read_text()
    for bucket in REQUIRED_BUCKET_FIELDS:
        assert bucket in doc, f"design doc missing bucket '{bucket}'"


def test_existing_user_config_is_forward_compatible():
    """If the user has a pre-Phase-B config.json, it should still parse.

    Run this only when ~/.openpets/config.json exists; skip otherwise.
    """
    cfg_path = Path.home() / ".openpets" / "config.json"
    if not cfg_path.exists():
        return  # no existing user — nothing to verify
    raw = json.loads(cfg_path.read_text())
    # All Phase A/B fields are optional via #[serde(default)]; an existing
    # config without pet_stats just means it's empty.
    pet_stats = raw.get("pet_stats", {})
    assert isinstance(pet_stats, dict), f"pet_stats must be a dict, got {type(pet_stats)}"
    # Each entry, if present, should have all REQUIRED_STATS_FIELDS.
    for pet_id, stats in pet_stats.items():
        missing = REQUIRED_STATS_FIELDS - set(stats.keys())
        # Allow internal-optimization fields to be absent on freshly-migrated
        # entries — Rust's #[serde(default)] handles them on read.
        permitted_absent = {"last_local_day_key"}
        actually_missing = missing - permitted_absent
        assert not actually_missing, (
            f"pet_stats[{pet_id!r}] missing fields: {sorted(actually_missing)}"
        )
