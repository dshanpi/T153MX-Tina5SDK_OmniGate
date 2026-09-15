# 工业网关完整构建与实板验证记录

验证日期：2026-09-14

## 结论

`gatewaycanethercat` 已合入远端 `main` 的最新 overlay，并完成完整 SDK 构建、
固件解析和一次成功的 eMMC 全量烧写。首轮板端验收确认 Linux、双以太网、双 CAN、
RS485、Wi-Fi、蓝牙、ADB、SOEM、CANopen 和 OmniGate Web 均能启动或枚举。

验收同时发现旧 Buildroot 输出目录没有自动吸收 defconfig 中的 ModemManager 选项。
重新载入 defconfig 后，已补齐 ModemManager 1.18.6、`mmcli`、QMI、MBIM 和 `uqmi`，
并生成修正版镜像。全擦除模式受目标 USB 链路不稳定影响，恢复过程中出现过擦除标记
传输失败和加载固件超时；重新传输并校验镜像缓存、复位目标后，使用分区模式成功写入
并校验全部 12 个分区，随后自动重启。修正版已在板端完成最终复验。

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

## 修正版烧写恢复与最终状态

修正版镜像传到 Lynx 缓存后，缓存文件与 SDK 主机的大小和 SHA-256 完全一致。开发板
从已验证的 Linux shell 进入 FEL，目标 USB 位置与项目绑定一致。最初的
`full_erase + verify + reboot` 在擦除标记传输阶段遇到 USB 传输错误，后续个别尝试
停留在加载固件阶段。目标复位并重新确认 FES 后，改用 `partition + verify + reboot`
恢复写入；此前成功的全量烧写已经建立了同一镜像布局，因此无需再次擦除介质。

最终 Lynx 任务 `flash-1789444086119233600` 完成状态：

- 状态和阶段：`success / complete`，进度 100%
- 分区写入：全部完成，共 `462744576` bytes
- 介质提交：`462926744` bytes
- 校验：成功，错误码 0；Boot0 和 Boot1 均通过校验
- 烧写后动作：自动重启成功（第 2 次检测确认）
- 退出码：0

重启后 COM19 回到 Linux `#` 提示符。修正版板端复验结果：

- `mmcli 1.18.6`、`ModemManager 1.18.6`、`qmicli 1.30.4`
- `/usr/sbin/ModemManager` 正在运行
- `/usr/bin/omnigate-ethercat` 存在
- Python 可导入 `canopen`、`flask`、`jsonpath_rw`
- `can0`、`can1` 均正常枚举，并按安全策略保持 DOWN
- OmniGate Web 进程运行，`GET /api/health` 返回
  `{"ok":true,"service":"omnigate-web"}`

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
