# USB Ethernet readiness by satellite

This audit separates static kernel readiness from hardware qualification. A
kernel containing host and usbnet drivers is not proof that a board safely
switches role, sources VBUS, preserves its recovery path, or survives unplug.

| Target | Static result | Remaining hardware boundary |
|---|---|---|
| Biscuit | Tater 3.18 kernel has explicit `/proc/mchange`, MII, usbnet/CDC-ECM, and built-in RTL8152 | Re-run acceptance with the exact published kernel and powered pass-through adapter |
| Radar | Same target-specific 3.18 prerequisites and built-in RTL8152, kept separate from Biscuit | Internal D+/D-/GND pads, barrel-powered device, externally powered adapter, serial recovery |
| Checkers | Existing 4.9 baseline already has MediaTek HDRC/OTG, MII, usbnet, CDC-ECM, and enumeration logging | Identify the board's role control and VBUS behavior; verify its own boot/recovery image |
| Crown | Existing 4.9 baseline has the same static prerequisites as Checkers | Qualify Crown's connector, device tree, VBUS, and recovery independently |
| Athena | Tater's MTU3 kernel has RTL8152, GPIO41 hardware-ID role switching, GPIO165 VBUS detection, and GPIO150 host-VBUS drive | Validate the intended adapter: enumeration, DHCP, traffic, unplug, reboot, and recovery |
| Rook | Tater's reproducible 4.9 build adds built-in RTL8152 and MediaTek's bounded `/proc/mchange` host/device control; internal USB Wi-Fi stays on `usb1` | Boot the exact candidate, validate the powered UCTRONICS adapter, then prove USB-serial and Wi-Fi recovery |

`python3 tools/audit_usb_ethernet.py` checks these static assertions in CI. It
verifies Dot's built-in RTL8152 and `/proc/mchange` configuration, plus Rook's
`CONFIG_USB_RTL8152` and `CONFIG_MTK_USB_CMD_CHANGE_MODE` build flags, rather
than changing the preserved LineageOS running-config dump. It deliberately
does not mark a target qualified.

## Intended UCTRONICS adapter

The current cross-platform qualification target is the powered UCTRONICS
B0B9ZLVGJ4 adapter (`0bda:8152`, RTL8152 family). It supplies both device power
and Ethernet over the satellite's micro-USB connector, using either IEEE
802.3af/at PoE or its separate micro-USB power input. Rook and Athena build the
vendor driver in. Checkers and Crown's 4.9 family configuration already carries
it, but their role/VBUS paths remain separate hardware gates.

Biscuit release-candidate testing proved that this adapter's advertised CDC-ECM
configuration enumerates on Amazon's trimmed 3.18 tree but does not transmit.
Biscuit and Radar therefore use the tracked, built-in RTL8152 backport while
retaining generic CDC-ECM support for other class-compliant adapters. Radar
still has no user-accessible USB connector.

## Baseline custody

[`baselines/satellite-baselines-v1.json`](../baselines/satellite-baselines-v1.json)
records the exact Checkers, Crown, Athena, and Rook inputs currently consumed by
Tater Echo Firmware. `tools/fetch_baselines.py` downloads each upstream release
asset, verifies its original SHA-256 and byte count, gives it a Tater release
name, and produces `BASELINE-PROVENANCE.json` plus `SHA256SUMS`.

These are provenance mirrors, not rebuilt or newly qualified artifacts. Their
bytes and hashes do not change. Moving custody to a Tater release removes an
availability dependency on the upstream release while retaining the exact
source URL and digest. A later Tater-built replacement must use a new release
tag and pass the per-target boot and recovery gate before firmware changes its
lock.
