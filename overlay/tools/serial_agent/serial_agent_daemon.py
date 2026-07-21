#!/usr/bin/env python3
"""Single-owner serial daemon for A133 debug.

One daemon owns /dev/ttyUSBx. Users and AI clients talk to the daemon via:
- Unix socket: JSON line protocol for command automation.
- TCP socket: simple interactive terminal, usable with nc/telnet.
- Log file: continuous serial RX log.
"""

import argparse
import json
import os
import queue
import selectors
import signal
import socket
import sys
import threading
import time
from collections import deque
from pathlib import Path

try:
    import serial
except ImportError as exc:
    print("missing dependency: pyserial. install with: pip3 install pyserial", file=sys.stderr)
    raise SystemExit(2) from exc


class SerialAgent:
    def __init__(self, port, baudrate, unix_sock, tcp_host, tcp_port, log_file, history_lines):
        self.port = port
        self.baudrate = baudrate
        self.unix_sock = Path(unix_sock)
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.log_file = Path(log_file)
        self.history = deque(maxlen=history_lines)
        self.history_lock = threading.Lock()
        self.write_q = queue.Queue()
        self.tcp_clients = set()
        self.tcp_lock = threading.Lock()
        self.stop = threading.Event()
        self.ser = None
        self.log_fp = None
        self.unix_server = None
        self.tcp_server = None

    def start(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.unix_sock.parent.mkdir(parents=True, exist_ok=True)
        if self.unix_sock.exists():
            self.unix_sock.unlink()
        self.log_fp = open(self.log_file, "ab", buffering=0)
        self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1, write_timeout=1)
        print(f"[serial-agent] opened {self.port} @ {self.baudrate}")
        print(f"[serial-agent] unix socket: {self.unix_sock}")
        print(f"[serial-agent] tcp terminal: {self.tcp_host}:{self.tcp_port}")
        print(f"[serial-agent] log file: {self.log_file}")
        threading.Thread(target=self._serial_reader, daemon=True).start()
        threading.Thread(target=self._serial_writer, daemon=True).start()
        threading.Thread(target=self._unix_loop, daemon=True).start()
        threading.Thread(target=self._tcp_loop, daemon=True).start()
        while not self.stop.is_set():
            time.sleep(0.2)
        self.close()

    def close(self):
        try:
            if self.unix_server:
                self.unix_server.close()
            if self.tcp_server:
                self.tcp_server.close()
            if self.ser:
                self.ser.close()
            if self.log_fp:
                self.log_fp.close()
            if self.unix_sock.exists():
                self.unix_sock.unlink()
        except Exception:
            pass

    def _append_rx(self, data: bytes):
        if not data:
            return
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log_fp.write(data)
        text = data.decode("utf-8", "replace")
        with self.history_lock:
            for line in text.splitlines():
                self.history.append(f"{ts} {line}")
        with self.tcp_lock:
            dead = []
            for c in self.tcp_clients:
                try:
                    c.sendall(data)
                except OSError:
                    dead.append(c)
            for c in dead:
                self.tcp_clients.discard(c)
                try:
                    c.close()
                except OSError:
                    pass

    def _serial_reader(self):
        while not self.stop.is_set():
            try:
                data = self.ser.read(4096)
                if data:
                    self._append_rx(data)
            except Exception as exc:
                self._append_rx(f"\n[serial-agent] reader error: {exc}\n".encode())
                time.sleep(0.5)

    def _serial_writer(self):
        while not self.stop.is_set():
            try:
                data = self.write_q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self.ser.write(data)
                self.ser.flush()
            except Exception as exc:
                self._append_rx(f"\n[serial-agent] writer error: {exc}\n".encode())

    def _unix_loop(self):
        self.unix_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.unix_server.bind(str(self.unix_sock))
        os.chmod(self.unix_sock, 0o666)
        self.unix_server.listen(8)
        while not self.stop.is_set():
            try:
                conn, _ = self.unix_server.accept()
                threading.Thread(target=self._handle_unix_client, args=(conn,), daemon=True).start()
            except OSError:
                break

    def _handle_unix_client(self, conn):
        with conn:
            f = conn.makefile("rwb", buffering=0)
            for raw in f:
                try:
                    req = json.loads(raw.decode())
                    resp = self._handle_request(req)
                except Exception as exc:
                    resp = {"ok": False, "error": str(exc)}
                f.write((json.dumps(resp, ensure_ascii=False) + "\n").encode())

    def _handle_request(self, req):
        action = req.get("action")
        if action == "write":
            data = req.get("data", "")
            if req.get("enter", False):
                data += "\n"
            self.write_q.put(data.encode())
            return {"ok": True}
        if action == "cmd":
            cmd = req.get("cmd", "")
            wait = float(req.get("wait", 0.8))
            before = self._history_snapshot()
            self.write_q.put((cmd + "\n").encode())
            time.sleep(wait)
            after = self._history_snapshot()
            return {"ok": True, "output": "\n".join(after[len(before):])}
        if action == "tail":
            n = int(req.get("lines", 120))
            return {"ok": True, "output": "\n".join(self._history_snapshot()[-n:])}
        if action == "status":
            return {
                "ok": True,
                "port": self.port,
                "baudrate": self.baudrate,
                "log_file": str(self.log_file),
                "unix_sock": str(self.unix_sock),
                "tcp": f"{self.tcp_host}:{self.tcp_port}",
                "tcp_clients": len(self.tcp_clients),
            }
        if action == "stop":
            self.stop.set()
            return {"ok": True}
        return {"ok": False, "error": f"unknown action: {action}"}

    def _history_snapshot(self):
        with self.history_lock:
            return list(self.history)

    def _tcp_loop(self):
        self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server.bind((self.tcp_host, self.tcp_port))
        self.tcp_server.listen(8)
        while not self.stop.is_set():
            try:
                conn, addr = self.tcp_server.accept()
                threading.Thread(target=self._handle_tcp_client, args=(conn, addr), daemon=True).start()
            except OSError:
                break

    def _handle_tcp_client(self, conn, addr):
        conn.setblocking(False)
        with self.tcp_lock:
            self.tcp_clients.add(conn)
        try:
            banner = (
                f"\r\n[serial-agent] connected from {addr[0]}:{addr[1]}\r\n"
                "[serial-agent] Ctrl-] then quit your nc/telnet client to exit.\r\n\r\n"
            )
            conn.sendall(banner.encode())
            with self.history_lock:
                if self.history:
                    history_tail = list(self.history)[-80:]
                    conn.sendall(("\r\n".join(history_tail) + "\r\n").encode())
            sel = selectors.DefaultSelector()
            sel.register(conn, selectors.EVENT_READ)
            while not self.stop.is_set():
                for key, _ in sel.select(timeout=0.2):
                    try:
                        data = key.fileobj.recv(4096)
                    except OSError:
                        data = b""
                    if not data:
                        return
                    self.write_q.put(data)
        finally:
            with self.tcp_lock:
                self.tcp_clients.discard(conn)
            try:
                conn.close()
            except OSError:
                pass


def main():
    ap = argparse.ArgumentParser(description="Single-owner serial daemon")
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baudrate", type=int, default=115200)
    ap.add_argument("--unix-sock", default="/tmp/a133-serial.sock")
    ap.add_argument("--tcp-host", default="127.0.0.1")
    ap.add_argument("--tcp-port", type=int, default=23333)
    ap.add_argument("--log-file", default="/tmp/a133-serial.log")
    ap.add_argument("--history-lines", type=int, default=2000)
    args = ap.parse_args()
    agent = SerialAgent(args.port, args.baudrate, args.unix_sock, args.tcp_host, args.tcp_port, args.log_file, args.history_lines)
    signal.signal(signal.SIGTERM, lambda *_: agent.stop.set())
    signal.signal(signal.SIGINT, lambda *_: agent.stop.set())
    agent.start()


if __name__ == "__main__":
    main()
