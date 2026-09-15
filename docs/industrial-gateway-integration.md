# OmniGate 工业网关集成说明

## 集成范围

| 功能 | 软件/接口 | 默认约定 |
| --- | --- | --- |
| 本地管理 | Flask + 单页 Web UI | HTTP 80，首次登录 `admin / omnigate` |
| 云网关 | ThingsBoard Gateway 3.8.3 | 默认禁用，配置 Token 后启用 |
| Modbus RTU | ThingsBoard Modbus Connector | `/dev/ttyAS5`，9600 8N1，站号 1 |
| CAN/CANopen | SocketCAN、python-can、CANopen 1.0.0 | `can0`、`can1`，CANopen 默认 `can0` 500 kbit/s |
| EtherCAT 主站 | SOEM 2.0.0 | `eth0`，无 IP 地址、原始二层通信 |
| 普通网络 | Linux 网络栈 | `eth1` |
| 双 4G | libqmi、qmi_wwan、option、PPP/MBIM | 等 EC20 接入后按 USB 枚举结果配置 |
| 系统校时 | NTP 4.2.8p15 | 联网后自动校时，供 MQTT/TLS 证书校验使用 |
| 蓝牙音频 | BlueZ + bluez-alsa + openaptx | 保持现有蓝牙音响配置 |

SOEM 2.0.0 以共享库 `libsoem.so` 和示例程序形式编入镜像。SOEM 采用
GPL-3.0 或商业授权；产品发布前需根据交付方式确认采用的授权路径。

## 系统架构

```text
                                 ┌─────────────────────┐
                                 │ ThingsBoard / MQTT  │
                                 └──────────▲──────────┘
                                            │ eth1 / Wi-Fi / 双 EC20
┌───────────────────────────────────────────┴────────────────────────────┐
│                         T153MX OmniGate                                │
│  ┌──────────────┐    ┌─────────────────────────────────────────────┐  │
│  │ Web 管理/API │───▶│ 配置、状态、诊断与受保护的控制服务          │  │
│  └──────────────┘    └──────┬──────────┬──────────┬───────────────┘  │
│                              │          │          │                  │
│                    ThingsBoard GW   python-canopen  SOEM 主站          │
│                              │          │          │                  │
└──────────────────────────────┼──────────┼──────────┼──────────────────┘
                               │          │          │
                         ttyAS5/RS485  can0/can1   eth0（专用）
                               │          │          │
                         Modbus RTU    CANopen     EtherCAT 从站链
```

启动阶段先初始化网络和现场总线接口，再启动 Web 服务；ThingsBoard 在配置有效
Token 后才启用。控制接口默认只允许发现、诊断和零位保持，现场设备的量程、方向、
急停和限位未确认前不自动执行规划运动。

## Web 管理页面

板子联网后直接打开：

```text
http://192.168.1.62/
```

首次登录账号为 `admin`，密码为 `omnigate`。页面会提示修改初始密码。管理页面
默认随系统启动，配置文件为 `/etc/omnigate-web/config.json`，服务日志为
`/var/log/omnigate-web.log`。

页面提供：

- ThingsBoard 地址、端口、Token 与服务启停
- RS485 RTU 串口、波特率、数据位、校验位、停止位和站号
- `can0` / `can1` 的经典 CAN、CAN-FD 波特率和链路状态
- EDS/DCF 上传并绑定 Node ID
- CANopen 节点扫描、身份/错误/心跳诊断、NMT、原始 SDO 读写、PDO 映射读取和 RPDO 发送
- EtherCAT `eth0` 结构化从站清单、CoE SDO 读写和限定时长的周期/WKC 测试
- 两路 EC20 QMI 设备、APN、账号、密码及拨号/断开
- ThingsBoard、蓝牙和 NTP 服务启停及板端日志查看

Web 管理口是面向可信局域网的 HTTP 服务。正式部署到不可信网络时，应在上游
反向代理启用 HTTPS、修改初始密码，并通过防火墙限制管理网段。

## Wi-Fi 首次配置

