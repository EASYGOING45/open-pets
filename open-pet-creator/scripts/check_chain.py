#!/usr/bin/env python3
"""Validate a pet's evolution chain before shipping.

Phase C tooling. Authors run this after wiring an `evolution.branches`
block in pet.json, before publishing the pet. The runtime trusts the
schema; a typo here surfaces to the user as "my pet vanished" the day
the trigger condition is met. Catch it at author time.

Checks (per docs/pet-evolution-variant-design.md §2.11):

  1. Every `branches[].to` points to an installed pet
  2. No cycles in the chain graph
  3. Every condition's `type` is in the §2.4 library
  4. Required fields per condition type are present and well-typed
  5. At most one empty-condition (default) branch, and only as the last
  6. Variant id parity warning across stages of the same chain
  7. Stage 2+ pets with `evolves_from` are reachable from a chain root

Exit codes: 0 = clean; 1 = warnings only; 2 = errors found.

Usage:
    python3 check_chain.py rocom-maodou               # check one chain
    python3 check_chain.py --all                      # check every installed pet
    python3 check_chain.py rocom-maodou --pets-dir ./pets   # custom dir
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

# --- Condition DSL (mirrors §2.4 of the design doc) -----------------------
#
# For each type: required fields (must be present and well-typed). Numeric
# fields accept int or float unless tagged. composite_or is special-cased
# in validate_condition.
CONDITION_TYPES: dict[str, dict[str, type | tuple[type, ...]]] = {
    "turns":       {"min": int, "max": (int, type(None))},
    "days_active": {"min": int, "max": (int, type(None))},
    "clicks":      {"min": (int, type(None)), "max": (int, type(None))},
    "waves":       {"min": (int, type(None)), "max": (int, type(None))},
    "failures":    {"min": (int, type(None)), "max": (int, type(None))},
    "time_of_day_ratio": {
        # one-of these keys is required; we enforce that in validate_condition.
        "morning_pct_min":   (float, int, type(None)),
        "afternoon_pct_min": (float, int, type(None)),
        "evening_pct_min":   (float, int, type(None)),
        "night_pct_min":     (float, int, type(None)),
        "morning_pct_max":   (float, int, type(None)),
        "afternoon_pct_max": (float, int, type(None)),
        "evening_pct_max":   (float, int, type(None)),
        "night_pct_max":     (float, int, type(None)),
    },
    "weekday_ratio": {
        "weekday_pct_min": (float, int, type(None)),
        "weekday_pct_max": (float, int, type(None)),
    },
    "attention_responsiveness": {
        "min": (float, int),
        "max": (float, int, type(None)),
        "min_attention_seen": (int, type(None)),
    },
    "click_rate": {
        "clicks_per_day_min": (float, int, type(None)),
        "clicks_per_day_max": (float, int, type(None)),
    },
    "recent_activity": {
        "days_since_last_max": (int, type(None)),
        "days_since_last_min": (int, type(None)),
    },
    "composite_or": {"of": list},
}

# Conditions that need *at least one* of a set of fields (vs. all required).
CONDITION_AT_LEAST_ONE: dict[str, list[str]] = {
    "time_of_day_ratio": [
        "morning_pct_min", "afternoon_pct_min", "evening_pct_min", "night_pct_min",
        "morning_pct_max", "afternoon_pct_max", "evening_pct_max", "night_pct_max",
    ],
    "weekday_ratio": ["weekday_pct_min", "weekday_pct_max"],
    "click_rate": ["clicks_per_day_min", "clicks_per_day_max"],
    "recent_activity": ["days_since_last_max", "days_since_last_min"],
}


# --- Result tracking -------------------------------------------------------


class Findings:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def exit_code(self) -> int:
        if self.errors:
            return 2
        if self.warnings:
            return 1
        return 0


# --- Pet manifest loading --------------------------------------------------


def default_pet_dir() -> Path:
    return Path(os.environ.get("HOME", "")) / ".codex" / "pets"


def load_pet_manifest(pet_id: str, pets_dir: Path) -> dict | None:
    path = pets_dir / pet_id / "pet.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"__parse_error__": str(e)}


def all_installed_pet_ids(pets_dir: Path) -> list[str]:
    if not pets_dir.is_dir():
        return []
    return sorted(
        d.name for d in pets_dir.iterdir()
        if d.is_dir() and (d / "pet.json").exists()
    )


# --- Validation ------------------------------------------------------------


def validate_condition(cond: object, where: str, findings: Findings) -> None:
    if not isinstance(cond, dict):
        findings.err(f"{where}: condition must be a JSON object, got {type(cond).__name__}")
        return
    ctype = cond.get("type")
    if not isinstance(ctype, str):
        findings.err(f"{where}: condition is missing string `type`")
        return
    if ctype not in CONDITION_TYPES:
        findings.err(
            f"{where}: condition type {ctype!r} is not in the DSL library "
            f"(see §2.4 of the design doc). Known types: {sorted(CONDITION_TYPES)}"
        )
        return

    spec = CONDITION_TYPES[ctype]

    # composite_or — recurse into `of`.
    if ctype == "composite_or":
        of = cond.get("of")
        if not isinstance(of, list) or not of:
            findings.err(f"{where}: composite_or requires a non-empty `of` list")
            return
        for i, sub in enumerate(of):
            validate_condition(sub, f"{where}.composite_or.of[{i}]", findings)
        return

    # at-least-one-of guards (range conditions where all fields optional).
    # Record the error but keep going — typo warnings ("clicks_per_day_minimum"
    # instead of "clicks_per_day_min") are MORE useful than the at_least_one
    # error in isolation; both together explain why the field requirement
    # wasn't met.
    if ctype in CONDITION_AT_LEAST_ONE:
        candidates = CONDITION_AT_LEAST_ONE[ctype]
        if not any(k in cond for k in candidates):
            findings.err(
                f"{where}: {ctype!r} requires at least one of {candidates}"
            )

    # Type-check declared fields
    for field, expected in spec.items():
        if field not in cond:
            if expected is int or expected is float or expected is list:
                if ctype in CONDITION_AT_LEAST_ONE:
                    continue
                findings.err(f"{where}: condition {ctype!r} requires field `{field}`")
            continue
        val = cond[field]
        types = expected if isinstance(expected, tuple) else (expected,)
        if not isinstance(val, types):
            findings.err(
                f"{where}: field `{field}` of {ctype!r} should be {types}, got "
                f"{type(val).__name__}"
            )

    # Reject unknown fields — catches typos like `clicks_per_day_minimum`.
    known = set(spec.keys()) | {"type"}
    for field in cond.keys():
        if field not in known:
            findings.warn(f"{where}: unknown field `{field}` on {ctype!r} (typo?)")


def validate_branch(
    branch: object,
    where: str,
    pets_dir: Path,
    installed: set[str],
    findings: Findings,
) -> str | None:
    """Return the target pet id if the branch validates structurally, else None."""
    if not isinstance(branch, dict):
        findings.err(f"{where}: branch must be a JSON object")
        return None
    target = branch.get("to")
    if not isinstance(target, str):
        findings.err(f"{where}: missing string `to`")
        return None
    if target not in installed:
        findings.err(
            f"{where}: target pet {target!r} is not installed in {pets_dir}"
            " (chain validator can't verify what isn't there)"
        )
    label = branch.get("label")
    if label is not None and not isinstance(label, (str, dict)):
        findings.err(f"{where}: `label` must be string or {{zh,en}} object if present")
    conditions = branch.get("conditions", [])
    if not isinstance(conditions, list):
        findings.err(f"{where}: `conditions` must be an array (got {type(conditions).__name__})")
    else:
        for i, c in enumerate(conditions):
            validate_condition(c, f"{where}.conditions[{i}]", findings)
    secret = branch.get("secret", False)
    if not isinstance(secret, bool):
        findings.err(f"{where}: `secret` must be bool if present")
    return target if isinstance(target, str) else None


def validate_chain(
    root_id: str,
    pets_dir: Path,
    installed: set[str],
    findings: Findings,
) -> None:
    """Walk the chain rooted at root_id. Detect cycles, validate each stage."""
    visiting: list[str] = []
    visited: set[str] = set()

    def walk(pet_id: str, came_from: str | None) -> None:
        if pet_id in visiting:
            cycle = " → ".join(visiting + [pet_id])
            findings.err(f"chain {root_id}: cycle detected — {cycle}")
            return
        if pet_id in visited:
            return
        visited.add(pet_id)
        visiting.append(pet_id)

        manifest = load_pet_manifest(pet_id, pets_dir)
        if manifest is None:
            visiting.pop()
            return
        if "__parse_error__" in manifest:
            findings.err(f"chain {root_id}: {pet_id}/pet.json parse error: {manifest['__parse_error__']}")
            visiting.pop()
            return

        evolution = manifest.get("evolution")
        if not evolution:
            visiting.pop()
            return  # final form

        evolves_from = evolution.get("evolves_from")
        if came_from and evolves_from and evolves_from != came_from:
            findings.warn(
                f"{pet_id}: declares evolves_from={evolves_from!r} but we "
                f"reached it from {came_from!r} — chain may be inconsistent"
            )

        branches = evolution.get("branches", [])
        if not isinstance(branches, list):
            findings.err(f"{pet_id}: `evolution.branches` must be an array")
            visiting.pop()
            return

        # Default-branch ordering check: empty conditions => "always fires".
        # Only the LAST branch may be a default; earlier ones short-circuit
        # all later branches as unreachable.
        empty_indexes = [
            i for i, b in enumerate(branches)
            if isinstance(b, dict) and not b.get("conditions", [])
        ]
        if empty_indexes:
            last_i = len(branches) - 1
            for i in empty_indexes:
                if i != last_i:
                    findings.err(
                        f"{pet_id}: branch[{i}] has empty conditions (always-fires) "
                        f"but is not the last branch — branches after it are unreachable"
                    )

        next_targets: list[str] = []
        for i, branch in enumerate(branches):
            target = validate_branch(
                branch, f"{pet_id}.branches[{i}]", pets_dir, installed, findings,
            )
            if target and target in installed:
                next_targets.append(target)

        # Variant-id parity warning across the immediate edge.
        my_variants = {v.get("id") for v in manifest.get("variants", []) if isinstance(v, dict)}
        for target_id in next_targets:
            target_manifest = load_pet_manifest(target_id, pets_dir)
            if not target_manifest or "__parse_error__" in target_manifest:
                continue
            their_variants = {v.get("id") for v in target_manifest.get("variants", []) if isinstance(v, dict)}
            if my_variants and their_variants:
                missing = my_variants - their_variants
                if missing:
                    findings.warn(
                        f"{pet_id} → {target_id}: variant ids {sorted(missing)} "
                        f"exist on stage 1 but not stage 2; rolls of those variants "
                        f"will fall back to stage-1 recipe at evolution time"
                    )

        for target_id in next_targets:
            walk(target_id, pet_id)

        visiting.pop()

    walk(root_id, None)


def find_orphan_mid_chain_pets(installed: set[str], pets_dir: Path, findings: Findings) -> None:
    """Warn about pets with `evolves_from` that no chain root reaches."""
    mid_chain: dict[str, str] = {}
    for pet_id in installed:
        manifest = load_pet_manifest(pet_id, pets_dir)
        if not manifest or "__parse_error__" in manifest:
            continue
        evolution = manifest.get("evolution") or {}
        ef = evolution.get("evolves_from")
        if isinstance(ef, str):
            mid_chain[pet_id] = ef

    reachable: set[str] = set()

    def dfs(pet_id: str) -> None:
        if pet_id in reachable:
            return
        reachable.add(pet_id)
        manifest = load_pet_manifest(pet_id, pets_dir)
        if not manifest or "__parse_error__" in manifest:
            return
        for b in (manifest.get("evolution") or {}).get("branches", []) or []:
            if isinstance(b, dict):
                t = b.get("to")
                if isinstance(t, str):
                    dfs(t)

    # Pre-compute "is someone's target" once for O(N) instead of O(N²).
    referenced_ids: set[str] = set()
    for other in installed:
        m = load_pet_manifest(other, pets_dir)
        if not m or "__parse_error__" in m:
            continue
        for b in ((m.get("evolution") or {}).get("branches") or []):
            if isinstance(b, dict) and isinstance(b.get("to"), str):
                referenced_ids.add(b["to"])

    for pet_id in installed:
        manifest = load_pet_manifest(pet_id, pets_dir)
        if not manifest or "__parse_error__" in manifest:
            continue
        has_predecessor = pet_id in mid_chain
        is_someones_target = pet_id in referenced_ids
        if not has_predecessor and not is_someones_target:
            dfs(pet_id)

    for pet_id, predecessor in mid_chain.items():
        if pet_id not in reachable:
            findings.warn(
                f"{pet_id}: declares evolves_from={predecessor!r} but is not "
                f"reachable from any chain root — orphan stage 2+ pet "
                f"(authors can ignore if working piecemeal)"
            )


# --- CLI -------------------------------------------------------------------


def check(roots: Iterable[str], pets_dir: Path) -> Findings:
    findings = Findings()
    installed = set(all_installed_pet_ids(pets_dir))
    if not installed:
        findings.err(f"no installed pets found in {pets_dir}")
        return findings

    for root in roots:
        if root not in installed:
            findings.err(f"chain root {root!r} not installed in {pets_dir}")
            continue
        manifest = load_pet_manifest(root, pets_dir)
        if not manifest:
            findings.err(f"could not read {root}/pet.json")
            continue
        if "__parse_error__" in manifest:
            findings.err(f"{root}/pet.json parse error: {manifest['__parse_error__']}")
            continue
        validate_chain(root, pets_dir, installed, findings)

    find_orphan_mid_chain_pets(installed, pets_dir, findings)
    return findings


def report(findings: Findings, roots: list[str]) -> None:
    label = ", ".join(roots) if roots else "all"
    if not findings.errors and not findings.warnings:
        print(f"✓ chain check passed for {label}")
        return
    for w in findings.warnings:
        print(f"⚠ {w}")
    for e in findings.errors:
        print(f"✗ {e}", file=sys.stderr)
    if findings.errors:
        print(f"\n{len(findings.errors)} error(s), {len(findings.warnings)} warning(s)", file=sys.stderr)
    else:
        print(f"\n{len(findings.warnings)} warning(s) — chain is shippable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("pet_id", nargs="?", help="Chain root pet id to check")
    group.add_argument("--all", action="store_true", help="Check every installed pet's chain")
    parser.add_argument(
        "--pets-dir", type=Path, default=default_pet_dir(),
        help="Pet directory (default: ~/.codex/pets)",
    )
    args = parser.parse_args()

    pets_dir = args.pets_dir.expanduser().resolve()
    roots: list[str] = []
    if args.all:
        roots = all_installed_pet_ids(pets_dir)
    elif args.pet_id:
        roots = [args.pet_id]

    findings = check(roots, pets_dir)
    report(findings, roots)
    return findings.exit_code()


if __name__ == "__main__":
    sys.exit(main())
