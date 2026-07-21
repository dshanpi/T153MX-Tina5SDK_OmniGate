#!/usr/bin/env python3
"""Auto flash A133 image via USB and verify boot via serial."""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional

from serial_core import auto_select_serial_port, make_serial_config, SerialSession


SDK_ROOT = "/home/ubuntu/A133-Tina5.0-v0.9"
DEFAULT_OPENIXCLI = f"{SDK_ROOT}/tools/OpenixCLI/target/release/openixcli"

# A133 defaults
DEFAULT_VID = "1a86"
DEFAULT_PID = "55d5"  # USB Quad Serial for A133
DEFAULT_BAUDRATE = 115200
DEFAULT_SERIAL_PORT = "/dev/ttyACM1"


def _latest_image() -> Optional[str]:
    imgs = glob.glob(f"{SDK_ROOT}/out/*.img")
    if not imgs:
        return None
    imgs.sort(key=os.path.getmtime, reverse=True)
    return imgs[0]


def _print(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_scan(openixcli: str, use_sudo: bool) -> tuple[int, str]:
    cmd = [openixcli, "scan", "-l"]
    if use_sudo:
        cmd.insert(0, "sudo")
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def has_fel_or_fes(scan_output: str) -> bool:
    return bool(re.search(r"\b(FEL|FES)\b|1f3a:efe8|Mode:\s*(FEL|FES)", scan_output, re.I))


def send_reboot_efex(port: str, baudrate: int) -> None:
    cfg = make_serial_config(port=port, baudrate=baudrate, timeout=1.0, write_timeout=1.0)
    sess = SerialSession(cfg)
    try:
        sess.open()
        sess.write_line("reboot efex")
        time.sleep(0.4)
        _ = sess.read_until_quiet(max_sec=1.2)
    finally:
        sess.close()


def try_uboot_efex(port: str, baudrate: int) -> None:
    """Best-effort fallback: reboot, break autoboot, send efex in U-Boot."""
    cfg = make_serial_config(port=port, baudrate=baudrate, timeout=0.2, write_timeout=1.0)
    sess = SerialSession(cfg)
    try:
        sess.open()
        sess.write_line("reboot")
        # Give reboot command a moment, then spam break keys.
        time.sleep(0.8)
        for _ in range(30):
            sess.write_bytes(b"s")
            sess.write_bytes(b"\x03")  # Ctrl+C
            time.sleep(0.12)
        sess.write_line("efex")
        time.sleep(0.5)
    finally:
        sess.close()


def flash_image(
    openixcli: str,
    image: str,
    use_sudo: bool,
    reconnect_timeout: int,
    reconnect_interval: int,
) -> tuple[int, bool]:
    cmd = [
        openixcli,
        "flash",
        image,
        "--reconnect-timeout-sec",
        str(reconnect_timeout),
        "--reconnect-interval-ms",
        str(reconnect_interval),
        "-v",
    ]
    if use_sudo:
        cmd.insert(0, "sudo")

    _print("开始烧录镜像...")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert p.stdout is not None

    success_mark = False
    for line in p.stdout:
        sys.stdout.write(line)
        if "All partitions flashed successfully" in line:
            success_mark = True

    rc = p.wait()
    return rc, success_mark


def verify_boot(
    serial_port: str,
    baudrate: int,
    boot_timeout_sec: int,
    max_uptime_sec: int,
) -> tuple[bool, str]:
    cfg = make_serial_config(port=serial_port, baudrate=baudrate, timeout=1.0, write_timeout=1.0)
    sess = SerialSession(cfg)
    start = time.time()
    boot_log = []
    try:
        sess.open()
        # Wait for board to finish reboot.
        while time.time() - start < boot_timeout_sec:
            out = sess.read_available_text()
            if out:
                boot_log.append(out)
                if any(k in out for k in ("login:", "# ", "$ ", "Starting kernel")):
                    break
            time.sleep(0.2)

        uname_out = sess.run_command("uname -a", max_wait_sec=4.0)
        date_out = sess.run_command("date '+%F %T %Z'", max_wait_sec=4.0)
        uptime_out = sess.run_command("cat /proc/uptime", max_wait_sec=4.0)
    finally:
        sess.close()

    uptime_val = None
    m = re.search(r"(\d+(?:\.\d+)?)", uptime_out)
    if m:
        uptime_val = float(m.group(1))

    ok_uname = "Linux" in uname_out
    ok_uptime = uptime_val is not None and uptime_val <= float(max_uptime_sec)

    detail = (
        f"uname={uname_out.strip() or '(empty)'}\n"
        f"date={date_out.strip() or '(empty)'}\n"
        f"uptime={uptime_out.strip() or '(empty)'}\n"
        f"uptime_limit={max_uptime_sec}s"
    )
    return (ok_uname and ok_uptime), detail


def main() -> int:
    parser = argparse.ArgumentParser(description="USB + 串口自动烧录并验证启动时间")
    parser.add_argument("--image", default="", help="镜像路径，默认自动选择 out/*.img 最新文件")
    parser.add_argument("--openixcli", default=DEFAULT_OPENIXCLI, help="openixcli 可执行文件路径")
    parser.add_argument("--serial-port", default="", help="串口设备，如 /dev/ttyACM0")
    parser.add_argument("--serial-vid", default=DEFAULT_VID, help="自动选串口 VID")
    parser.add_argument("--serial-pid", default=DEFAULT_PID, help="自动选串口 PID")
    parser.add_argument("--baudrate", type=int, default=115200, help="串口波特率")
    parser.add_argument("--scan-timeout-sec", type=int, default=30, help="等待 FEL/FES 超时秒数")
    parser.add_argument("--boot-timeout-sec", type=int, default=120, help="启动验证超时秒数")
    parser.add_argument("--max-uptime-sec", type=int, default=300, help="判定为刚启动的最大 uptime 秒数")
    parser.add_argument("--reconnect-timeout-sec", type=int, default=240, help="openixcli 重连超时")
    parser.add_argument("--reconnect-interval-ms", type=int, default=300, help="openixcli 重连间隔")
    parser.add_argument("--no-sudo", action="store_true", help="不使用 sudo")
    args = parser.parse_args()

    use_sudo = not args.no_sudo
    image = args.image or _latest_image()
    if not image:
        _print("未找到镜像，请先编译并打包产出 out/*.img")
        return 2
    if not os.path.exists(image):
        _print(f"镜像不存在: {image}")
        return 2
    if not os.path.exists(args.openixcli):
        _print(f"openixcli 不存在: {args.openixcli}")
        return 2

    serial_port = args.serial_port
    if not serial_port:
        serial_port = auto_select_serial_port(vid=args.serial_vid, pid=args.serial_pid)

    _print(f"镜像: {image}")
    _print(f"串口: {serial_port}@{args.baudrate}")
    _print("检查是否已在 FEL/FES...")

    rc, out = run_scan(args.openixcli, use_sudo=use_sudo)
    if rc == 0 and has_fel_or_fes(out):
        _print("已检测到 FEL/FES。")
    else:
        _print("未检测到 FEL/FES，尝试通过串口发送 reboot efex...")
        send_reboot_efex(serial_port, args.baudrate)

        deadline = time.time() + args.scan_timeout_sec
        while time.time() < deadline:
            rc, out = run_scan(args.openixcli, use_sudo=use_sudo)
            if rc == 0 and has_fel_or_fes(out):
                _print("设备已进入 FEL/FES。")
                break
            time.sleep(1.0)
        else:
            _print("reboot efex 未生效，尝试自动打断 U-Boot 并发送 efex...")
            try_uboot_efex(serial_port, args.baudrate)

            deadline = time.time() + args.scan_timeout_sec
            while time.time() < deadline:
                rc, out = run_scan(args.openixcli, use_sudo=use_sudo)
                if rc == 0 and has_fel_or_fes(out):
                    _print("设备已通过 U-Boot efex 进入 FEL/FES。")
                    break
                time.sleep(1.0)
            else:
                _print("等待 FEL/FES 超时。请手动在 U-Boot 输入 efex 后重试。")
                return 3

    flash_rc, flash_ok = flash_image(
        openixcli=args.openixcli,
        image=image,
        use_sudo=use_sudo,
        reconnect_timeout=args.reconnect_timeout_sec,
        reconnect_interval=args.reconnect_interval_ms,
    )
    if flash_rc != 0 or not flash_ok:
        _print(f"烧录失败: rc={flash_rc}, success_mark={flash_ok}")
        return 4

    _print("烧录完成，开始串口启动验证（uname/date/uptime）...")
    ok, detail = verify_boot(
        serial_port=serial_port,
        baudrate=args.baudrate,
        boot_timeout_sec=args.boot_timeout_sec,
        max_uptime_sec=args.max_uptime_sec,
    )
    _print(detail)
    if not ok:
        _print("启动验证失败：未满足 uname 或 uptime 条件")
        return 5

    _print("验证通过：系统可启动，且 uptime 在阈值内，判定为本次烧录生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
