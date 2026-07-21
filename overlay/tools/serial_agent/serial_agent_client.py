#!/usr/bin/env python3
"""Client for serial_agent_daemon.py."""

import argparse
import json
import socket
import sys


def request(sock_path, payload):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    with s:
        s.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    return json.loads(data.decode())


def main():
    ap = argparse.ArgumentParser(description="serial-agent client")
    ap.add_argument("--sock", default="/tmp/a133-serial.sock")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status")
    p = sub.add_parser("tail")
    p.add_argument("-n", "--lines", type=int, default=120)
    p = sub.add_parser("write")
    p.add_argument("data")
    p.add_argument("--enter", action="store_true")
    p = sub.add_parser("cmd")
    p.add_argument("command")
    p.add_argument("--wait", type=float, default=0.8)
    p = sub.add_parser("stop")
    args = ap.parse_args()

    if args.cmd == "status":
        payload = {"action": "status"}
    elif args.cmd == "tail":
        payload = {"action": "tail", "lines": args.lines}
    elif args.cmd == "write":
        payload = {"action": "write", "data": args.data, "enter": args.enter}
    elif args.cmd == "cmd":
        payload = {"action": "cmd", "cmd": args.command, "wait": args.wait}
    elif args.cmd == "stop":
        payload = {"action": "stop"}
    else:
        raise SystemExit(2)

    resp = request(args.sock, payload)
    if not resp.get("ok"):
        print(resp.get("error", resp), file=sys.stderr)
        raise SystemExit(1)
    if "output" in resp:
        print(resp["output"])
    else:
        print(json.dumps(resp, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
