---
name: "system-sdk-ai-default"
description: "Builds T153 Linux SDK, packs t153_linux_omnigate_uart0.img, flashes it, and validates boot over serial. Invoke for default SDK AI development and bring-up."
---

# 系统SDK AI开发 默认使用

本 Skill 用于 T153 SDK 的默认 AI 开发流程，覆盖从清理配置、编译打包到烧录与串口启动验证的完整闭环。

## 触发场景

在以下场景优先调用本 Skill：
- 首次搭建或切换 SDK 编译环境
- 需要生成并烧录 `t153_linux_omnigate_uart0.img`
- 需要验证固件是否正常启动进入 Linux shell
- 需要统一团队的标准操作流程

## 目标产物

- 固件镜像：`out/t153_linux_omnigate_uart0.img`
- 烧录结果：OpenixCLI 正常完成
- 启动结果：串口进入 Linux shell，`uname -a` 可执行
- OpenixCLI 路径：`tools/OpenixCLI/openixcli`（相对 SDK 根目录）

## 基础环境准备（首次机器）

### A. 安装依赖包

```bash
sudo apt update
sudo apt install build-essential subversion git-core libncurses5-dev zlib1g-dev gawk flex quilt \
  libssl-dev xsltproc libxml-parser-perl mercurial bzr ecj cvs unzip lib32z1 lib32z1-dev \
  lib32stdc++6 libstdc++6 bison -y
```

### B. VMware 场景安装共享工具（可选）

```bash
sudo apt install open-vm-tools open-vm-tools-desktop -y
sudo reboot
```

### C. 环境连通性检查

```bash
git --version
python3 --version
```

## 标准流程

### 1) 进入 SDK 根目录并清理旧配置

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0
rm -f .buildconfig
```

### 2) 初始化环境

```bash
source build/envsetup.sh
```

初始化成功后，确认快捷命令可用：`croot cboot ckernel cbr cdts cout`。

### 3) 配置编译选项（首次）

```bash
./build.sh config
```

按以下选项选择：
- platform: `linux`（输入 `1`）
- linux_dev: `buildroot`（输入 `1`）
- ic: `t153`（输入 `0`）
- board: `omnigate`（输入 `12`）
- flash: `default`（输入 `0`）
- kern_name: `linux-5.10-origin`（输入 `0`）

### 4) 编译固件

```bash
./build.sh
```

编译内容包括：
- U-Boot
- Linux Kernel
- Buildroot RootFS
- C906 RTOS

### 5) 打包镜像

```bash
./build.sh pack
cout
ls -lh t153_linux_omnigate_uart0.img
```

### 6) 烧录前检查设备

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0
lsusb
sudo tools/OpenixCLI/openixcli scan -l
```

期望看到烧录设备：`1f3a:efe8`（FEL/FES）。

### 6.1) 若当前在 Tina Linux shell，直接切换烧录模式

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0/tools/serial_agent
sudo python3 trae_serial_terminal.py io \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --send "reboot efex"
```

说明：
- 该命令会让板子自动重启并进入 FEL/FES 烧录模式
- 随后回到 OpenixCLI 终端重新执行 `scan -l` 和 `flash`

### 7) 开启串口日志（建议新终端）

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0/tools/serial_agent
sudo python3 trae_serial_terminal.py terminal-raw \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --log-file /tmp/openix_serial.log
```

### 8) 执行烧录

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0
sudo tools/OpenixCLI/openixcli flash /home/ubuntu/T153MX/T153_Tina_V1.0/out/t153_linux_omnigate_uart0.img \
  --reconnect-timeout-sec 240 \
  --reconnect-interval-ms 300 \
  -v
```

### 9) 启动验证

烧录完成后通过串口观察启动，进入 Linux shell 后执行：

```sh
uname -a
```

出现内核版本信息即验证通过。

## U-Boot 进入方式

- 若需要进入 U-Boot 命令行，在启动 `auto` 倒计时 3 秒内按 `s` 或 `Ctrl+C`
- 进入 `=>` 后可执行 `efex` 手动切回烧录通道

## 串口联动命令（推荐）

### A. 串口实时透传 + 落盘

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0/tools/serial_agent
sudo python3 trae_serial_terminal.py terminal-raw \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --log-file /tmp/openix_serial.log
```

### B. 一次性串口验证

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0/tools/serial_agent
sudo python3 trae_serial_terminal.py io \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --send "uname -a"
```

## 异常恢复

### A. U-Boot 停在 `=>`

在串口输入：

```text
efex
```

设备会重新进入烧录通道，然后重新执行第 8 步烧录。

### B. `Device reconnect failed` 或 USB 抖动

- 保持第 8 步参数不变（已包含重连窗口）
- 再执行一次：
  - `sudo tools/OpenixCLI/openixcli scan -l`
  - `sudo tools/OpenixCLI/openixcli flash ... -v`

### C. 出现 `cbw signature ... bad`

- 先确认使用的是已修复版 OpenixCLI（包含 AWUC magic 修复）
- 先在串口执行 `reboot efex`，再执行 `scan -l` 与 `flash -v`
- 若仍失败，抓取 `/tmp/openix_serial.log` 和 `dmesg` 同步分析

### D. 需要查看详细证据

- 串口日志：`/tmp/openix_serial.log`
- 主机 USB 日志：`sudo dmesg | tail -n 120`

## 本 Skill 依赖能力

- `serial_agent` 支持：
  - 自动选口（VID/PID/SN）
  - `terminal-raw` 字符级透传
  - `--log-file` 收发双向日志
- `OpenixCLI` 支持：
  - `--reconnect-timeout-sec` / `--reconnect-interval-ms`
  - FES 首次握手失败自动重试一次

## 常用编译命令速查

- `./build.sh`：编译全部
- `./build.sh bootloader`：仅 U-Boot
- `./build.sh kernel`：仅内核
- `./build.sh buildroot_rootfs`：仅 Buildroot
- `./build.sh menuconfig`：内核配置
- `./build.sh buildroot_menuconfig`：Buildroot 配置
- `./build.sh clean`：清理产物
- `./build.sh distclean`：彻底清理
