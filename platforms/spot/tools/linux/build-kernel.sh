#!/bin/bash
# build-kernel.sh — the Echo Spot's kernel (LineageOS 18.1 rook, 4.9.337 arm64) with Bluetooth added,
# at the commit the LineageOS boot image was built from, so its vendor module (amzn-bcmdhd.ko, built
# with CONFIG_MODVERSIONS) still loads. Run inside WSL/Linux. Modeled on TECHO5's build-kernel.sh.
#
#   tools/linux/build-kernel.sh [-o Image.gz-dtb]
#
# Environment: KREPO (a clone of github.com/amazon-oss/android_kernel_amazon_mt8163; ~/kernel),
# KSRC (a clean worktree made from it at KCOMMIT; ~/kernel-rook), KCOMMIT (4174e0b4d0e2: `uname -r` on
# LineageOS is 4.9.337-g<KCOMMIT>), KCONFIG (the running kernel's /proc/config.gz, saved in
# docs/dumps: it is the one the modules were built with, and differs from rook_defconfig),
# CROSS_COMPILE (an aarch64 GCC; Arm's 8.3-2019.03 release), KOUT (build directory; ~/kout-rook).
#
# Bluetooth: core, BR/EDR, LE, RFCOMM and the virtual HCI driver. Tater's btbridge talks to the
# BCM43569A2 on /dev/ttyMT1 itself (firmware patch, baud rate, address) and hands the kernel a
# ready controller through /dev/vhci, as it does for the Show's and the Dot's MediaTek radios.
#
# USB Ethernet: the external MUSB controller already contains MediaTek's bounded command-mode
# switch. CONFIG_MTK_USB_CMD_CHANGE_MODE exposes it as /proc/mchange so userspace can briefly
# probe host mode and always restore the normal USB gadget/serial role. CONFIG_USB_RTL8152 is
# built in for powered UCTRONICS adapters such as B0B9ZLVGJ4 (0bda:8152). The internal Broadcom
# Wi-Fi adapter remains on the separate usb1/MUSBFSH controller.
set -euo pipefail

HERE=$(cd "$(dirname "$0")/../.." && pwd)
KREPO=${KREPO:-$HOME/kernel}
KSRC=${KSRC:-$HOME/kernel-rook}
KCOMMIT=${KCOMMIT:-4174e0b4d0e2}
KOUT=${KOUT:-$HOME/kout-rook}
KCONFIG=${KCONFIG:-$HERE/docs/dumps/rook-lineage-kernel-4.9.337.config}
KPATCH=${KPATCH:-$HERE/patches/0001-fix-mchange-irq-prototype.patch}
CROSS_COMPILE=${CROSS_COMPILE:-$HOME/toolchain/gcc-arm-8.3-2019.03-x86_64-aarch64-linux-gnu/bin/aarch64-linux-gnu-}
OUT=
while [ $# -gt 0 ]; do
	case "$1" in
	-o) OUT=$2; shift 2;;
	*) echo "unknown argument: $1" >&2; exit 1;;
	esac
done

if ! git -C "$KREPO" rev-parse --git-dir >/dev/null 2>&1; then
	mkdir -p "$(dirname "$KREPO")"
	git clone --filter=blob:none --no-checkout \
		https://github.com/amazon-oss/android_kernel_amazon_mt8163.git "$KREPO"
fi
if [ ! -d "$KSRC" ]; then
	git -C "$KREPO" cat-file -e "$KCOMMIT^{commit}" 2>/dev/null || git -C "$KREPO" fetch origin "$KCOMMIT"
	git -C "$KREPO" worktree add --detach "$KSRC" "$KCOMMIT"
fi
cd "$KSRC"
head=$(git rev-parse --short=12 HEAD)
case "$head" in "$KCOMMIT"*) ;; *) echo "kernel tree is at $head, not $KCOMMIT" >&2; exit 1;; esac
if [ -n "$(git status --porcelain)" ]; then
	echo "kernel tree is not clean (LOCALVERSION would get -dirty):" >&2
	git status --short >&2
	exit 1
fi
# Amazon shipped the command-mode implementation behind a disabled option with
# a stale IRQ-handler prototype. Apply Tater's minimal build fix while keeping
# the source revision and resulting module ABI at the pinned Lineage commit.
[ -f "$KPATCH" ] || { echo "missing kernel patch: $KPATCH" >&2; exit 1; }
git apply --check "$KPATCH"
git apply "$KPATCH"
printf '%s\n' "-g$(git rev-parse --short=12 HEAD)" > .scmversion
cleanup_source() {
	rm -f .scmversion
	git apply -R "$KPATCH"
}
trap cleanup_source EXIT
# Keep the builder's account, host and zone out of the image.
export KBUILD_BUILD_USER=tater KBUILD_BUILD_HOST=tater-rook-build TZ=UTC
export ARCH=arm64 CROSS_COMPILE
mkdir -p "$KOUT"
cp "$KCONFIG" "$KOUT/.config"
scripts/config --file "$KOUT/.config" \
	-e BT -e BT_BREDR -e BT_LE -e BT_RFCOMM -e BT_RFCOMM_TTY \
	-e BT_HCIVHCI -d BT_DEBUGFS \
	-e MTK_USB_CMD_CHANGE_MODE -e USB_RTL8152 -e USB_ANNOUNCE_NEW_DEVICES
make -s O="$KOUT" olddefconfig
for want in \
	'CONFIG_BT=y' \
	'CONFIG_BT_HCIVHCI=y' \
	'CONFIG_LOCALVERSION_AUTO=y' \
	'CONFIG_MODVERSIONS=y' \
	'CONFIG_USB_MTK_HDRC=y' \
	'CONFIG_USB_MTK_OTG=y' \
	'CONFIG_MTK_USB_CMD_CHANGE_MODE=y' \
	'CONFIG_MII=y' \
	'CONFIG_USB_USBNET=y' \
	'CONFIG_USB_NET_CDCETHER=y' \
	'CONFIG_USB_RTL8152=y' \
	'CONFIG_USB_ANNOUNCE_NEW_DEVICES=y'; do
	grep -qxF "$want" "$KOUT/.config" || { echo "config check failed: $want" >&2; exit 1; }
done
make -j"$(nproc)" O="$KOUT" Image.gz-dtb
echo "release: $(cat "$KOUT/include/config/kernel.release")"
ls -la "$KOUT/arch/arm64/boot/Image.gz-dtb"
if [ -n "$OUT" ]; then
	mkdir -p "$(dirname "$OUT")"
	cp "$KOUT/arch/arm64/boot/Image.gz-dtb" "$OUT"
	cp "$KOUT/.config" "$OUT.config"
	cp "$KOUT/System.map" "$OUT.System.map"
	echo "copied to $OUT"
fi
