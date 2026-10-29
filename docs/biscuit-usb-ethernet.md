# Biscuit micro-USB Ethernet

The Dot platform can build a Biscuit kernel that switches the shared
micro-USB controller between its normal serial gadget and USB host mode for a
powered Ethernet adapter.

Initial testing on 2026-10-25 showed a UCTRONICS U6113 adapter (`0bda:8152`)
enumerating through its CDC-ECM configuration. Release-candidate testing on a
physical Biscuit on 2026-10-29 exposed the missing gate: `cdc_ether` created
`eth0` and received frames but transmitted none, so DHCP could not complete.
The release kernel therefore keeps CDC-ECM for class-compliant adapters while
binding `0bda:8152` to the proper built-in Realtek `r8152` driver.

## Source changes

- `platforms/dot/tools/linux/kernel-usbnet.fragment` enables MediaTek's
  `/proc/mchange` forced-role interface, usbnet, MII, CDC-ECM, and built-in
  RTL8152 support.
- `0050-r8152-3.18-eee-helpers.patch` supplies the EEE helpers missing from the
  vendor 3.18 tree so the pinned upstream driver builds cleanly.
- `0049-usbnet-report-probe-failures.patch` makes otherwise silent probe failures
  visible.
- `build-kernel.sh` grafts usbnet, CDC-ECM, and RTL8152 sources omitted from
  Amazon's partial GPL archive and verifies every fragment line in the final
  configuration.

Build on a case-sensitive Linux filesystem:

```sh
WORK="$HOME/biscuit-build" \
  bash platforms/dot/tools/linux/build-kernel.sh \
  --board biscuit -o build/biscuit
```

The firmware-side `tater-usb-ethernet` controller is automatic. It keeps Wi-Fi
up during the probe, switches only after Ethernet has an address and route, and
restores USB serial plus Wi-Fi on adapter failure or link loss.

Do not publish a loose `r8152.ko`; the driver is built into the verified kernel
so it is present before rootfs selection and cannot drift from that kernel's
ABI. Publish the kernel, configuration, source revision, and SHA-256 together
as a Tater Linux Biscuit release. Radar retains its separately built image and
requires its own physical role, power, enumeration, and recovery validation.
