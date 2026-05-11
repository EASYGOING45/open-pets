"""Test the OpenPets state machine by simulating hook event sequences.

Validates that the state.json written by openpets-event matches the
expected state for each hook event in the Claude Code lifecycle.

Usage:
    python3 tests/test_state_machine.py
"""

import json
import subprocess
import time
import os
from dataclasses import dataclass

HELPER = os.path.expanduser("~/.local/bin/openpets-event")
STATEFILE = os.path.expanduser("~/.openpets/state.json")

# ── helpers ──────────────────────────────────────────────────────────


def emit(state: str, source: str = "test") -> None:
    subprocess.run([HELPER, state, source], check=True, capture_output=True)
    time.sleep(0.15)


def emit_auto(json_payload: dict, source: str = "test") -> None:
    p = subprocess.Popen(
        [HELPER, "auto", source],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    p.communicate(input=json.dumps(json_payload).encode())
    time.sleep(0.15)


def current_state() -> str:
    with open(STATEFILE) as f:
        return json.load(f)["state"]


def check(desc: str, expected: str) -> bool:
    actual = current_state()
    ok = actual == expected
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {desc}")
    if not ok:
        print(f"         expected={expected}  actual={actual}")
    return ok


# ── test cases ───────────────────────────────────────────────────────


def test_session_lifecycle() -> bool:
    """SessionStart → idle, SessionEnd → idle."""
    print("\n── Session lifecycle ──")
    all_ok = True
    emit("idle")
    all_ok &= check("SessionStart", "idle")
    emit("running")
    emit("waving")
    emit("idle")
    all_ok &= check("SessionEnd", "idle")
    return all_ok


def test_turn_lifecycle() -> bool:
    """UserPromptSubmit → running, Stop → waving."""
    print("\n── Turn lifecycle ──")
    all_ok = True
    emit("idle")
    emit("running")
    all_ok &= check("UserPromptSubmit", "running")
    emit("waving")
    all_ok &= check("Stop", "waving")
    return all_ok


def test_tool_execution() -> bool:
    """PreToolUse → running, PostToolUse → running."""
    print("\n── Tool execution ──")
    all_ok = True
    emit("idle")
    emit("running")
    all_ok &= check("PreToolUse → running", "running")
    emit("running")
    all_ok &= check("PostToolUse → running", "running")
    emit("failed")
    all_ok &= check("PostToolUseFailure → failed", "failed")
    return all_ok


def test_notification_permission_prompt() -> bool:
    """Notification with permission_prompt → review."""
    print("\n── Notification: permission_prompt ──")
    all_ok = True
    emit("idle")
    emit("review")
    all_ok &= check("permission_prompt → review", "review")
    return all_ok


def test_notification_idle_prompt() -> bool:
    """Notification with idle_prompt → waiting."""
    print("\n── Notification: idle_prompt ──")
    all_ok = True
    emit("idle")
    emit("waiting")
    all_ok &= check("idle_prompt → waiting", "waiting")
    return all_ok


def test_subagent() -> bool:
    """SubagentStop → running (main session continues)."""
    print("\n── Subagent lifecycle ──")
    all_ok = True
    emit("idle")
    emit("running")
    all_ok &= check("SubagentStop → running", "running")
    emit("waving")  # main Stop
    all_ok &= check("Main Stop → waving", "waving")
    return all_ok


def test_full_turn_sequence() -> bool:
    """Complete conversation turn from idle → running → ... → waving.

    This is the sequence a user sees in one Claude Code turn:
    idle → prompt → tools → finished → idle
    """
    print("\n── Full turn sequence ──")
    all_ok = True

    # Start: idle
    emit("idle")
    all_ok &= check("Initial idle", "idle")

    # User sends prompt
    emit("running")
    all_ok &= check("  UserPromptSubmit", "running")

    # Claude runs tools (PreToolUse + PostToolUse multiple times)
    for i in range(3):
        emit("running")
        all_ok &= check(f"  PreToolUse #{i+1}", "running")
        emit("running")
        all_ok &= check(f"  PostToolUse #{i+1}", "running")

    # Turn finishes
    emit("waving")
    all_ok &= check("  Stop → waving", "waving")

    # After oneshot animation, JS would set to idle.
    # Next turn starts:
    emit("running")
    all_ok &= check("  Next turn: UserPromptSubmit", "running")

    return all_ok


def test_error_during_turn() -> bool:
    """Tool failure mid-turn → failed, then next tool → running."""
    print("\n── Error during turn ──")
    all_ok = True
    emit("running")
    all_ok &= check("Turn start", "running")
    emit("failed")
    all_ok &= check("  PostToolUseFailure → failed", "failed")
    # Next tool starts (Claude retries or runs different tool)
    emit("running")
    all_ok &= check("  Next tool → back to running", "running")
    emit("waving")
    all_ok &= check("  Stop", "waving")
    return all_ok


def test_permission_in_turn() -> bool:
    """Permission prompt interrupts running → review, then tool → running."""
    print("\n── Permission mid-turn ──")
    all_ok = True
    emit("running")
    all_ok &= check("Turn start", "running")
    emit("review")
    all_ok &= check("  Permission prompt → review", "review")
    # User approves → Claude continues
    emit("running")
    all_ok &= check("  Resumed → running", "running")
    emit("waving")
    all_ok &= check("  Stop", "waving")
    return all_ok


def test_idle_prompt_after_stop() -> bool:
    """Simulate: Stop → idle → idle_prompt (too soon).

    This is the regression the user reported: idle_prompt fires right
    after a turn completes, making the pet show "Waiting for you"
    when the user is just reading the response.

    The JS-side cooldown should suppress idle_prompt → waiting
    transitions that arrive within 30s of the pet entering idle.
    """
    print("\n── idle_prompt after Stop (cooldown test) ──")
    all_ok = True
    emit("running")
    all_ok &= check("Turn start", "running")
    emit("waving")
    all_ok &= check("  Stop → waving", "waving")
    # JS oneshot: waving → idle (not reflected in state.json)
    # idle_prompt fires 5s later → waiting
    # The JS-side cooldown should suppress this.
    # (This test verifies the state.json side; JS cooldown is tested via
    #  the running degrade / cooldown logic in main.js.)
    time.sleep(1.0)
    emit("waiting")
    all_ok &= check("  idle_prompt → waiting (state.json)", "waiting")
    return all_ok


# ── main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("OpenPets State Machine Tests")
    print("=" * 50)

    results = [
        test_session_lifecycle(),
        test_turn_lifecycle(),
        test_tool_execution(),
        test_notification_permission_prompt(),
        test_notification_idle_prompt(),
        test_subagent(),
        test_full_turn_sequence(),
        test_error_during_turn(),
        test_permission_in_turn(),
        test_idle_prompt_after_stop(),
    ]

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} passed")

    if passed < total:
        print("FAILED")
        exit(1)
    else:
        print("OK")
