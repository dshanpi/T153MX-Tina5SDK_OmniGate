# 工业网关完整构建与实板验证记录

验证日期：2026-09-14

## 结论

`gatewaycanethercat` 已合入远端 `main` 的最新 overlay，并完成完整 SDK 构建、
固件解析和一次成功的 eMMC 全量烧写。首轮板端验收确认 Linux、双以太网、双 CAN、
RS485、Wi-Fi、蓝牙、ADB、SOEM、CANopen 和 OmniGate Web 均能启动或枚举。

验收同时发现旧 Buildroot 输出目录没有自动吸收 defconfig 中的 ModemManager 选项。
重新载入 defconfig 后，已补齐 ModemManager 1.18.6、`mmcli`、QMI、MBIM 和 `uqmi`，
并生成修正版镜像。修正版的第二次烧写在写入任何分区前发生 USB 传输错误；按 FES
安全规则没有自动重试。因此，修正版镜像已通过主机侧构建与结构校验，但仍需恢复
FEL 后完成最终烧写和板端复验。

## 可复现构建

应用 overlay 后，在 SDK 根目录执行：

```sh
./build.sh config
# linux / buildroot / t153 / omnigate / default / linux-5.10-origin

make -C buildroot/buildroot-202205 \
    O="$PWD/out/t153/omnigate/buildroot/buildroot" \
    sun8iw22p1_t153_mmc_defconfig

./build.sh
./build.sh pack
```

必须显式重新载入 Buildroot defconfig。顶层 `.buildconfig` 只决定板型和构建系统，
不会把新增 `BR2_PACKAGE_*` 选项合并进已有的
`out/t153/omnigate/buildroot/buildroot/.config`。

## 修正版镜像

- 路径：`out/t153_linux_omnigate_uart0.img`
- 大小：`569962496` bytes（543.56 MiB）
- SHA-256：`b2713337df5150c30970f80bca3041626cdb14dd9dc45439912b190ca6b440e7`
- OpenixCLI：`IMAGEWTY` v3，46 个嵌入文件，12 个 MBR 分区
- A/B 内容：双 `boot`、双 `dtbo`、双 `rootfs`
- rootfs：`mmcli`、`ModemManager`、`qmicli`、`uqmi`、SOEM、
  `omnigate-ethercat`、CANopen、ThingsBoard Gateway 和 OmniGate Web 均已安装

构建期间 `mkfs.ubifs` 会为未选用的 UBIFS 产物报告 `max_leb_cnt too low`；当前 eMMC
产品实际打包的是 ext4 sparse `rootfs.fex`，随后 ext4、SquashFS 和 Dragon 镜像打包
均成功。最终镜像经 OpenixCLI 独立解析，两个 rootfs 均为 199.00 MiB sparse 文件。

## 首轮烧写与启动证据

首轮镜像 SHA-256 为
`5acdc98bf5a2d5e69c9b17363e2fb5f7feef763af8aa1e1d6fa85a0f1b8f74f0`。
Lynx 通过绑定的 COM19 Linux `#` 提示符执行固定 `reboot efex`，FES 查询确认：

- 存储类型：eMMC
- 容量：7456 MiB
- 模式：`full_erase`
- 校验：成功，错误码 0
- 已提交介质字节：`425157976`
- 烧写后重启：成功

冷启动串口确认 Linux 5.10.198 正常进入 shell，启动时间戳为
`Mon Sep 14 22:18:51 EDT 2026`。板端检查结果：

- `can0`、`can1` 均枚举，驱动参数和 `restart-ms=100` 正常；工业网关脚本随后将
  两路 CAN 置为 DOWN，避免未知现场波特率下主动驱动总线。
- `eth0`、`eth1` 均枚举并置为 UP；当时两口均无载波。
- `/dev/ttyAS0`、`/dev/ttyAS5`、`/dev/ttyAS7` 均存在。
- AIC8800D80 Wi-Fi 初始化完成，`hci0` 启动成功。
- `omnigate-ethercat`、`slaveinfo`、`simple_ng`、`candump`、`cansend`、
  `qmicli` 和 Python 3 均存在。
- Python 可导入 `canopen`、`flask`、`jsonpath_rw`。
- OmniGate Web 进程运行，`GET /api/health` 返回
  `{"ok":true,"service":"omnigate-web"}`。
- ThingsBoard Gateway 已安装但按设计默认禁用，配置 Token 后才允许启动。

## 修正版二次烧写状态

修正版镜像已传到 Lynx 缓存，传输后的 SHA-256 与 SDK 主机一致。开发板再次从已
验证的 Linux shell 进入 FEL，目标 USB 位置仍与项目绑定一致。第二次
`full_erase + verify + reboot` 在 12% 的擦除标记传输阶段终止：

```text
phase=verify
transferredBytes=0
committedBytes=null
verifyErrorCode=-1
postFlashState=not_run
USB transfer failed
```

失败后 FEL/FES USB 设备仍可扫描到，但依照 Allwinner FES 流程，失败任务不得自动
重试。恢复 FEL 并获得新的重试授权后，应重新烧写修正版，再以串口确认 `mmcli
--version`、`ModemManager --version` 和 `/api/health`。

## 工业外设边界

本次连接状态没有 EtherCAT 从站载波、CANopen 节点或可识别的 EC20 QMI 设备，
因此不能把协议栈安装与接口枚举写成外设通信已通过。接入现场设备后按以下顺序验收：

1. 只读发现 EtherCAT 从站、CANopen 节点和 EC20 控制口，核对身份及能力。
2. 读取设备手册规定的只读 SDO/对象字典；写操作前建立可回滚配置快照。
3. 执行机构保持禁止输出；驱动器只允许零位保持闭环，不下发计划运动轨迹。
4. EtherCAT 周期测试限制在 1000 次、1 ms，并检查 WKC；结束后回到 SAFE-OP。
5. 本地 ThingsBoard/MQTT 测试通过后再启用远端 Token 和开机服务。

启动日志中的 NFS `nfsd` 挂载失败、首次 UDISK 格式化和 USB UDC 电源告警不影响
本轮工业网关进程启动；它们作为基础 SDK 的已知告警保留，不作为外设验收通过项。
