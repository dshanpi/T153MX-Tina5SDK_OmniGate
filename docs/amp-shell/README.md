# T153MX OmniGate AMP Shell 使用指南

本文面向当前 SDK 的 `t153_omnigate_mmc-buildroot` 配置，说明如何从 Linux A7 侧通过
`remoteproc + RPMsg` 进入 E907 FreeRTOS Shell，并给出编译、使用、扩展和故障诊断案例。

## 1. 先区分两种 Shell

| Shell | 常见提示符 | 运行位置 | 主要用途 |
| --- | --- | --- | --- |
| Linux UART Shell | `#` | Cortex-A7 / Linux | `dmesg`、挂载、eMMC、网络和 Linux 服务诊断 |
| AMP Shell | `msh >` | E907 / FreeRTOS，通过 RPMsg 转发 | RTOS 命令、任务、外设和核间通信调试 |

串口接入后看到根提示符 `#`，说明当前仍在 Linux Shell。要进入真正的 AMP Shell，需要在
Linux Shell 中运行 `omnigate-amp shell`。eMMC 是 Linux 管理的块设备，应该在 Linux Shell
中检查；E907 AMP Shell 不提供 Linux 的 `dmesg`、`mount` 或 `/sys/block`。

## 2. 数据链路

```text
开发机串口/SSH
      |
      v
A7 Linux Shell
      |
      +-- /usr/bin/omnigate-amp       启停、状态与诊断入口
      +-- /usr/bin/amp_shell          Linux 侧 RPMsg Shell 客户端
      +-- /dev/rpmsg_ctrl-*           RPMsg 控制设备
      |
      v
remoteproc + VirtIO/RPMsg + MSGBOX
      |
      v
E907 FreeRTOS multi_console            msh >
```

板级配置将 `t153_e907_bga_demo` 构建为 `amp_rv0.bin`。Linux 的 remoteproc 驱动加载该固件，
RTOS 的 RPMsg multi-console 注册名为 `console` 的服务；`amp_shell` 创建端点并转发输入输出。

## 3. 相关代码索引

### Linux 用户态

- `device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/omnigate-amp`
  - 面向用户的统一入口。
  - 自动查找 E907 remoteproc 与 `/dev/rpmsg_ctrl-*`。
  - 启动前校验固件必须为 `amp_rv0.bin`，防止误拉起其他镜像。
- `platform/allwinner/system/amp_shell/files/main.c`
  - 保存、切换和恢复终端属性。
- `platform/allwinner/system/amp_shell/files/shell.c`
  - 交互模式、`-e` 单命令模式和 RPMsg 接收线程。
- `platform/allwinner/system/amp_shell/files/command.c`
  - 封装 `OPEN/CLOSE/WRITE` 控制包；提供客户端本地命令 `amp_help`、`amp_exit`。
- `platform/allwinner/system/amp_shell/files/rawdev/rpmsg.c`
  - 创建 RPMsg endpoint。
  - 当前版本先尝试 auto-free ioctl，不兼容时自动回退普通 endpoint ioctl。
- `platform/allwinner/system/amp_shell/files/Makefile`
  - 生成并安装 `/usr/bin/amp_shell`。

### E907 RTOS

- `rtos/lichee/rtos/projects/t153_e907/bga_demo/defconfig`
  - 已启用 `CONFIG_MULTI_CONSOLE`、`CONFIG_RPMSG_MULTI_CONSOLE`。
- `rtos/lichee/rtos/projects/t153_e907/bga_demo/src/main.c`
  - 初始化 OpenAMP、RPMsg 控制设备和 multi-console。
- `rtos/lichee/rtos-components/aw/multi_console/`
  - RTOS 多控制台框架。
- `rtos/lichee/rtos-components/aw/multi_console/rpmsg_console/`
  - RPMsg console 的 RTOS 端实现。
- `rtos/lichee/rtos-components/aw/multi_console/shell.c`
  - RTOS Shell 输入解析和命令调度。

### 板级与内核

- `device/config/chips/t153/configs/omnigate/buildroot/BoardConfig.mk`
  - `LICHEE_RTOS_PROJECT_NAME` 指定 E907 项目和 `amp_rv0.bin`。
- `device/config/chips/t153/configs/omnigate/linux-5.10-rt/board.dts`
  - remoteproc、共享内存、vring 和 AMP 资源定义。
- `device/config/chips/t153/configs/omnigate/linux-5.10-rt/buildroot_linux_defconfig`
  - remoteproc、RPMsg control、heartbeat 和 RPBuf 配置。
- `device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/omnigate-amp`
  - 被复制到最终根文件系统。

当前构建产物可在以下位置核对：

