"""Power-loss-aware local inventory and point model for the edge API."""
import json
import sqlite3
import threading
import time
from pathlib import Path


SCHEMA_VERSION = 1


class EdgeStore:
    def __init__(self, path="/var/lib/omnigate/edge.db"):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self):
        with self.lock, self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    template_id TEXT NOT NULL, channel TEXT NOT NULL,
                    address TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS points (
                    id TEXT PRIMARY KEY, device_id TEXT NOT NULL,
                    name TEXT NOT NULL, data_type TEXT NOT NULL,
                    unit TEXT NOT NULL DEFAULT '', access TEXT NOT NULL DEFAULT 'r',
                    address TEXT NOT NULL, scale REAL NOT NULL DEFAULT 1.0,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(device_id) REFERENCES devices(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS points_device ON points(device_id);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL,
                    actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL,
                    result TEXT NOT NULL, detail_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS edge_audit_ts ON audit(ts DESC);
            """)
            conn.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
                         ("schema_version", str(SCHEMA_VERSION)))

    @staticmethod
    def _rows(cursor):
        rows = []
        for row in cursor:
            value = dict(row)
            if "config_json" in value:
                value["config"] = json.loads(value.pop("config_json") or "{}")
            if "detail_json" in value:
                value["detail"] = json.loads(value.pop("detail_json") or "{}")
            if "enabled" in value:
                value["enabled"] = bool(value["enabled"])
            rows.append(value)
        return rows

    def list_devices(self):
        with self.lock, self.connect() as conn:
            return self._rows(conn.execute("SELECT * FROM devices ORDER BY id"))

    def get_device(self, device_id):
        with self.lock, self.connect() as conn:
            values = self._rows(conn.execute(
                "SELECT * FROM devices WHERE id=?", (device_id,)))
            return values[0] if values else None

    def put_device(self, value, actor):
        now = int(time.time())
        with self.lock, self.connect() as conn:
            previous = conn.execute("SELECT revision FROM devices WHERE id=?",
                                    (value["id"],)).fetchone()
            revision = (previous["revision"] + 1) if previous else 1
            conn.execute("""
                INSERT INTO devices(id,name,template_id,channel,address,enabled,
                    config_json,revision,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                    template_id=excluded.template_id,channel=excluded.channel,
                    address=excluded.address,enabled=excluded.enabled,
                    config_json=excluded.config_json,revision=excluded.revision,
                    updated_at=excluded.updated_at
            """, (value["id"], value["name"], value["template_id"], value["channel"],
                  value["address"], int(value.get("enabled", True)),
                  json.dumps(value.get("config", {}), sort_keys=True), revision,
                  now, now))
            self._audit_conn(conn, actor, "device.put", value["id"], "success",
                             {"revision": revision})
        return revision

    def delete_device(self, device_id, actor):
        with self.lock, self.connect() as conn:
            row = conn.execute("SELECT revision FROM devices WHERE id=?",
                               (device_id,)).fetchone()
            if row is None:
                return False
            conn.execute("DELETE FROM devices WHERE id=?", (device_id,))
            self._audit_conn(conn, actor, "device.delete", device_id, "success",
                             {"revision": row["revision"]})
            return True

    def list_points(self, device_id=None):
        with self.lock, self.connect() as conn:
            if device_id:
                cursor = conn.execute("SELECT * FROM points WHERE device_id=? ORDER BY id",
                                      (device_id,))
            else:
                cursor = conn.execute("SELECT * FROM points ORDER BY id")
            return self._rows(cursor)

    def get_point(self, point_id):
        with self.lock, self.connect() as conn:
            values = self._rows(conn.execute(
                "SELECT * FROM points WHERE id=?", (point_id,)))
            return values[0] if values else None

    def put_point(self, value, actor):
        with self.lock, self.connect() as conn:
            if conn.execute("SELECT 1 FROM devices WHERE id=?",
                            (value["device_id"],)).fetchone() is None:
                raise ValueError("point device does not exist")
            conn.execute("""
                INSERT INTO points(id,device_id,name,data_type,unit,access,address,
                    scale,enabled)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET device_id=excluded.device_id,
                    name=excluded.name,data_type=excluded.data_type,
                    unit=excluded.unit,access=excluded.access,
                    address=excluded.address,scale=excluded.scale,
                    enabled=excluded.enabled
            """, (value["id"], value["device_id"], value["name"],
                  value["data_type"], value.get("unit", ""), value["access"],
                  value["address"], value.get("scale", 1.0),
                  int(value.get("enabled", True))))
            self._audit_conn(conn, actor, "point.put", value["id"], "success",
                             {"device_id": value["device_id"]})

    def delete_point(self, point_id, actor):
        with self.lock, self.connect() as conn:
            row = conn.execute("SELECT device_id FROM points WHERE id=?",
                               (point_id,)).fetchone()
            if row is None:
                return False
            conn.execute("DELETE FROM points WHERE id=?", (point_id,))
            self._audit_conn(conn, actor, "point.delete", point_id, "success",
                             {"device_id": row["device_id"]})
            return True

    def audit(self, limit=200):
        with self.lock, self.connect() as conn:
            return self._rows(conn.execute(
                "SELECT * FROM audit ORDER BY ts DESC LIMIT ?", (limit,)))

    @staticmethod
    def _audit_conn(conn, actor, action, target, result, detail):
        conn.execute("INSERT INTO audit(ts,actor,action,target,result,detail_json) "
                     "VALUES(?,?,?,?,?,?)", (int(time.time()), actor, action, target,
                     result, json.dumps(detail, sort_keys=True)))
