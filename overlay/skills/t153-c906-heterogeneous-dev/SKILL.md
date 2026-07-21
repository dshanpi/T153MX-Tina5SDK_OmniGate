---
name: "t153-c906-heterogeneous-dev"
description: "Validates T153 C906 AMP/RPMsg flow with remoteproc and amp_shell, and handles ioctl compatibility fallback. Invoke for C906 heterogeneous bring-up, rpmsg debugging, or amp_shell failures."
---

# T153 C906 异构小核开发

本 Skill 用于 T153 的 A7 Linux + C906 RTOS 异构开发联调，重点覆盖：
- remoteproc 启停与固件状态检查
- RPMsg 控制节点创建验证
- `amp_shell -d /dev/rpmsg_ctrl-c906_rproc@0` 实测
- `amp_shell` 与内核 ioctl 不兼容问题定位与修复

## 何时调用

- 需要验证 C906 小核是否被 Linux 正常拉起
- 需要跑通 AMP/RPMsg 通信链路
- `amp_shell` 提示 `raw device init failed` / `Failed to create auto free endpoint`
- 需要形成可复用的异构开发标准流程

## 架构要点（开发侧）

- A7 Linux 侧通过 `remoteproc` 管理 C906 生命周期（load/start/stop）
- 核间通信用 `MSGBOX + RPMsg(OpenAMP/VirtIO)` 实现
- 常见链路：`remoteproc1(c906)` -> `virtio_rpmsg_bus` -> `/dev/rpmsg_ctrl-*` -> `amp_shell`

## 标准验证流程

### 1) 串口在线与系统确认

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0/tools/serial_agent
sudo python3 trae_serial_terminal.py io \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --send "uname -a"
```

### 2) 检查 remoteproc 节点

```bash
sudo python3 trae_serial_terminal.py io \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --send "ls -l /sys/class/remoteproc; cat /sys/class/remoteproc/remoteproc1/state; cat /sys/class/remoteproc/remoteproc1/firmware"
```

期望：
- `remoteproc1 -> c906_rproc`
- firmware 常见为 `amp_rv0.bin`

### 3) 拉起 C906 并检查 RPMsg 设备

```bash
sudo python3 trae_serial_terminal.py io \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --send "echo start > /sys/class/remoteproc/remoteproc1/state"
```

再查看：

```bash
sudo python3 trae_serial_terminal.py io \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --send "cat /sys/class/remoteproc/remoteproc1/state; ls -l /dev/rpmsg* 2>/dev/null"
```

期望：
- `state=running`
- 出现 `/dev/rpmsg_ctrl-c906_rproc@0`（不同内核命名可能不同）

### 4) 执行 amp_shell

```bash
sudo python3 trae_serial_terminal.py io \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --send "amp_shell -d /dev/rpmsg_ctrl-c906_rproc@0"
```

## 常见问题与修复

### A. `Failed to open "/dev/rpmsg_ctrl-c906_rproc@0"`

- 原因：remoteproc1 还未启动，或节点名不一致
- 处理：
  - 先 `echo start > /sys/class/remoteproc/remoteproc1/state`
  - 再 `ls /dev/rpmsg*` 确认真实设备名

### B. `Failed to create auto free endpoint` + 内核 `Undown konw cmd=0x4028b505`

- 现象说明：`amp_shell` 在调用 `RPMSG_CREATE_AF_EPT_IOCTL` 时与内核驱动协议不兼容
- 处理策略：
  - 修改 `amp_shell` 的 rpmsg 逻辑：AF ioctl 失败后自动回退 `RPMSG_CREATE_EPT_IOCTL`
  - 代码位置：`platform/allwinner/system/amp_shell/files/rawdev/rpmsg.c`
  - 重新执行：`buildroot_rootfs -> pack -> 烧录`

建议回退逻辑：
- 先尝试 `RPMSG_CREATE_AF_EPT_IOCTL`
- 失败后打印告警并回退 `RPMSG_CREATE_EPT_IOCTL`
- 保障不同内核版本都可运行

## 联动烧录验证（必要时）

若需要同步更新镜像后验证：

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0/tools/serial_agent
sudo python3 trae_serial_terminal.py io --auto-select --vid 1a86 --pid 55d4 --baudrate 115200 --send "reboot efex"
```

```bash
cd /home/ubuntu/T153MX/T153_Tina_V1.0
sudo tools/OpenixCLI/openixcli flash /home/ubuntu/T153MX/T153_Tina_V1.0/out/t153_linux_omnigate_uart0.img \
  --reconnect-timeout-sec 240 \
  --reconnect-interval-ms 300 \
  -v
```

## 诊断留存

- 串口日志建议用：

```bash
sudo python3 trae_serial_terminal.py terminal-raw \
  --auto-select --vid 1a86 --pid 55d4 \
  --baudrate 115200 \
  --log-file /tmp/amp_rpmsg_serial.log
```

- 建议同时保存：
  - `openixcli -v` 输出
  - `dmesg | grep -i -E 'remoteproc|rpmsg|virtio'`
