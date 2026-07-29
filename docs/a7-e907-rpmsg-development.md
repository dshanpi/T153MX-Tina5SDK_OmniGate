# A7 Linux 与 E907 FreeRTOS 核间通信

交付分支：`ampcpudev`

## 目标

在 OmniGate T153 上由 A7 Linux 通过 remoteproc 管理 E907 FreeRTOS，并通过
MSGBOX、virtio/RPMsg 和 OpenAMP 与 E907 的 `console` 端点双向通信：

```text
remoteproc(e907_rproc)
  -> start amp_rv0.bin
  -> virtio_rpmsg_bus
  -> /dev/rpmsg_ctrl-*
  -> amp_shell
  -> E907 console endpoint
```

验收标准：

1. E907 对应的 `/sys/class/remoteproc/remoteproc*` 存在，固件为
   `amp_rv0.bin`，启动前状态为 `offline`。
2. 写入 `start` 后状态变成 `running`。
3. `/dev/rpmsg_ctrl-*` 出现，创建端点后 `/dev/rpmsgN` 出现。
4. `amp_shell` 成功建立 `console` 端点并与 E907 收发数据。

remoteproc 编号和 RPMsg 控制节点名称由内核动态分配，不能依赖固定的
`remoteproc1` 或 `rpmsg_ctrl-c906_rproc@0`。

## 分支包含的修改

### amp_shell ioctl 兼容

`platform/allwinner/system/amp_shell/files/rawdev/rpmsg.c` 改为：

1. 先尝试 `RPMSG_CREATE_AF_EPT_IOCTL`。
2. 内核不支持时自动回退 `RPMSG_CREATE_EPT_IOCTL`。
3. 普通端点模式显式销毁，Auto Free 模式通过关闭控制 fd 自动销毁。
4. 修正设备路径截断、fd 等于 0 时未关闭、端点节点异步出现等待不足等问题。

旧内核探测不支持的 Auto Free ioctl 时仍可能产生一次内核告警，但不会再因该
ioctl 失败而终止端点创建。

### rootfs 和板端工具

Buildroot defconfig 已启用：

```text
BR2_PACKAGE_AMP_SHELL=y
```

镜像新增 `/usr/bin/omnigate-amp`：

```sh
omnigate-amp status
omnigate-amp start
omnigate-amp stop
omnigate-amp shell
omnigate-amp exec help
omnigate-amp diagnose
```

工具会根据 remoteproc 的 `name` 和 `firmware` 自动寻找 E907，校验
`amp_rv0.bin`，等待 RPMsg 控制节点出现，再调用 `amp_shell`。

## 内核和 DTS

OmniGate 的 Linux 5.10 origin/RT 配置已有：

```text
CONFIG_AW_MSGBOX=y
CONFIG_AW_REMOTEPROC=y
CONFIG_AW_REMOTEPROC_E907_BOOT=y
CONFIG_AW_RPMSG_CTRL=y
CONFIG_RPMSG_VIRTIO=y
```

DTS 已提供固件区、vring、vdev buffer、E907 DRAM 保留区、MSGBOX mailbox 和
`e907_rproc`。`auto-boot` 保持关闭，以便明确验证 `offline -> running`。

`CONFIG_SUNXI_RPROC_SHARE_IRQ` 不属于 MSGBOX/RPMsg 基础通信依赖。当前 DTS 没有
AMP 示例板完整的 `reserved-irq` 描述，因此本分支保持该选项关闭。后续确实需要
把 GPIO 或外设中断交给 E907 时，应同时补齐 DTS 共享中断表、memory-region 和
内核配置，并单独验证中断所有权。

## 应用和构建

```sh
./t153mx-ominigate-v1/scripts/apply_overlay.sh "$PWD"
./t153mx-ominigate-v1/scripts/verify_amp_e907.sh "$PWD"

make -C buildroot/buildroot-202205 \
  O="$PWD/out/t153/omnigate/buildroot/buildroot" \
  sun8iw22p1_t153_mmc_defconfig

./build.sh buildroot_rootfs
./build.sh rootfs
./build.sh pack
```

本次在共享开发 SDK 中完成的集成构建验证结果：

- `amp_shell` 使用 ARM hard-float 交叉工具链编译并进入 rootfs。
- `/usr/bin/amp_shell` 和 `/usr/bin/omnigate-amp` 均存在于 `rootfs.tar`。
- `amp_rv0.bin` 与打包后的 `amp_rv0.fex` SHA-256 一致：
  `68f165b568a02fb726560dde3e657a1a0bf00c04e7a50bd8382e8ed0f73f27ac`。
- squashfs：`54648.01 KiB`。
- 打包结果：`Dragon execute image.cfg SUCCESS`、`pack finish`。
- 镜像：`out/t153_linux_omnigate_uart0.img`
- 大小：`529295360` bytes。
- SHA-256：
  `76f64efa46c7f0dc0b5689f5c2b443dc86a2088785065ae77199ece253073058`

该 SDK 同时保留了此前已应用的其他 OmniGate 功能，以上哈希用于核对本机生成的
集成测试镜像，不代表从 `origin/main` 仅应用本分支后仍会得到相同哈希。固件体积
超过 GitHub 普通 Git 单文件限制，因此分支只保存独立的 AMP/E907 源码、配置和
验证记录，不提交镜像。

## 板端验收

烧录后执行：

```sh
omnigate-amp status
omnigate-amp start
omnigate-amp diagnose
omnigate-amp exec help
omnigate-amp shell
```

如果失败，保存以下输出：

```sh
omnigate-amp diagnose
cat /proc/iomem
cat /proc/interrupts
```

当前构建环境没有枚举到板卡串口、ADB 或 FEL，所以已完成代码、配置、rootfs 和
固件打包验证，E907 实际启动与双向收发仍需烧录后在实板确认。
