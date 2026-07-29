# 默认 SDK 应用、编译与烧录验证记录

验证日期：2026-07-24

## 验证范围

1. 所有 repo project 恢复到 `aiot-t153-linux-v1.0 release`。
2. 清理 repo project 中的未跟踪文件。
3. 仅通过 `scripts/apply_overlay.sh` 把本交付覆盖到默认 SDK。
4. 选择 `linux / buildroot / t153 / omnigate / default /
   linux-5.10-origin`。
5. 完成 U-Boot、Linux 5.10.198、内核模块和 Buildroot rootfs 构建。
6. 强制删除旧 BlueALSA package 输出并从源码重新构建。
7. 重新生成 rootfs、打包完整固件、FEL 全擦写、逐分区校验并启动实板。

## 关键结果

- `scripts/verify_bluetooth_speaker.sh`：
  `[OK] Bluetooth speaker overlay matches target SDK`
- 内核：`Linux Tina5.0 5.10.198`
- AIC 模块：`aic8800_bsp.ko`、`aic8800_fdrv.ko`、
  `aic8800_btlpm.ko` 均安装成功。
- BlueALSA 的实际 configure 参数包含：
  `--without-libopenaptx --disable-aptx --disable-aptx-hd`
- `bluealsa --help` 的 A2DP Source/Sink 均只列出 SBC。
- 完整镜像：`out/t153_linux_omnigate_uart0.img`
- 镜像大小：`426377216` bytes
- SHA-256：
  `035d40668dfacc467dd8ad27a5c72124736ad6f79095c3c46a454581da05d4cf`
- OpenixCLI 检查到 46 个嵌入文件、12 个 MBR 分区。
- FEL 全量烧写 `322305024` bytes；MBR、boot、dtbo、rootfsA、
  rootfsB、Boot0 和 Boot1 写后校验全部通过。
- 启动后 ADB 序列号：`0402101560`
- 蓝牙控制器：AIC UART `hci0`，地址 `22:22:36:31:85:5D`
- `bt-speaker start` 后：
  - 名称：`T153 Bluetooth Speaker`
  - Class：Audio/Video Loudspeaker
  - A2DP Sink：SBC
  - 配对 agent：NoInputNoOutput
  - `SPK` 与 `LINEOUTL`：开启

## 已知的非致命构建提示

rootfs 阶段可能打印 `max_leb_cnt too low`。该提示来自未采用的 UBI 产物；
本板实际使用的 ext4/squashfs 随后会成功生成，最终应以 `pack rootfs ok` 为准。

pack 阶段可能打印 `Can not find kernel.its`，随后会使用普通 Linux 打包路径。
只有同时出现 `Dragon execute image.cfg SUCCESS` 与 `pack finish`，才可把生成的
镜像用于烧录。

## 工业网关扩展构建记录

在上述基线之上加入 ThingsBoard Gateway、SOEM、EC20 支持后再次执行完整构建：

- ThingsBoard Gateway 3.8.3 及 Modbus/CAN 连接器交叉编译成功。
- SOEM 2.0.0、`libsoem.so`、`slaveinfo`、`simple_ng` 等工具交叉编译成功。
- `qmicli`、pppd、usb-modeswitch 数据已进入 rootfs。
- 最终内核配置确认 `CONFIG_USB_NET_QMI_WWAN=y`、
  `CONFIG_USB_SERIAL_OPTION=y`、`CONFIG_PPP=y`。
- 最终 Buildroot 配置确认 `BR2_PACKAGE_SOEM=y`、
  `BR2_PACKAGE_THINGSBOARD_GATEWAY=y`、`BR2_PACKAGE_LIBQMI=y`、
  `BR2_PACKAGE_PPPD=y`。
- `scripts/verify_industrial_gateway.sh` 全部检查通过。
- 原蓝牙音响 overlay 一致性检查仍通过。
- squashfs：`53481.76 KiB`。
- 完整镜像：`out/t153_linux_omnigate_uart0.img`
- 镜像大小：`521261056` bytes
- SHA-256：
  `de805f80fa331ec455b04e6170c7a60331528c64f1f3747e4d511e09befb8408`

本次镜像已通过 `Dragon execute image.cfg SUCCESS` 和 `pack finish`。实板通过
串口 `reboot efex` 进入 FEL 后，虚拟机需要重新接入枚举为 `1f3a:efe8` 的
Allwinner USB Device，才能继续 OpenixCLI 烧写。

第一轮工业网关镜像已用 OpenixCLI `full_erase` 写入实板：

- 9 个镜像分区全部写入并回读校验通过，共写入 `415472640` bytes。
- Boot0、Boot1 校验通过，设备自动重启。
- Linux 5.10.198 正常启动，AIC Wi-Fi/蓝牙、`eth0`、`eth1`、`can0`、
  `can1` 和 `/dev/ttyAS5` 均完成枚举。
- ThingsBoard Gateway 及 `pymodbus`、`python-can`、`cryptography`、
  `orjson` 导入成功；服务保持 `ENABLED=0`。
- `qmicli`、`pppd` 存在；运行内核确认 QMI WWAN、USB Option 和 PPP 为内建。
- `soem-scan eth0` 成功打开原始套接字；未接 EtherCAT 从站时正确返回
  `No slaves found!`。
- `bt-speaker start` 后控制器名称、Loudspeaker Class、BlueALSA 进程和功放
  mixer 状态正常；全擦写后原配对记录需重新建立。
- Wi-Fi 连接 `Programmers7` 后 DHCP 和公网 DNS/ICMP 正常。

联网检查发现无 RTC 的冷启动时间为 1970 年，HTTPS 会因此拒绝尚未生效的证书。
交付配置随后补入 NTP 4.2.8p15、`ntpd` 和 `S49ntp`，并再次完整构建、打包：

- 最终镜像大小：`524013568` bytes
- 最终 SHA-256：
  `f12c078492b0b03c00eeeeb7fe228544c3b45cc859c4797d3247926eeeee2c55`
- 最终 squashfs：`53966.57 KiB`
- `scripts/verify_industrial_gateway.sh`（含 NTP）及蓝牙 overlay 检查均通过。

最终 NTP 版镜像已完成第二次 FEL 全擦写：

- 9 个镜像分区全部写入并回读校验通过，共写入 `418225152` bytes。
- rootfsA、rootfsB、Boot0、Boot1 均校验通过，设备自动重启。
- `S49ntp` 开机启动成功；Wi-Fi 联网后系统时间由 1970 年自动校准到
  2026-07-24。
- Python `requests` 访问 `https://thingsboard.io/robots.txt` 返回 HTTP 200，
  TLS 证书校验正常。
- ThingsBoard 关键模块再次导入成功；SOEM 再次成功打开 `eth0` 原始套接字。
- 蓝牙音响再次启动成功，BlueALSA、Loudspeaker Class、SPK/LINEOUTL 状态正常。
- `/dev/ttyAS5`、双 CAN-FD、`qmicli`、pppd 以及 QMI/Option/PPP 内核配置再次
  确认存在。

VMware 在每次 FEL 重新枚举后仍需手动把 `1f3a:efe8` 设备连接到虚拟机。
