import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "overlay/buildroot/buildroot-202205/package/omnigate-core/src"
WEB = ROOT / ("overlay/device/config/chips/t153/configs/omnigate/"
              "buildroot/overlay/usr/lib/omnigate-web")


class WebApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        base = Path(cls.temporary.name)
        assets = base / "assets"
        assets.mkdir()
        (assets / "index.html").write_text("<!doctype html><title>test</title>",
                                           encoding="utf-8")
        manifest = {
            "schema_version": 1, "board_id": "test-board", "soc": "test-soc",
            "runtime_profile": "lite", "channels": {
                "can0": {"kind": "can", "device": "can0", "role": "fieldbus"},
                "management0": {"kind": "ethernet", "device": "eth0",
                                "role": "management"},
                "display0": {"kind": "display", "device": "/dev/fb0",
                             "role": "local-hmi"},
            },
        }
        manifest_path = base / "platform.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        password = "host-test-password"
        salt = "host-test-salt"
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 120000).hex()
        config = {"auth": {"username": "admin", "role": "administrator",
                           "salt": salt, "password_hash": password_hash,
                           "must_change": True}, "can": {}, "canopen": {},
                  "ec20": {"profiles": {}}}
        config_path = base / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        hmi_settings = base / "hmi.json"
        hmi_settings.write_text(json.dumps({"demo_mode": False}), encoding="utf-8")
        values = {
            "OMNIGATE_CORE_PATH": str(CORE),
            "OMNIGATE_PLATFORM_MANIFEST": str(manifest_path),
            "OMNIGATE_WEB_ASSETS": str(assets),
            "OMNIGATE_WEB_CONFIG": str(config_path),
            "OMNIGATE_WEB_SECRET": str(base / "secret.key"),
            "OMNIGATE_WEB_LOG": str(base / "web.log"),
            "OMNIGATE_EDGE_DB": str(base / "edge.db"),
            "OMNIGATE_HMI_DB": str(base / "hmi.db"),
            "OMNIGATE_HMI_SETTINGS": str(hmi_settings),
            "OMNIGATE_MODBUS_CONFIG": str(base / "modbus.json"),
            "OMNIGATE_CONFIG": str(config_path),
            "OMNIGATE_TB_CONFIG": str(base / "thingsboard.json"),
            "OMNIGATE_EDS_DIR": str(base / "eds"),
        }
        os.environ.update(values)
        sys.path[:0] = [str(CORE), str(WEB)]
        spec = importlib.util.spec_from_file_location("omnigate_web_test_app",
                                                      WEB / "app.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.app.config.update(TESTING=True)
        cls.app = module.app
        cls.password = password

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def login(self, client):
        response = client.post("/api/login", json={
            "username": "admin", "password": self.password})
        self.assertEqual(response.status_code, 200)
        return response.get_json()["csrf"]

    def test_security_login_and_standard_errors(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/api/v1/platform").status_code, 401)
        health = client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.headers["X-Frame-Options"], "DENY")
        self.login(client)
        self.assertEqual(client.get("/does-not-exist").status_code, 404)
        self.assertEqual(client.post(
            "/api/login", data="not-json", content_type="application/json"
        ).status_code, 400)

    def test_device_point_crud_csrf_and_audit(self):
        client = self.app.test_client()
        csrf = self.login(client)
        headers = {"X-CSRF-Token": csrf}
        device = {"name": "Meter", "template_id": "meter.v1",
                  "channel": "can0", "address": "7"}
        response = client.put("/api/v1/devices/meter-1", json=device,
                              headers=headers)
        self.assertEqual(response.get_json()["revision"], 1)
        point = {"device_id": "meter-1", "name": "Temperature",
                 "data_type": "float", "unit": "C", "access": "r",
                 "address": "0x1000:1", "scale": 0.1}
        self.assertEqual(client.put(
            "/api/v1/points/meter-1.temperature", json=point,
            headers=headers).status_code, 200)
        self.assertEqual(client.get(
            "/api/v1/points/meter-1.temperature").get_json()["point"]["unit"], "C")
        self.assertEqual(client.put(
            "/api/v1/points/no-csrf", json=point).status_code, 403)
        audit = client.get("/api/v1/audit").get_json()["audit"]
        self.assertIn("point.put", [row["action"] for row in audit])

    def test_hmi_demo_is_off_by_default(self):
        response = self.app.test_client().get("/api/hmi/v1/snapshot")
        self.assertEqual(response.status_code, 200)
        value = response.get_json()
        self.assertFalse(value["settings"]["demo_mode"])
        self.assertEqual(value["sensors"], [])
        self.assertNotIn("演示", json.dumps(value, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
