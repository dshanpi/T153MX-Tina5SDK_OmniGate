#!/usr/bin/env python3
"""Loopback-only telemetry and control API for the OmniGate Qt HMI."""
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

from flask import Blueprint, jsonify, request
from omnigate_core.platform import load_manifest


DB_PATH = Path(os.environ.get("OMNIGATE_HMI_DB", "/var/lib/omnigate-hmi/hmi.db"))
SETTINGS_PATH = Path(os.environ.get("OMNIGATE_HMI_SETTINGS", "/etc/omnigate-hmi/config.json"))
MODBUS_CONFIG = Path(os.environ.get("OMNIGATE_MODBUS_CONFIG", "/etc/thingsboard-gateway/config/modbus.json"))
OMNIGATE_CONFIG = Path(os.environ.get("OMNIGATE_CONFIG", "/etc/omnigate-web/config.json"))
MAX_OUTPUT = 32768
DB_LOCK = threading.RLock()
CPU_LOCK = threading.Lock()
CPU_PREVIOUS = None
LAST_TELEMETRY_BUCKET = None
PLATFORM = load_manifest()

DEFAULT_SETTINGS = {
    "demo_mode": False,
    "brightness": 220,
    "refresh_ms": 1000,
    "page_cycle_seconds": 0,
}

SERVICES = {
    "thingsboard": "/etc/init.d/S70thingsboard-gateway",
    "bluetooth": "/usr/bin/bt-speaker",
    "ntp": "/etc/init.d/S49ntp",
    "web": "/etc/init.d/S71omnigate-web",
}


