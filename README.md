# Tater Linux

Tater Linux is the board-platform source used to build Linux kernels, root
filesystems, rescue images, and factory tooling for Tater Echo satellites.
It keeps the original upstream histories intact while giving Tater one place
to maintain and release the complete platform stack.

## Platforms

| Directory | Boards | Imported from |
|---|---|---|
| `platforms/dot/` | Biscuit, Radar | `HuskerMinion/techo5-dot` |
| `platforms/show/` | Checkers, Crown, Athena | `HuskerMinion/techo5` |
| `platforms/spot/` | Rook | `HuskerMinion/techo5-spot` |

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

