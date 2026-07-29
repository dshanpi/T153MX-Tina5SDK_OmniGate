# Gateway CANopen / EtherCAT 交付清单

整理日期：2026-07-29
交付分支：`gatewaycanethercat`

## 目的

本分支备份 OmniGate 工业网关的软件集成、配置、构建记录和后续实物验收方法。
仓库采用 overlay 形式保存改动，不包含完整 Tina SDK，也不直接保存大体积固件。

## 代码与配置

### EtherCAT

- `overlay/buildroot/buildroot-202205/package/soem/`
  - SOEM 2.0.0 Buildroot 包、校验值和 Tina CMake 兼容补丁。
- `overlay/buildroot/buildroot-202205/package/omnigate-ethercat/`
  - 结构化从站扫描、CoE SDO 读写和限定时长的 PDO/WKC 周期测试工具。
- `overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/etc/ethercat/`
  - EtherCAT 网卡、CPU 亲和性和实时优先级默认配置。
- `overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/soem-*`
  - SOEM 扫描和实时调度启动包装脚本。

### CAN / CANopen / RS485

- `overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/bin/omnigate-can`
  - 经典 CAN/CAN-FD 接口配置脚本。
- Web 后端使用 `python-can`、`python-canopen` 提供节点扫描、NMT、身份/心跳诊断、
  SDO、PDO 映射和 RPDO 操作。
- ThingsBoard 配置模板包含 `can0`、`can1` 和 `/dev/ttyAS5` Modbus RTU 连接器。

### Web、云端和系统服务

- `overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/lib/omnigate-web/app.py`
  - 本地管理 API。
- `overlay/device/config/chips/t153/configs/omnigate/buildroot/overlay/usr/share/omnigate-web/index.html`
  - 本地管理页面。
- `overlay/buildroot/buildroot-202205/package/thingsboard-gateway/`
  - ThingsBoard Gateway 3.8.3 Buildroot 包和启动服务。
- `overlay/buildroot/buildroot-202205/package/python-jsonpath-rw/`
  - ThingsBoard Gateway 缺失的 Python 依赖。
- `S46omnigate-wifi`、`S69industrial-interfaces`、`S71omnigate-web`
  - Wi-Fi、工业接口和 Web 管理服务启动脚本。

### 构建配置

- Buildroot defconfig 启用 SOEM、OmniGate EtherCAT、python-canopen、Flask、
  ThingsBoard Gateway、NTP、QMI、PPP 等组件。
- Linux 5.10 origin/RT defconfig 启用 EC20 所需的 USB 串口、QMI/WWAN、MBIM
  和 PPP 驱动。
- `scripts/apply_overlay.sh` 负责复制 overlay，并幂等注册自定义 Buildroot 包。
- `scripts/verify_industrial_gateway.sh` 核对源文件、配置和 target 安装结果。

## 文档索引

- [工业网关集成与操作说明](./industrial-gateway-integration.md)
- [2026-07-29 EtherCAT/CANopen 续作记录](./industrial-gateway-development-2026-07-29.md)
- [完整构建、烧录及历史验证记录](./build-flash-verification-2026-07-24.md)

## 已完成验证

- overlay 与本次成功构建所使用的 SDK 源文件逐项比较一致。
- `omnigate-ethercat` 使用 ARM hard-float 工具链和
  `-Wall -Wextra -Werror` 编译通过。
- Buildroot 包构建、完整系统构建和 `pack` 均成功。
- 最终镜像：`out/t153_linux_omnigate_uart0.img`
- 镜像大小：`529254400` bytes
- SHA-256：
  `c512212d77681261270839af4efcfeb1247c37eba698d9beaef08b6d6142dd88`

固件约 505 MiB，超过 GitHub 普通 Git 单文件限制，因此不提交到本仓库。使用本
分支应用 overlay 后可重建同一软件配置；以上 SHA-256 用于核对此次本地备份镜像。

## 尚待实物验证

当前没有连接 EtherCAT 或 CANopen 从站，所以下列测试明确留待设备接入后执行：

1. EtherCAT 扫描及 Vendor ID、Product Code、Revision、Serial 核对。
2. CiA402 从站的安全只读 SDO、PDO 映射、OP 状态和 WKC 周期测试。
3. CANopen `0x1000`、`0x1001`、`0x1017`、`0x1018` 读取及 NMT 心跳测试。
4. 执行机构安全禁止条件下的控制字、目标位置和实际位置闭环验证。

SDO 写入、NMT Reset、RPDO 和 CiA402 控制字可能引发电机动作。测试前必须确认
接线、终端电阻、急停、限位、节点地址及驱动器对象字典。
