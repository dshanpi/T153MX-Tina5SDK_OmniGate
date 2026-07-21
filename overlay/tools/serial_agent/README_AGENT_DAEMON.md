# Serial Agent Daemon

目标：只有一个进程独占 `/dev/ttyUSBx`，用户和 AI 都通过 client 访问，避免串口抢占。

## 启动 daemon

```sh
cd /home/ubuntu/A133-Tina5.0-v0.9/tools/serial_agent
python3 serial_agent_daemon.py --port /dev/ttyUSB0 --baudrate 115200
```

默认资源：

```text
Unix socket: /tmp/a133-serial.sock
TCP terminal: 127.0.0.1:23333
Log file: /tmp/a133-serial.log
```

## 用户终端连接

```sh
nc 127.0.0.1 23333
```

用户退出 `nc` 不会关闭 daemon，串口仍由 daemon 保持。

## AI/脚本调用

```sh
python3 serial_agent_client.py status
python3 serial_agent_client.py tail -n 120
python3 serial_agent_client.py cmd 'ps | grep -E "lv|aidesktop|adbd"' --wait 1.2
python3 serial_agent_client.py cmd 'logread | tail -100' --wait 1.5
python3 serial_agent_client.py write 'reboot' --enter
```

## 停止 daemon

```sh
python3 serial_agent_client.py stop
```

## 规则

- 不要再让 `picocom/minicom/screen` 直接打开同一个串口。
- 用户、AI、脚本都通过 daemon 访问。
- daemon 持续写 `/tmp/a133-serial.log`。
- TCP 终端适合用户实时看和手动输入；Unix socket 适合 AI 自动命令。
