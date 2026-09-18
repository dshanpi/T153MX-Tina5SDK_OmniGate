import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / ("overlay/device/config/chips/t153/configs/omnigate/"
                "linux-5.10-origin/board.dts")
BOARD_OVERLAY = ROOT / ("overlay/device/config/chips/t153/configs/omnigate/"
                        "buildroot/overlay")
GOODIX_PATCH = ROOT / ("patches/linux-5.10-origin/"
                       "0001-goodix-reset-without-int-gpio.patch")


class BoardInvariantTests(unittest.TestCase):
    def test_gt911_binding_matches_verified_t153mx_wiring(self):
        text = BOARD.read_text(encoding="utf-8")
        match = re.search(
            r"goodix_ts:\s*touchscreen@14\s*\{(?P<body>.*?)\n\s*\};",
            text,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "GT911 must be declared at I2C address 0x14")
        body = match.group("body")
        self.assertIn('compatible = "goodix,gt911";', body)
        self.assertRegex(body, r"reg\s*=\s*<0x14>;")
        self.assertIn("pinctrl-0 = <&goodix_int_pin>;", body)
        self.assertIn("interrupts = <9 7 IRQ_TYPE_EDGE_FALLING>;", body)
        self.assertIn("reset-gpios = <&pio PJ 6 GPIO_ACTIVE_LOW>;", body)
        self.assertIn("goodix,reset-without-int-gpio;", body)
        self.assertIn("touchscreen-size-x = <1024>;", body)
        self.assertIn("touchscreen-size-y = <768>;", body)
        self.assertNotIn("irq-gpios", body)
        patch = GOODIX_PATCH.read_text(encoding="utf-8")
        self.assertIn('"goodix,reset-without-int-gpio"', patch)
        self.assertIn("if (!ts->gpiod_int)", patch)

    def test_can_defaults_match_web_configuration(self):
        defaults = (BOARD_OVERLAY / "etc/default/can").read_text(encoding="utf-8")
        init_script = (BOARD_OVERLAY / "etc/init.d/S42can").read_text(
            encoding="utf-8")
        config = json.loads((BOARD_OVERLAY / "etc/omnigate-web/config.json").read_text(
            encoding="utf-8"))

        values = dict(re.findall(r"^(CAN[01]_BITRATE)=(\d+)$", defaults,
                                 re.MULTILINE))
        self.assertEqual("500000", values.get("CAN0_BITRATE"))
        self.assertEqual("500000", values.get("CAN1_BITRATE"))
        self.assertIn('CAN0_BITRATE="${CAN0_BITRATE:-500000}"', init_script)
        self.assertIn('CAN1_BITRATE="${CAN1_BITRATE:-500000}"', init_script)
        self.assertEqual(config["can"]["can0"]["bitrate"], int(values["CAN0_BITRATE"]))
        self.assertEqual(config["can"]["can1"]["bitrate"], int(values["CAN1_BITRATE"]))


if __name__ == "__main__":
    unittest.main()
