#!/usr/bin/env python3
"""Interactive serial helper based on pexpect + picocom."""

from __future__ import annotations

import shlex
from typing import Optional

import pexpect


class PexpectSerialTerminal:
    """Use picocom to handle interactive serial login/prompts."""

    def __init__(self, port: str, baudrate: int = 115200, timeout: int = 20) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._child: Optional[pexpect.spawn] = None

    def open(self) -> None:
        cmd = f"picocom -b {self.baudrate} {shlex.quote(self.port)}"
        self._child = pexpect.spawn(cmd, encoding="utf-8", timeout=self.timeout)
        self._child.expect([r"Terminal ready", r"FATAL", pexpect.TIMEOUT])

    def login(self, username: str, password: str, prompt: str = r"[#\$] ") -> str:
        self._require()
        self._child.sendline("")
        self._child.expect([r"login:", prompt], timeout=self.timeout)
        if "login:" in self._child.after:
            self._child.sendline(username)
            self._child.expect(r"Password:", timeout=self.timeout)
            self._child.sendline(password)
            self._child.expect(prompt, timeout=self.timeout)
        return self._child.before

    def run(self, command: str, prompt: str = r"[#\$] ") -> str:
        self._require()
        self._child.sendline(command)
        self._child.expect(prompt, timeout=self.timeout)
        return self._child.before

    def close(self) -> None:
        if self._child is not None:
            self._child.sendcontrol("a")
            self._child.sendcontrol("x")
            self._child.close(force=True)
            self._child = None

    def _require(self) -> None:
        if self._child is None:
            raise RuntimeError("terminal not opened")
