"""Versioned management API shared by Web UI, HMI, and fleet agents."""
import os
import math
import re
import shutil
import time
from pathlib import Path

from flask import Blueprint, jsonify, request, session

from .platform import ManifestError, load_manifest
from .store import EdgeStore


IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,63}$")
POINT_TYPES = {"bool", "int8", "uint8", "int16", "uint16", "int32",
               "uint32", "int64", "uint64", "float", "double", "string",
               "bytes"}


def _system_status():
    usage = shutil.disk_usage("/")
    return {
        "time": int(time.time()),
        "uptime_seconds": int(float(Path("/proc/uptime").read_text().split()[0])),
        "storage": {"total": usage.total, "used": usage.used, "free": usage.free},
        "release": os.uname().release,
    }


def _device_payload(body, manifest):
    required = ("id", "name", "template_id", "channel", "address")
    missing = [key for key in required if not body.get(key)]
    if missing:
        raise ValueError("missing device fields: " + ", ".join(missing))
    for key in ("id", "template_id"):
        if not IDENTIFIER.fullmatch(str(body[key])):
            raise ValueError("invalid %s" % key)
    if body["channel"] not in manifest["channels"]:
        raise ValueError("unknown platform channel")
    if not isinstance(body.get("config", {}), dict):
        raise ValueError("device config must be an object")
    return {key: body[key] for key in required} | {
        "enabled": bool(body.get("enabled", True)), "config": body.get("config", {})}


def _point_payload(body):
    required = ("id", "device_id", "name", "data_type", "address", "access")
    missing = [key for key in required if body.get(key) in (None, "")]
    if missing:
        raise ValueError("missing point fields: " + ", ".join(missing))
    for key in ("id", "device_id"):
        if not IDENTIFIER.fullmatch(str(body[key])):
            raise ValueError("invalid %s" % key)
    if body["data_type"] not in POINT_TYPES:
        raise ValueError("unsupported point data type")
    if body["access"] not in ("r", "w", "rw"):
        raise ValueError("point access must be r, w, or rw")
    name = str(body["name"])
    address = str(body["address"])
    unit = str(body.get("unit", ""))
    if not 1 <= len(name) <= 128:
        raise ValueError("point name must contain 1..128 characters")
    if not 1 <= len(address) <= 256:
        raise ValueError("point address must contain 1..256 characters")
    if len(unit) > 32:
        raise ValueError("point unit must not exceed 32 characters")
    try:
        scale = float(body.get("scale", 1.0))
    except (TypeError, ValueError):
        raise ValueError("point scale must be numeric")
    if not math.isfinite(scale):
        raise ValueError("point scale must be finite")
    return {
        "id": str(body["id"]), "device_id": str(body["device_id"]),
        "name": name, "data_type": body["data_type"], "address": address,
        "access": body["access"], "unit": unit, "scale": scale,
        "enabled": bool(body.get("enabled", True)),
    }


def create_blueprint(manifest_path=None, database_path=None):
    manifest = load_manifest(manifest_path)
    store = EdgeStore(database_path or os.environ.get(
        "OMNIGATE_EDGE_DB", "/var/lib/omnigate/edge.db"))
    bp = Blueprint("edge_api_v1", __name__)

    @bp.get("/api/v1/platform")
    def platform():
        public = dict(manifest)
        public.pop("manufacturing", None)
        return jsonify(ok=True, platform=public)

    @bp.get("/api/v1/system")
    def system():
        return jsonify(ok=True, system=_system_status())

    @bp.get("/api/v1/channels")
    def channels():
        values = [dict(value, name=name) for name, value in manifest["channels"].items()]
        return jsonify(ok=True, channels=values)

    @bp.get("/api/v1/devices")
    def devices():
        return jsonify(ok=True, devices=store.list_devices())

    @bp.get("/api/v1/devices/<device_id>")
    def get_device(device_id):
        value = store.get_device(device_id)
        if value is None:
            return jsonify(error="device not found"), 404
        return jsonify(ok=True, device=value)

    @bp.put("/api/v1/devices/<device_id>")
    def put_device(device_id):
        body = request.get_json(force=True) or {}
        if body.get("id", device_id) != device_id:
            raise ValueError("device id does not match URL")
        body["id"] = device_id
        value = _device_payload(body, manifest)
        revision = store.put_device(value, session.get("username", "administrator"))
        return jsonify(ok=True, id=device_id, revision=revision)

    @bp.delete("/api/v1/devices/<device_id>")
    def delete_device(device_id):
        deleted = store.delete_device(
            device_id, session.get("username", "administrator"))
        if not deleted:
            return jsonify(error="device not found"), 404
        return jsonify(ok=True, id=device_id)

    @bp.get("/api/v1/points")
    def points():
        return jsonify(ok=True, points=store.list_points(request.args.get("device_id")))

    @bp.get("/api/v1/points/<point_id>")
    def get_point(point_id):
        value = store.get_point(point_id)
        if value is None:
            return jsonify(error="point not found"), 404
        return jsonify(ok=True, point=value)

    @bp.put("/api/v1/points/<point_id>")
    def put_point(point_id):
        body = request.get_json(force=True) or {}
        if body.get("id", point_id) != point_id:
            raise ValueError("point id does not match URL")
        body["id"] = point_id
        value = _point_payload(body)
        store.put_point(value, session.get("username", "administrator"))
        return jsonify(ok=True, id=point_id)

    @bp.delete("/api/v1/points/<point_id>")
    def delete_point(point_id):
        deleted = store.delete_point(
            point_id, session.get("username", "administrator"))
        if not deleted:
            return jsonify(error="point not found"), 404
        return jsonify(ok=True, id=point_id)

    @bp.get("/api/v1/audit")
    def audit():
        try:
            limit = min(500, max(1, int(request.args.get("limit", 200))))
        except ValueError:
            raise ValueError("invalid audit limit")
        return jsonify(ok=True, audit=store.audit(limit))

    return bp
