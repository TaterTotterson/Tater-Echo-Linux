#!/usr/bin/env python3
"""Validate and materialize byte-identical Tater satellite baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "baselines" / "satellite-baselines-v1.json"
EXPECTED_TARGETS = {"checkers", "crown", "athena", "rook"}
EXPECTED_ROLES = {
    "rootfs-baseline",
    "boot-baseline",
    "kernel-baseline",
    "rescue-baseline",
}
EXPECTED_TARGET_ROLES = {
    ("checkers", "rootfs-baseline"),
    ("checkers", "boot-baseline"),
    ("crown", "rootfs-baseline"),
    ("crown", "boot-baseline"),
    ("athena", "rootfs-baseline"),
    ("athena", "boot-baseline"),
    ("rook", "rootfs-baseline"),
    ("rook", "kernel-baseline"),
    ("rook", "rescue-baseline"),
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_manifest(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    manifest = json.loads(raw)
    if raw != json.dumps(manifest, indent=2) + "\n":
        raise ValueError("manifest is not canonical two-space JSON")
    if manifest.get("schema") != 1:
        raise ValueError("unsupported baseline manifest schema")
    release = manifest.get("release", {})
    if release.get("tag") != "satellite-baselines-v1.0.0":
        raise ValueError("unexpected baseline release tag")
    if release.get("kind") != "byte-identical-provenance-mirror":
        raise ValueError("baseline release must remain a provenance mirror")
    commits = manifest.get("platform_commits", {})
    if set(commits) != {"show", "athena", "rook"}:
        raise ValueError("baseline platform commits must cover show, athena, and rook")
    for platform, commit in commits.items():
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError(f"invalid {platform} platform commit")

    names: set[str] = set()
    covered: set[str] = set()
    target_roles: set[tuple[str, str]] = set()
    for asset in manifest.get("assets", []):
        targets = set(asset.get("targets", []))
        if not targets or not targets <= EXPECTED_TARGETS:
            raise ValueError(f"invalid baseline targets: {sorted(targets)}")
        covered |= targets
        role = asset.get("role")
        if role not in EXPECTED_ROLES:
            raise ValueError(f"invalid baseline role: {role}")
        target_roles |= {(target, role) for target in targets}
        name = asset.get("published_name", "")
        if not name or name != Path(name).name or name in names or not name.startswith("tater-echo-"):
            raise ValueError(f"invalid or duplicate published name: {name}")
        names.add(name)
        url = asset.get("source_url", "")
        if not url.startswith("https://github.com/HuskerMinion/"):
            raise ValueError(f"unapproved baseline source URL: {url}")
        sha256 = asset.get("sha256", "")
        if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
            raise ValueError(f"invalid SHA-256 for {name}")
        if not isinstance(asset.get("size"), int) or asset["size"] <= 0:
            raise ValueError(f"invalid size for {name}")
    if covered != EXPECTED_TARGETS:
        raise ValueError(f"baseline targets are incomplete: {sorted(covered)}")
    if target_roles != EXPECTED_TARGET_ROLES:
        raise ValueError("baseline target/role coverage is incomplete")
    return manifest


def fetch(asset: dict, destination: Path) -> None:
    if destination.is_file() and destination.stat().st_size == asset["size"]:
        if digest(destination) == asset["sha256"]:
            print(f"verified cached {destination.name}")
            return
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(
        asset["source_url"],
        headers={"User-Agent": "Tater-Echo-Linux baseline fetcher"},
    )
    with urllib.request.urlopen(request) as source, partial.open("wb") as output:
        shutil.copyfileobj(source, output, length=1024 * 1024)
    if partial.stat().st_size != asset["size"]:
        partial.unlink(missing_ok=True)
        raise ValueError(f"size mismatch for {destination.name}")
    actual = digest(partial)
    if actual != asset["sha256"]:
        partial.unlink(missing_ok=True)
        raise ValueError(f"SHA-256 mismatch for {destination.name}: {actual}")
    partial.replace(destination)
    print(f"verified {destination.name}")


def materialize(manifest_path: Path, output: Path) -> None:
    manifest = load_manifest(manifest_path)
    output.mkdir(parents=True, exist_ok=True)
    for asset in manifest["assets"]:
        fetch(asset, output / asset["published_name"])
    provenance = output / "BASELINE-PROVENANCE.json"
    provenance.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    files = sorted(path for path in output.iterdir() if path.name != "SHA256SUMS")
    checksums = "".join(f"{digest(path)}  {path.name}\n" for path in files)
    (output / "SHA256SUMS").write_text(checksums, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        if args.check:
            print(f"validated {len(manifest['assets'])} satellite baseline assets")
            return 0
        if args.output is None:
            parser.error("--output is required unless --check is used")
        materialize(args.manifest, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"baseline error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