镜像包含 `S46omnigate-wifi`，只要 `/etc/wpa_supplicant.conf` 中已有一个
`network` 配置，后续开机就会自动关联并通过 DHCP 获取地址。交付仓库不保存现场
SSID 或密码。首次可从串口或 ADB 执行：

```sh
ip link set wlan0 up
wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf
wpa_cli -i wlan0 add_network
wpa_cli -i wlan0 set_network 0 ssid '"YOUR_SSID"'
wpa_cli -i wlan0 set_network 0 psk '"YOUR_PASSWORD"'
wpa_cli -i wlan0 enable_network 0
wpa_cli -i wlan0 save_config
/etc/init.d/S46omnigate-wifi restart
```

量产时建议由安全的首次配置流程写入凭据，并在路由器上为设备做 DHCP 地址保留；
文中的 `192.168.1.62` 是本次验收地址，并非镜像硬编码地址。

## 从干净 SDK 应用并编译

不要直接复制仓库顶层目录。必须运行脚本，让 `overlay/` 中的路径落到 SDK
真实目录，同时把自定义 Buildroot 包注册到 Kconfig：

```sh
cd /path/to/T153_Tina_V1.0
./t153mx-ominigate-v1/scripts/apply_overlay.sh "$PWD"

./build.sh config
# linux / buildroot / t153 / omnigate / default / linux-5.10-origin

# 已有输出目录也必须重新载入方案 defconfig，避免漏装后续新增软件包
make -C buildroot/buildroot-202205 \
    O="$PWD/out/t153/omnigate/buildroot/buildroot" \
    sun8iw22p1_t153_mmc_defconfig

./build.sh
./build.sh pack
```

输出镜像：

```text
out/t153_linux_omnigate_uart0.img
```

## ThingsBoard Gateway

修改板端 `/etc/thingsboard-gateway/config/tb_gateway.json`：

```json
{
  "thingsboard": {
    "host": "thingsboard.cloud",
    "port": 1883,
    "security": {
      "accessToken": "PUT_GATEWAY_ACCESS_TOKEN_HERE"
    }
  }
}
```

确认连接器模板：

```sh
vi /etc/thingsboard-gateway/config/modbus.json
vi /etc/thingsboard-gateway/config/can0.json
vi /etc/thingsboard-gateway/config/can1.json
```

配置完成后启用并启动：

```sh
sed -i 's/^ENABLED=.*/ENABLED=1/' /etc/default/thingsboard-gateway
/etc/init.d/S70thingsboard-gateway restart
tail -f /var/log/thingsboard-gateway.log
```

默认禁用是为了防止占位 Token 在首次启动时产生持续重连和写盘。

板上没有可靠 RTC 时，冷启动日期可能回到 1970 年。镜像已包含 `ntpd` 和
`S49ntp`；普通以太网、Wi-Fi 或 4G 联网后应先确认 `date` 已校准，再启用
ThingsBoard。错误系统时间会导致 MQTT/HTTPS 的 TLS 证书校验失败。

## EtherCAT / SOEM

把 EtherCAT 从站接到 `eth0`。启动脚本会清除 `eth0` 的 IP 地址并将链路拉起，
避免 DHCP 与 EtherCAT 原始帧通信争用。

```sh
# 扫描并显示从站
soem-scan

# 指定网卡
soem-scan eth0

# 以 CPU2、FIFO 80 优先级运行 SOEM 示例
soem-run simple_ng eth0

# 其他随镜像提供的工具
slaveinfo eth0
eepromtool
firm_update
eoe_test

# 结构化从站清单（JSON）
omnigate-ethercat eth0 scan

# CoE SDO 上传/下载
omnigate-ethercat eth0 sdo-read 1 0x1000 0 256
omnigate-ethercat eth0 sdo-write 1 0x6040 0 "06 00"

# 1000 个 1 ms 周期的过程数据/WKC 测试
omnigate-ethercat eth0 cycle 1000 1000
```

`/etc/ethercat/soem.conf` 可修改网卡、实时优先级和 CPU 亲和性。SOEM 是用户态
主站，确定性会受到 Linux 调度、网卡驱动和从站周期要求影响；严格亚毫秒周期需
结合实物从站进行抖动和丢帧测试。

