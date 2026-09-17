import json
import tempfile
import unittest
from pathlib import Path

from omnigate_core.platform import ManifestError, channel, load_manifest
from omnigate_core.store import EdgeStore


MANIFEST = {
    "schema_version": 1,
    "board_id": "test-board",
    "soc": "test-soc",
    "runtime_profile": "lite",
    "channels": {
        "can_primary": {"kind": "can", "device": "vcan0", "role": "fieldbus"},
        "management": {"kind": "ethernet", "device": "eth9", "role": "management"}
    }
}


class PlatformTests(unittest.TestCase):
    def test_load_and_resolve(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "platform.json"
            path.write_text(json.dumps(MANIFEST), encoding="utf-8")
            value = load_manifest(path)
            self.assertEqual(channel(value, "can_primary", "can")["device"], "vcan0")

    def test_rejects_unknown_profile(self):
        value = dict(MANIFEST, runtime_profile="large")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "platform.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ManifestError):
                load_manifest(path)


class StoreTests(unittest.TestCase):
    def test_device_revision_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EdgeStore(Path(directory) / "edge.db")
            value = {"id": "meter-1", "name": "Meter", "template_id": "meter.v1",
                     "channel": "can_primary", "address": "7", "config": {}}
            self.assertEqual(store.put_device(value, "tester"), 1)
            self.assertEqual(store.put_device(value, "tester"), 2)
            self.assertEqual(store.list_devices()[0]["revision"], 2)
            self.assertEqual(len(store.audit()), 2)
            self.assertEqual(store.get_device("meter-1")["id"], "meter-1")
            self.assertTrue(store.delete_device("meter-1", "tester"))
            self.assertIsNone(store.get_device("meter-1"))
            self.assertFalse(store.delete_device("meter-1", "tester"))
            self.assertIn("device.delete", [row["action"] for row in store.audit()])

    def test_point_crud_and_device_cascade(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EdgeStore(Path(directory) / "edge.db")
            device = {"id": "meter-1", "name": "Meter",
                      "template_id": "meter.v1", "channel": "can_primary",
                      "address": "7", "config": {}}
            store.put_device(device, "tester")
            point = {"id": "meter-1.temperature", "device_id": "meter-1",
                     "name": "Temperature", "data_type": "float",
                     "unit": "C", "access": "r", "address": "0x1000:1",
                     "scale": 0.1, "enabled": True}
            store.put_point(point, "tester")
            self.assertEqual(store.get_point(point["id"])["scale"], 0.1)
            self.assertEqual(len(store.list_points("meter-1")), 1)
            self.assertTrue(store.delete_point(point["id"], "tester"))
            self.assertFalse(store.delete_point(point["id"], "tester"))
            store.put_point(point, "tester")
            store.delete_device("meter-1", "tester")
            self.assertEqual(store.list_points(), [])


class ApiTests(unittest.TestCase):
    def test_platform_and_device_contract(self):
        try:
            from flask import Flask
        except ImportError:
            self.skipTest("host Flask is not installed")
        from omnigate_core.api import create_blueprint
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "platform.json"
            manifest.write_text(json.dumps(MANIFEST), encoding="utf-8")
            app = Flask(__name__)
            app.secret_key = "test"
            app.register_blueprint(create_blueprint(
                manifest, str(Path(directory) / "edge.db")))
            client = app.test_client()
            self.assertEqual(client.get("/api/v1/platform").status_code, 200)
            response = client.put("/api/v1/devices/meter-1", json={
                "name": "Meter", "template_id": "meter.v1",
                "channel": "can_primary", "address": "7"
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(client.get("/api/v1/devices").json["devices"][0]["id"],
                             "meter-1")
            self.assertEqual(client.get("/api/v1/devices/meter-1").status_code, 200)
            point = {"device_id": "meter-1", "name": "Temperature",
                     "data_type": "float", "unit": "C", "access": "r",
                     "address": "0x1000:1", "scale": 0.1}
            self.assertEqual(client.put(
                "/api/v1/points/meter-1.temperature", json=point).status_code, 200)
            self.assertEqual(client.get(
                "/api/v1/points/meter-1.temperature").json["point"]["unit"], "C")
            self.assertEqual(len(client.get(
                "/api/v1/points?device_id=meter-1").json["points"]), 1)
            self.assertEqual(client.delete(
                "/api/v1/points/meter-1.temperature").status_code, 200)
            self.assertEqual(client.delete("/api/v1/devices/meter-1").status_code, 200)
            self.assertEqual(client.get("/api/v1/devices/meter-1").status_code, 404)


if __name__ == "__main__":
    unittest.main()
