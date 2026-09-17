# Goodix 修复与平台整理续作记录（2026-09-16）

## Goodix 修复

此前 DTS 把已知可用的 GT911 从 `0x14` 改成 `0x5d`，启动日志持续出现
`xfer failed dev addr 0x5d`。第一次修正虽然恢复了 `0x14`，但新增的 `irq-gpios`
使通用 Goodix 驱动在 probe 时尝试把已由 pinctrl 固定为 IRQ 的 PJ7 切成输出，最终以
`-EINVAL` 退出。最终修复恢复了本板最开始验证可用的接法：PJ7 只作为固定中断输入，
PJ6 作为低有效复位，不声明 `irq-gpios`。

最终 DTB 已确认包含：

- `compatible = "goodix,gt911"`
- `reg = <0x14>`
- `interrupts = <PJ7 IRQ_TYPE_EDGE_FALLING>`
- 不含 `irq-gpios`
- `reset-gpios = <... PJ6 GPIO_ACTIVE_LOW>`
- 1024×768 触摸范围

最终启动清理版镜像大小为 604371968 bytes，SHA-256 为
`84914b6b79c59c5dd5221ba9aa59ae107c06d4826d193c10260ed7ce5cc87f17`。

## 实板烧写与验证

新镜像已进入 Lynx 缓存，但本轮重刷没有成功：

1. 第一次 full erase 写到 `rootfsB`、总进度约 67.13% 时 USB 传输中断；此前
   `boot-resource` 到 `rootfsA` 已写入。
2. 第二次在预检打开 USB 设备时失败，没有开始写入。
3. 完整下电重启后两次均能装载 U-Boot/FES、识别 7456 MB eMMC 和 12 分区，但在
   写 MBR 时报告 `USB transfer failed`。
4. 用户重新插拔 USB 后，MBR 写入及校验成功，随后写 `boot-resource` 约 2.8 MB 时
   再次出现 `USB transfer failed`。这证明重新枚举有效，但持续 USB 数据传输仍不稳定。
5. 按用户要求再次完整下电恢复 FEL 后进行单次受控重试；DRAM、U-Boot/FES 和 eMMC
   查询均成功，但写 64 KiB MBR 时再次发生相同 USB 错误，随后停止重试并下电。
6. 再次受控重试时已完成 `boot-resource`、env、双 boot、双 dtbo 和 `rootfsA`，在
   `rootfsB` RAW 分块回读校验阶段于总进度 85.25% 发生 USB 中断。镜像写入路径可运行，
   但 verify 未完成，仍不能作为合格镜像使用，板卡随后再次下电。

随后继续按“失败后完整断电、重新枚举、单任务烧写”的方式重试。最终任务
`flash-1789547974498904700` 成功完成分区更新、回读校验和重启：

- `progressPct=100`
- `verifyState=success`、`verifyErrorCode=0`
- `postFlashState=success`
- Boot0、Boot1 均为 verified
- boot-resource、双 boot、双 dtbo 和双 rootfs 全部写入完成

本次是建立在此前多轮全擦写已经创建 12 分区布局之后的 `partition + verify + reboot`，
不能表述为本次单任务 full erase 成功。

最终系统启动为 `Linux Tina5.0 5.10.198 #69`。实板日志确认：

- `Goodix-TS 2-0014: ID 967, version: 1060`
- 已注册 `Goodix Capacitive TouchScreen`
- `/proc/bus/input/devices` 显示 `Handlers=event1`
- `/dev/input/event1` 存在
- 不再出现 `probe failed with error -22`

因此 Goodix 驱动枚举和输入事件节点验证通过；物理触摸已由现场用户在当前界面实际
操作确认可用。本次真实 framebuffer 位于
`acceptance-results/bootclean-20260916/screenshots/framebuffer-boot69.png`，SHA-256 为
`4a99cdb02598c8fa4e21329968302588da87997fdc70d0c0bd6d0837b07a0949`。

启动清理版任务 `flash-1789549182223988600` 最终完成 `partition + verify + reboot`：

- `progressPct=100`、`writtenBytes=497333984`
- `verifyState=success`、`verifyErrorCode=0`
- `postFlashState=success`
- Boot0、Boot1 verified，双 boot、双 dtbo、双 rootfs 均完成写入

冷启动日志中不再出现缺失 `powerkey_display`、`powerkey_suspend` 或无法启动
`rpc.nfsd` 的告警，且未发现 panic、Oops 或 OOM。

## 工业控制桌面产品层

`omnigate-platform/` 已从说明性目录扩展为可发布、可校验的产品层：

- Lite 和 Enhanced 运行 profile；
- T153MX 板卡描述和运行时 Manifest 绑定；
- `/api/v1` 与 MQTT 契约；
- profile、板卡、遥测和受控命令 Schema；
- 四层架构、板卡移植指南和发布规则；
- 机器可读的当前验证状态，明确 Enhanced 实板和生产安全均未通过。

新增 5 项平台结构测试后，平台核心、Web/HMI 和发布结构共 13 项主机测试通过。
overlay 已清理测试缓存和临时内核模块产物，162 个交付项与 SDK 一致，SHA-256
清单全部通过。