```sh
ls -l out/t153/omnigate/buildroot/buildroot/target/usr/bin/amp_shell
ls -l out/t153/omnigate/buildroot/buildroot/target/usr/bin/omnigate-amp
ls -l out/t153/omnigate/buildroot/buildroot/target/lib/firmware/amp_rv0.bin
ls -l out/t153/omnigate/pack_out/amp_rv0.bin
```

## 4. 安装 AMP Shell overlay

当前 SDK 已经应用了 AMP Shell 改动。如果要把压缩包应用到另一份同版本 SDK，先检查内容，
再覆盖；不要直接把压缩包解到不确定的目录。

```sh
tar -tzf t153mx-ominigate-ampshell-v1.tar.gz | less

work_dir=$(mktemp -d)
tar -xzf t153mx-ominigate-ampshell-v1.tar.gz -C "$work_dir"
rsync -avn "$work_dir/t153mx-ominigate-ampshell-v1/overlay/" /path/to/TinaSDK/
```

确认 dry-run 清单正确后再去掉 `-n`。overlay 会覆盖同名文件，操作前应保存目标 SDK 中尚未
提交的修改。

## 5. 编译与打包

在 SDK 根目录执行完整构建：

```sh
source build/envsetup.sh
lunch t153_omnigate_mmc-buildroot
make
pack
```

打包前至少确认：

```sh
test -x out/t153/omnigate/buildroot/buildroot/target/usr/bin/amp_shell
test -x out/t153/omnigate/buildroot/buildroot/target/usr/bin/omnigate-amp
test -s out/t153/omnigate/pack_out/amp_rv0.bin
```

烧录属于独立步骤。烧录成功并重启后，再按下文从 Linux Shell 验证 AMP 链路。

## 6. 快速上手

以下命令均在板卡 Linux Shell 的 `#` 提示符下运行。

### 6.1 查看状态

```sh
omnigate-amp status
```

正常情况下应看到 E907 remoteproc、`firmware=amp_rv0.bin`、`state=running` 或 `offline`，
以及至少一个 `/dev/rpmsg_ctrl-*` 控制设备。`offline` 不是故障，执行 `start` 或 `shell` 可启动。

### 6.2 启动 E907

```sh
omnigate-amp start
```

该命令只在 E907 尚未运行时向 remoteproc 写入 `start`，并等待 RPMsg 控制设备出现。

### 6.3 进入交互式 AMP Shell

```sh
omnigate-amp shell
```

看到 `msh >` 后，输入：

```text
help
```

退出客户端建议输入：

```text
amp_exit
```

`amp_exit` 是 Linux 侧 `amp_shell` 的本地退出命令。不要使用 `Ctrl+Z` 挂起客户端，否则可能
暂时保留终端或 endpoint 状态。

### 6.4 执行一条 RTOS 命令

```sh
omnigate-amp exec help
omnigate-amp exec "console_dump"
```

含空格的命令必须整体作为一个参数传给 `exec`：

```sh
omnigate-amp exec "your_command arg1 arg2"
```

`amp_shell -e` 当前等待约 1 秒后退出，适合输出较短的命令。长时间任务或大量输出应使用
`omnigate-amp shell` 交互模式。

### 6.5 指定 RPMsg 控制设备

仅在系统存在多个 RPMsg 控制设备时需要：

```sh
ls -l /dev/rpmsg_ctrl-* /dev/rpmsg_ctrl[0-9]* 2>/dev/null
omnigate-amp shell /dev/rpmsg_ctrl-e907_rproc@0
omnigate-amp exec "help" /dev/rpmsg_ctrl-e907_rproc@0
```

设备名随内核实现变化，必须使用板卡上实际列出的名字。

## 7. 使用案例

### 案例 A：首次启动后的最小验收

```sh
omnigate-amp status
omnigate-amp start
omnigate-amp exec help
omnigate-amp diagnose
```

也可把本目录的脚本复制到板卡运行：

```sh
sh amp-shell-smoke-test.sh
sh amp-shell-smoke-test.sh "console_dump"
```

脚本只读取 Linux 状态并执行一条指定的 RTOS 命令，不停止 E907、不重启 Linux、不操作存储。

### 案例 B：区分 Linux 与 RTOS 命令

```sh
# Linux 命令：直接在 # 下运行
uname -a
dmesg | grep -Ei 'remoteproc|rpmsg|e907'

# RTOS 命令：通过 AMP Shell 转发
omnigate-amp exec help
```

不要执行 `omnigate-amp exec "dmesg"` 来检查 Linux 日志；该命令会被送到 E907，RTOS 通常
不存在 `dmesg`。

### 案例 C：新增一条 E907 Shell 命令

可在 E907 项目源码中加入类似代码：

```c
#include <stdio.h>
#include <console.h>

static int cmd_board_info(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    printf("board=t153mx core=e907 status=ok\r\n");
    return 0;
}

FINSH_FUNCTION_EXPORT_CMD(cmd_board_info, board_info,
                          show T153MX E907 board information);
```

