#!/usr/bin/env python3
"""Serial access core for AI agents."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import serial
from serial import SerialException
from serial.tools import list_ports


@dataclass
class SerialConfig:
    port: str
    baudrate: int = 115200
    timeout: float = 1.0
    write_timeout: float = 1.0
    bytesize: int = serial.EIGHTBITS
    parity: str = serial.PARITY_NONE
    stopbits: int = serial.STOPBITS_ONE
    xonxoff: bool = False
    rtscts: bool = False
    dsrdtr: bool = False


class SerialSession:
    """Thin wrapper around pyserial with safe text I/O helpers."""

    def __init__(self, cfg: SerialConfig) -> None:
        self.cfg = cfg
        self._ser: Optional[serial.Serial] = None

    def open(self) -> None:
        if self._ser and self._ser.is_open:
            return
        self._ser = serial.Serial(
            port=self.cfg.port,
            baudrate=self.cfg.baudrate,
            timeout=self.cfg.timeout,
            write_timeout=self.cfg.write_timeout,
            bytesize=self.cfg.bytesize,
            parity=self.cfg.parity,
            stopbits=self.cfg.stopbits,
            xonxoff=self.cfg.xonxoff,
            rtscts=self.cfg.rtscts,
            dsrdtr=self.cfg.dsrdtr,
        )

    def close(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()

    def write_line(self, text: str, line_end: str = "\n") -> None:
        self._require_open()
        payload = (text + line_end).encode("utf-8", errors="ignore")
        self._ser.write(payload)
        self._ser.flush()

    def read_until_quiet(self, quiet_sec: float = 0.3, max_sec: float = 3.0) -> str:
        self._require_open()
        end_deadline = time.time() + max_sec
        last_data_ts = time.time()
        chunks: List[bytes] = []
        while time.time() < end_deadline:
            waiting = self._ser.in_waiting
            if waiting > 0:
                chunks.append(self._ser.read(waiting))
                last_data_ts = time.time()
            elif time.time() - last_data_ts >= quiet_sec:
                break
            else:
                time.sleep(0.02)
        return b"".join(chunks).decode("utf-8", errors="replace")

    def run_command(self, cmd: str, wait_quiet_sec: float = 0.4, max_wait_sec: float = 5.0) -> str:
        self.write_line(cmd)
        return self.read_until_quiet(wait_quiet_sec, max_wait_sec)

    def read_available_text(self) -> str:
        self._require_open()
        waiting = self._ser.in_waiting
        if waiting <= 0:
            return ""
        return self._ser.read(waiting).decode("utf-8", errors="replace")

    def write_text(self, text: str) -> None:
        self._require_open()
        self._ser.write(text.encode("utf-8", errors="ignore"))
        self._ser.flush()

    def write_bytes(self, payload: bytes) -> None:
        self._require_open()
        self._ser.write(payload)
        self._ser.flush()

    def _require_open(self) -> None:
        if not self._ser or not self._ser.is_open:
            raise SerialException("Serial port is not open")


def list_serial_ports() -> List[str]:
    return [item["device"] for item in list_serial_ports_detail()]


def list_serial_ports_detail() -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for p in sorted(list_ports.comports(), key=lambda x: x.device):
        vid = f"0x{p.vid:04x}" if p.vid is not None else ""
        pid = f"0x{p.pid:04x}" if p.pid is not None else ""
        items.append(
            {
                "device": p.device or "",
                "name": p.name or "",
                "description": p.description or "",
                "hwid": p.hwid or "",
                "vid": vid,
                "pid": pid,
                "serial_number": p.serial_number or "",
                "manufacturer": p.manufacturer or "",
                "product": p.product or "",
                "location": p.location or "",
                "interface": p.interface or "",
            }
        )
    return items


def resolve_bytesize(value: str) -> int:
    mapping = {
        "5": serial.FIVEBITS,
        "6": serial.SIXBITS,
        "7": serial.SEVENBITS,
        "8": serial.EIGHTBITS,
    }
    if value not in mapping:
        raise ValueError(f"unsupported bytesize: {value}, expected one of 5/6/7/8")
    return mapping[value]


def resolve_parity(value: str) -> str:
    v = value.upper()
    mapping = {
        "N": serial.PARITY_NONE,
        "E": serial.PARITY_EVEN,
        "O": serial.PARITY_ODD,
        "M": serial.PARITY_MARK,
        "S": serial.PARITY_SPACE,
    }
    if v not in mapping:
        raise ValueError("unsupported parity, expected one of N/E/O/M/S")
    return mapping[v]


def resolve_stopbits(value: str) -> float:
    mapping = {
        "1": serial.STOPBITS_ONE,
        "1.5": serial.STOPBITS_ONE_POINT_FIVE,
        "2": serial.STOPBITS_TWO,
    }
    if value not in mapping:
        raise ValueError("unsupported stopbits, expected one of 1/1.5/2")
    return mapping[value]


def make_serial_config(
    port: str,
    baudrate: int = 115200,
    timeout: float = 1.0,
    write_timeout: float = 1.0,
    bytesize: str = "8",
    parity: str = "N",
    stopbits: str = "1",
    xonxoff: bool = False,
    rtscts: bool = False,
    dsrdtr: bool = False,
) -> SerialConfig:
    return SerialConfig(
        port=port,
        baudrate=baudrate,
        timeout=timeout,
        write_timeout=write_timeout,
        bytesize=resolve_bytesize(bytesize),
        parity=resolve_parity(parity),
        stopbits=resolve_stopbits(stopbits),
        xonxoff=xonxoff,
        rtscts=rtscts,
        dsrdtr=dsrdtr,
    )


def auto_select_serial_port(
    vid: str = "",
    pid: str = "",
    serial_number: str = "",
    product: str = "",
    description: str = "",
) -> str:
    ports = list_serial_ports_detail()
    if not ports:
        raise ValueError("未发现串口设备")

    def _norm_hex(v: str) -> str:
        val = v.strip().lower()
        if not val:
            return ""
        return val if val.startswith("0x") else f"0x{val}"

    vid_n = _norm_hex(vid)
    pid_n = _norm_hex(pid)
    sn_n = serial_number.strip().lower()
    product_n = product.strip().lower()
    desc_n = description.strip().lower()
    has_filter = bool(vid_n or pid_n or sn_n or product_n or desc_n)

    candidates = ports
    if sn_n:
        candidates = [p for p in candidates if p["serial_number"].strip().lower() == sn_n]
    if vid_n:
        candidates = [p for p in candidates if p["vid"].strip().lower() == vid_n]
    if pid_n:
        candidates = [p for p in candidates if p["pid"].strip().lower() == pid_n]
    if product_n:
        candidates = [p for p in candidates if product_n in p["product"].strip().lower()]
    if desc_n:
        candidates = [p for p in candidates if desc_n in p["description"].strip().lower()]

    if has_filter and not candidates:
        raise ValueError("自动选口失败：未找到匹配 vid/pid/sn/product/description 的设备")

    # Prefer common USB serial nodes first.
    priority = sorted(
        candidates,
        key=lambda x: (
            0
            if x["device"].startswith("/dev/ttyACM")
            else 1
            if x["device"].startswith("/dev/ttyUSB")
            else 2,
            x["device"],
        ),
    )
    return priority[0]["device"]
