#!/usr/bin/env python3
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SHOW = ROOT / "platforms" / "show"


class AthenaBootSplashTests(unittest.TestCase):
    def test_init_uses_safe_early_linux_framebuffer(self) -> None:
        init = (SHOW / "tools/linux/athena/init").read_text()
        self.assertIn("fbprobe -fill 000000 -logo", init)
        self.assertIn("-leave", init)
        self.assertIn("/usr/local/share/tater-boot.png", init)
        self.assertNotIn("/dev/mmcblk0p18", init)
        self.assertNotIn("/dev/mmcblk1p18", init)

    def test_store_builder_installs_renderer_and_logo(self) -> None:
        builder = (SHOW / "tools/linux/athena/mkstore.sh").read_text()
        self.assertIn("-l) LOGO=$2", builder)
        self.assertIn('"$R/usr/local/bin/fbprobe"', builder)
        self.assertIn('"$R/usr/local/share/tater-boot.png"', builder)


if __name__ == "__main__":
    unittest.main()
