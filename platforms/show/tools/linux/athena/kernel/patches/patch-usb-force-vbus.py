#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Patch mainline mtu3 + T-PHY for athena's role-aware VBUS sensing.

athena senses VBUS on a GPIO (GPIO165), not through the USB PHY, so neither the U2 PHY nor the
mtu3 MAC sees a peripheral session. Early test builds forced it by hand (devmem U2PHYDTM1 = 0x2c2c,
U3D_MISC_CTRL |= VBUS_FRC_EN | VBUS_ON). This does the same from the drivers in device mode, while
leaving the PHY's device-session inputs unforced in host mode:

  - T-PHY (phy-mtk-tphy.c), on a U2 port with mediatek,force-vbus: force VBUSVALID, BVALID and
    AVALID only in USB device mode. Host mode clears those overrides so the xHCI port can observe
    the attached device normally;
  - MTU3's role switch (mtu3_dr.c): tell the generic PHY whether each role is host or device. The
    upstream MTU3 switch selects the controller port but otherwise never calls phy_set_mode();
  - mtu3 (mtu3_core.c), on the controller with mediatek,force-vbus: VBUS forced on instead of
    "vbus detected by HW" for its device engine.

Usage: patch-usb-force-vbus.py KTREE   (idempotent)
"""
import sys

tree = sys.argv[1]
MARK = "athena: force-vbus"


def edit(path, pairs):
    p = tree + "/" + path
    s = open(p).read()
    if MARK in s:
        return
    for a, b in pairs:
        assert s.count(a) == 1, (path, a[:70], s.count(a))
        s = s.replace(a, b)
    open(p, "w").write(s)


edit("drivers/phy/mediatek/phy-mtk-tphy.c", [
    ("#define P2C_RG_VBUSVALID\t\tBIT(5)\n",
     "/* athena: force-vbus, the force bits for the session signals in U2PHYDTM1 */\n"
     "#define P2C_FORCE_VBUSVALID\t\tBIT(13)\n"
     "#define P2C_FORCE_BVALID\t\tBIT(11)\n"
     "#define P2C_FORCE_AVALID\t\tBIT(10)\n"
     "#define P2C_RG_BVALID\t\t\tBIT(3)\n"
     "#define P2C_RG_VBUSVALID\t\tBIT(5)\n"),
    ("\tbool type_force_mode;\n",
     "\tbool type_force_mode;\n"
     "\tbool force_vbus;\n"),
    ("""\tif (instance->type == PHY_TYPE_USB3)
\t\tinstance->type_force_mode = device_property_read_bool(dev, "mediatek,force-mode");
""",
     """\tif (instance->type == PHY_TYPE_USB3)
\t\tinstance->type_force_mode = device_property_read_bool(dev, "mediatek,force-mode");
\tif (instance->type == PHY_TYPE_USB2)
\t\tinstance->force_vbus = device_property_read_bool(dev, "mediatek,force-vbus");
"""),
    ("""\tswitch (mode) {
\tcase PHY_MODE_USB_DEVICE:
\t\ttmp |= P2C_FORCE_IDDIG | P2C_RG_IDDIG;
\t\tbreak;
\tcase PHY_MODE_USB_HOST:
\t\ttmp |= P2C_FORCE_IDDIG;
\t\ttmp &= ~P2C_RG_IDDIG;
\t\tbreak;
\tcase PHY_MODE_USB_OTG:
\t\ttmp &= ~(P2C_FORCE_IDDIG | P2C_RG_IDDIG);
\t\tbreak;
""",
     """\tswitch (mode) {
\tcase PHY_MODE_USB_DEVICE:
\t\ttmp |= P2C_FORCE_IDDIG | P2C_RG_IDDIG;
\t\t/* athena: force-vbus only for the peripheral session */
\t\tif (instance->force_vbus) {
\t\t\ttmp |= P2C_FORCE_VBUSVALID | P2C_FORCE_BVALID | P2C_FORCE_AVALID |
\t\t\t       P2C_RG_VBUSVALID | P2C_RG_BVALID | P2C_RG_AVALID;
\t\t\ttmp &= ~P2C_RG_SESSEND;
\t\t}
\t\tbreak;
\tcase PHY_MODE_USB_HOST:
\t\ttmp |= P2C_FORCE_IDDIG;
\t\ttmp &= ~P2C_RG_IDDIG;
\t\tif (instance->force_vbus) {
\t\t\t/* The A-host must see the line state, not a forced B-session. */
\t\t\ttmp &= ~(P2C_FORCE_VBUSVALID | P2C_FORCE_BVALID |
\t\t\t\t P2C_FORCE_AVALID | P2C_RG_BVALID);
\t\t\ttmp |= P2C_RG_VBUSVALID | P2C_RG_AVALID;
\t\t\ttmp &= ~P2C_RG_SESSEND;
\t\t}
\t\tbreak;
\tcase PHY_MODE_USB_OTG:
\t\ttmp &= ~(P2C_FORCE_IDDIG | P2C_RG_IDDIG);
\t\tbreak;
"""),
])

edit("drivers/usb/mtu3/mtu3_dr.c", [
    ("""\tenum usb_role desired_role = otg_sx->desired_role;
\tenum usb_role current_role;
""",
     """\tenum usb_role desired_role = otg_sx->desired_role;
\tenum usb_role current_role;
\tint ret;
"""),
    ("""\tcase USB_ROLE_HOST:
\t\tssusb_set_force_mode(ssusb, MTU3_DR_FORCE_HOST);
\t\tmtu3_stop(mtu);
""",
     """\tcase USB_ROLE_HOST:
\t\t/* athena: force-vbus is role-aware in the T-PHY */
\t\tret = phy_set_mode(ssusb->phys[0], PHY_MODE_USB_HOST);
\t\tif (ret)
\t\t\tdev_warn(ssusb->dev, "could not set USB2 PHY host mode: %d\\n", ret);
\t\tssusb_set_force_mode(ssusb, MTU3_DR_FORCE_HOST);
\t\tmtu3_stop(mtu);
"""),
    ("""\tcase USB_ROLE_DEVICE:
\t\tssusb_set_force_mode(ssusb, MTU3_DR_FORCE_DEVICE);
\t\tssusb->is_host = false;
""",
     """\tcase USB_ROLE_DEVICE:
\t\t/* athena: force-vbus is role-aware in the T-PHY */
\t\tret = phy_set_mode(ssusb->phys[0], PHY_MODE_USB_DEVICE);
\t\tif (ret)
\t\t\tdev_warn(ssusb->dev, "could not set USB2 PHY device mode: %d\\n", ret);
\t\tssusb_set_force_mode(ssusb, MTU3_DR_FORCE_DEVICE);
\t\tssusb->is_host = false;
"""),
])

edit("drivers/usb/mtu3/mtu3_core.c", [
    ("""\t/* vbus detected by HW */
\tmtu3_clrbits(mbase, U3D_MISC_CTRL, VBUS_FRC_EN | VBUS_ON);
""",
     """\t/* vbus detected by HW, or forced on where the board senses it elsewhere (athena: force-vbus) */
\tif (of_property_read_bool(mtu->dev->of_node, "mediatek,force-vbus"))
\t\tmtu3_setbits(mbase, U3D_MISC_CTRL, VBUS_FRC_EN | VBUS_ON);
\telse
\t\tmtu3_clrbits(mbase, U3D_MISC_CTRL, VBUS_FRC_EN | VBUS_ON);
"""),
])
print("patched")
