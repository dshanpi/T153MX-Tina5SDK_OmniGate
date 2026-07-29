# A7 Linux 与 E907 FreeRTOS 核间通信实现记录

日期：2026-07-29

## 目标和验收链路

在 OmniGate T153 上由 A7 Linux 管理 E907 FreeRTOS 生命周期，并通过
MSGBOX、remoteproc、virtio/RPMsg 和 OpenAMP 建立双向数据通道：

```text
remoteproc(e907_rproc)
  -> start amp_rv0.bin
  -> virtio_rpmsg_bus
  -> /dev/rpmsg_ctrl-*
  -> amp_shell
  -> E907 "console" endpoint
```

板端通过以下四项才算完成端到端验收：

1. E907 对应的 `/sys/class/remoteproc/remoteproc*` 存在，固件为
   `amp_rv0.bin`，启动前状态为 `offline`。
2. 写入 `start` 后状态变成 `running`。
3. `/dev/rpmsg_ctrl-*` 出现，创建端点后 `/dev/rpmsgN` 出现。
4. `amp_shell` 成功建立 `console` 端点并与 E907 收发数据。

remoteproc 编号和 RPMsg 控制节点名称由内核动态分配，验证逻辑不硬编码
`remoteproc1` 或 `rpmsg_ctrl-c906_rproc@0`。

## 本轮实现

### amp_shell ioctl 兼容

交付 overlay 新增：

```text
platform/allwinner/system/amp_shell/files/rawdev/rpmsg.c
```

端点创建由编译时二选一改成运行时探测：

1. 先尝试 `RPMSG_CREATE_AF_EPT_IOCTL`。
2. 内核不支持时回退到 `RPMSG_CREATE_EPT_IOCTL`。
3. 普通端点模式显式执行销毁；Auto Free 模式通过关闭控制 fd 自动销毁。
4. 修正设备路径截断、fd 为 0 时未关闭、端点异步出现等待时间过短等边界问题。

这使同一个 `amp_shell` 可以兼容带和不带 Auto Free API 的 BSP 内核。旧内核探测
不支持的 ioctl 时仍可能产生一次内核告警，但不会再因为该 ioctl 失败而终止端点
创建。

### rootfs 集成

T153 MMC Buildroot defconfig 已启用：

```text
BR2_PACKAGE_AMP_SHELL=y
```

仅修改 defconfig 不会改变已经存在的 Buildroot 输出 `.config`，因此必须重新应用
defconfig或执行一次完整 rootfs 构建。本次构建结果应同时满足：

```sh
grep '^BR2_PACKAGE_AMP_SHELL=y' \
  out/t153/omnigate/buildroot/buildroot/.config
test -x out/t153/omnigate/buildroot/buildroot/target/usr/bin/amp_shell
```

### 板端辅助工具

镜像新增 `/usr/bin/omnigate-amp`：

```sh
omnigate-amp status
omnigate-amp start
omnigate-amp shell
omnigate-amp exec help
omnigate-amp diagnose
omnigate-amp stop
```

该工具按 remoteproc 的 `name` 和 `firmware` 自动定位 E907，校验固件名称，等待
RPMsg 控制节点出现，再把真实节点路径传给 `amp_shell`。

## 内核和 DTS 核对

OmniGate 的 Linux 5.10 origin/RT 配置已经启用：

```text
CONFIG_AW_MSGBOX=y
CONFIG_AW_REMOTEPROC=y
CONFIG_AW_REMOTEPROC_E907_BOOT=y
CONFIG_AW_RPMSG_CTRL=y
CONFIG_RPMSG=y
CONFIG_RPMSG_VIRTIO=y
```

DTS 已提供 E907 固件区、vring、vdev buffer、DRAM 保留区、MSGBOX mailbox 和
`e907_rproc` 节点。`auto-boot` 保持关闭，便于从 Linux 明确验证
offline -> running 生命周期。

### `SUNXI_RPROC_SHARE_IRQ` 结论

`CONFIG_SUNXI_RPROC_SHARE_IRQ` 只负责把选定外设/GPIO中断在 A7 与 E907 之间做
所有权保存、恢复和共享表同步；MSGBOX/RPMsg 基础数据通道不依赖它。当前 OmniGate
DTS 虽保留 `share-irq = "e907"` 和共享表内存，但没有 AMP 示例板完整的
`reserved-irq` 描述，也没有把共享表加入 remoteproc 的 `memory-region`。

因此本轮保持该选项关闭：

- 不影响 remoteproc 启动和 RPMsg 收发。
- 配置关闭时驱动不会解析 `share-irq` 属性，不应产生相关报错。
- 后续确实需要把 GPIO/外设中断交给 E907 时，再一次性补齐 DTS
  `reserved-irq`、memory-region 和内核选项，并单独验证中断所有权。

## 板端验收

烧录新镜像后执行：

```sh
omnigate-amp status
omnigate-amp start
omnigate-amp diagnose
omnigate-amp exec help
omnigate-amp shell
```

手工等价命令：

```sh
for r in /sys/class/remoteproc/remoteproc*; do
    echo "$r $(cat "$r/name") $(cat "$r/firmware") $(cat "$r/state")"
done

echo start > /sys/class/remoteproc/remoteproc1/state
cat /sys/class/remoteproc/remoteproc1/state
ls -l /dev/rpmsg_ctrl-* /dev/rpmsg[0-9]*
amp_shell -d /dev/rpmsg_ctrl-c906_rproc@0
```

最后两行中的编号和设备名仅为示例，应以本机枚举结果为准。若启动失败，保存：

```sh
omnigate-amp diagnose
cat /proc/iomem
cat /proc/interrupts
```

实物验收前只能确认代码、固件、内核配置和 rootfs 产物完整；E907 真正执行及
双向收发必须在烧录后的板卡上判定。

## 构建结果

本轮重新生成 Buildroot `.config` 后执行：

```sh
./build.sh buildroot_rootfs
./build.sh rootfs
./build.sh pack
```

结果：

- `amp_shell` 使用 ARM hard-float 交叉工具链编译并安装成功。
- `rootfs.tar`、ext4 和 squashfs 重新生成，归档中存在
  `/usr/bin/amp_shell`、`/usr/bin/omnigate-amp`。
- squashfs：`54648.01 KiB`。
- `amp_rv0.bin` 与打包后的 `amp_rv0.fex` SHA-256 一致：
  `68f165b568a02fb726560dde3e657a1a0bf00c04e7a50bd8382e8ed0f73f27ac`。
- `Dragon execute image.cfg SUCCESS`，`pack finish`。
- 镜像：`out/t153_linux_omnigate_uart0.img`
- 大小：`529295360` bytes。
- SHA-256：
  `76f64efa46c7f0dc0b5689f5c2b443dc86a2088785065ae77199ece253073058`

打包阶段的 `Can not find kernel.its` 是本板普通 Linux 非 FIT 路径的既有提示；
后续 Dragon 打包成功。UBI 的 `max_leb_cnt too low` 也不影响本板实际采用并成功
生成的 ext4/squashfs。
