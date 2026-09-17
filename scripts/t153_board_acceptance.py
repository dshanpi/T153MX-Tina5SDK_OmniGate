#!/usr/bin/env python3
"""Evidence-first T153 full-flash and 24-hour acceptance runner.

The runner never sends CANopen, Modbus, or EtherCAT control traffic.  Hardware
results are emitted only from LYNX/board observations and are kept separate
from host-only Node-RED evidence.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import threading
import time
import uuid


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
SDK_DIR = REPO_DIR.parent
LYNX_DIR = SDK_DIR / "tools" / "lynx_mcp"
sys.path.insert(0, str(LYNX_DIR))
try:
    from lynx_mcp import LynxMCP, LynxMCPError
except ImportError:
    LynxMCP = None
    LynxMCPError = RuntimeError


TERMINAL = {"success", "failed", "cancelled"}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def partition_list(path):
    names = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"\s*name\s*=\s*([A-Za-z0-9_-]+)\s*$", line)
        if match:
            names.append(match.group(1))
    # Allwinner pack adds the remaining-capacity UDISK after the explicitly
    # configured entries.  Report the final on-media layout, not only fex rows.
    if "UDISK" not in names:
        names.append("UDISK")
    return names


class Runner:
    def __init__(self, args):
        self.args = args
        stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        self.output = Path(args.output or SDK_DIR / "acceptance-results" / stamp)
        self.output.mkdir(parents=True, exist_ok=True)
        for name in ("build", "lynx", "serial", "api", "screenshots", "soak", "final"):
            (self.output / name).mkdir(exist_ok=True)
        self.lynx = LynxMCP(args.lynx_url, timeout=90) if LynxMCP else None
        self.samples = []
        self.events = []
        self.serial_handle = args.serial_handle
        self.board_transport = None

    def save_json(self, relative, value):
        path = self.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n", encoding="utf-8")
        return value

    def event(self, name, **detail):
        value = {"timestamp": int(time.time()), "event": name, **detail}
        self.events.append(value)
        self.save_json("events.json", self.events)

    def build_manifest(self):
        image = Path(self.args.image).resolve()
        partitions = partition_list(self.args.partitions)
        value = {
            "created_at": dt.datetime.now().astimezone().isoformat(),
            "image": str(image), "image_bytes": image.stat().st_size,
            "sha256": sha256(image), "partition_count": len(partitions),
            "partitions": partitions, "boot_components": ["Boot0", "Boot1"],
            "git": subprocess.run(
                ["git", "-C", str(REPO_DIR), "status", "--short", "--branch"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout,
        }
        self.save_json("build/build-manifest.json", value)
        if len(partitions) != 12:
            raise RuntimeError("expected 12 eMMC partitions plus Boot0/Boot1; got %d" % len(partitions))
        return value

    def require_lynx(self):
        if not self.lynx:
            raise RuntimeError("tools/lynx_mcp/lynx_mcp.py is unavailable")
        status = self.save_json("lynx/workbench-status.json", self.lynx.status())
        if not status.get("online"):
            raise RuntimeError("LYNX workbench is not online")
        return status

    def wait_task(self, task_id, name, timeout):
        deadline = time.time() + timeout
        last_contact = time.time()
        history = []
        while time.time() < deadline:
            try:
                value = self.lynx.task_status(task_id)
                last_contact = time.time()
            except (OSError, LynxMCPError) as exc:
                history.append({"poll_error": str(exc), "timestamp": int(time.time())})
                self.save_json("lynx/%s-history.json" % name, history)
                if time.time() - last_contact > 90:
                    raise RuntimeError("%s task status unavailable for 90 seconds: %s" %
                                       (name, exc))
                # Sessions are disposable; the flash task belongs to the LYNX
                # application and remains queryable after reconnecting.
                self.lynx = LynxMCP(self.args.lynx_url, timeout=90)
                time.sleep(2)
                continue
            history.append(value)
            self.save_json("lynx/%s-history.json" % name, history)
            if value.get("state") in TERMINAL:
                if value.get("state") != "success":
                    raise RuntimeError("%s task failed: %s" % (name, value))
                return value
            time.sleep(2)
        raise RuntimeError("%s task timed out" % name)

    def enter_fel(self, status):
        scan = self.save_json("lynx/pre-flash-scan.json", self.lynx.scan())
        if scan.get("devices"):
            return
        port = status.get("serialPort") or self.args.serial_port
        handle = self.lynx.serial_open(port, 115200)["handle"]
        try:
            tools = status.get("capabilityManifest", {}).get("serial", [])
            if "lynx_allwinner_enter_fel" in tools:
                result = self.lynx.call("lynx_allwinner_enter_fel", {
                    "method": "serial_shell_reboot_efex",
                    "confirmDestructive": True,
                    "handle": handle,
                    "preserveSerialMonitor": False,
                })
                self.save_json("lynx/enter-fel.json", result)
            else:
                # Compatibility path for older gateways without the bounded
                # board-specific transition tool.
                self.lynx.serial_write(handle, "sync; reboot efex")
        finally:
            try:
                self.lynx.serial_close(handle)
            except Exception:
                pass
        deadline = time.time() + 45
        while time.time() < deadline:
            scan = self.lynx.scan()
            if scan.get("devices"):
                self.save_json("lynx/fel-scan.json", scan)
                return
            time.sleep(2)
        raise RuntimeError("board did not enter FEL; manual FEL action is required")

    def serial_capture(self, stop, path, port):
        client = LynxMCP(self.args.lynx_url, timeout=30)
        handle = None
        with open(path, "a", encoding="utf-8", errors="replace") as stream:
            while not stop.is_set():
                try:
                    if not handle:
                        handle = client.serial_open(port, 115200)["handle"]
                    value = client.serial_read(handle, 2000)
                    text = value.get("text", "") if isinstance(value, dict) else str(value)
                    if text:
                        stream.write(text.replace("\x00", ""))
                        stream.flush()
                except Exception as exc:
                    stream.write("\n[SERIAL_REOPEN %s]\n" % exc)
                    stream.flush()
                    handle = None
                    time.sleep(1)
            if handle:
                try:
                    client.serial_close(handle)
                except Exception:
                    pass

    def flash(self):
        status = self.require_lynx()
        caps = self.save_json("lynx/flash-capabilities.json",
                              self.lynx.flash_capabilities())
        # LYNX 0.9 wraps the advertised values in ``capabilities`` while
        # older gateways returned them at the top level.
        advertised = caps.get("capabilities", caps)
        modes = advertised.get("modes", [])
        if "full_erase" not in modes:
            raise RuntimeError("LYNX does not advertise full_erase")
        self.enter_fel(status)
        transfer = self.lynx.download(str(Path(self.args.image).resolve()),
                                      status.get("projectId"), wait=False)
        self.save_json("lynx/download-start.json", transfer)
        transfer_final = self.wait_task(transfer["taskId"], "download", 3600)
        local_path = transfer.get("localPath") or transfer_final.get("localPath")
        if not local_path:
            raise RuntimeError("LYNX download did not return a cache path")
        for value in (transfer, transfer_final):
            remote_sha = value.get("sha256") or value.get("verifiedSha256")
            if remote_sha and remote_sha.lower() != sha256(self.args.image):
                raise RuntimeError("LYNX cache SHA-256 differs from local image")
        stop = threading.Event()
        serial_path = self.output / "serial" / "flash-and-cold-boot.log"
        port = status.get("serialPort") or self.args.serial_port
        thread = threading.Thread(target=self.serial_capture,
                                  args=(stop, serial_path, port), daemon=True)
        thread.start()
        try:
            started = self.lynx.start_flash(local_path, mode="full_erase",
                                            post_flash="reboot", verify=True,
                                            wait=False)
            self.save_json("lynx/flash-start.json", started)
            final = self.wait_task(started["taskId"], "flash", 7200)
            self.save_json("lynx/flash-final.json", final)
            if final.get("verifyState") != "success" or final.get("verifyErrorCode") not in (0, "0", None):
                raise RuntimeError("flash verification did not pass")
            boot_deadline = time.time() + 120
            while time.time() < boot_deadline:
                text = serial_path.read_text(encoding="utf-8", errors="replace") if serial_path.exists() else ""
                if "Linux version" in text and ("login:" in text or "omnigate-web" in text or "# " in text):
                    self.event("cold_boot_detected", within_seconds=120)
                    break
                time.sleep(2)
            else:
                raise RuntimeError("Linux readiness was not observed on COM19 within 120 seconds")
        finally:
            stop.set()
            thread.join(timeout=10)

    def _ssh(self, command, timeout=30, input_text=None):
        target = "%s@%s" % (self.args.ssh_user, self.args.board_host)
        argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                target, command]
        completed = subprocess.run(argv, input=input_text, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   timeout=timeout)
        if completed.returncode:
            raise RuntimeError("board command failed: %s" % completed.stdout[-2000:])
        return completed.stdout

    def board_exec(self, command, timeout=30):
        if self.args.board_host:
            return self._ssh(command, timeout)
        if self.args.board_transport in ("auto", "adb") and self.board_transport != "serial":
            try:
                devices = self.lynx.adb_list()
                if devices.get("online"):
                    self.board_transport = "adb"
                    value = self.lynx.adb_shell(command)
                    if isinstance(value, str):
                        return value
                    for key in ("output", "stdout", "text"):
                        if value.get(key) is not None:
                            return value[key]
                    return json.dumps(value)
                if self.args.board_transport == "adb":
                    raise RuntimeError("configured ADB device is not online")
            except Exception:
                if self.args.board_transport == "adb":
                    raise
        self.board_transport = "serial"
        return self._serial_exec(command, timeout)

    def _serial_exec(self, command, timeout):
        marker = uuid.uuid4().hex
        begin = "__OMNIGATE_BEGIN_%s__" % marker
        end = "__OMNIGATE_END_%s__" % marker
        wrapped = "echo %s; %s; __omnigate_rc=$?; echo %s:$__omnigate_rc" % (
            begin, command, end)
        deadline = time.time() + timeout
        output = ""
        try:
            if not self.serial_handle:
                opened = self.lynx.serial_open(self.args.serial_port, 115200)
                self.serial_handle = opened["handle"]
            self.lynx.serial_write(self.serial_handle, wrapped)
            while time.time() < deadline:
                value = self.lynx.serial_read(
                    self.serial_handle,
                    max(100, min(2000, int((deadline - time.time()) * 1000))))
                output += value.get("text", "") if isinstance(value, dict) else str(value)
                # A serial console echoes the submitted command, including a
                # literal ``:$__omnigate_rc``. Only a numeric status marks the
                # real completion line.
                matches = list(re.finditer(re.escape(end) + r":([0-9]+)\r?\n?", output))
                if matches:
                    match = matches[-1]
                    end_at = match.start()
                    begin_at = output.rfind(begin, 0, end_at)
                else:
                    begin_at = end_at = -1
                if begin_at >= 0:
                    body = output[begin_at + len(begin):end_at].strip("\r\n")
                    status = int(match.group(1))
                    if status:
                        raise RuntimeError("board command exited %d: %s" % (status, body[-2000:]))
                    return body
            raise RuntimeError("serial command timed out after %ss" % timeout)
        except Exception:
            if self.serial_handle:
                try:
                    self.lynx.serial_close(self.serial_handle)
                except Exception:
                    pass
            self.serial_handle = None
            raise

    def functional(self):
        self.require_lynx()
        commands = {
            "identity": "uname -a; cat /proc/cmdline; cat /etc/omnigate/platform.json",
            "partitions": "ls -l /dev/by-name 2>/dev/null; ls /dev/mmcblk0*",
            "services": "/etc/init.d/S71omnigate-web status; /etc/init.d/S72omnigate-supervisor status; pidof omnigate-hmi ModemManager || true",
            "interfaces": "ip -details link show; ip address show; ls -l /dev/ttyAS* /dev/input/event* /dev/fb* /dev/cdc-wdm* 2>/dev/null || true",
            "drivers": "dmesg | grep -Ei 'can|rs485|ttyAS|eth|wlan|wifi|dsi|lcd|touch|goodix|ft5|modem|qmi|mbim' | tail -300",
            "safety": "cat /sys/class/net/can0/operstate 2>/dev/null; cat /sys/class/net/can1/operstate 2>/dev/null",
            "kernel": "dmesg | grep -Ei 'panic|oops|out of memory|oom-killer|read-only|I/O error' || true",
            "hmi_settings": "cat /etc/omnigate-hmi/config.json; wget -qO- http://127.0.0.1/api/hmi/v1/snapshot",
        }
        for name, command in commands.items():
            output = self.board_exec(command, 60)
            (self.output / "final" / (name + ".txt")).write_text(
                output, encoding="utf-8", errors="replace")
        if self.args.board_host:
            remote = "/tmp/omnigate-acceptance-framebuffer.png"
            self.board_exec("fbgrab %s && test -s %s" % (remote, remote), 30)
            target = "%s@%s:%s" % (self.args.ssh_user, self.args.board_host, remote)
            subprocess.run(["scp", "-q", target,
                            str(self.output / "screenshots" / "framebuffer.png")],
                           check=True, timeout=60)
            self.board_exec("rm -f %s" % remote)
        else:
            self.event("framebuffer_pending", reason="SSH/SCP board host not provided")

    def wait_online(self, timeout=300):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                self.board_exec("true", 15)
                return
            except Exception:
                time.sleep(5)
        raise RuntimeError("board did not return after controlled reboot")

    def soak(self):
        self.require_lynx()
        duration = int(self.args.duration_hours * 3600)
        start = time.time()
        next_sample = start
        injected = False
        rebooted = False
        planned_reboot_pending = False
        previous_uptime = None
        while time.time() - start < duration:
            now = time.time()
            elapsed = now - start
            if not injected and elapsed >= self.args.fault_hour * 3600:
                before = self.board_exec("cat /var/run/omnigate-supervisor.json 2>/dev/null || true")
                self.board_exec("kill $(cat /var/run/omnigate-web.pid)")
                self.event("web_fault_injected", supervisor_before=before.strip())
                injected = True
            if not rebooted and elapsed >= self.args.reboot_hour * 3600:
                planned_reboot_pending = True
                try:
                    self.board_exec("sync; reboot", 10)
                except Exception:
                    pass
                self.event("controlled_reboot_started")
                self.wait_online(300)
                self.event("controlled_reboot_completed")
                rebooted = True
            if now >= next_sample:
                try:
                    raw = self.board_exec("/usr/bin/omnigate-acceptance-snapshot", 40)
                    sample = json.loads(raw.strip().splitlines()[-1])
                    sample["host_elapsed_seconds"] = int(elapsed)
                    sample["reachable"] = True
                    uptime = sample.get("uptime_seconds")
                    if (previous_uptime is not None and uptime is not None
                            and uptime + self.args.interval < previous_uptime):
                        kind = "planned" if planned_reboot_pending else "unplanned"
                        sample["reboot_observed"] = kind
                        self.event(kind + "_reboot_observed",
                                   previous_uptime=previous_uptime,
                                   current_uptime=uptime,
                                   elapsed_seconds=int(elapsed))
                    if uptime is not None:
                        previous_uptime = uptime
                    if sample.get("reboot_observed") == "planned":
                        planned_reboot_pending = False
                except Exception as exc:
                    sample = {"timestamp": int(time.time()),
                              "host_elapsed_seconds": int(elapsed),
                              "reachable": False, "error": str(exc)}
                self.samples.append(sample)
                with open(self.output / "soak" / "samples.jsonl", "a", encoding="utf-8") as stream:
                    stream.write(json.dumps(sample, sort_keys=True) + "\n")
                next_sample += self.args.interval
            time.sleep(min(5, max(0.2, next_sample - time.time())))

    def final_report(self):
        sample_path = self.output / "soak" / "samples.jsonl"
        if sample_path.exists():
            self.samples = [json.loads(line) for line in sample_path.read_text().splitlines() if line]
        reachable = [row for row in self.samples if row.get("reachable")]
        planned_window = 6  # up to six one-minute samples around controlled reboot
        misses = len(self.samples) - len(reachable)
        denominator = max(1, len(self.samples) - min(misses, planned_window))
        health = {}
        failures = []
        event_path = self.output / "events.json"
        if event_path.exists():
            self.events = json.loads(event_path.read_text(encoding="utf-8"))
        unplanned = [event for event in self.events
                     if event.get("event") == "unplanned_reboot_observed"]
        if unplanned:
            failures.append("%d unplanned reboot(s) observed" % len(unplanned))
        for service in ("web", "hmi"):
            healthy = sum(bool(row.get("services", {}).get(service, {}).get("running"))
                          for row in reachable)
            rate = healthy / max(1, denominator)
            health[service] = rate
            if rate < 0.995:
                failures.append("%s health %.3f < 0.995" % (service, rate))
        anomalies = sorted({line for row in reachable for line in row.get("kernel_anomalies", [])})
        if anomalies:
            failures.append("kernel anomalies observed")
        if reachable:
            for service in ("web", "hmi"):
                rss = [sum(item.get("rss_kib", 0) for item in row.get("processes", {}).get(service, []))
                       for row in reachable]
                stable = rss[max(0, len(rss) // 10):]
                if stable:
                    baseline = max(1, sum(stable[:min(10, len(stable))]) / min(10, len(stable)))
                    final = sum(stable[-min(10, len(stable)):]) / min(10, len(stable))
                    growth = (final - baseline) / baseline
                    if growth > 0.20:
                        failures.append("%s RSS growth %.1f%% > 20%%" % (service, growth * 100))
            for field, label in (("log_bytes", "logs"),
                                 ("database_bytes", "databases")):
                first = sum(reachable[0].get(field, {}).values())
                last = sum(reachable[-1].get(field, {}).values())
                growth = last - first
                if growth > 50 * 1024 * 1024:
                    failures.append("%s growth %d bytes > 50 MiB" % (label, growth))
            restart_values = [row.get("supervisor", {}).get("restart_count")
                              for row in reachable]
            restart_values = [value for value in restart_values
                              if isinstance(value, int)]
            expected_restarts = sum(event.get("event") == "web_fault_injected"
                                    for event in self.events)
            if restart_values:
                observed_restarts = max(restart_values) - min(restart_values)
                if observed_restarts > expected_restarts:
                    failures.append(
                        "supervisor restarted web %d time(s), expected at most %d" %
                        (observed_restarts, expected_restarts))
        sqlite_output = ""
        try:
            sqlite_output = self.board_exec(
                "for d in /var/lib/omnigate/*.db; do [ -f \"$d\" ] || continue; echo \"$d\"; sqlite3 \"$d\" 'PRAGMA integrity_check;'; done", 60)
            integrity_results = [
                line.strip() for line in sqlite_output.splitlines()
                if line.strip() and not line.strip().endswith(".db")
            ]
            if not integrity_results or any(line != "ok" for line in integrity_results):
                failures.append("SQLite integrity output requires review")
        except Exception as exc:
            failures.append("SQLite integrity check unavailable: %s" % exc)
        report = {
            "conclusion": "FAIL" if failures else "PASS_WITH_PERIPHERAL_LIMITATIONS",
            "failures": failures, "health": health, "kernel_anomalies": anomalies,
            "samples": len(self.samples), "reachable_samples": len(reachable),
            "events": self.events,
            "sqlite_integrity": sqlite_output,
            "limitations": [
                "No CANopen, Modbus, or EtherCAT slave was attached; interoperability is not passed.",
                "Physical touch accuracy remains pending unless five real click events are separately recorded.",
                "This development image is not IEC 62443 production-security certified.",
                "RK3568/T536 OCI limits, power-loss recovery, and hardware load remain pending.",
            ],
        }
        self.save_json("final/report.json", report)
        lines = ["# T153 acceptance report", "", "Conclusion: **%s**" % report["conclusion"], ""]
        lines += ["- %s" % item for item in (failures or report["limitations"])]
        (self.output / "final" / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("manifest", "flash", "functional", "soak", "final", "all"))
    parser.add_argument("--image", default=str(SDK_DIR / "out/t153_linux_omnigate_uart0.img"))
    parser.add_argument("--partitions", default=str(SDK_DIR / "device/config/chips/t153/configs/omnigate/buildroot/sys_partition.fex"))
    parser.add_argument("--output")
    parser.add_argument("--lynx-url", default="http://127.0.0.1:18765/mcp")
    parser.add_argument("--serial-port", default="COM19")
    parser.add_argument("--serial-handle", help="reuse an existing LYNX serial handle")
    parser.add_argument("--board-transport", choices=("auto", "adb", "serial"),
                        default="auto")
    parser.add_argument("--board-host", help="board IP/hostname for SSH, screenshots, and soak")
    parser.add_argument("--ssh-user", default="root")
    parser.add_argument("--duration-hours", type=float, default=24.0)
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--fault-hour", type=float, default=1.0)
    parser.add_argument("--reboot-hour", type=float, default=12.0)
    args = parser.parse_args()
    runner = Runner(args)
    runner.build_manifest()
    if args.phase in ("flash", "all"):
        runner.flash()
    if args.phase in ("functional", "all"):
        runner.functional()
    if args.phase in ("soak", "all"):
        runner.soak()
    if args.phase in ("final", "all"):
        report = runner.final_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    print(runner.output)


if __name__ == "__main__":
    main()
