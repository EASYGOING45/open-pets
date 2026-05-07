#!/usr/bin/env python3
"""Install a Codex/Open Pets pet folder under ~/.codex/pets."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pet-id", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--spritesheet", required=True)
    parser.add_argument("--output-root", default="~/.codex/pets")
    parser.add_argument("--spritesheet-name", default="spritesheet.webp")
    args = parser.parse_args()

    source = Path(args.spritesheet).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"spritesheet not found: {source}")

    output_root = Path(args.output_root).expanduser().resolve()
    pet_dir = output_root / args.pet_id
    pet_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, pet_dir / args.spritesheet_name)
    pet_json = {
        "id": args.pet_id,
        "displayName": args.display_name,
        "description": args.description,
        "spritesheetPath": args.spritesheet_name,
    }
    (pet_dir / "pet.json").write_text(json.dumps(pet_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(pet_dir)


if __name__ == "__main__":
    main()
