#!/usr/bin/env python3
"""Validate the Tater Echo Linux satellite/platform boundary manifest."""

from __future__ import annotations

import json
from pathlib import Path
import shlex
import sys


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "targets" / "targets.json"
EXPECTED_TARGETS = {"biscuit", "radar", "checkers", "crown", "athena", "rook"}
EXPECTED_FAMILIES = {"dot", "show", "spot"}


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    try:
        raw = MANIFEST.read_text(encoding="utf-8")
        manifest = json.loads(raw)
    except (OSError, ValueError) as error:
        fail(f"cannot read {MANIFEST}: {error}")

    if raw != json.dumps(manifest, indent=2) + "\n":
        fail("targets/targets.json is not canonical two-space JSON")
    if manifest.get("schema") != 1:
        fail("unsupported target manifest schema")
    repository = manifest.get("repository", "")
    if repository != "https://github.com/TaterTotterson/Tater-Echo-Linux":
        fail("target manifest must name the canonical Tater Echo Linux repository")

    families = manifest.get("families", {})
    if set(families) != EXPECTED_FAMILIES:
        fail(f"families must be exactly {sorted(EXPECTED_FAMILIES)}")

    found: set[str] = set()
    for family_name, family in families.items():
        platform_path = ROOT / family.get("path", "")
        if not platform_path.is_dir():
            fail(f"{family_name} platform path does not exist: {platform_path}")
        upstream = family.get("upstream", "")
        if not upstream.startswith("https://github.com/"):
            fail(f"{family_name} upstream is not an HTTPS GitHub URL")
        targets = family.get("targets", {})
        if not targets:
            fail(f"{family_name} has no targets")
        for target, details in targets.items():
            if target in found:
                fail(f"target appears more than once: {target}")
            found.add(target)
            for key in ("device", "model", "kernel", "build"):
                if not isinstance(details.get(key), str) or not details[key].strip():
                    fail(f"{target} has no {key}")
            build_parts = shlex.split(details["build"])
            entrypoint = platform_path / build_parts[0]
            if not entrypoint.is_file():
                fail(f"{target} build entry point does not exist: {entrypoint}")
            artifacts = details.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                fail(f"{target} has no release artifacts")
            if len(artifacts) != len(set(artifacts)) or not all(
                isinstance(value, str) and value for value in artifacts
            ):
                fail(f"{target} artifacts must be unique non-empty strings")

    if found != EXPECTED_TARGETS:
        fail(f"targets must be exactly {sorted(EXPECTED_TARGETS)}")
    print("validated Tater Echo Linux targets: " + ", ".join(sorted(found)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
