"""Board manifest loader. Business services must not hard-code Linux device names."""
import json
import os
import sys
from pathlib import Path


MANIFEST_PATH = Path(os.environ.get(
    "OMNIGATE_PLATFORM_MANIFEST", "/etc/omnigate/platform.json"))
REQUIRED = ("schema_version", "board_id", "soc", "runtime_profile", "channels")
RUNTIME_PROFILES = {"lite", "enhanced"}
CHANNEL_KINDS = {"ethernet", "can", "serial", "cellular", "wifi", "display"}


class ManifestError(ValueError):
    pass


def _validate_channel(name, value):
    if not isinstance(value, dict):
        raise ManifestError("channel %s must be an object" % name)
    if value.get("kind") not in CHANNEL_KINDS:
        raise ManifestError("channel %s has unsupported kind" % name)
    if not isinstance(value.get("device"), str) or not value["device"]:
        raise ManifestError("channel %s must define device" % name)
    role = value.get("role")
    if role is not None and (not isinstance(role, str) or not role):
        raise ManifestError("channel %s has invalid role" % name)


def validate_manifest(value):
    if not isinstance(value, dict):
        raise ManifestError("platform manifest must be an object")
    missing = [key for key in REQUIRED if key not in value]
    if missing:
        raise ManifestError("platform manifest missing: " + ", ".join(missing))
    if value["schema_version"] != 1:
        raise ManifestError("unsupported platform manifest version")
    if value["runtime_profile"] not in RUNTIME_PROFILES:
        raise ManifestError("runtime_profile must be lite or enhanced")
    if not isinstance(value["channels"], dict) or not value["channels"]:
        raise ManifestError("platform manifest must define channels")
    for name, channel in value["channels"].items():
        _validate_channel(name, channel)
    return value


def load_manifest(path=None):
    path = Path(path) if path else MANIFEST_PATH
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except OSError as exc:
        raise ManifestError("cannot read platform manifest: %s" % exc)
    except ValueError as exc:
        raise ManifestError("invalid platform manifest JSON: %s" % exc)
    return validate_manifest(value)


def channel(manifest, logical_name, expected_kind=None):
    try:
        value = manifest["channels"][logical_name]
    except KeyError:
        raise ManifestError("channel not available: %s" % logical_name)
    if expected_kind and value["kind"] != expected_kind:
        raise ManifestError("channel %s is not %s" % (logical_name, expected_kind))
    return value


def find_by_role(manifest, role):
    return [dict(value, name=name) for name, value in manifest["channels"].items()
            if value.get("role") == role]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    manifest = load_manifest()
    if len(argv) == 2 and argv[0] == "role":
        values = find_by_role(manifest, argv[1])
    elif len(argv) == 2 and argv[0] == "kind":
        values = [dict(value, name=name) for name, value in manifest["channels"].items()
                  if value.get("kind") == argv[1]]
    else:
        raise SystemExit("usage: python -m omnigate_core.platform {role|kind} VALUE")
    for value in values:
        print(value["device"])


if __name__ == "__main__":
    main()
