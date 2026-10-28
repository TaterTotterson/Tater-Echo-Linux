# Building and releasing satellite platform artifacts

Tater Echo Linux owns kernel, boot, rescue, and platform sources for every
supported Echo satellite. It does not make the images interchangeable. Each
artifact is tied to one target, one source revision, one configuration, and
one SHA-256 digest.

## Target boundaries

| Target | Platform root | Published boot input |
|---|---|---|
| Biscuit | `platforms/dot/` | 3.18 `zImage-dtb` |
| Radar | `platforms/dot/` | Radar-specific 3.18 `zImage-dtb` |
| Checkers | `platforms/show/` | Checkers Android boot image |
| Crown | `platforms/show/` | Crown Android boot image |
| Athena | `platforms/show/` | Athena mainline boot image and GPL source |
| Rook | `platforms/spot/` | Rook kernel, rescue input, and assembled boot image |

The firmware repository must pin the exact Tater Echo Linux source commit and
every downloaded artifact digest. A new platform commit is not usable by a
firmware release until its corresponding board artifact has been built,
verified, and published.

## Migration gates

1. Preserve the currently working upstream input as a hash-pinned baseline.
2. Build the Tater artifact from the target's own platform directory.
3. Verify its boot format, kernel configuration, device trees, and recovery
   path for that target.
4. Publish the artifact, configuration, source revision, and `SHA256SUMS`
   together in a Tater Echo Linux release.
5. Change only that target's firmware lock entry.
6. Build and verify its factory and OTA bundles before hardware testing.

Biscuit and Radar have a shared manual CI kernel workflow. It builds both
matrix entries from `platforms/dot/tools/linux/build-kernel.sh`, retaining
separate outputs and checksums. Rook has its own manual workflow with the
pinned Amazon source revision, Arm GCC 8.3 toolchain, running configuration,
and tracked fix for the previously dormant MediaTek command-mode option.
Checkers, Crown, and Athena are represented in the target manifest and source
tree, but their Tater-hosted binary switch must wait until their complete
toolchain and target-specific boot inputs are pinned in CI. Until then the
firmware may use this repository for source while retaining the existing
hash-pinned binary baseline.

The current Dot-family prerelease is
[`dot-kernel-v1.0.0`](https://github.com/TaterTotterson/Tater-Echo-Linux/releases/tag/dot-kernel-v1.0.0).
It is built from `d5867a594f1707964f2ee58fbb773da522a3a6cd`, which is
based directly on the previously pinned Dot source commit and contains only
the Tater USB Ethernet kernel integration. Its Biscuit and Radar images,
configs, System maps, and checksums are published separately.

The Rook hardware-validation prerelease is
[`rook-kernel-v1.0.0`](https://github.com/TaterTotterson/Tater-Echo-Linux/releases/tag/rook-kernel-v1.0.0).
It is built from `a514109abeccb75c67593d3b1b9f614f181436f3` and preserves
the pinned `4.9.337-g4174e0b4d0e2` module ABI while adding RTL8152 and
bounded `/proc/mchange` role switching. Its kernel, exact config, System map,
source record, and checksums are published together; hardware qualification is
still required before promotion.

The non-Dot inputs are also recorded in
[`baselines/satellite-baselines-v1.json`](../baselines/satellite-baselines-v1.json).
The manual **Build satellite baseline mirror** workflow verifies the original
byte counts and SHA-256 digests, then emits Tater-named copies with provenance
and checksums. These copies are custody mirrors, not rebuilds; a Tater-built
replacement still requires the migration gates above.

Static USB Ethernet readiness and the remaining hardware boundaries are tracked
in [`usb-ethernet-readiness.md`](usb-ethernet-readiness.md). The audit runs in CI
and must remain fail-closed for Athena's peripheral-only device tree.

Historical `techo5-*` paths and names are compatibility interfaces inherited
by installed systems and rescue tooling. New repository-level names are
Tater-first; compatibility names are removed only through a separately tested
migration.
