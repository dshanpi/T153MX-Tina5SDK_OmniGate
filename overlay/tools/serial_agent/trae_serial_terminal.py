#!/usr/bin/env python3
"""Serial terminal CLI for Trae AI terminal integration."""

from __future__ import annotations

import argparse
import json
import os
import select
import sys
import threading
import time
import tty
import termios
from typing import Dict, List
from datetime import datetime

from serial_core import (
    SerialSession,
    auto_select_serial_port,
    list_serial_ports_detail,
    make_serial_config,
)


def _bool_flag(text: str) -> bool:
    v = text.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid bool value: {text}")


def _print_scan(items: List[Dict[str, str]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    if not items:
        print("未发现串口设备")
        return
    for item in items:
        print(
            f"{item['device']} | desc={item['description']} | vid={item['vid']} "
            f"| pid={item['pid']} | sn={item['serial_number']}"
        )


def cmd_scan(args: argparse.Namespace) -> int:
    _print_scan(list_serial_ports_detail(), as_json=args.json)
    return 0


def _build_session(args: argparse.Namespace) -> SerialSession:
    target_port = _resolve_port(args)
    args.port = target_port
    cfg = make_serial_config(
        port=target_port,
        baudrate=args.baudrate,
        timeout=args.timeout,
        write_timeout=args.write_timeout,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
        xonxoff=args.xonxoff,
        rtscts=args.rtscts,
        dsrdtr=args.dsrdtr,
    )
    return SerialSession(cfg)


def _resolve_port(args: argparse.Namespace) -> str:
    if args.port:
        return args.port
    if args.auto_select or args.vid or args.pid or args.serial_number or args.product or args.description:
        return auto_select_serial_port(
            vid=args.vid,
            pid=args.pid,
            serial_number=args.serial_number,
            product=args.product,
            description=args.description,
        )
    raise ValueError("请指定 --port，或使用 --auto-select/--vid/--pid/--serial-number")


def _append_log(path: str, direction: str, payload: bytes) -> None:
    if not path or not payload:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    body = payload.decode("utf-8", errors="replace")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{direction}] {body}")


def cmd_io(args: argparse.Namespace) -> int:
    sess = _build_session(args)
    try:
        sess.open()
        print(f"[serial] connected: {args.port}@{args.baudrate}")
        if args.send is not None:
            out = sess.run_command(args.send, max_wait_sec=args.max_wait_sec)
        else:
            out = sess.read_until_quiet(max_sec=args.max_wait_sec)
        print(out if out else "(无输出)")
        return 0
    finally:
        sess.close()


def _run_raw_terminal(sess: SerialSession, args: argparse.Namespace, banner_name: str) -> int:
    if not sys.stdin.isatty():
        raise RuntimeError(f"{banner_name} 需要在交互式 TTY 终端中运行")

    fd = sys.stdin.fileno()
    old_term = termios.tcgetattr(fd)
    print(
        f"[{banner_name}] connected: {args.port}@{args.baudrate}, bytesize={args.bytesize}, "
        f"parity={args.parity}, stopbits={args.stopbits}, xonxoff={args.xonxoff}, "
        f"rtscts={args.rtscts}, dsrdtr={args.dsrdtr}"
    )
    print(f"[{banner_name}] 长连接透传已开启（支持 Tab 补齐），按 Ctrl+] 退出。")

    try:
        sess.open()
        tty.setraw(fd)
        while True:
            out = sess.read_available_text()
            if out:
                sys.stdout.write(out)
                sys.stdout.flush()
                _append_log(args.log_file, "RX", out.encode("utf-8", errors="replace"))

            rlist, _, _ = select.select([fd], [], [], 0.02)
            if fd in rlist:
                data = os.read(fd, 1024)
                if not data:
                    break
                # Ctrl+] exits local terminal without sending it to target.
                if b"\x1d" in data:
                    head = data.split(b"\x1d", 1)[0]
                    if head:
                        sess.write_bytes(head)
                        _append_log(args.log_file, "TX", head)
                    break
                sess.write_bytes(data)
                _append_log(args.log_file, "TX", data)
        return 0
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_term)
        sess.close()
        print(f"\n[{banner_name}] disconnected")


def cmd_terminal(args: argparse.Namespace) -> int:
    sess = _build_session(args)
    return _run_raw_terminal(sess, args, "serial")


def cmd_terminal_raw(args: argparse.Namespace) -> int:
    sess = _build_session(args)
    return _run_raw_terminal(sess, args, "serial-raw")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="扫描和访问 USB 串口设备，可直接在 Trae AI 终端中调用。"
    )
    sub = parser.add_subparsers(dest="subcmd", required=True)

    scan = sub.add_parser("scan", help="扫描串口设备")
    scan.add_argument("--json", action="store_true", help="以 JSON 输出")
    scan.set_defaults(func=cmd_scan)

    for name in ("io", "terminal", "terminal-raw"):
        p = sub.add_parser(name, help="串口输入输出")
        p.add_argument("--port", default=None, help="设备节点，例如 /dev/ttyACM0")
        p.add_argument("--auto-select", action="store_true", help="自动选择串口")
        p.add_argument("--vid", default="", help="匹配 VID，例如 1a86")
        p.add_argument("--pid", default="", help="匹配 PID，例如 55d4")
        p.add_argument("--serial-number", default="", help="匹配序列号")
        p.add_argument("--product", default="", help="匹配产品名关键字")
        p.add_argument("--description", default="", help="匹配描述关键字")
        p.add_argument("--baudrate", type=int, default=115200, help="波特率")
        p.add_argument("--timeout", type=float, default=1.0, help="读超时")
        p.add_argument("--write-timeout", type=float, default=1.0, help="写超时")
        p.add_argument("--bytesize", default="8", choices=["5", "6", "7", "8"], help="数据位")
        p.add_argument("--parity", default="N", choices=["N", "E", "O", "M", "S"], help="校验位")
        p.add_argument("--stopbits", default="1", choices=["1", "1.5", "2"], help="停止位")
        p.add_argument("--xonxoff", type=_bool_flag, default=False, help="软件流控")
        p.add_argument("--rtscts", type=_bool_flag, default=False, help="RTS/CTS 流控")
        p.add_argument("--dsrdtr", type=_bool_flag, default=False, help="DSR/DTR 流控")
        p.add_argument("--max-wait-sec", type=float, default=3.0, help="输出等待时间")
        p.add_argument("--log-file", default="", help="可选，串口日志文件路径")

    io = sub.choices["io"]
    io.add_argument("--send", default=None, help="一次性发送并读取输出")
    io.set_defaults(func=cmd_io)

    sub.choices["terminal"].set_defaults(func=cmd_terminal)
    sub.choices["terminal-raw"].set_defaults(func=cmd_terminal_raw)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
