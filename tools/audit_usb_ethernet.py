#!/usr/bin/env python3
"""Audit static USB Ethernet prerequisites without qualifying hardware."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_49 = (
    "CONFIG_USB_MTK_HDRC=y",
    "CONFIG_USB_MTK_OTG=y",
    "CONFIG_MII=y",
    "CONFIG_USB_USBNET=y",
    "CONFIG_USB_NET_CDCETHER=y",
    "CONFIG_USB_ANNOUNCE_NEW_DEVICES=y",
)


def require(path: Path, values: tuple[str, ...]) -> None:
    contents = path.read_text(encoding="utf-8")
    missing = [value for value in values if value not in contents.splitlines()]
    if missing:
        raise ValueError(f"{path.relative_to(ROOT)} is missing {', '.join(missing)}")


def main() -> int:
    try:
        dot = (ROOT / "platforms/dot/tools/linux/kernel-usbnet.fragment").read_text(encoding="utf-8")
        for value in ("CONFIG_CMD_MODE_CHANGE=y", "CONFIG_MII=y", "CONFIG_USB_USBNET=y", "CONFIG_USB_NET_CDCETHER=y"):
            if value not in dot.splitlines():
                raise ValueError(f"Dot USB fragment is missing {value}")

        require(ROOT / "platforms/show/docs/dumps/cronos-lineage-kernel-4.9.337.config", REQUIRED_49)
        require(ROOT / "platforms/spot/docs/dumps/rook-lineage-kernel-4.9.337.config", REQUIRED_49)

        athena = (ROOT / "platforms/show/tools/linux/athena/kernel/dts/mt8183-amazon-athena.dts").read_text(encoding="utf-8")
        for fail_closed in ('dr_mode = "peripheral";', "&usb_host {\n\tstatus = \"disabled\";"):
            if fail_closed not in athena:
                raise ValueError("Athena no longer has the expected peripheral-only hardware gate")
    except (OSError, ValueError) as error:
        print(f"USB Ethernet audit failed: {error}", file=sys.stderr)
        return 1

    print("static USB Ethernet audit passed")
    print("  Biscuit/Radar: explicit MediaTek role control and usbnet/CDC-ECM present")
    print("  Checkers/Crown/Rook: host and usbnet/CDC-ECM prerequisites present; role/VBUS remains unqualified")
    print("  Athena: peripheral-only device tree gate remains in place")
    return 0


if __name__ == "__main__":
    sys.exit(main())
