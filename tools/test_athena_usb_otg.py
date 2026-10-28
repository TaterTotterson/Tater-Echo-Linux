#!/usr/bin/env python3
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / "platforms/show/tools/linux/athena/kernel"


class AthenaUsbOtgTests(unittest.TestCase):
    def test_kernel_build_enables_dual_role_and_mtk_host(self) -> None:
        config = (KERNEL / "athena_defconfig").read_text()
        build = (KERNEL / "build.sh").read_text()
        for setting in (
            "CONFIG_USB_MTU3_DUAL_ROLE=y",
            "CONFIG_USB_ROLE_SWITCH=y",
            "CONFIG_USB_CONN_GPIO=y",
            "CONFIG_USB_XHCI_HCD=y",
            "CONFIG_USB_XHCI_PLATFORM=y",
            "CONFIG_USB_XHCI_MTK=y",
            "CONFIG_USB_RTL8152=y",
            "CONFIG_USB_USBNET=y",
            "CONFIG_USB_NET_AX8817X=y",
            "CONFIG_USB_NET_AX88179_178A=y",
            "CONFIG_USB_NET_CDCETHER=y",
            "CONFIG_USB_NET_CDC_NCM=y",
        ):
            self.assertIn(setting, config)
            self.assertIn(repr(setting), build)
        self.assertNotIn("CONFIG_USB_MTU3_GADGET=y", config)

    def test_device_tree_defaults_safe_and_models_all_three_signals(self) -> None:
        dts = (KERNEL / "dts/mt8183-amazon-athena.dts").read_text()
        self.assertIn('dr_mode = "otg";', dts)
        self.assertIn("usb-role-switch;", dts)
        self.assertIn('role-switch-default-mode = "peripheral";', dts)
        self.assertIn('compatible = "gpio-usb-b-connector", "usb-b-connector";', dts)
        self.assertIn("id-gpios = <&pio 41 GPIO_ACTIVE_HIGH>;", dts)
        self.assertIn("vbus-gpios = <&pio 165 GPIO_ACTIVE_HIGH>;", dts)
        self.assertIn("gpio = <&pio 150 GPIO_ACTIVE_HIGH>;", dts)
        self.assertEqual(dts.count("vbus-supply = <&usb_otg_vbus>;"), 3)
        self.assertEqual(dts.count("vusb33-supply = <&mt6358_vusb_reg>;"), 2)
        self.assertIn("PINMUX_GPIO41__FUNC_GPIO41", dts)
        self.assertIn("PINMUX_GPIO150__FUNC_GPIO150", dts)
        self.assertRegex(
            dts,
            r"&usb_host \{\s*vbus-supply = <&usb_otg_vbus>;\s*"
            r"vusb33-supply = <&mt6358_vusb_reg>;\s*status = \"okay\";",
        )


if __name__ == "__main__":
    unittest.main()
