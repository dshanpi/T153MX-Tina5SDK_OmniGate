#!/usr/bin/env python3
"""CrewAI Tool wrappers for serial access."""

from __future__ import annotations

from typing import Optional, Type

from pydantic import BaseModel, Field

from serial_core import (
    SerialSession,
    auto_select_serial_port,
    list_serial_ports_detail,
    make_serial_config,
)

_SESSIONS = {}


class OpenInput(BaseModel):
    port: Optional[str] = Field(None, description="串口设备路径，例如 /dev/ttyUSB0")
    baudrate: int = Field(115200, description="波特率")
    timeout: float = Field(1.0, description="读超时秒数")
    write_timeout: float = Field(1.0, description="写超时秒数")
    bytesize: str = Field("8", description="数据位: 5/6/7/8")
    parity: str = Field("N", description="校验位: N/E/O/M/S")
    stopbits: str = Field("1", description="停止位: 1/1.5/2")
    xonxoff: bool = Field(False, description="软件流控")
    rtscts: bool = Field(False, description="硬件流控 RTS/CTS")
    dsrdtr: bool = Field(False, description="硬件流控 DSR/DTR")
    auto_select: bool = Field(False, description="是否自动选串口")
    vid: str = Field("", description="可选，目标 VID，例如 1a86")
    pid: str = Field("", description="可选，目标 PID，例如 55d4")
    serial_number: str = Field("", description="可选，目标序列号")
    product: str = Field("", description="可选，产品名关键字")
    description: str = Field("", description="可选，描述关键字")


class CmdInput(BaseModel):
    port: str = Field(..., description="串口设备路径")
    command: str = Field(..., description="发送到串口的命令")
    max_wait_sec: float = Field(5.0, description="读取等待时间")


class CloseInput(BaseModel):
    port: str = Field(..., description="串口设备路径")


def _new_tool_base():
    from crewai.tools import BaseTool

    return BaseTool


def build_crewai_tools():
    BaseTool = _new_tool_base()

    class ListSerialPortsTool(BaseTool):
        name: str = "list_serial_ports"
        description: str = "列出 Linux 可用串口设备"
        args_schema: Type[BaseModel] = BaseModel

        def _run(self) -> str:
            ports = list_serial_ports_detail()
            if not ports:
                return "未发现串口设备"
            lines = []
            for item in ports:
                lines.append(
                    f"{item['device']} | desc={item['description']} | vid={item['vid']} | pid={item['pid']} | sn={item['serial_number']}"
                )
            return "\n".join(lines)

    class OpenSerialTool(BaseTool):
        name: str = "open_serial"
        description: str = "打开串口连接"
        args_schema: Type[BaseModel] = OpenInput

        def _run(
            self,
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

    class SendSerialCommandTool(BaseTool):
        name: str = "send_serial_command"
        description: str = "发送串口命令并读取输出"
        args_schema: Type[BaseModel] = CmdInput

        def _run(self, port: str, command: str, max_wait_sec: float = 5.0) -> str:
            if port not in _SESSIONS:
                return f"串口未打开: {port}，请先调用 open_serial"
            out = _SESSIONS[port].run_command(command, max_wait_sec=max_wait_sec)
            return out or "(无输出)"

    class CloseSerialTool(BaseTool):
        name: str = "close_serial"
        description: str = "关闭串口连接"
        args_schema: Type[BaseModel] = CloseInput

        def _run(self, port: str) -> str:
            sess = _SESSIONS.pop(port, None)
            if not sess:
                return f"串口未打开: {port}"
            sess.close()
            return f"串口已关闭: {port}"

    class ReadSerialOutputTool(BaseTool):
        name: str = "read_serial_output"
        description: str = "读取串口缓存输出（不发送命令）"
        args_schema: Type[BaseModel] = CloseInput

        def _run(self, port: str) -> str:
            if port not in _SESSIONS:
                return f"串口未打开: {port}，请先调用 open_serial"
            out = _SESSIONS[port].read_available_text()
            return out or "(无输出)"

    return [
        ListSerialPortsTool(),
        OpenSerialTool(),
        SendSerialCommandTool(),
        CloseSerialTool(),
        ReadSerialOutputTool(),
    ]
