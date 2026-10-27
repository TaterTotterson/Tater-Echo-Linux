#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import unittest
import zlib

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_tater_boot_logos", ROOT / "tools" / "build-tater-boot-logos.py"
)
assert SPEC is not None and SPEC.loader is not None
logos = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(logos)


class TaterBootLogoTests(unittest.TestCase):
    def check_payload(self, path: Path, slot: int, size: tuple[int, int]) -> None:
        payload = path.read_bytes()
        self.assertEqual(slot, len(payload))
        count, total, offset = struct.unpack_from("<III", payload)
        self.assertEqual((1, 12), (count, offset))
        raw = zlib.decompress(payload[12:total])
        self.assertEqual(size[0] * size[1] * 4, len(raw))
        image = Image.frombuffer("RGBA", size, raw, "raw", "BGRA", 0, 1).convert("RGB")
        self.assertEqual({(0, 0, 0), (255, 255, 255)}, set(image.getdata()))
        self.assertEqual(bytes(slot - total), payload[total:])

    def test_show_payload(self) -> None:
        self.check_payload(logos.SHOW_PAYLOAD, logos.SHOW_SLOT, logos.SHOW_SIZE)

    def test_rook_payload(self) -> None:
        self.check_payload(logos.ROOK_PAYLOAD, logos.ROOK_SLOT, logos.ROOK_SIZE)

    def test_previews_match_bootloader_geometry(self) -> None:
        with Image.open(logos.SHOW_PREVIEW) as show:
            self.assertEqual(logos.SHOW_SIZE, show.size)
        with Image.open(logos.ROOK_PREVIEW) as rook:
            self.assertEqual(logos.ROOK_SIZE, rook.size)


if __name__ == "__main__":
    unittest.main()
