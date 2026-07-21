# T153 串口独占代理使用规范

## 目标

T153 调试时避免用户终端、AI、脚本同时抢占 `/dev/ttyACM0`。

固定采用 single-owner serial-agent 模式：

```text
/dev/ttyACM0 (1a86:55d5 USB Quad_Serial)
   |
serial_agent_daemon.py 独占串口
   |
   +-- /tmp/a133-serial.log 持续日志
   +-- /tmp/a133-serial.sock 给 AI/脚本发命令
   +-- 127.0.0.1:23334 给用户终端实时查看/输入 raw serial
```

## 规则

- 只有 `serial_agent_daemon.py` 可以直接打开串口设备。
- 用户不要再用 `picocom`、`minicom`、`screen` 直接打开同一个串口。
- AI 不要直接打开串口，只能通过 `serial_agent_client.py` 操作。
- 用户终端通过 TCP client：`nc 127.0.0.1 23334`。
- daemon 持续写 `/tmp/a133-serial.log`，用于回溯启动日志。

## 启动 daemon

T153 当前常用节点是 `/dev/ttyACM0`（USB Quad_Serial `1a86:55d5`），启动：

```sh
cd /home/ubuntu/T153MX/T153_Tina_V1.0/tools/serial_agent
sudo python3 serial_agent_daemon.py --port /dev/ttyACM0 --baudrate 115200 --tcp-port 23334
```

启动成功标志：TCP 23334 监听 + log 文件写入。

## 用户独立终端连接 (nc)

用户可以在任意终端执行：

```sh
nc 127.0.0.1 23334
```

说明：
- 退出 `nc` 不会关闭 daemon。
- daemon 仍然继续持有串口并记录日志。
- 多个 TCP client 可以看日志，但手动输入时要避免多人同时输入命令。

## AI/脚本操作方式

```sh
cd /home/ubuntu/T153MX/T153_Tina_V1.0
python3 tools/serial_agent/serial_agent_client.py status
python3 tools/serial_agent/serial_agent_client.py tail -n 120
python3 tools/serial_agent/serial_agent_client.py cmd 'pwd' --wait 1.0
python3 tools/serial_agent/serial_agent_client.py cmd 'dmesg | tail -30' --wait 1.5
python3 tools/serial_agent/serial_agent_client.py cmd 'lsmod | grep aic' --wait 1.0
python3 tools/serial_agent/serial_agent_client.py cmd 'ifconfig wlan0' --wait 1.2
```

发送原始输入：

```sh
python3 tools/serial_agent/serial_agent_client.py write 'reboot efex' --enter
python3 tools/serial_agent/serial_agent_client.py write '\x03' --enter
```

停止 daemon：

```sh
python3 tools/serial_agent/serial_agent_client.py stop
```

## 烧录前切 FEL 模式

若板子当前在 Linux shell，通过 daemon 发送 `reboot efex` 进入烧录模式：

```sh
python3 tools/serial_agent/serial_agent_client.py write 'reboot efex' --enter
```

等待板子重启后，检查 FEL 设备：

```sh
lsusb | grep 1f3a
sudo tools/OpenixCLI/openixcli scan -l
```

## 串口乱码恢复

若串口输出全部变成 base64 乱码（常见于加载 aic8800 驱动后），原因是旧 shell 进程卡住。恢复方法：

```sh
# 通过 ADB 杀掉旧 shell，init 会自动重启
sudo adb shell "kill -9 \$(ps | grep 'bin/sh\|bin/bash' | grep -v grep | head -1 | awk '{print \$1}')"
```

重启 daemon 后串口恢复清晰。

## ADB 备用通道

当串口输出不可读时，使用 ADB 作为补充：

```sh
sudo adb kill-server && sudo adb start-server && sudo adb devices
sudo adb shell "dmesg | tail -30"
sudo adb shell "lsmod | grep aic"
sudo adb push <local_file> <remote_path>
```

ADB 设备识别：`18d1:0002` Google Configfs ffs gadget。

## 后续调试约定

只要 serial-agent daemon 已启动，后续所有串口调试都通过：

```sh
python3 tools/serial_agent/serial_agent_client.py cmd '<command>' --wait <seconds>
```

不要再直接运行 `picocom`、`minicom`、`screen` 等直接打开串口。
