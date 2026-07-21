#!/usr/bin/env python3
"""LangChain StructuredTool wrappers for serial access."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from serial_core import (
    SerialSession,
    auto_select_serial_port,
    list_serial_ports_detail,
    make_serial_config,
)

_SESSIONS = {}


class OpenSerialInput(BaseModel):
    port: Optional[str] = Field(default=None, description="串口设备路径，例如 /dev/ttyUSB0")
    baudrate: int = Field(default=115200, description="波特率")
    timeout: float = Field(default=1.0, description="读超时秒数")
    write_timeout: float = Field(default=1.0, description="写超时秒数")
    bytesize: str = Field(default="8", description="数据位: 5/6/7/8")
    parity: str = Field(default="N", description="校验位: N/E/O/M/S")
    stopbits: str = Field(default="1", description="停止位: 1/1.5/2")
    xonxoff: bool = Field(default=False, description="软件流控")
    rtscts: bool = Field(default=False, description="硬件流控 RTS/CTS")
    dsrdtr: bool = Field(default=False, description="硬件流控 DSR/DTR")
    auto_select: bool = Field(default=False, description="是否自动选串口")
    vid: str = Field(default="", description="可选，目标 VID，例如 1a86")
    pid: str = Field(default="", description="可选，目标 PID，例如 55d4")
    serial_number: str = Field(default="", description="可选，目标序列号")
    product: str = Field(default="", description="可选，产品名关键字")
    description: str = Field(default="", description="可选，描述关键字")


class SerialCommandInput(BaseModel):
    port: str = Field(description="串口设备路径")
    command: str = Field(description="要发送的命令，不需要换行")
    max_wait_sec: float = Field(default=5.0, description="最大等待输出秒数")


class ReadSerialInput(BaseModel):
    port: str = Field(description="串口设备路径")


def lc_list_ports() -> str:
    ports = list_serial_ports_detail()
    if not ports:
        return "未发现串口设备"
    lines = []
    for item in ports:
        lines.append(
            f"{item['device']} | desc={item['description']} | vid={item['vid']} | pid={item['pid']} | sn={item['serial_number']}"
        )
    return "\n".join(lines)


def lc_open_serial(
    port: Optional[str] = None,
    baudrate: int = 115200,
    timeout: float = 1.0,
    write_timeout: float = 1.0,
    bytesize: str = "8",
    parity: str = "N",
    stopbits: str = "1",
    xonxoff: bool = False,
    rtscts: bool = False,
    dsrdtr: bool = False,
    auto_select: bool = False,
    vid: str = "",
    pid: str = "",
    serial_number: str = "",
    product: str = "",
    description: str = "",
) -> str:
    target_port = port
    if auto_select or not target_port:
        target_port = auto_select_serial_port(
            vid=vid,
            pid=pid,
            serial_number=serial_number,
            product=product,
            description=description,
        )
    cfg = make_serial_config(
        port=target_port,
        baudrate=baudrate,
        timeout=timeout,
        write_timeout=write_timeout,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        xonxoff=xonxoff,
        rtscts=rtscts,
        dsrdtr=dsrdtr,
    )
    sess = SerialSession(cfg)
    sess.open()
    _SESSIONS[target_port] = sess
    return (
        f"串口已打开: {target_port} @ {baudrate}, bytesize={bytesize}, parity={parity}, "
        f"stopbits={stopbits}, xonxoff={xonxoff}, rtscts={rtscts}, dsrdtr={dsrdtr}"
    )


def lc_send_command(port: str, command: str, max_wait_sec: float = 5.0) -> str:
    if port not in _SESSIONS:
        return f"串口未打开: {port}，请先调用 open_serial"
    out = _SESSIONS[port].run_command(command, max_wait_sec=max_wait_sec)
    return out or "(无输出)"


def lc_close_serial(port: str) -> str:
    sess = _SESSIONS.pop(port, None)
    if not sess:
        return f"串口未打开: {port}"
    sess.close()
    return f"串口已关闭: {port}"


def lc_read_serial(port: str) -> str:
    if port not in _SESSIONS:
        return f"串口未打开: {port}，请先调用 open_serial"
    out = _SESSIONS[port].read_available_text()
    return out or "(无输出)"


def build_langchain_tools():
    from langchain_core.tools import StructuredTool

    return [
        StructuredTool.from_function(
            name="list_serial_ports",
            description="列出 Linux 可用串口设备",
            func=lc_list_ports,
        ),
        StructuredTool.from_function(
            name="open_serial",
            description="打开串口连接",
            func=lc_open_serial,
            args_schema=OpenSerialInput,
        ),
        StructuredTool.from_function(
            name="send_serial_command",
            description="发送串口命令并读取输出",
            func=lc_send_command,
            args_schema=SerialCommandInput,
        ),
        StructuredTool.from_function(
            name="close_serial",
            description="关闭串口连接",
            func=lc_close_serial,
            args_schema=ReadSerialInput,
        ),
        StructuredTool.from_function(
            name="read_serial_output",
            description="读取串口当前缓存输出（不发送命令）",
            func=lc_read_serial,
            args_schema=ReadSerialInput,
        ),
    ]
