#!/usr/bin/env python3
import glob
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

sys.path.insert(0, os.environ.get("OMNIGATE_CORE_PATH", "/usr/lib/omnigate-core"))
from omnigate_core.platform import load_manifest

APP_DIR = Path(os.environ.get("OMNIGATE_WEB_ASSETS", "/usr/share/omnigate-web"))
CONFIG_FILE = Path(os.environ.get(
    "OMNIGATE_WEB_CONFIG", "/etc/omnigate-web/config.json"))
TB_CONFIG = Path(os.environ.get(
    "OMNIGATE_TB_CONFIG", "/etc/thingsboard-gateway/config/tb_gateway.json"))
MODBUS_CONFIG = Path(os.environ.get(
    "OMNIGATE_MODBUS_CONFIG", "/etc/thingsboard-gateway/config/modbus.json"))
EDS_DIR = Path(os.environ.get("OMNIGATE_EDS_DIR", "/var/lib/omnigate/eds"))
SECRET_FILE = Path(os.environ.get(
    "OMNIGATE_WEB_SECRET", "/etc/omnigate-web/secret.key"))
LOG_FILE = Path(os.environ.get("OMNIGATE_WEB_LOG", "/var/log/omnigate-web.log"))
MAX_OUTPUT = 32768
LOCK = threading.RLock()
LOGIN_LOCK = threading.Lock()
LOGIN_FAILURES = {}
PLATFORM = load_manifest()

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = Flask(__name__, static_folder=None)


