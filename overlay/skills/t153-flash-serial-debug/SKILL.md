---
name: "t153-flash-serial-debug"
description: "Standardizes T153 serial connection and firmware flashing workflow with recovery steps. Invoke when doing T153 bring-up, flashing, or USB/FEL/FES troubleshooting."
---

# T153 Flash And Serial Debug

本 Skill 用于统一 T153 硬件调试流程，覆盖：
- 串口连接与实时日志抓取
- OpenixCLI 固件烧录
- FEL -> FES 重连异常处理
- U-Boot 下 `efex` 手动回切烧录模式

## 何时调用

在以下场景应优先调用本 Skill：
- 需要给 T153 烧录新镜像
- 需要观察串口启动日志并和烧录联动调试
- 出现 `Device reconnect failed`、`cbw signature ... bad`、USB 枚举抖动等问题
- 需要形成可复用的 bring-up 标准操作步骤

## 前置条件

- 工作目录：`/home/ubuntu/T153MX/T153_Tina_V1.0`
- OpenixCLI 路径：`tools/OpenixCLI/openixcli`（相对 SDK 根目录）
- 串口设备（常见）：
  - 调试串口：`1a86:55d4` -> `/dev/ttyACM0`
  - 烧录口：`1f3a:efe8` (FEL/FES)
- 推荐以 `sudo` 运行烧录命令，避免 USB 权限问题

## 标准流程

### 1) 检查设备在位

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0
lsusb
sudo tools/OpenixCLI/openixcli scan -l
```

判定标准：
- `lsusb` 能看到 `1f3a:efe8`（烧录口）
- `scan -l` 能识别 `FEL` 或 `FES`

### 2) 打开串口透传并落盘日志（建议单独终端）

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0/tools/serial_agent
sudo python3 trae_serial_terminal.py terminal-raw \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --log-file /tmp/openix_serial.log
```

说明：
- `Ctrl+]` 退出 raw 模式
- `--log-file` 会记录 `[TX]/[RX]`，便于复盘

### 3) 执行烧录（主终端）

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0
sudo tools/OpenixCLI/openixcli flash /home/ubuntu/T153MX/T153_Tina_V1.0/out/t153_linux_omnigate_uart0.img \
  --reconnect-timeout-sec 240 \
  --reconnect-interval-ms 300 \
  -v
```

成功标志：
- `All partitions flashed successfully`
- `Device will reboot`

## 故障处理

### A. `Device reconnect failed`

- 先看串口是否已进入 `run usb efex`
- 检查 VM 透传稳定性（`dmesg | tail -n 80` 看 `1f3a:efe8` 是否频繁断连）
- 重新执行：
  - `sudo tools/OpenixCLI/openixcli scan -l`
  - 再次 `flash ... --reconnect-timeout-sec 240 --reconnect-interval-ms 300 -v`

### B. 串口停在 `=>`（U-Boot 提示符）

在串口终端输入：

```text
efex
```

设备会重新进入烧录通道，随后在主终端重跑 `openixcli flash ...`。

### C. 出现 `cbw signature ... bad`

- 优先判定为 USB 协议首包/透传抖动问题
- 先确保 `openixcli` 使用已修补版本（AWUC magic 修复）
- 再执行一次 `scan -l` + `flash -v`

## 会话结束建议产物

- 串口日志：`/tmp/openix_serial.log`
- 烧录终端日志（`-v` 输出）
- 失败时同时保存 `dmesg` 片段用于定位 VM USB 抖动