确保该 `.c` 文件被 E907 工程的 Makefile/objects.mk 编译后，重新构建、打包和烧录。验证：

```sh
omnigate-amp exec board_info
```

预期输出：

```text
board=t153mx core=e907 status=ok
```

### 案例 D：只读诊断 RPMsg 链路

```sh
omnigate-amp diagnose
cat /sys/class/remoteproc/remoteproc*/name
cat /sys/class/remoteproc/remoteproc*/firmware
cat /sys/class/remoteproc/remoteproc*/state
ls -l /dev/rpmsg* 2>/dev/null
```

内核日志重点关注：

```sh
dmesg | grep -Ei 'remoteproc|rpmsg|virtio|msgbox|e907|share.?irq'
```

### 案例 E：通过板卡 MCP 协助验证

在目标 SDK 根目录启动连接到当前服务端口的 Codex：

```sh
codex -c 'mcp_servers={"lynx-t153mx-ominigate-sdk"={url="http://127.0.0.1:18765/mcp"}}'
```

建议给 AI 明确边界，例如：

```text
只使用 lynx-t153mx-ominigate-sdk MCP。通过串口进入 Linux Shell，执行
omnigate-amp status、omnigate-amp exec help 和 omnigate-amp diagnose。
只读检查，不停止 remoteproc、不重启、不烧录；结束时关闭串口句柄，报告原始关键行。
```

若要检查 eMMC，应改为要求 AI 在 Linux `#` Shell 执行 `dmesg`、`/proc/partitions` 和
`/sys/block/mmcblk0/device/*` 检查，不要称其为 E907 AMP Shell 检查。

## 8. 常见故障

### `E907 remoteproc was not found`

检查内核配置、设备树和启动日志：

```sh
ls -l /sys/class/remoteproc
dmesg | grep -Ei 'remoteproc|e907|reserved|vring'
```

若 `/sys/class/remoteproc` 为空，优先检查固件中的内核/DTB 是否来自当前 omnigate 配置。

### `Unexpected E907 firmware`

`omnigate-amp` 有意拒绝启动非 `amp_rv0.bin` 固件。检查：

```sh
cat /sys/class/remoteproc/remoteproc*/firmware
ls -l /lib/firmware/amp_rv0.bin
```

不要为了绕过检查直接修改脚本；应先确认板级配置和固件映射。

### E907 running，但没有 `/dev/rpmsg_ctrl-*`

```sh
OMNIGATE_AMP_WAIT_SECONDS=20 omnigate-amp start
omnigate-amp diagnose
```

常见原因是 RTOS 未启用 RPMsg multi-console、共享内存/vring 配置不匹配，或 Linux RPMsg
control 驱动未启用。

### `Failed to create auto free endpoint`

当前 `rawdev/rpmsg.c` 已实现兼容逻辑：auto-free ioctl 失败后回退
`RPMSG_CREATE_EPT_IOCTL`。如果日志中连回退方式也失败，应保存：

```sh
omnigate-amp diagnose
uname -a
ls -l /dev/rpmsg*
```

然后核对运行中的 `amp_shell` 是否确实来自当前构建产物。

### `amp_shell -e` 输出不完整

单命令模式只等待约 1 秒。改用：

```sh
omnigate-amp shell
```

对于自动化命令，建议让 RTOS 命令输出唯一结束标记，调用端读到标记后再关闭会话。

### endpoint 或终端疑似残留

先退出占用 `amp_shell` 的进程，再重新检查，不要直接重启或删除设备节点：

```sh
ps | grep '[a]mp_shell'
ls -l /dev/rpmsg* 2>/dev/null
omnigate-amp status
```

正常退出会执行 endpoint 清理。只有确认没有业务运行在 E907 上时，才考虑
`omnigate-amp stop`；该命令会改变 E907 运行状态，不属于只读诊断。

## 9. 收集问题反馈时的最小信息

提交 AMP Shell 问题时建议附上：

```sh
uname -a
omnigate-amp status
omnigate-amp diagnose
ls -l /dev/rpmsg* 2>/dev/null
sha256sum /usr/bin/amp_shell /lib/firmware/amp_rv0.bin
```

同时注明：

- SDK/overlay 版本和构建时间。
- 使用的板型、启动介质、Linux 内核类型（origin 或 RT）。
- 操作顺序以及预期/实际结果。
- 是否存在另一个串口客户端、烧录扫描或硬件任务占用。
- 完整原始错误文本，不只写“AMP Shell 失败”。

涉及烧录问题时还应单独附上烧录任务 ID、固件绝对路径、写入与校验阶段日志；不要把烧录
失败与 AMP/RPMsg 故障合并成一个结论。

