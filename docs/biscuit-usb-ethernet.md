# Biscuit micro-USB Ethernet

The Dot platform can build a Biscuit kernel that switches the shared
micro-USB controller between its normal serial gadget and USB host mode for a
powered Ethernet adapter.

This path was verified on an Echo Dot 2nd Gen with a UCTRONICS U6113 adapter
(`0bda:8152`) in CDC-ECM configuration 2. The in-kernel `cdc_ether` driver
created `eth0`; DHCP assigned `192.168.1.9` and installed a working default
route on 2026-10-25.

## Source changes

- `platforms/dot/tools/linux/kernel-usbnet.fragment` enables MediaTek's
  `/proc/mchange` forced-role interface, usbnet, MII, and CDC-ECM.
- `0052-cdcether-rtl8152-no-blacklist.patch` removes Linux 3.18's intentional
  generic-driver rejection for `0bda:8152`. This is the required functional
  patch.
- `0049-usbnet-report-probe-failures.patch` makes otherwise silent probe failures
  visible.
- `build-kernel.sh` grafts usbnet files omitted from Amazon's partial GPL
  source archive and verifies every fragment line in the final configuration.

Build on a case-sensitive Linux filesystem:

```sh
WORK="$HOME/biscuit-build" \
  bash platforms/dot/tools/linux/build-kernel.sh \
  --board biscuit -o build/biscuit
```

The firmware-side `tater-usb-ethernet` controller is intentionally opt-in. It
keeps Wi-Fi up during the probe, switches only after Ethernet has an address
and route, and restores USB serial plus Wi-Fi on disable or link loss.

Do not publish the old loose `r8152.ko` test artifact; the unused vendor driver
is disabled. Publish the kernel, configuration, source revision, and SHA-256
together as a Tater Linux Biscuit release. Radar and the other board families
stay disabled until their USB role, power, enumeration, and recovery paths are
verified independently.
