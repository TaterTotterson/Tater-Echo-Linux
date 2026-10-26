# USB Ethernet readiness by satellite

This audit separates static kernel readiness from hardware qualification. A
kernel containing host and usbnet drivers is not proof that a board safely
switches role, sources VBUS, preserves its recovery path, or survives unplug.

| Target | Static result | Remaining hardware boundary |
|---|---|---|
| Biscuit | Tater 3.18 kernel has explicit `/proc/mchange`, MII, usbnet, and CDC-ECM | Re-run acceptance with the exact published kernel and powered pass-through adapter |
| Radar | Same target-specific 3.18 prerequisites, kept separate from Biscuit | Internal D+/D-/GND pads, barrel-powered device, externally powered adapter, serial recovery |
| Checkers | Existing 4.9 baseline already has MediaTek HDRC/OTG, MII, usbnet, CDC-ECM, and enumeration logging | Identify the board's role control and VBUS behavior; verify its own boot/recovery image |
| Crown | Existing 4.9 baseline has the same static prerequisites as Checkers | Qualify Crown's connector, device tree, VBUS, and recovery independently |
| Athena | Intentionally fail-closed: current device tree is peripheral-only and disables `usb_host` | Implement and bench-test MTU3 role switching, GPIO41 ID, GPIO165 VBUS detection, and GPIO150 drive before enabling host mode |
| Rook | Existing 4.9 baseline has MediaTek HDRC/OTG, MII, usbnet, CDC-ECM, and enumeration logging | Prove external `usb0` role/VBUS without disturbing internal `usb1` Wi-Fi; verify rescue |

`python3 tools/audit_usb_ethernet.py` checks these static assertions in CI. It
deliberately does not edit a configuration or mark a target qualified.

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
