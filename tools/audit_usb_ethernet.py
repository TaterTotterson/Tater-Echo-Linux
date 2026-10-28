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

REQUIRED_49_RTL8152 = REQUIRED_49 + ("CONFIG_USB_RTL8152=y",)


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

        require(ROOT / "platforms/show/docs/dumps/cronos-lineage-kernel-4.9.337.config", REQUIRED_49_RTL8152)
        require(ROOT / "platforms/spot/docs/dumps/rook-lineage-kernel-4.9.337.config", REQUIRED_49)

        rook_build = (ROOT / "platforms/spot/tools/linux/build-kernel.sh").read_text(encoding="utf-8")
        for value in (
            "-e MTK_USB_CMD_CHANGE_MODE -e USB_RTL8152 -e USB_ANNOUNCE_NEW_DEVICES",
            "'CONFIG_MTK_USB_CMD_CHANGE_MODE=y'",
            "'CONFIG_USB_RTL8152=y'",
            "patches/0001-fix-mchange-irq-prototype.patch",
            'git apply --check "$KPATCH"',
        ):
            if value not in rook_build:
                raise ValueError(f"Rook Ethernet kernel build is missing {value}")
        rook_patch = (ROOT / "platforms/spot/patches/0001-fix-mchange-irq-prototype.patch").read_text(
            encoding="utf-8"
        )
        if rook_patch.count("mt_usb_ext_iddig_int(0, NULL)") != 3:
            raise ValueError("Rook command-mode patch does not fix all three forced-role calls")
        if "extern irqreturn_t mt_usb_ext_iddig_int(int irq, void *dev_id);" not in rook_patch:
            raise ValueError("Rook command-mode patch does not fix the IDDIG IRQ prototype")

        athena_root = ROOT / "platforms/show/tools/linux/athena/kernel"
        athena = (athena_root / "dts/mt8183-amazon-athena.dts").read_text(encoding="utf-8")
        for value in (
            'dr_mode = "otg";',
            "usb-role-switch;",
            "role-switch-default-mode = \"peripheral\";",
            "id-gpios = <&pio 41 GPIO_ACTIVE_HIGH>;",
            "vbus-supply = <&usb_otg_vbus>;",
            "&usb_host {\n\tstatus = \"okay\";",
        ):
            if value not in athena:
                raise ValueError(f"Athena OTG kernel is missing {value}")
        require(athena_root / "athena_defconfig", ("CONFIG_USB_RTL8152=y", "CONFIG_USB_MTU3_DUAL_ROLE=y"))
    except (OSError, ValueError) as error:
        print(f"USB Ethernet audit failed: {error}", file=sys.stderr)
        return 1

    print("static USB Ethernet audit passed")
    print("  Biscuit/Radar: explicit MediaTek role control and usbnet/CDC-ECM present")
    print("  Checkers/Crown: RTL8152 and usbnet prerequisites present; role/VBUS remains unqualified")
    print("  Athena: RTL8152 and hardware-driven OTG role switching present; adapter validation remains")
    print("  Rook: reproducible build enables RTL8152 and bounded /proc/mchange role switching")
    return 0


if __name__ == "__main__":
    sys.exit(main())
