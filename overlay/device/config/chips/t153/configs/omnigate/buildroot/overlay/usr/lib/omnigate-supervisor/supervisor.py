#!/usr/bin/env python3
"""Conservative process supervisor with optional hardware watchdog feeding."""
import json
import os
import signal
import subprocess
import time
import urllib.request
from pathlib import Path


HEALTH_URL = os.environ.get("HEALTH_URL", "http://127.0.0.1/api/health")
CHECK_INTERVAL = max(2, int(os.environ.get("CHECK_INTERVAL", "10")))
FAILURE_THRESHOLD = max(2, int(os.environ.get("FAILURE_THRESHOLD", "3")))
RESTART_COOLDOWN = max(30, int(os.environ.get("RESTART_COOLDOWN", "120")))
WATCHDOG_ENABLE = os.environ.get("WATCHDOG_ENABLE", "0") == "1"
WATCHDOG_DEVICE = os.environ.get("WATCHDOG_DEVICE", "/dev/watchdog")
STATUS_PATH = Path("/var/run/omnigate-supervisor.json")
RUNNING = True


def stop(_signum, _frame):
    global RUNNING
    RUNNING = False


def health_ok():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=4) as response:
            value = json.loads(response.read().decode("utf-8"))
        return response.status == 200 and value.get("ok") is True
    except (OSError, ValueError):
        return False


def write_status(value):
    temp = STATUS_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(temp), str(STATUS_PATH))


def restart_web():
    return subprocess.run(["/etc/init.d/S71omnigate-web", "restart"],
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=30).returncode == 0


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    watchdog = None
    if WATCHDOG_ENABLE:
        watchdog = open(WATCHDOG_DEVICE, "wb", buffering=0)
    failures = 0
    restart_count = 0
    last_restart = 0
    try:
        while RUNNING:
            healthy = health_ok()
            failures = 0 if healthy else failures + 1
            now = int(time.time())
            if failures >= FAILURE_THRESHOLD and now - last_restart >= RESTART_COOLDOWN:
                restart_web()
                restart_count += 1
                last_restart = now
                failures = 0
            if watchdog is not None and healthy:
                watchdog.write(b"\0")
            write_status({"healthy": healthy, "failures": failures,
                          "restart_count": restart_count, "updated_at": now,
                          "hardware_watchdog": WATCHDOG_ENABLE})
            time.sleep(CHECK_INTERVAL)
    finally:
        if watchdog is not None:
            try:
                watchdog.write(b"V")
                watchdog.close()
            except OSError:
                pass


if __name__ == "__main__":
    main()
