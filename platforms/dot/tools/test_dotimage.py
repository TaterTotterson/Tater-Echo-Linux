from __future__ import annotations

import importlib.util
import lzma
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest


TOOLS = Path(__file__).resolve().parent
LINUX = TOOLS / "linux"

# dotimage's release helpers are irrelevant to these boot-image tests.  Supply
# the small interface it imports so the module can be tested without network or
# a release checkout.
techo5lib = types.ModuleType("techo5lib")
techo5lib.Release = object
techo5lib.alpine = lambda *_: None
techo5lib.fail = lambda message: (_ for _ in ()).throw(RuntimeError(message))
techo5lib.repo_root = lambda: str(TOOLS.parent)
techo5lib.tar_extract_all = lambda *_: None
techo5lib.tar_read = lambda *_: None
sys.modules.setdefault("techo5lib", techo5lib)

spec = importlib.util.spec_from_file_location("tater_dotimage", TOOLS / "dotimage.py")
assert spec is not None and spec.loader is not None
dotimage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dotimage)

mk_spec = importlib.util.spec_from_file_location("tater_mkimage", LINUX / "mkimage.py")
assert mk_spec is not None and mk_spec.loader is not None
mkimage = importlib.util.module_from_spec(mk_spec)
mk_spec.loader.exec_module(mkimage)


class TwrpHandoffImageTests(unittest.TestCase):
    def fixture(self, folder: Path) -> Path:
        archive = mkimage.Cpio()
        archive.file("init.recovery.mt8163.rc", b"on init\n    setprop tater.test 1\n")
        raw = archive.finish()
        ramdisk = lzma.compress(raw, format=lzma.FORMAT_ALONE, preset=1)
        header = bytearray(2048)
        header[:8] = b"ANDROID!"
        struct.pack_into("<I", header, 36, 2048)
        struct.pack_into("<I", header, 40, 0)
        source = folder / "twrp.img"
        dotimage._write_boot_image(header, b"test-kernel", ramdisk, 2048, source)
        return source

    def test_builds_verified_handoff_service_from_unit_twrp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = self.fixture(folder)
            output = folder / "twrp-handoff.img"

            size = dotimage.build_twrp_handoff_image(source, output)

            self.assertEqual(size, output.stat().st_size)
            _, kernel, compressed, _ = dotimage._read_boot_image(output)
            self.assertEqual(kernel, b"test-kernel")
            raw = lzma.decompress(compressed, format=lzma.FORMAT_AUTO)
            self.assertEqual(raw.count(b"service tater-restore-linux "), 1)
            self.assertEqual(raw.count(b"tater-twrp-handoff: restoring Linux"), 1)
            self.assertEqual(raw.count(b"bs=13 count=1"), 1)
            self.assertEqual(raw.count(b"bs=1 seek=7168"), 1)
            self.assertIn(b"Linux restored, armed, and verified", raw)
            self.assertNotIn(b"conv=notrunc,sync", raw)
            self.assertNotIn(b"TWRP cleared the boot target; re-arming Linux", raw)
            names = mkimage.verify_cpio(raw)
            self.assertIn("sbin/tater-restore-linux.sh", names)

    def test_handoff_script_has_valid_posix_shell_syntax(self) -> None:
        subprocess.run(
            ["sh", "-n"], input=dotimage.TWRP_HANDOFF_SCRIPT, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def test_refuses_to_patch_an_already_patched_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = self.fixture(folder)
            once = folder / "once.img"
            twice = folder / "twice.img"
            dotimage.build_twrp_handoff_image(source, once)

            with self.assertRaisesRegex(RuntimeError, "already contains"):
                dotimage.build_twrp_handoff_image(once, twice)


if __name__ == "__main__":
    unittest.main()
