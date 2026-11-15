# Reviewed camera-kernel input builds

These are reproducibility inputs, not permission to install or release a kernel.
No device, owner boot image, calibration or vendor library is read by the build.

`tools/build_hardware_kernel.py` builds Checkers, Cronos and Rook from fresh
trees in an explicitly selected offline Linux container. It verifies the source
archive, Arm GCC 8.3 archive and exact target configuration, applies only the
listed source patches and requires the reviewed raw output SHA-256. A mismatch
fails rather than repinning the result. Logs/failed outputs are retained for
inspection. The old Checkers Docker-hostname label is pinned solely to reproduce
its existing raw binary; it is not a device serial number.

Public kernel source:

- Checkers/Cronos: amazon-oss/android_kernel_amazon_mt8163 commit
  `8d928c5176cc1ced93a564dd8a949a6cda3b8231`.
- Rook: the same repository, commit
  `4174e0b4d0e2eb452d14fbe3c0e5094611f748b6`.
- Toolchain: Arm GCC 8.3-2019.03 x86_64 AArch64 Linux GNU, archive SHA-256
  `8ce3e7688a47d8cd2d8e8323f147104ae1c8139520eca50ccf8a7fa933002731`.
- The current development Linux builder image is explicitly recorded as
  `sha256:5f34238481f9c2cc7a70d06630093551f0bde2f7270c65adb54aebae4ae734c0`.
  This is a local image identity, not a public registry URL. Rebuilders may use
  a suitable Linux image with host GCC, git, make, bc, bison and flex; output
  hashes must still match. A public frozen kernel-builder publication is not
  implied by this record.

Example (each output must be a new directory):

```sh
python3 tools/build_hardware_kernel.py --target checkers \
  --source /path/to/kernel-8d928c5176cc.tar.gz \
  --toolchain /path/to/gcc-arm-8.3-2019.03-x86_64-aarch64-linux-gnu.tar.xz \
  --builder YOUR_LINUX_BUILD_IMAGE --output /path/to/new-checkers-build
```

For Show release candidates, run `tools/prepare_show_hardware_boot.py` with
the **hash-pinned public baseline boot**, freshly verified raw kernel and pinned
Tater Echo Hardware tooling. It preserves that public ramdisk, boot parameters
and board device trees; no private owner donor is accepted. It checks that the
baseline device trees retain separate microphone channels. This deliberately
corrects the old Checkers camera trial's re-enabled `amzn,mic-downmix` property.
The corrected Checkers candidate needs a new physical voice test before release.
Its clean raw build also normalizes the default, empty built-in initramfs
timestamps to the pinned November 12 build time. The older incremental trial
retained November 11 timestamps in that empty archive. A byte comparison
isolated the raw-image differences to that archive and its GNU build ID; the
remaining image bytes and complete module-symbol versions are unchanged.
Cronos retains its already tested baseline DTBs rather than substituting newly
compiled ones. Neither command flashes or changes a satellite.

Crown's uninstalled camera-clock experiment is not in these build profiles.
Athena is a separate mainline platform and must not receive an MT8163 kernel.
GPLv2 kernel sources/configurations/patches retain their applicable upstream
license terms; independent helper tooling retains its own source notices.

## Athena mainline/AP inputs

`tools/build_athena_hardware_kernel.py` separately rebuilds Linux 6.18.56,
the empty-tuning board DTB, the gated SCP modules and both original AP adapters.
It uses the exact `athena.config`, explicit GCC 13.3 host/target compilers,
the pinned Hardware source and firmware codec lock, a fresh container and no
network. The full kernel build and standalone `M=drivers/remoteproc` invocation
are both intentional: they reproduce the reviewed module metadata as well as
the code. Every exported binary must match the existing codec/source lock.
The build never reads or embeds the owner's SCP firmware or speaker tuning.

The native ARM64 development builder identity is
`sha256:b3c5e4fd26e255937cd4aa2daeb180b631c833d927a71ed6233278646d005253`;
the Linux source archive SHA-256 is
`4633bbda2ab95eaf2a7af4041236451d6759c72e6946265531af4b3aacefbf89`.
Use `--help` for the required source, hardware checkout, codec-lock, builder
and new output directory arguments. This is not a public registry image URL.

`tools/prepare_athena_hardware_boot.py` then applies the narrowly audited 8 MiB
codec reservation to the rebuilt empty-tuning DTB. It preserves only the
existing **public** Athena baseline's redistributable Wi-Fi/BT ramdisk, checks
the tuning slot is still empty, and reproduces the reviewed `c6f38f2c…`
template. The public baseline ramdisk's own MediaTek license remains included;
it is not an owner's private firmware backup. Per-device speaker tuning is
still filled locally by the existing factory installer. No owner SCP firmware
or video runtime is redistributed by this boot assembly.

Publishing any input is separate from approving a USB/system migration, OTA,
reboot, rollback, runtime provisioning or physical voice/video test.