Web 周期测试会完成 PDO 映射、把从站临时切到 OP、按指定周期交换有限次数过程
数据，再退回 SAFE-OP，并报告期望/实际 WKC。单次最长 10 秒，目的是接线、映射
和基本通信验收，不替代长期运行的实时 EtherCAT 主站。CoE SDO 写入会改变从站
参数，尤其驱动器对象 `0x6040` 等控制对象必须按设备手册和安全流程操作。

## RS485 / Modbus RTU

本方案只占用一路 RTU，默认 `/dev/ttyAS5`。接线后先做本地验证：

```sh
ls -l /dev/ttyAS5
stty -F /dev/ttyAS5 9600 cs8 -cstopb -parenb
```

实际站号、寄存器地址、功能码和缩放系数在 `modbus.json` 中按现场设备手册修改。

## CAN-FD

```sh
omnigate-can can0 500000 2000000
omnigate-can can1 500000 2000000
ip -details link show can0
candump can0
```

无终端电阻或总线上没有其他节点时，发送测试可能进入 bus-off；实测前确认两端
120 Ω 终端和共地。

## CANopen 主站

Web 页面使用 Python CANopen 主站协议栈，通过 Linux SocketCAN 操作 `can0` 或
`can1`。进入“CAN / CANopen”页面，先选择接口和与从站一致的波特率，然后扫描
Node ID 1–127。扫描通过读取对象 `0x1000:00` 发现在线节点。

“节点诊断”读取 `0x1000` 设备类型、`0x1001` 错误寄存器、`0x1017` 心跳生产
周期和 `0x1018` 身份对象，并短暂等待一次心跳以报告 NMT 状态。部分对象为可选；
设备不实现时对应字段会显示为空。若未配置生产者心跳，身份信息仍可读取，但
`nmt_state` 为空。

SDO 原始读写不强制要求 EDS；PDO 映射和按变量名发送 RPDO 则必须先上传正确的
EDS/DCF，并在上传时绑定对应 Node ID。NMT 支持广播 Node ID 0，也支持指定节点。
CANopen 使用经典 CAN 帧，页面执行 CANopen 操作时会把所选接口切换为非 FD 模式。

注意：执行 NMT Reset、SDO 写或 RPDO 发送会直接改变从站状态或参数，现场操作前
应确认节点 ID、对象字典及设备安全状态。

## 双 EC20

镜像已打开 `option`、`USB_WDM`、`qmi_wwan`、CDC MBIM/NCM、PPP，并包含
libqmi、pppd 和 usb-modeswitch 数据。模组接入后先记录各自 USB 拓扑：

```sh
lsusb
dmesg | grep -E 'ttyUSB|cdc-wdm|qmi_wwan|wwan'
ls -l /dev/ttyUSB* /dev/cdc-wdm*
qmicli -d /dev/cdc-wdm0 --dms-get-operating-mode
```

双模组不要依赖动态生成的 `ttyUSB` 顺序；部署时应按 USB 物理端口创建稳定
udev/mdev 名称，再分别配置 APN、路由表和链路健康检查。由于当前 EC20 尚未接入，
本次只能验证驱动与工具完整，拨号、SIM、APN 和双链路切换需接硬件后验收。

## 板端快速验收

```sh
python3 -c 'import thingsboard_gateway, pymodbus, can, canopen, flask, cryptography, orjson; print("gateway imports OK")'
test -x /usr/bin/slaveinfo && echo "SOEM tools OK"
test -x /usr/bin/omnigate-ethercat && echo "EtherCAT diagnostics OK"
ldd /usr/bin/slaveinfo
test -x /usr/sbin/ntpd && echo "NTP OK"
python3 -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1/api/health").read().decode())'
ip link show eth0
ip link show can0
zcat /proc/config.gz | grep -E 'QMI_WWAN|USB_SERIAL_OPTION|PPP='
```

没有 ThingsBoard Token、Modbus/CAN/EtherCAT 从站或 EC20 实物时，以上只代表软件
集成和驱动就绪，不代表对应外设的端到端通信已经完成。