def _run(args, timeout=15, check=False):
    try:
        proc = subprocess.run(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        raise ValueError("操作超时")
    except OSError as exc:
        if check:
            raise ValueError("命令不可用: %s" % exc)
        return {"returncode": 127, "output": str(exc)[-MAX_OUTPUT:]}
    output = (proc.stdout or "")[-MAX_OUTPUT:]
    if check and proc.returncode:
        raise ValueError(output.strip() or "命令执行失败")
    return {"returncode": proc.returncode, "output": output}


def _read(path, default=""):
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return default


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    os.chmod(str(temp), 0o600)
    os.replace(str(temp), str(path))


def _settings():
    value = dict(DEFAULT_SETTINGS)
    value.update(_read_json(SETTINGS_PATH, {}))
    return value


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_db():
    with DB_LOCK, _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS alarms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                severity TEXT NOT NULL,
                source TEXT NOT NULL,
                code TEXT NOT NULL,
                message TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'active',
                acknowledged_at INTEGER,
                acknowledged_by TEXT
            );
            CREATE INDEX IF NOT EXISTS alarms_ts ON alarms(ts DESC);
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                request_json TEXT NOT NULL,
                result TEXT NOT NULL,
                detail TEXT
            );
            CREATE INDEX IF NOT EXISTS audit_ts ON audit(ts DESC);
            CREATE TABLE IF NOT EXISTS telemetry (
                bucket INTEGER PRIMARY KEY,
                cpu REAL, memory REAL, temperature REAL, storage REAL
            );
        """)
        if _settings()["demo_mode"]:
            _ensure_demo_alarms(conn)


def _ensure_demo_alarms(conn):
    """Create labelled sample alarms only after demo mode is explicitly enabled."""
    count = conn.execute(
        "SELECT COUNT(*) FROM alarms WHERE source='demo'"
    ).fetchone()[0]
    if count:
        return
    now = int(time.time())
    conn.executemany(
        "INSERT INTO alarms(ts,severity,source,code,message,state) "
        "VALUES(?,?,?,?,?,?)",
        [
            (now - 120, "warning", "demo", "TEMP_HIGH",
             "设备07温度偏高", "active"),
            (now - 1680, "info", "demo", "CAN_RECOVERED",
             "CAN1错误帧已恢复", "cleared"),
            (now - 6420, "info", "demo", "CELL_RECONNECT",
             "4G-A网络已重连", "cleared"),
        ],
    )


def _cpu_percent():
    global CPU_PREVIOUS
    fields = [int(x) for x in _read("/proc/stat").splitlines()[0].split()[1:]]
    if len(fields) < 4:
        return 0.0
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    total = sum(fields)
    with CPU_LOCK:
        old = CPU_PREVIOUS
        CPU_PREVIOUS = (idle, total)
    if not old or total <= old[1]:
        load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
        return min(100.0, load * 25.0)
    return round(100.0 * (1.0 - (idle - old[0]) / float(total - old[1])), 1)


def _memory_percent():
    values = {}
    for line in _read("/proc/meminfo").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            try:
                values[key] = int(value.split()[0])
            except (IndexError, ValueError):
                pass
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    return round(100.0 * (total - available) / total, 1) if total else 0.0


def _temperature():
    for path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        try:
            value = float(_read(path))
            value = value / 1000.0 if value > 1000 else value
            if -20 < value < 150:
                return round(value, 1)
        except ValueError:
            pass
    return None


def _interface(name):
    base = Path("/sys/class/net") / name
    if not base.exists():
        return {"name": name, "online": False, "state": "未发现", "address": ""}
    state = _read(base / "operstate", "unknown")
    address = _run(["ip", "-4", "-o", "addr", "show", "dev", name], timeout=3)["output"]
    match = re.search(r"\binet\s+([^\s]+)", address)
    return {
        "name": name,
        "online": state == "up",
        "state": state,
        "address": match.group(1) if match else "",
    }


def _can(name):
    info = _run(["ip", "-details", "-statistics", "link", "show", name], timeout=4)
    text = info["output"]
    state_match = re.search(r"can state ([A-Z-]+)", text)
    bitrate_match = re.search(r"bitrate (\d+)", text)
    return {
        "name": name.upper(),
        "online": "state UP" in text,
        "state": state_match.group(1) if state_match else ("UP" if "state UP" in text else "DOWN"),
        "bitrate": int(bitrate_match.group(1)) if bitrate_match else 0,
        "source": "real",
    }


def _service(name):
    result = _run([SERVICES[name], "status"], timeout=4)
    return {"name": name, "running": result["returncode"] == 0,
            "detail": result["output"].strip()}


def _channel_devices(kind):
    return [item["device"] for item in PLATFORM["channels"].values()
            if item["kind"] == kind]


def _role_device(role):
    for item in PLATFORM["channels"].values():
        if item.get("role") == role:
            return item["device"]
    raise ValueError("板型未定义接口角色: " + role)


def _active_slot():
    cmdline = _read("/proc/cmdline")
    return "rootfsB" if cmdline.startswith("rootfsB ") else "rootfsA"


def _demo_sensors(now):
    phase = now / 8.0
    return [
        {"id": "temperature", "name": "温度", "value": round(55 + 5 * math.sin(phase), 1),
         "unit": "°C", "source": "demo", "state": "正常"},
        {"id": "pressure", "name": "压力", "value": round(38 + 3 * math.sin(phase * .7), 1),
         "unit": "kPa", "source": "demo", "state": "正常"},
        {"id": "flow", "name": "流量", "value": round(20 + 4 * math.sin(phase * 1.3), 1),
         "unit": "L/min", "source": "demo", "state": "正常"},
    ]


def _store_telemetry(system):
    global LAST_TELEMETRY_BUCKET
    bucket = int(time.time()) // 60 * 60
    if LAST_TELEMETRY_BUCKET == bucket:
        return
    LAST_TELEMETRY_BUCKET = bucket
    with DB_LOCK, _db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO telemetry(bucket,cpu,memory,temperature,storage) VALUES(?,?,?,?,?)",
            (bucket, system["cpu"], system["memory"], system["temperature"], system["storage"]),
        )
        conn.execute("DELETE FROM telemetry WHERE bucket < ?", (bucket - 30 * 86400,))


def _alarm_summary(include_demo=False):
    source_filter = "" if include_demo else " AND source!='demo'"
    with DB_LOCK, _db() as conn:
        active = conn.execute(
            "SELECT COUNT(*) FROM alarms WHERE state='active'" + source_filter
        ).fetchone()[0]
        since = int(time.time()) - 86400
        today = conn.execute(
            "SELECT COUNT(*) FROM alarms WHERE ts>=?" + source_filter, (since,)
        ).fetchone()[0]
        recent = [dict(row) for row in conn.execute(
            "SELECT * FROM alarms WHERE ts>=?" + source_filter +
            " ORDER BY ts DESC LIMIT 3", (since,)
        )]
    return {"active": active, "today": today, "recent": recent}


def _snapshot():
    now = time.time()
    usage = shutil.disk_usage("/")
    temp = _temperature()
    system = {
        "cpu": _cpu_percent(),
        "memory": _memory_percent(),
        "temperature": temp if temp is not None else 0.0,
        "temperature_source": "real" if temp is not None else "unavailable",
        "storage": round(100.0 * usage.used / usage.total, 1),
        "uptime_seconds": int(float(_read("/proc/uptime", "0").split()[0])),
        "hostname": _read("/etc/hostname", "OmniGate"),
        "kernel": _read("/proc/sys/kernel/osrelease"),
        "active_slot": _active_slot(),
    }
    _store_telemetry(system)
    settings = _settings()
    buses = [_can(name) for name in _channel_devices("can")]
    demo_mode = settings["demo_mode"]
    buses.extend([
        {"name": "RS485", "online": False,
         "state": "演示 6台" if demo_mode else "未检测到从站",
         "load": 26 if demo_mode else 0,
         "source": "demo" if demo_mode else "unavailable"},
        {"name": "EtherCAT", "online": False,
         "state": "演示 OP 4站" if demo_mode else "未检测到从站",
         "load": 41 if demo_mode else 0,
         "source": "demo" if demo_mode else "unavailable"},
    ])
    network_kinds = {"ethernet", "wifi"}
    network_names = [item["device"] for item in PLATFORM["channels"].values()
                     if item["kind"] in network_kinds]
    network_names.extend([profile.get("interface") for profile in
        _read_json(OMNIGATE_CONFIG, {}).get("ec20", {}).get("profiles", {}).values()
        if profile.get("interface")])
    networks = [_interface(name) for name in dict.fromkeys(network_names)]
    for item in networks:
        item["source"] = "real"
    if settings["demo_mode"]:
        for item in networks:
            if item["name"] in ("wwan0", "wwan1") and not item["online"]:
                item.update({"state": "在线" if item["name"] == "wwan0" else "备用",
                             "source": "demo"})
    alarms = _alarm_summary(include_demo=demo_mode)
    return {
        "ok": True,
        "timestamp": int(now),
        "system": system,
        "summary": {
            "status": "正常" if alarms["active"] == 0 else "有告警",
            "online_devices": sum(1 for x in buses + networks if x.get("online")) +
                              (12 if settings["demo_mode"] else 0),
            "today_alarms": alarms["today"],
        },
        "buses": buses,
        "networks": networks,
        "sensors": _demo_sensors(now) if settings["demo_mode"] else [],
        "alarms": alarms,
        "services": {name: _service(name) for name in ("thingsboard", "ntp")},
        "settings": settings,
    }


def _audit(action, params, result, detail=""):
    target = str(params.get("interface") or params.get("service") or params.get("profile") or "")
    with DB_LOCK, _db() as conn:
        conn.execute(
            "INSERT INTO audit(ts,action,target,request_json,result,detail) VALUES(?,?,?,?,?,?)",
            (int(time.time()), action, target,
             json.dumps(params, ensure_ascii=False, sort_keys=True), result, detail[-4000:]),
        )


def _integer(value, name, minimum, maximum):
    try:
        value = int(str(value), 0)
    except (TypeError, ValueError):
        raise ValueError(name + "必须是整数")
    if value < minimum or value > maximum:
        raise ValueError("%s范围必须是%d..%d" % (name, minimum, maximum))
    return value


def _can_connect(interface):
    if interface not in _channel_devices("can"):
        raise ValueError("CAN接口非法")
    import canopen
    network = canopen.Network()
    try:
        network.connect(channel=interface, interface="socketcan")
    except TypeError:
        network.connect(channel=interface, bustype="socketcan")
    return network


def _execute_action(action, p):
    if action == "brightness":
        value = _integer(p.get("value"), "亮度", 10, 255)
        Path("/sys/class/backlight/backlight0/brightness").write_text(str(value))
        cfg = _settings(); cfg["brightness"] = value; _atomic_json(SETTINGS_PATH, cfg)
        return {"brightness": value}
    if action == "service":
        name, operation = p.get("service"), p.get("operation")
        if name not in SERVICES or operation not in ("start", "stop", "restart"):
            raise ValueError("服务操作非法")
        return _run([SERVICES[name], operation], timeout=25)
    if action == "can_apply":
        interface = p.get("interface")
        if interface not in _channel_devices("can"):
            raise ValueError("CAN接口非法")
        bitrate = _integer(p.get("bitrate"), "波特率", 10000, 1000000)
        dbitrate = _integer(p.get("data_bitrate", 2000000), "数据波特率", bitrate, 8000000)
        restart = _integer(p.get("restart_ms", 100), "恢复时间", 0, 60000)
        _run(["ip", "link", "set", interface, "down"], timeout=5)
        args = ["ip", "link", "set", interface, "type", "can", "bitrate", str(bitrate),
                "restart-ms", str(restart)]
        if p.get("fd"):
            args += ["dbitrate", str(dbitrate), "fd", "on"]
        _run(args, timeout=5, check=True)
        _run(["ip", "link", "set", interface, "up"], timeout=5, check=True)
        return {"interface": interface, "bitrate": bitrate, "fd": bool(p.get("fd"))}
    if action == "rs485_config":
        cfg = _read_json(MODBUS_CONFIG, {})
        slaves = cfg.setdefault("master", {}).setdefault("slaves", [])
        if not slaves:
            raise ValueError("Modbus模板没有从站")
        port = str(p.get("port", _role_device("modbus-rtu")))
        if not re.fullmatch(r"/dev/tty(?:AS|USB)[0-9]+", port):
            raise ValueError("串口路径非法")
        slaves[0].update({"port": port, "method": "rtu",
                          "baudrate": _integer(p.get("baudrate", 9600), "波特率", 300, 4000000),
                          "unitId": _integer(p.get("unit_id", 1), "站号", 1, 247),
                          "pollPeriod": _integer(p.get("poll_ms", 1000), "轮询周期", 50, 3600000)})
        _atomic_json(MODBUS_CONFIG, cfg)
        return slaves[0]
    if action in ("canopen_nmt", "canopen_sdo_write", "canopen_rpdo"):
        can_devices = _channel_devices("can")
        interface = p.get("interface", can_devices[0] if can_devices else "")
        if interface not in can_devices:
            raise ValueError("CAN接口非法")
        node_id = _integer(p.get("node_id"), "节点", 0 if action == "canopen_nmt" else 1, 127)
        network = _can_connect(interface)
        try:
            if action == "canopen_nmt":
                state = str(p.get("state", "OPERATIONAL")).upper()
                if state not in ("OPERATIONAL", "PRE-OPERATIONAL", "STOPPED", "RESET", "RESET COMMUNICATION"):
                    raise ValueError("NMT状态非法")
                if node_id == 0: network.nmt.state = state
                else: network.add_node(node_id).nmt.state = state
                return {"node_id": node_id, "state": state}
            node = network.add_node(node_id)
            index = _integer(p.get("index"), "对象索引", 0, 0xffff)
            subindex = _integer(p.get("subindex", 0), "子索引", 0, 255)
            if action == "canopen_sdo_write":
                value = _integer(p.get("value"), "写入值", -2147483648, 4294967295)
                size = _integer(p.get("size", 4), "字节数", 1, 4)
                node.sdo[index][subindex].raw = value
                return {"node_id": node_id, "index": index, "subindex": subindex,
                        "value": value, "size": size}
            values = p.get("values")
            if not isinstance(values, dict) or not values:
                raise ValueError("RPDO变量不能为空")
            number = _integer(p.get("pdo", 1), "PDO编号", 1, 4)
            node.rpdo.read(); node.rpdo[number].enabled = True
            for key, value in values.items(): node.rpdo[number][str(key)].raw = int(value)
            node.rpdo[number].transmit()
            return {"node_id": node_id, "pdo": number, "values": values}
        finally:
            network.disconnect()
    if action in ("ethercat_sdo_write", "ethercat_cycle"):
        ethercat_interface = _role_device("ethercat")
        if action == "ethercat_cycle":
            count = _integer(p.get("count", 1000), "周期数", 1, 10000)
            period = _integer(p.get("period_us", 1000), "周期", 100, 1000000)
            return _run(["/usr/bin/omnigate-ethercat", ethercat_interface,
                         "cycle", str(count), str(period)],
                        timeout=20, check=True)
        slave = _integer(p.get("slave"), "从站", 1, 65535)
        index = _integer(p.get("index"), "对象索引", 0, 0xffff)
        subindex = _integer(p.get("subindex", 0), "子索引", 0, 255)
        value = str(p.get("value", "")).strip()
        if not re.fullmatch(r"(?:[0-9A-Fa-f]{2})(?:\s+[0-9A-Fa-f]{2}){0,31}", value):
            raise ValueError("EtherCAT值必须是1到32字节十六进制")
        return _run(["/usr/bin/omnigate-ethercat", ethercat_interface,
                     "sdo-write", str(slave),
                     hex(index), str(subindex), value], timeout=20, check=True)
    if action == "ec20":
        profile, operation = p.get("profile"), p.get("operation")
        if profile not in ("ec20a", "ec20b") or operation not in ("connect", "disconnect"):
            raise ValueError("4G操作非法")
        cfg = _read_json(OMNIGATE_CONFIG, {}).get("ec20", {}).get("profiles", {}).get(profile, {})
        device, interface = cfg.get("device"), cfg.get("interface")
        if not device or not interface:
            raise ValueError("4G配置不存在")
        if operation == "disconnect":
            runtime = _read_json("/var/run/omnigate-ec20-%s.json" % profile, {})
            result = _run([
                "qmicli", "-d", device, "--device-open-proxy",
                "--wds-stop-network=" + str(runtime.get("handle", "0")),
            ], timeout=20)
            _run(["ip", "link", "set", interface, "down"], timeout=5)
            return {"profile": profile, "state": "disconnected", "qmi": result["output"]}
        if not Path(device).exists():
            raise ValueError("4G设备未连接")
        if not (Path("/sys/class/net") / interface).exists():
            raise ValueError("4G网络接口未出现")
        raw_ip = Path("/sys/class/net") / interface / "qmi" / "raw_ip"
        _run(["ip", "link", "set", interface, "down"], timeout=5)
        if raw_ip.exists():
            raw_ip.write_text("Y", encoding="ascii")
        _run(["ip", "link", "set", interface, "up"], timeout=5, check=True)
        settings = ["ip-type=4"]
        for key in ("apn", "username", "password", "auth"):
            value = cfg.get(key)
            if value and value != "none":
                settings.append("%s='%s'" % (key, value))
        qmi = _run([
            "qmicli", "-d", device, "--device-open-proxy",
            "--wds-start-network=" + ",".join(settings), "--client-no-release-cid",
        ], timeout=30, check=True)
        match = re.search(r"Packet data handle: '([0-9]+)'", qmi["output"])
        _atomic_json("/var/run/omnigate-ec20-%s.json" % profile, {
            "device": device, "interface": interface,
            "handle": match.group(1) if match else "",
        })
        dhcp = _run(["udhcpc", "-i", interface, "-q", "-n", "-t", "5"], timeout=25)
        if dhcp["returncode"]:
            raise RuntimeError(dhcp["output"].strip() or "4G DHCP失败")
        return {"profile": profile, "state": "connected", "qmi": qmi["output"],
                "dhcp": dhcp["output"]}
    if action == "system_reboot":
        threading.Timer(1.0, lambda: subprocess.Popen(["reboot"])).start()
        return {"scheduled": True}
    raise ValueError("不支持的HMI动作")


def create_blueprint():
    _init_db()
    bp = Blueprint("hmi_api", __name__)

    @bp.get("/api/hmi/v1/snapshot")
    def snapshot():
        return jsonify(_snapshot())

    @bp.get("/api/hmi/v1/history")
    def history():
        metric = request.args.get("metric", "temperature")
        if metric not in ("cpu", "memory", "temperature", "storage"):
            raise ValueError("历史指标非法")
        hours = _integer(request.args.get("hours", 24), "小时", 1, 720)
        with DB_LOCK, _db() as conn:
            rows = [dict(row) for row in conn.execute(
                "SELECT bucket,%s AS value FROM telemetry WHERE bucket>=? ORDER BY bucket" % metric,
                (int(time.time()) - hours * 3600,))]
        return jsonify(ok=True, metric=metric, points=rows)

    @bp.get("/api/hmi/v1/alarms")
    def alarms():
        limit = _integer(request.args.get("limit", 100), "条数", 1, 500)
        include_demo = _settings()["demo_mode"]
        source_filter = "" if include_demo else " WHERE source!='demo'"
        with DB_LOCK, _db() as conn:
            rows = [dict(row) for row in conn.execute(
                "SELECT * FROM alarms" + source_filter +
                " ORDER BY ts DESC LIMIT ?", (limit,))]
        return jsonify(ok=True, alarms=rows)

    @bp.post("/api/hmi/v1/alarms/<int:alarm_id>/ack")
    def acknowledge(alarm_id):
        with DB_LOCK, _db() as conn:
            changed = conn.execute(
                "UPDATE alarms SET state='acknowledged',acknowledged_at=?,acknowledged_by='local-hmi' "
                "WHERE id=?", (int(time.time()), alarm_id)).rowcount
        return jsonify(ok=bool(changed), id=alarm_id)

    @bp.route("/api/hmi/v1/settings", methods=["GET", "PUT"])
    def settings():
        if request.method == "GET":
            return jsonify(ok=True, settings=_settings())
        body = request.get_json(force=True) or {}
        cfg = _settings()
        if "demo_mode" in body: cfg["demo_mode"] = bool(body["demo_mode"])
        if "brightness" in body: cfg["brightness"] = _integer(body["brightness"], "亮度", 10, 255)
        if "refresh_ms" in body: cfg["refresh_ms"] = _integer(body["refresh_ms"], "刷新周期", 500, 10000)
        if "page_cycle_seconds" in body:
            cfg["page_cycle_seconds"] = _integer(body["page_cycle_seconds"], "轮播周期", 0, 300)
        _atomic_json(SETTINGS_PATH, cfg)
        if cfg["demo_mode"]:
            with DB_LOCK, _db() as conn:
                _ensure_demo_alarms(conn)
        return jsonify(ok=True, settings=cfg)

    @bp.post("/api/hmi/v1/actions")
    def actions():
        body = request.get_json(force=True) or {}
        action = str(body.get("action", ""))
        params = body.get("params") or {}
        if not isinstance(params, dict):
            raise ValueError("动作参数非法")
        if not body.get("confirmed"):
            raise ValueError("操作未确认")
        try:
            result = _execute_action(action, params)
            _audit(action, params, "success", json.dumps(result, ensure_ascii=False))
            return jsonify(ok=True, action=action, result=result)
        except Exception as exc:
            _audit(action, params, "failed", str(exc))
            raise

    @bp.get("/api/hmi/v1/audit")
    def audit():
        with DB_LOCK, _db() as conn:
            rows = [dict(row) for row in conn.execute(
                "SELECT * FROM audit ORDER BY ts DESC LIMIT 200")]
        return jsonify(ok=True, audit=rows)

    return bp
