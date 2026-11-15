import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from tools import build_hardware_kernel as kernel, build_video_decoder as video, prepare_show_hardware_boot as boot


class HardwareInputTests(unittest.TestCase):
    def test_exact_configs_and_patch_boundaries(self):
        for target, profile in kernel.PROFILES.items():
            self.assertEqual(kernel.sha256(kernel.INPUTS/(target+'.config')), profile['config_sha256'])
            self.assertTrue(all((kernel.ROOT/path).is_file() for path in profile['patches']))
            self.assertFalse(any('jpeg' in path.lower() for path in profile['patches']))
        self.assertNotEqual(kernel.PROFILES['rook']['source_sha256'],kernel.PROFILES['checkers']['source_sha256'])

    def test_kernel_rejects_wrong_inputs_before_building_or_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); source=root/'source';source.write_bytes(b'wrong')
            with mock.patch.object(kernel.subprocess,'run') as run:
                with self.assertRaises(ValueError):kernel.build('checkers',source,source,root/'output','unused',1)
                self.assertFalse((root/'output').exists());run.assert_not_called()

    def test_video_recipe_pins_source_builder_packages_and_output(self):
        lock=json.loads(video.LOCK.read_text())
        self.assertRegex(lock['builder'],r'@sha256:[0-9a-f]{64}$')
        for package in lock['packages']:self.assertIn('=',package)
        self.assertRegex(lock['source_sha256'],r'^[0-9a-f]{64}$')
        self.assertRegex(lock['output_sha256'],r'^[0-9a-f]{64}$')
        recipe=(video.ROOT/lock['recipe']).read_text()
        for option in ('h264_mp4toannexb','h264_metadata','framecrc'):self.assertIn(option,recipe)

    def test_video_rejects_wrong_source_before_docker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'source';source.write_bytes(b'wrong')
            with mock.patch.object(video.subprocess,'run') as run:
                with self.assertRaises(ValueError):video.build(source,root/'output')
                self.assertFalse((root/'output').exists());run.assert_not_called()

    def test_show_boot_refuses_unknown_or_private_donors_before_loading_tooling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'source';source.write_bytes(b'not the public baseline')
            with mock.patch.object(boot,'module') as load:
                with self.assertRaises(ValueError):boot.prepare('checkers',source,source,root,root/'output')
                load.assert_not_called();self.assertFalse((root/'output').exists())

    def test_show_candidates_retain_distinct_baselines_and_kernels(self):
        self.assertNotEqual(boot.PROFILES['checkers']['baseline_sha256'],boot.PROFILES['cronos']['baseline_sha256'])
        self.assertNotEqual(boot.PROFILES['checkers']['raw_sha256'],boot.PROFILES['checkers']['kernel_sha256'])
        self.assertEqual(boot.PROFILES['cronos']['kernel_sha256'],'79410d93c4a5a5c2920cd4b4164f2d99afef17661b0cdaea1a45336e6ab734e4')


if __name__=='__main__':unittest.main()