def load_or_create_session_secret():
    """Return a persistent per-device Flask signing key without logging it."""
    try:
        value = SECRET_FILE.read_text(encoding="ascii").strip()
        if len(value) >= 64:
            return value
    except OSError:
        pass

    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_hex(32)
    fd, temporary = tempfile.mkstemp(
        prefix=SECRET_FILE.name + ".", dir=str(SECRET_FILE.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(value + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, SECRET_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return value


app.secret_key = load_or_create_session_secret()
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("OMNIGATE_HTTPS", "0") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = 1800


def atomic_json(path, data, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return {} if default is None else default


def load_config():
    return load_json(CONFIG_FILE, {})


def save_config(data):
    atomic_json(CONFIG_FILE, data)


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 120000
    ).hex()


def command(args, timeout=15, check=False):
    try:
        completed = subprocess.run(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=timeout, check=False
        )
        output = completed.stdout[-MAX_OUTPUT:]
        if check and completed.returncode:
            raise RuntimeError(output.strip() or "command failed")
        return {"returncode": completed.returncode, "output": output}
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        raise RuntimeError("command timed out: " + output[-1000:])


def parse_int(value, name, minimum, maximum):
    try:
        number = int(str(value), 0)
    except (TypeError, ValueError):
        raise ValueError(f"{name} 必须是整数")
    if not minimum <= number <= maximum:
        raise ValueError(f"{name} 范围必须是 {minimum}..{maximum}")
    return number


def valid_interface(value, can_only=False):
    kinds = {"can"} if can_only else {"can", "ethernet", "cellular", "wifi"}
    allowed = {item["device"] for item in PLATFORM["channels"].values()
               if item["kind"] in kinds and not item["device"].startswith("/dev/")}
    if not isinstance(value, str) or value not in allowed:
        raise ValueError("非法网络接口")
    return value


def devices_by_kind(kind):
    return [item["device"] for item in PLATFORM["channels"].values()
            if item["kind"] == kind]


def device_by_role(role):
    for item in PLATFORM["channels"].values():
        if item.get("role") == role:
            return item["device"]
    raise RuntimeError("板型未定义接口角色: " + role)


@app.before_request
def require_login():
    if request.path.startswith("/api/hmi/v1/"):
        if request.remote_addr in ("127.0.0.1", "::1"):
            return None
        return jsonify(error="HMI API仅允许本机访问"), 403
    public = {"/", "/api/login", "/api/health"}
    if request.path.startswith("/assets/") or request.path in public:
        return None
    if not session.get("authenticated"):
        return jsonify(error="请先登录"), 401
    if request.method not in ("GET", "HEAD", "OPTIONS") and session.get("role") == "viewer":
        return jsonify(error="当前角色只有只读权限"), 403
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        expected = session.get("csrf")
        if not expected or not hmac.compare_digest(
            request.headers.get("X-CSRF-Token", ""), expected
        ):
            return jsonify(error="CSRF 校验失败"), 403
    return None


@app.after_request
def secure_response(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(Exception)
def handle_error(exc):
    if isinstance(exc, HTTPException):
        code = exc.code or 500
        message = exc.description
        app.logger.warning("request rejected: %s", exc)
    elif isinstance(exc, (ValueError, RuntimeError)):
        code = 400
        message = str(exc)
        app.logger.warning("request rejected: %s", exc)
    else:
        code = 500
        message = "内部服务错误"
        app.logger.exception("request failed")
    return jsonify(error=message), code


@app.get("/")
def index():
    return send_from_directory(APP_DIR, "index.html")


@app.get("/assets/<path:name>")
def assets(name):
    return send_from_directory(APP_DIR / "assets", name)


@app.get("/api/health")
def health():
    return jsonify(ok=True, service="omnigate-web")


@app.post("/api/login")
def login():
    body = request.get_json(force=True)
    client = request.remote_addr or "unknown"
    now = time.monotonic()
    with LOGIN_LOCK:
        attempts = [stamp for stamp in LOGIN_FAILURES.get(client, []) if now - stamp < 300]
        LOGIN_FAILURES[client] = attempts
    if len(attempts) >= 8:
        return jsonify(error="登录失败次数过多，请稍后再试"), 429
    cfg = load_config().get("auth", {})
    supplied = password_hash(str(body.get("password", "")), cfg.get("salt", ""))
    if body.get("username") != cfg.get("username") or not hmac.compare_digest(
        supplied, cfg.get("password_hash", "")
    ):
        with LOGIN_LOCK:
            LOGIN_FAILURES.setdefault(client, []).append(now)
        time.sleep(0.3)
        return jsonify(error="用户名或密码错误"), 401
    session.clear()
    session.permanent = True
    session["authenticated"] = True
    session["username"] = cfg.get("username")
    session["role"] = cfg.get("role", "administrator")
    session["csrf"] = secrets.token_hex(24)
    with LOGIN_LOCK:
        LOGIN_FAILURES.pop(client, None)
    return jsonify(
        ok=True, csrf=session["csrf"], must_change=bool(cfg.get("must_change"))
    )


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/password")
def change_password():
    body = request.get_json(force=True)
    new_password = str(body.get("password", ""))
    if len(new_password) < 12:
        raise ValueError("新密码至少 12 位")
    cfg = load_config()
    salt = secrets.token_hex(16)
    cfg["auth"]["salt"] = salt
    cfg["auth"]["password_hash"] = password_hash(new_password, salt)
    cfg["auth"]["must_change"] = False
    save_config(cfg)
    return jsonify(ok=True)


def service_state(script):
    result = command([script, "status"], timeout=5)
    return {
        "running": result["returncode"] == 0,
        "detail": result["output"].strip()
    }


def default_enabled(path):
    try:
        content = Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return re.search(r"(?m)^\s*ENABLED\s*=\s*1\s*(?:#.*)?$", content) is not None


@app.get("/api/status")
def status():
    cfg = load_config()
    return jsonify(
        hostname=command(["hostname"], timeout=2)["output"].strip(),
        uptime=command(["uptime"], timeout=2)["output"].strip(),
        time=command(["date", "-Iseconds"], timeout=2)["output"].strip(),
        addresses=command(["ip", "-brief", "address"], timeout=4)["output"],
        services={
            "thingsboard": service_state("/etc/init.d/S70thingsboard-gateway"),
            "web": service_state("/etc/init.d/S71omnigate-web"),
        },
        auth={"must_change": cfg.get("auth", {}).get("must_change", True)}
    )


@app.get("/api/config/thingsboard")
def get_thingsboard():
    data = load_json(TB_CONFIG, {})
    tb = data.get("thingsboard", {})
    security = tb.get("security", {})
    return jsonify(
        host=tb.get("host", ""),
        port=tb.get("port", 1883),
        security_type=security.get("type", "accessToken"),
        token_configured=bool(
            security.get("accessToken")
            and security.get("accessToken") != "PUT_GATEWAY_ACCESS_TOKEN_HERE"
        ),
        enabled=default_enabled("/etc/default/thingsboard-gateway")
    )


@app.put("/api/config/thingsboard")
def put_thingsboard():
    body = request.get_json(force=True)
    host = str(body.get("host", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,253}", host):
        raise ValueError("ThingsBoard 主机名不合法")
    port = parse_int(body.get("port", 1883), "端口", 1, 65535)
    data = load_json(TB_CONFIG, {})
    tb = data.setdefault("thingsboard", {})
    tb["host"] = host
    tb["port"] = port
    security = tb.setdefault("security", {"type": "accessToken"})
    token = str(body.get("token", "")).strip()
    if token:
        security["accessToken"] = token
    atomic_json(TB_CONFIG, data, 0o600)
    enabled = bool(body.get("enabled"))
    Path("/etc/default/thingsboard-gateway").write_text(
        "# Managed by OmniGate Web UI\nENABLED=%d\n" % enabled,
        encoding="utf-8"
    )
    if body.get("restart"):
        command(["/etc/init.d/S70thingsboard-gateway", "restart"], timeout=15)
    return jsonify(ok=True)


@app.get("/api/config/rs485")
def get_rs485():
    data = load_json(MODBUS_CONFIG, {})
    slaves = data.get("master", {}).get("slaves", [])
    return jsonify(slaves[0] if slaves else {})


@app.put("/api/config/rs485")
def put_rs485():
    body = request.get_json(force=True)
    data = load_json(MODBUS_CONFIG, {})
    slaves = data.setdefault("master", {}).setdefault("slaves", [])
    if not slaves:
        raise ValueError("Modbus 模板中没有从站")
    port = str(body.get("port", device_by_role("modbus-rtu")))
    if not re.fullmatch(r"/dev/tty(?:AS|USB)[0-9]+", port):
        raise ValueError("串口路径不合法")
    slave = slaves[0]
    slave.update({
        "port": port,
        "method": "rtu",
        "baudrate": parse_int(body.get("baudrate"), "波特率", 300, 4000000),
        "bytesize": parse_int(body.get("bytesize", 8), "数据位", 5, 8),
        "stopbits": parse_int(body.get("stopbits", 1), "停止位", 1, 2),
        "parity": str(body.get("parity", "N")).upper(),
        "unitId": parse_int(body.get("unitId", 1), "站号", 1, 247),
        "pollPeriod": parse_int(body.get("pollPeriod", 1000), "轮询周期", 50, 3600000)
    })
    if slave["parity"] not in ("N", "E", "O"):
        raise ValueError("校验位必须是 N/E/O")
    atomic_json(MODBUS_CONFIG, data)
    return jsonify(ok=True, config=slave)


def configure_can(iface, settings):
    iface = valid_interface(iface, True)
    bitrate = parse_int(settings.get("bitrate"), "仲裁波特率", 10000, 1000000)
    restart_ms = parse_int(settings.get("restart_ms", 100), "自动恢复", 0, 60000)
    command(["ip", "link", "set", iface, "down"], timeout=5)
    args = [
        "ip", "link", "set", iface, "type", "can",
        "bitrate", str(bitrate), "restart-ms", str(restart_ms)
    ]
    if settings.get("fd"):
        data_bitrate = parse_int(
            settings.get("data_bitrate"), "数据波特率", bitrate, 8000000
        )
        args += ["dbitrate", str(data_bitrate), "fd", "on"]
    command(args, timeout=5, check=True)
    command(["ip", "link", "set", iface, "up"], timeout=5, check=True)
    return command(["ip", "-details", "link", "show", iface], timeout=5)["output"]


@app.get("/api/config/can")
def get_can():
    cfg = load_config()
    return jsonify(
        config=cfg.get("can", {}),
        state={
            name: command(["ip", "-details", "link", "show", name], timeout=4)["output"]
            for name in devices_by_kind("can")
        }
    )


@app.put("/api/config/can/<iface>")
def put_can(iface):
    body = request.get_json(force=True)
    iface = valid_interface(iface, True)
    cfg = load_config()
    settings = cfg.setdefault("can", {}).setdefault(iface, {})
    settings.update({
        "bitrate": parse_int(body.get("bitrate"), "仲裁波特率", 10000, 1000000),
        "data_bitrate": parse_int(
            body.get("data_bitrate", 2000000), "数据波特率", 10000, 8000000
        ),
        "fd": bool(body.get("fd")),
        "restart_ms": parse_int(body.get("restart_ms", 100), "自动恢复", 0, 60000)
    })
    detail = configure_can(iface, settings)
    save_config(cfg)
    return jsonify(ok=True, detail=detail)


def canopen_settings(body):
    cfg = load_config()
    defaults = cfg.setdefault("canopen", {})
    iface = valid_interface(body.get("interface", defaults.get("interface", "can0")), True)
    bitrate = parse_int(body.get("bitrate", defaults.get("bitrate", 500000)), "波特率", 10000, 1000000)
    defaults.update({"interface": iface, "bitrate": bitrate})
    save_config(cfg)
    configure_can(iface, {"bitrate": bitrate, "fd": False, "restart_ms": 100})
    return cfg, iface


def connect_canopen(iface):
    import canopen
    network = canopen.Network()
    try:
        network.connect(channel=iface, interface="socketcan")
    except TypeError:
        try:
            network.disconnect()
        except Exception:
            pass
        network = canopen.Network()
        network.connect(channel=iface, bustype="socketcan")
    return network


def node_eds(cfg, node_id):
    item = cfg.get("canopen", {}).get("nodes", {}).get(str(node_id), {})
    path = item.get("eds")
    if path and Path(path).is_file() and Path(path).parent == EDS_DIR:
        return path
    return None


@app.get("/api/canopen/eds")
def list_eds():
    cfg = load_config()
    return jsonify(
        files=[p.name for p in sorted(EDS_DIR.glob("*")) if p.suffix.lower() in (".eds", ".dcf")],
        nodes=cfg.get("canopen", {}).get("nodes", {})
    )


@app.post("/api/canopen/eds")
def upload_eds():
    import canopen
    upload = request.files.get("file")
    if not upload or not upload.filename:
        raise ValueError("请选择 EDS/DCF 文件")
    filename = secure_filename(upload.filename)
    if Path(filename).suffix.lower() not in (".eds", ".dcf"):
        raise ValueError("仅允许 .eds 或 .dcf")
    EDS_DIR.mkdir(parents=True, exist_ok=True)
    destination = EDS_DIR / filename
    upload.save(destination)
    try:
        canopen.import_od(str(destination))
    except Exception:
        destination.unlink(missing_ok=True)
        raise ValueError("EDS/DCF 文件解析失败")
    node_id = request.form.get("node_id")
    if node_id:
        node_id = parse_int(node_id, "节点 ID", 1, 127)
        cfg = load_config()
        cfg.setdefault("canopen", {}).setdefault("nodes", {})[str(node_id)] = {
            "eds": str(destination)
        }
        save_config(cfg)
    return jsonify(ok=True, filename=filename, node_id=node_id)


@app.post("/api/canopen/scan")
def canopen_scan():
    body = request.get_json(force=True)
    cfg, iface = canopen_settings(body)
    limit = parse_int(body.get("limit", 127), "扫描上限", 1, 127)
    wait = min(max(float(body.get("wait", 0.8)), 0.1), 5.0)
    with LOCK:
        network = connect_canopen(iface)
        try:
            network.scanner.reset()
            network.scanner.search(limit)
            time.sleep(wait)
            nodes = sorted(set(network.scanner.nodes))
        finally:
            network.disconnect()
    return jsonify(ok=True, interface=iface, nodes=nodes)


@app.post("/api/canopen/nmt")
def canopen_nmt():
    body = request.get_json(force=True)
    cfg, iface = canopen_settings(body)
    state = str(body.get("state", "")).upper()
    allowed = {"OPERATIONAL", "PRE-OPERATIONAL", "STOPPED", "RESET", "RESET COMMUNICATION"}
    if state not in allowed:
        raise ValueError("不支持的 NMT 状态")
    node_id = parse_int(body.get("node_id", 0), "节点 ID", 0, 127)
    with LOCK:
        network = connect_canopen(iface)
        try:
            if node_id == 0:
                network.nmt.state = state
            else:
                node = network.add_node(node_id, node_eds(cfg, node_id))
                node.nmt.state = state
        finally:
            network.disconnect()
    return jsonify(ok=True, node_id=node_id, state=state)


def parse_sdo_payload(body):
    encoding = body.get("encoding", "hex")
    value = body.get("value", "")
    if encoding == "hex":
        try:
            return bytes.fromhex(str(value).replace("0x", "").replace(" ", ""))
        except ValueError:
            raise ValueError("十六进制数据不合法")
    if encoding == "text":
        return str(value).encode("utf-8")
    if encoding == "integer":
        size = parse_int(body.get("size", 4), "整数长度", 1, 8)
        number = int(str(value), 0)
        return number.to_bytes(size, "little", signed=bool(body.get("signed")))
    raise ValueError("不支持的数据编码")


@app.post("/api/canopen/sdo/read")
def canopen_sdo_read():
    body = request.get_json(force=True)
    cfg, iface = canopen_settings(body)
    node_id = parse_int(body.get("node_id"), "节点 ID", 1, 127)
    index = parse_int(body.get("index"), "索引", 0, 0xFFFF)
    subindex = parse_int(body.get("subindex", 0), "子索引", 0, 0xFF)
    with LOCK:
        network = connect_canopen(iface)
        try:
            node = network.add_node(node_id, node_eds(cfg, node_id))
            payload = node.sdo.upload(index, subindex)
        finally:
            network.disconnect()
    return jsonify(
        ok=True, hex=payload.hex(" "), length=len(payload),
        unsigned=int.from_bytes(payload, "little", signed=False),
        signed=int.from_bytes(payload, "little", signed=True),
        text=payload.decode("utf-8", errors="replace")
    )


@app.post("/api/canopen/sdo/write")
def canopen_sdo_write():
    body = request.get_json(force=True)
    cfg, iface = canopen_settings(body)
    node_id = parse_int(body.get("node_id"), "节点 ID", 1, 127)
    index = parse_int(body.get("index"), "索引", 0, 0xFFFF)
    subindex = parse_int(body.get("subindex", 0), "子索引", 0, 0xFF)
    payload = parse_sdo_payload(body)
    with LOCK:
        network = connect_canopen(iface)
        try:
            node = network.add_node(node_id, node_eds(cfg, node_id))
            node.sdo.download(index, subindex, payload)
        finally:
            network.disconnect()
    return jsonify(ok=True, written=len(payload), hex=payload.hex(" "))


def serialize_pdo(collection):
    result = []
    for number, mapping in collection.items():
        variables = []
        for variable in mapping:
            variables.append({
                "name": getattr(variable, "name", ""),
                "index": getattr(variable, "index", 0),
                "subindex": getattr(variable, "subindex", 0),
                "length": getattr(variable, "length", 0)
            })
        result.append({
            "number": number,
            "cob_id": getattr(mapping, "cob_id", None),
            "enabled": bool(getattr(mapping, "enabled", False)),
            "transmission_type": getattr(mapping, "trans_type", None),
            "variables": variables
        })
    return result


def sdo_diagnostic(node, index, subindex=0, required=False):
    try:
        payload = node.sdo.upload(index, subindex)
    except Exception as exc:
        if required:
            raise RuntimeError(
                f"读取 0x{index:04X}:{subindex:02X} 失败: {exc}"
            )
        return None
    return {
        "hex": payload.hex(" "),
        "length": len(payload),
        "unsigned": int.from_bytes(payload, "little", signed=False)
    }


@app.post("/api/canopen/node")
def canopen_node():
    body = request.get_json(force=True)
    cfg, iface = canopen_settings(body)
    node_id = parse_int(body.get("node_id"), "节点 ID", 1, 127)
    timeout = min(max(float(body.get("heartbeat_wait", 0.5)), 0.0), 3.0)
    with LOCK:
        network = connect_canopen(iface)
        try:
            node = network.add_node(node_id, node_eds(cfg, node_id))
            result = {
                "device_type": sdo_diagnostic(node, 0x1000, required=True),
                "error_register": sdo_diagnostic(node, 0x1001),
                "heartbeat_producer_ms": sdo_diagnostic(node, 0x1017),
                "identity": {
                    "vendor_id": sdo_diagnostic(node, 0x1018, 1),
                    "product_code": sdo_diagnostic(node, 0x1018, 2),
                    "revision": sdo_diagnostic(node, 0x1018, 3),
                    "serial": sdo_diagnostic(node, 0x1018, 4)
                }
            }
            heartbeat_state = None
            heartbeat_error = ""
            if timeout:
                try:
                    node.nmt.wait_for_heartbeat(timeout)
                    heartbeat_state = node.nmt.state
                except Exception as exc:
                    heartbeat_error = str(exc)
        finally:
            network.disconnect()
    return jsonify(
        ok=True, interface=iface, node_id=node_id,
        nmt_state=heartbeat_state, heartbeat_error=heartbeat_error, **result
    )


@app.post("/api/canopen/pdo/read")
def canopen_pdo_read():
    body = request.get_json(force=True)
    cfg, iface = canopen_settings(body)
    node_id = parse_int(body.get("node_id"), "节点 ID", 1, 127)
    eds = node_eds(cfg, node_id)
    if not eds:
        raise ValueError("该节点尚未绑定 EDS/DCF")
    with LOCK:
        network = connect_canopen(iface)
        try:
            node = network.add_node(node_id, eds)
            node.tpdo.read()
            node.rpdo.read()
            result = {"tpdo": serialize_pdo(node.tpdo), "rpdo": serialize_pdo(node.rpdo)}
        finally:
            network.disconnect()
    return jsonify(ok=True, **result)


@app.post("/api/canopen/pdo/transmit")
def canopen_pdo_transmit():
    body = request.get_json(force=True)
    cfg, iface = canopen_settings(body)
    node_id = parse_int(body.get("node_id"), "节点 ID", 1, 127)
    pdo_number = parse_int(body.get("pdo", 1), "PDO 编号", 1, 512)
    eds = node_eds(cfg, node_id)
    if not eds:
        raise ValueError("该节点尚未绑定 EDS/DCF")
    values = body.get("values", {})
    if not isinstance(values, dict) or not values:
        raise ValueError("values 必须包含至少一个对象字典变量")
    with LOCK:
        network = connect_canopen(iface)
        try:
            node = network.add_node(node_id, eds)
            node.rpdo.read()
            mapping = node.rpdo[pdo_number]
            for name, value in values.items():
                mapping[name].raw = value
            mapping.transmit()
        finally:
            network.disconnect()
    return jsonify(ok=True, node_id=node_id, pdo=pdo_number)


def ethercat_settings(body):
    expected = device_by_role("ethercat")
    iface = body.get("interface", expected)
    if iface != expected:
        raise ValueError("EtherCAT 必须使用板型定义的专用接口")
    return iface


def ethercat_command(arguments, timeout=20, require_success=True):
    iface = device_by_role("ethercat")
    with LOCK:
        result = command(
            ["/usr/bin/omnigate-ethercat", iface, *arguments],
            timeout=timeout
        )
    parsed = None
    for line in reversed(result["output"].splitlines()):
        try:
            parsed = json.loads(line)
            break
        except ValueError:
            continue
    if require_success and result["returncode"]:
        raise RuntimeError(
            result["output"].strip() or "EtherCAT 操作失败"
        )
    if parsed is None:
        parsed = {
            "ok": result["returncode"] == 0,
            "output": result["output"]
        }
    parsed["returncode"] = result["returncode"]
    return parsed


@app.post("/api/ethercat/scan")
def ethercat_scan():
    body = request.get_json(silent=True) or {}
    ethercat_settings(body)
    return jsonify(**ethercat_command(["scan"], require_success=False))


@app.post("/api/ethercat/sdo/read")
def ethercat_sdo_read():
    body = request.get_json(force=True)
    ethercat_settings(body)
    slave = parse_int(body.get("slave"), "从站位置", 1, 200)
    index = parse_int(body.get("index"), "索引", 0, 0xFFFF)
    subindex = parse_int(body.get("subindex", 0), "子索引", 0, 0xFF)
    maximum = parse_int(body.get("max_bytes", 256), "最大长度", 1, 4096)
    return jsonify(**ethercat_command([
        "sdo-read", str(slave), hex(index), str(subindex), str(maximum)
    ]))


@app.post("/api/ethercat/sdo/write")
def ethercat_sdo_write():
    body = request.get_json(force=True)
    ethercat_settings(body)
    slave = parse_int(body.get("slave"), "从站位置", 1, 200)
    index = parse_int(body.get("index"), "索引", 0, 0xFFFF)
    subindex = parse_int(body.get("subindex", 0), "子索引", 0, 0xFF)
    value = str(body.get("value", "")).strip()
    compact = re.sub(r"(?:0x|[\s:-])", "", value, flags=re.IGNORECASE)
    if not compact or len(compact) > 8192 or not re.fullmatch(r"[0-9A-Fa-f]+", compact):
        raise ValueError("写入值必须是 1..4096 字节十六进制数据")
    if len(compact) % 2:
        raise ValueError("十六进制写入值必须包含完整字节")
    return jsonify(**ethercat_command([
        "sdo-write", str(slave), hex(index), str(subindex), compact
    ]))


@app.post("/api/ethercat/cycle")
def ethercat_cycle():
    body = request.get_json(force=True)
    ethercat_settings(body)
    count = parse_int(body.get("count", 100), "周期数", 1, 10000)
    period = parse_int(body.get("period_us", 1000), "周期", 100, 1000000)
    if count * period > 10_000_000:
        raise ValueError("单次周期测试最长 10 秒")
    timeout = max(20, int(count * period / 1_000_000) + 12)
    return jsonify(**ethercat_command(
        ["cycle", str(count), str(period)],
        timeout=timeout, require_success=False
    ))


def ec20_status():
    return {
        "usb": command(["lsusb"], timeout=5)["output"],
        "devices": sorted(glob.glob("/dev/cdc-wdm*") + glob.glob("/dev/ttyUSB*")),
        "links": command(["ip", "-brief", "address"], timeout=5)["output"]
    }


@app.get("/api/ec20/status")
def get_ec20_status():
    return jsonify(**ec20_status())


@app.get("/api/ec20/profiles")
def get_ec20_profiles():
    profiles = load_config().get("ec20", {}).get("profiles", {})
    safe = {}
    for name, profile in profiles.items():
        safe[name] = dict(profile)
        safe[name]["password"] = ""
        safe[name]["password_configured"] = bool(profile.get("password"))
    return jsonify(profiles=safe)


@app.put("/api/ec20/profiles/<name>")
def put_ec20_profile(name):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", name):
        raise ValueError("配置名称不合法")
    body = request.get_json(force=True)
    device = str(body.get("device", ""))
    iface = str(body.get("interface", ""))
    if not re.fullmatch(r"/dev/cdc-wdm[0-9]+", device):
        raise ValueError("QMI 设备路径不合法")
    if not re.fullmatch(r"wwan[0-9]+", iface):
        raise ValueError("WWAN 接口不合法")
    apn = str(body.get("apn", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{0,100}", apn):
        raise ValueError("APN 不合法")
    cfg = load_config()
    profiles = cfg.setdefault("ec20", {}).setdefault("profiles", {})
    old = profiles.get(name, {})
    profiles[name] = {
        "device": device,
        "interface": iface,
        "apn": apn,
        "username": str(body.get("username", ""))[:100],
        "password": str(body.get("password", ""))[:100] or old.get("password", ""),
        "auth": str(body.get("auth", "none"))
    }
    if profiles[name]["auth"] not in ("none", "pap", "chap", "both"):
        raise ValueError("认证方式不合法")
    save_config(cfg)
    return jsonify(ok=True)


def ec20_profile(name):
    profile = load_config().get("ec20", {}).get("profiles", {}).get(name)
    if not profile:
        raise ValueError("未找到 EC20 配置")
    if not Path(profile["device"]).exists():
        raise ValueError("EC20 QMI 设备尚未出现")
    if not Path("/sys/class/net").joinpath(profile["interface"]).exists():
        raise ValueError("EC20 网络接口尚未出现")
    return profile


@app.post("/api/ec20/<name>/connect")
def connect_ec20(name):
    profile = ec20_profile(name)
    device, iface = profile["device"], profile["interface"]
    raw_ip = Path("/sys/class/net") / iface / "qmi" / "raw_ip"
    command(["ip", "link", "set", iface, "down"], timeout=5)
    if raw_ip.exists():
        raw_ip.write_text("Y", encoding="ascii")
    command(["ip", "link", "set", iface, "up"], timeout=5, check=True)
    settings = ["ip-type=4"]
    for key in ("apn", "username", "password", "auth"):
        value = profile.get(key)
        if value and value != "none":
            settings.append(f"{key}='{value}'")
    result = command([
        "qmicli", "-d", device, "--device-open-proxy",
        "--wds-start-network=" + ",".join(settings),
        "--client-no-release-cid"
    ], timeout=30, check=True)
    match = re.search(r"Packet data handle: '([0-9]+)'", result["output"])
    runtime = {"device": device, "interface": iface, "handle": match.group(1) if match else ""}
    atomic_json(f"/var/run/omnigate-ec20-{name}.json", runtime)
    dhcp = command(["udhcpc", "-i", iface, "-q", "-n", "-t", "5"], timeout=25)
    return jsonify(ok=dhcp["returncode"] == 0, qmi=result["output"], dhcp=dhcp["output"])


@app.post("/api/ec20/<name>/disconnect")
def disconnect_ec20(name):
    profile = ec20_profile(name)
    runtime = load_json(f"/var/run/omnigate-ec20-{name}.json", {})
    handle = runtime.get("handle", "0")
    result = command([
        "qmicli", "-d", profile["device"], "--device-open-proxy",
        f"--wds-stop-network={handle}"
    ], timeout=20)
    command(["ip", "link", "set", profile["interface"], "down"], timeout=5)
    return jsonify(ok=result["returncode"] == 0, output=result["output"])


SERVICES = {
    "thingsboard": "/etc/init.d/S70thingsboard-gateway",
    "bluetooth": "/usr/bin/bt-speaker",
    "ntp": "/etc/init.d/S49ntp"
}


@app.post("/api/services/<name>/<action>")
def control_service(name, action):
    if name not in SERVICES or action not in ("start", "stop", "restart", "status"):
        raise ValueError("不支持的服务操作")
    result = command([SERVICES[name], action], timeout=20)
    return jsonify(ok=result["returncode"] == 0, **result)


LOGS = {
    "web": "/var/log/omnigate-web.log",
    "thingsboard": "/var/log/thingsboard-gateway.log",
    "messages": "/var/log/messages"
}


@app.get("/api/logs/<name>")
def logs(name):
    if name not in LOGS:
        raise ValueError("不支持的日志")
    lines = parse_int(request.args.get("lines", 200), "行数", 10, 1000)
    path = LOGS[name]
    if not Path(path).exists():
        return jsonify(output="", missing=True)
    return jsonify(output=command(["tail", "-n", str(lines), path], timeout=5)["output"])


from hmi_api import create_blueprint
from omnigate_core.api import create_blueprint as create_edge_blueprint
app.register_blueprint(create_blueprint())
app.register_blueprint(create_edge_blueprint())


if __name__ == "__main__":
    address = os.environ.get("OMNIGATE_LISTEN_ADDRESS", "0.0.0.0")
    port = int(os.environ.get("OMNIGATE_LISTEN_PORT", "80"))
    cert = os.environ.get("OMNIGATE_TLS_CERT", "")
    key = os.environ.get("OMNIGATE_TLS_KEY", "")
    if bool(cert) != bool(key):
        raise RuntimeError("TLS_CERT and TLS_KEY must be configured together")
    app.run(host=address, port=port, threaded=True,
            ssl_context=(cert, key) if cert else None)
