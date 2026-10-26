# Tater Echo Linux

Tater Echo Linux is the kernel, boot, root filesystem, rescue, and
board-platform source for every Tater Echo satellite. It keeps the original
upstream histories intact while giving Tater one place to maintain and
release the complete platform stack.

## Platforms

| Directory | Boards | Imported from |
|---|---|---|
| `platforms/dot/` | Biscuit, Radar | `HuskerMinion/techo5-dot` |
| `platforms/show/` | Checkers, Crown, Athena | `HuskerMinion/techo5` |
| `platforms/spot/` | Rook | `HuskerMinion/techo5-spot` |

The machine-readable [target manifest](targets/targets.json) maps every
supported satellite to its isolated platform directory, build entry point,
and release artifacts. Run `python3 tools/validate_targets.py` before pushing
platform changes.

These directories intentionally remain separate. The board families have
different kernels, device trees, boot formats, and recovery contracts;
artifacts must always be built and published per target.

New Tater tooling and names are canonical. Compatibility paths may retain a
`techo5-*` name while existing factory, rescue, rollback, and installed-image
flows still depend on that interface. Remove those aliases only through a
tested migration.

## Release policy

- Pin every source and downloaded input.
- Build board-specific artifacts reproducibly and publish SHA-256 hashes.
- Reproduce the currently pinned upstream artifacts before changing the
  Tater Echo Firmware platform lock.
- Preserve recovery paths and never substitute one board's kernel or boot
  image for another.
- Retain all upstream license and provenance files.

Tater application code remains in
[`Tater-Echo-Firmware`](https://github.com/TaterTotterson/Tater-Echo-Firmware).

Build and release policy is documented in
[`docs/releasing.md`](docs/releasing.md). Dot-family kernels can be built on a
pinned GitHub runner with the manual **Build Biscuit and Radar kernels**
workflow. Other families remain separately gated until their toolchains and
boot inputs are pinned in CI; they must never borrow another board's image.

Current Tater platform work:

- [Biscuit micro-USB Ethernet](docs/biscuit-usb-ethernet.md)

