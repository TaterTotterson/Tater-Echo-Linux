#!/usr/bin/env python3
"""Build fixed-size monochrome Tater boot-logo payloads from the primary logo.

The Show bootloader draws a 315x170 BGRA zlib bundle from a 6105-byte slot.
Rook draws a 480x480 bundle from a 12096-byte slot.  Both outputs retain the
original bundle header and pad unused bytes with zeroes so installers only
replace the already-verified logo slot.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import zlib

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "platforms" / "show" / "logo" / "tater-logo-primary.png"
SHOW_PREVIEW = ROOT / "platforms" / "show" / "logo" / "tater-boot-315.png"
SHOW_PAYLOAD = ROOT / "platforms" / "show" / "tools" / "boot-logo" / "tater-wordmark.bin"
ROOK_PREVIEW = ROOT / "platforms" / "spot" / "logo" / "tater-boot-480.png"
ROOK_PAYLOAD = ROOT / "platforms" / "spot" / "logo" / "tater-boot-480.bin"

SHOW_SIZE = (315, 170)
SHOW_SCALE = 0.90
SHOW_SLOT = 6105
ROOK_SIZE = (480, 480)
ROOK_SCALE = 0.80
ROOK_SLOT = 12096
MONO_THRESHOLD = 110


def render(source: Image.Image, size: tuple[int, int], scale_fraction: float) -> Image.Image:
    image = source.convert("RGBA")
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Tater logo contains no visible pixels")
    image = image.crop(bounds)
    scale = min(size[0] / image.width, size[1] / image.height) * scale_fraction
    image = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", size, (0, 0, 0, 255))
    canvas.alpha_composite(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    gray = canvas.convert("L")
    return gray.point(lambda value: 255 if value >= MONO_THRESHOLD else 0, mode="1").convert("RGB")


def bundle(image: Image.Image, slot_size: int) -> bytes:
    raw = image.convert("RGBA").tobytes("raw", "BGRA")
    compressed = zlib.compress(raw, 9)
    payload = struct.pack("<III", 1, 12 + len(compressed), 12) + compressed
    if len(payload) > slot_size:
        raise ValueError(f"boot logo needs {len(payload)} bytes; slot holds {slot_size}")
    return payload + bytes(slot_size - len(payload))


def write_output(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    print(f"{path.relative_to(ROOT)}  {len(contents)} bytes  sha256:{hashlib.sha256(contents).hexdigest()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()

    source = Image.open(args.source)
    show = render(source, SHOW_SIZE, SHOW_SCALE)
    rook = render(source, ROOK_SIZE, ROOK_SCALE)

    SHOW_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    ROOK_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    show.save(SHOW_PREVIEW, optimize=True)
    rook.save(ROOK_PREVIEW, optimize=True)
    write_output(SHOW_PAYLOAD, bundle(show, SHOW_SLOT))
    write_output(ROOK_PAYLOAD, bundle(rook, ROOK_SLOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
