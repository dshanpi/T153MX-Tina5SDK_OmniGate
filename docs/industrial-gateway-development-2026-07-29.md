# 工业网关续作记录

日期：2026-07-29

## 本轮目标

在已有 SOEM 扫描、CANopen SDO/PDO 和 Web 管理基础上，补齐现场调试闭环：

- EtherCAT 信息从不可机器读取的 `slaveinfo` 文本升级为结构化从站清单。
- 增加 EtherCAT CoE SDO 上传/下载。
- 增加有次数和时长上限的 EtherCAT 过程数据/WKC 测试。
- 增加 CANopen 节点身份、错误寄存器、生产者心跳和 NMT 状态诊断。

## 实现

新增 Buildroot 包 `omnigate-ethercat`。该包链接 SOEM 2.0.0，安装
`/usr/bin/omnigate-ethercat`，支持：

```text
omnigate-ethercat IFACE scan
omnigate-ethercat IFACE sdo-read SLAVE INDEX SUBINDEX [MAX-BYTES]
omnigate-ethercat IFACE sdo-write SLAVE INDEX SUBINDEX HEX-BYTES
omnigate-ethercat IFACE cycle [COUNT] [PERIOD-US]
```

Web 后端增加 `/api/ethercat/scan`、`/api/ethercat/sdo/read`、
`/api/ethercat/sdo/write`、`/api/ethercat/cycle` 和
`/api/canopen/node`。所有 EtherCAT 与 CANopen 总线操作继续使用同一把进程锁，
避免管理请求并发占用原始网卡或 CAN 接口。写接口保留 CSRF 校验，页面另有显式
确认。

周期测试最多 10000 周期、单次最长 10 秒；完成后请求 SAFE-OP。它用于验收
PDO 映射和 WKC，不作为常驻实时主站。

## 已完成验证

- `omnigate-ethercat.c` 使用 Tina SDK 的 ARM hard-float 交叉工具链并以
  `-Wall -Wextra -Werror` 编译通过。
- Buildroot `make omnigate-ethercat` 完成 source sync、编译并安装到 target。
- Buildroot 增量完整构建成功，重新生成 `rootfs.ext2` 和 `rootfs.tar`；归档中确认
  包含新二进制、Web 后端和页面。
- Web 后端通过 Python 字节码语法检查。
- `scripts/verify_industrial_gateway.sh` 覆盖新增包和 target 可执行文件。

## 尚需实物验收

当前环境没有接入 EtherCAT/CANopen 从站，以下项目需接实物后执行：

1. 对照从站铭牌核对结构化扫描中的 Vendor ID、Product Code、Revision 和 Serial。
2. 读取一个设备手册规定的只读 CoE SDO，并验证大小和字节序。
3. 在执行机构保持安全禁止状态时运行 1 ms/1000 周期测试，确认 WKC 零失败。
4. 使用 CANopen 节点诊断核对 `0x1018`，并确认配置 `0x1017` 后能得到 NMT 状态。
5. 任何 SDO 写入测试都应先使用无运动风险的测试对象；驱动器控制字需单独审批。

## 全系统构建与打包

应后续要求执行了完整 `./build.sh` 和 `./build.sh pack`。首次顶层构建发现
`OMNIGATE_ETHERCAT_SITE` 使用 `PKGDIR` 时在该调用路径下带尾斜杠，Buildroot
拒绝本地包路径。现已改为稳定的
`$(TOPDIR)/package/omnigate-ethercat`，独立清理重建该包后，全系统重新构建成功。

- RTOS：`t153_e907_bga_demo` 构建成功。
- Linux：5.10.198，内核、模块和 `boot.img` 构建成功。
- Buildroot：构建成功，工业网关校验脚本全部通过。
- squashfs：`54642.91 KiB`。
- pack：`Dragon execute image.cfg SUCCESS`、`pack finish`。
- 镜像：`out/t153_linux_omnigate_uart0.img`
- 大小：`529254400` bytes。
- SHA-256：
  `c512212d77681261270839af4efcfeb1247c37eba698d9beaef08b6d6142dd88`
- OpenixCLI：识别 46 个嵌入文件和 12 个 MBR 分区。

打包后的 `rootfs.tar` 已确认包含 `omnigate-ethercat`、`soem-scan`、新版 Web
后端和页面。

执行烧录前检查时，虚拟机未枚举到 ADB、串口或 `1f3a:efe8` FEL 设备；扫描
`192.168.1.0/24` 和 `10.0.0.0/24` 也未发现可访问的 OmniGate 管理服务。因此本轮
尚未烧录，EtherCAT/CANopen 实物通信测试等待板卡 USB 和对应从站接入。
